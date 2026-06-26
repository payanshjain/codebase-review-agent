"""
Incremental documentation service implementation.

Calculates SHA256 hashes of repository files and compares against
disk cache manifests to skip redundant regeneration.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from documentation_agent.config import DOCS_STORE_DIR
from documentation_agent.repository_parser.parser import ParsedRepository
from documentation_agent.schemas import DocumentationOutput, ManifestRecord

logger = logging.getLogger(__name__)


class IncrementalService:
    """
    Manages incremental manifest cache hashing.
    """

    def compute_repo_hash(self, parsed: ParsedRepository) -> str:
        """Calculate a composite SHA256 hash of all file names and sizes."""
        hasher = hashlib.sha256()
        for p in sorted(parsed.all_files):
            try:
                stat = p.stat()
                hasher.update(f"{p.name}:{stat.st_size}:{stat.st_mtime}".encode("utf-8"))
            except Exception:
                pass
        return hasher.hexdigest()

    def check_cache(self, repo_id: str, current_hash: str) -> DocumentationOutput | None:
        """Check if cached documentation matches current repository hash."""
        manifest_path = DOCS_STORE_DIR / repo_id / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = ManifestRecord(**data)
            if record.sha256_hash == current_hash:
                logger.info("Incremental manifest hit for repo %s. Skipping regeneration.", repo_id)
                return record.documentation
        except Exception:
            logger.debug("Failed to read manifest record at %s", manifest_path)

        return None

    def save_manifest(self, repo_id: str, current_hash: str, output: DocumentationOutput) -> None:
        """Persist new manifest record to disk."""
        manifest_path = DOCS_STORE_DIR / repo_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        record = ManifestRecord(
            repo_id=repo_id,
            sha256_hash=current_hash,
            generated_at=datetime.now(timezone.utc).isoformat(),
            documentation=output,
        )
        manifest_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved incremental manifest cache at: %s", manifest_path)
