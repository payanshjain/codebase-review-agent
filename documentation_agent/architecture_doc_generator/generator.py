"""
Architecture documentation generator implementation.

Synthesizes architecture report covering system overview, component diagrams,
data flow sequence diagrams, and dependency graphs.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class ArchitectureDocGenerator:
    """
    Generates Architecture Documentation markdown report.
    """

    async def generate(self, metadata: RepositoryMetadata, diagrams: dict[str, str]) -> str:
        """
        Synthesize architecture markdown report embedding Mermaid diagrams.
        """
        logger.info("Synthesizing Architecture Documentation for repo: %s", metadata.repo_name)

        sys_diag = diagrams.get("system_architecture", "")
        seq_diag = diagrams.get("sequence_diagram", "")
        dep_diag = diagrams.get("dependency_diagram", "")

        core_list = "\n".join(f"- `{c.name}` ({c.file_path})" for c in metadata.classes[:10]) or "- Functional/Script Modules"

        doc = f"""# 🏛️ {metadata.repo_name} — Architecture Documentation

## 🌐 1. System Overview

The **{metadata.repo_name}** architecture follows modular design principles, isolating ingestion, semantic processing, storage, and API routing. This separation ensures high maintainability and testability across multi-repository workflows.

```mermaid
{sys_diag}
```

---

## 🧩 2. Component Diagrams & Structure

The repository is structured into distinct operational layers:

### Core Components & Classes
{core_list}

### Configuration & Deployment Artifacts
{chr(10).join(f'- `{cf}`' for cf in metadata.configuration_files) or '- Standard Configs'}

---

## 🔄 3. Data Flow & Execution Pipeline

The sequence diagram below illustrates the typical request lifecycle from client invocation through API routing, core controller logic, and database persistence:

```mermaid
{seq_diag}
```

---

## 🕸️ 4. Dependency Graph

The relationship graph highlights external dependencies and database entity models:

```mermaid
{dep_diag}
```
"""
        return doc
