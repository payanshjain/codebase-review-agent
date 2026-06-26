"""
Diagram generator implementation.

Synthesizes valid Mermaid.js diagrams for system architecture graphs,
API workflow sequence diagrams, and database ER / dependency diagrams.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class DiagramGenerator:
    """
    Generates Mermaid diagrams from extracted RepositoryMetadata.
    """

    def generate_all_diagrams(self, metadata: RepositoryMetadata) -> dict[str, str]:
        """
        Synthesize system architecture, sequence, and dependency diagrams.
        """
        logger.info("Synthesizing Mermaid diagrams for repo: %s", metadata.repo_name)
        return {
            "system_architecture": self.generate_system_architecture(metadata),
            "sequence_diagram": self.generate_sequence_diagram(metadata),
            "dependency_diagram": self.generate_dependency_diagram(metadata),
        }

    def generate_system_architecture(self, metadata: RepositoryMetadata) -> str:
        """Create a top-level architecture flowchart diagram."""
        lines = ["graph TD", '    User["User / Client"]']

        # Add API Layer
        if metadata.api_endpoints:
            lines.append('    subgraph API_Layer["API Endpoints"]')
            for i, ep in enumerate(metadata.api_endpoints[:6]):
                lines.append(f'        ep{i}["{ep.method} {ep.path}"]')
            lines.append("    end")
            lines.append("    User --> API_Layer")

        # Add Core Logic / Classes
        if metadata.classes:
            lines.append('    subgraph Core_Services["Core Logic / Services"]')
            for i, cls in enumerate(metadata.classes[:6]):
                lines.append(f'        cls{i}["class: {cls.name}"]')
            lines.append("    end")
            if metadata.api_endpoints:
                lines.append("    API_Layer --> Core_Services")
            else:
                lines.append("    User --> Core_Services")

        # Add Storage / Database Layer
        if metadata.databases:
            lines.append('    subgraph Storage_Layer["Database Models & Storage"]')
            for i, db in enumerate(metadata.databases[:4]):
                lines.append(f'        db{i}[("Table/Model: {db.name}")]')
            lines.append("    end")
            if metadata.classes:
                lines.append("    Core_Services --> Storage_Layer")
            elif metadata.api_endpoints:
                lines.append("    API_Layer --> Storage_Layer")

        return "\n".join(lines)

    def generate_sequence_diagram(self, metadata: RepositoryMetadata) -> str:
        """Create a request sequence diagram illustrating typical execution flow."""
        lines = [
            "sequenceDiagram",
            "    autonumber",
            "    actor Client",
            "    participant API as API Router",
            "    participant Controller as Core Service",
            "    participant DB as Database Store",
        ]

        if metadata.api_endpoints:
            ep = metadata.api_endpoints[0]
            lines.append(f"    Client->>+API: HTTP {ep.method} {ep.path}")
            lines.append(f"    API->>+Controller: invoke {ep.function_name}()")
            if metadata.databases:
                db_name = metadata.databases[0].name
                lines.append(f"    Controller->>+DB: Query {db_name}")
                lines.append("    DB-->>-Controller: Return Entity Data")
            lines.append("    Controller-->>-API: Return Response Schema")
            lines.append("    API-->>-Client: 200 OK JSON")
        else:
            lines.append("    Client->>+Controller: Call Function/Method")
            lines.append("    Controller-->>-Client: Return Output")

        return "\n".join(lines)

    def generate_dependency_diagram(self, metadata: RepositoryMetadata) -> str:
        """Create an Entity Relationship or Component Dependency diagram."""
        if metadata.databases:
            lines = ["erDiagram"]
            for db in metadata.databases:
                col_str = "\n".join(f"        string {c}" for c in db.columns[:5])
                lines.append(f"    {db.name} {{\n{col_str}\n    }}")
            # Add basic relationships if multiple
            if len(metadata.databases) >= 2:
                lines.append(f"    {metadata.databases[0].name} ||--o{{ {metadata.databases[1].name} : has")
            return "\n".join(lines)
        else:
            # Fallback to module dependency graph
            lines = ["graph LR", f'    Repo["Repo: {metadata.repo_name}"]']
            for i, dep in enumerate(metadata.dependencies[:8]):
                lines.append(f'    dep{i}["pkg: {dep}"]')
                lines.append(f"    Repo --> dep{i}")
            return "\n".join(lines)
