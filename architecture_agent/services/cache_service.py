"""
Cache service for the Architecture Agent.

SHA256-based caching of analysis results. Stores serialized ArchitectureOutput
as a JSON manifest keyed by composite repository hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from architecture_agent.config import ARCH_STORE_DIR
from architecture_agent.repository_parser.parser import ParsedRepo
from architecture_agent.schemas import ArchitectureOutput, CacheManifest

logger = logging.getLogger(__name__)


class CacheService:
    """Manages incremental analysis cache."""

    def compute_repo_hash(self, parsed: ParsedRepo) -> str:
        """Compute composite SHA256 of all file names, sizes, and mtimes."""
        hasher = hashlib.sha256()
        for p in sorted(parsed.all_files):
            try:
                stat = p.stat()
                hasher.update(f"{p.name}:{stat.st_size}:{stat.st_mtime}".encode("utf-8"))
            except Exception:
                pass
        return hasher.hexdigest()

    def check_cache(self, repo_id: str, current_hash: str) -> ArchitectureOutput | None:
        """Return cached output if hash matches, else None."""
        manifest_path = ARCH_STORE_DIR / repo_id / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = CacheManifest(**data)
            if record.sha256_hash == current_hash:
                logger.info("Cache hit for repo %s — skipping re-analysis.", repo_id)
                return record.output
        except Exception:
            logger.debug("Failed to read cache manifest at %s", manifest_path)

        return None

    def save_cache(self, repo_id: str, current_hash: str, output: ArchitectureOutput) -> None:
        """Persist analysis result to disk cache."""
        manifest_path = ARCH_STORE_DIR / repo_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        record = CacheManifest(
            repo_id=repo_id,
            sha256_hash=current_hash,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            output=output,
        )
        manifest_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved analysis cache at: %s", manifest_path)
