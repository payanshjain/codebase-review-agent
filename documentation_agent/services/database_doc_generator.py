"""
Database documentation generator implementation.

Synthesizes database report detailing tables, ORM entity models,
columns/attributes, and foreign key relationships.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class DatabaseDocGenerator:
    """
    Generates Database Documentation markdown report.
    """

    async def generate(self, metadata: RepositoryMetadata) -> str:
        """
        Synthesize database schemas documentation.
        """
        logger.info("Synthesizing Database Documentation for repo: %s", metadata.repo_name)

        if not metadata.databases:
            return f"""# 💾 {metadata.repo_name} — Database Documentation

*No relational database schemas or ORM entity models were detected in this repository.*
"""

        model_blocks: list[str] = []
        for db in metadata.databases:
            cols = "\n".join(f"- `{col}` (Attribute)" for col in db.columns) or "- Standard Primary Key ID"
            rels = "\n".join(f"- `{rel}`" for rel in db.relationships) or "- None"

            block = f"""### Table / Entity Model: `{db.name}`

- **Source File**: `{db.file_path}:{db.line}`

#### Columns & Fields
{cols}

#### Relationships & Foreign Keys
{rels}

---
"""
            model_blocks.append(block)

        doc = f"""# 💾 {metadata.repo_name} — Database Documentation

This document catalogs the data entity schemas, ORM models, and storage tables used within **{metadata.repo_name}**.

## 📊 Models Summary

| Table / Model Name | Source Location | Column Count |
|--------------------|-----------------|--------------|
{chr(10).join(f'| **{db.name}** | `{db.file_path}` | {len(db.columns)} |' for db in metadata.databases)}

---

## 🗃️ Entity Schema Details

{chr(10).join(model_blocks)}
"""
        return doc
