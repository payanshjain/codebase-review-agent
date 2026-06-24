"""
Repository metadata persistence — JSON file on disk.

Why JSON over SQLite?
- Zero new dependencies (works with stdlib json).
- Perfectly adequate for ≤10 repos (the stated scale target).
- Human-readable and easy to debug.
- Thread-safety is acceptable because writes only happen during
  index / delete operations (infrequent).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RepositoryRecord:
    """Metadata for a single indexed repository."""

    repo_id: str
    name: str
    url: Optional[str]  # None for local-path repos
    local_path: str
    source: str  # "github" or "local"
    files_count: int = 0
    chunks_count: int = 0
    languages: list[str] = field(default_factory=list)
    indexed_at: Optional[str] = None  # ISO-8601 timestamp
    status: str = "pending"  # pending | indexing | indexed | error

    def mark_indexed(
        self,
        *,
        files_count: int,
        chunks_count: int,
        languages: list[str],
    ) -> None:
        """Update record after successful indexing."""
        self.files_count = files_count
        self.chunks_count = chunks_count
        self.languages = sorted(set(languages))
        self.indexed_at = datetime.now(timezone.utc).isoformat()
        self.status = "indexed"

    def mark_error(self, message: str) -> None:
        self.status = f"error: {message}"


class RepositoryMetadataStore:
    """
    CRUD operations for repository metadata backed by a single JSON file.

    All mutations read → modify → write the entire file.  This is fine for
    the expected scale (≤10 repositories).
    """

    def __init__(self, metadata_path: str | Path) -> None:
        self._path = Path(metadata_path)

    # ── read ────────────────────────────────────────────────────────

    def _load(self) -> dict[str, dict]:
        """Load raw JSON from disk; return empty dict if file missing."""
        if not self._path.exists():
            return {}
        text = self._path.read_text(encoding="utf-8")
        return json.loads(text) if text.strip() else {}

    def load_all(self) -> dict[str, RepositoryRecord]:
        """Return all repositories keyed by repo_id."""
        raw = self._load()
        return {rid: RepositoryRecord(**data) for rid, data in raw.items()}

    def get(self, repo_id: str) -> RepositoryRecord | None:
        """Return a single repo record, or None if not found."""
        raw = self._load()
        data = raw.get(repo_id)
        return RepositoryRecord(**data) if data else None

    # ── write ───────────────────────────────────────────────────────

    def _save(self, records: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(self, record: RepositoryRecord) -> None:
        """Upsert a single repository record."""
        raw = self._load()
        raw[record.repo_id] = asdict(record)
        self._save(raw)

    def delete(self, repo_id: str) -> bool:
        """Remove a repo record.  Returns True if it existed."""
        raw = self._load()
        if repo_id not in raw:
            return False
        del raw[repo_id]
        self._save(raw)
        return True

    def exists(self, repo_id: str) -> bool:
        return repo_id in self._load()
