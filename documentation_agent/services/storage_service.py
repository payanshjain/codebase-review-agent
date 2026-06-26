"""
Storage service implementation.

Saves generated documentation markdown reports to dedicated repository folders.
"""

from __future__ import annotations

import logging
from pathlib import Path

from documentation_agent.config import DOCS_STORE_DIR
from documentation_agent.schemas import DocumentationOutput

logger = logging.getLogger(__name__)


class StorageService:
    """
    Persists generated markdown documentation on local disk.
    """

    def save_all(self, repo_id: str, docs: DocumentationOutput) -> dict[str, Path]:
        """Save README, Architecture, API, Onboarding, and Database docs."""
        target_dir = DOCS_STORE_DIR / repo_id
        target_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "readme": target_dir / "README.md",
            "architecture_docs": target_dir / "ARCHITECTURE.md",
            "api_docs": target_dir / "API_DOCUMENTATION.md",
            "onboarding_guide": target_dir / "ONBOARDING_GUIDE.md",
            "database_docs": target_dir / "DATABASE_DOCUMENTATION.md",
        }

        files["readme"].write_text(docs.readme, encoding="utf-8")
        files["architecture_docs"].write_text(docs.architecture_docs, encoding="utf-8")
        files["api_docs"].write_text(docs.api_docs, encoding="utf-8")
        files["onboarding_guide"].write_text(docs.onboarding_guide, encoding="utf-8")
        files["database_docs"].write_text(docs.database_docs, encoding="utf-8")

        logger.info("Persisted all markdown documentation files in: %s", target_dir)
        return files
