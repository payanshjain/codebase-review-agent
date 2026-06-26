"""
Mermaid diagram generator for the Architecture Agent.

Converts NetworkX graphs and ArchitectureSummary into valid Mermaid
diagram strings for:
- Dependency graph (file imports)
- System architecture (frontend/backend/database layers)
- Call graph (function call relationships)
"""

from __future__ import annotations

import logging
import re

import networkx as nx

from architecture_agent.config import MERMAID_MAX_NODES
from architecture_agent.schemas import ArchitectureSummary

logger = logging.getLogger(__name__)


def _safe_id(name: str) -> str:
    """Convert a file/function name into a Mermaid-safe node ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _short_label(path: str, max_len: int = 30) -> str:
    """Truncate a label for readability."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]


class MermaidGenerator:
    """Generates Mermaid diagram strings."""

    def generate_dependency_graph(
        self, graph: nx.DiGraph, important_files: list[tuple[str, float]]
    ) -> str:
        """
        Render the top-N most important files and their edges as a Mermaid graph.
        """
        top_files = {f for f, _ in important_files[:MERMAID_MAX_NODES]}
        if not top_files:
            top_files = set(list(graph.nodes())[:MERMAID_MAX_NODES])

        lines = ["graph LR"]

        for node in sorted(top_files):
            if node in graph:
                nid = _safe_id(node)
                label = _short_label(node)
                lines.append(f'    {nid}["{label}"]')

        for u, v in graph.edges():
            if u in top_files and v in top_files:
                lines.append(f"    {_safe_id(u)} --> {_safe_id(v)}")

        return "\n".join(lines)

    def generate_system_architecture(self, summary: ArchitectureSummary) -> str:
        """
        Render the high-level system architecture with layer subgraphs.
        """
        lines = ["graph TD"]

        # Client node
        lines.append('    Client["Client / User"]')

        layers = summary.layers

        # Frontend layer
        if "frontend" in layers:
            lines.append('    subgraph Frontend["Frontend Layer"]')
            for i, f in enumerate(layers["frontend"][:5]):
                lines.append(f'        fe{i}["{_short_label(f)}"]')
            lines.append("    end")
            lines.append("    Client --> Frontend")

        # Backend / API layer
        if "backend" in layers:
            lines.append('    subgraph Backend["Backend / API Layer"]')
            for i, f in enumerate(layers["backend"][:6]):
                lines.append(f'        be{i}["{_short_label(f)}"]')
            lines.append("    end")
            if "frontend" in layers:
                lines.append("    Frontend --> Backend")
            else:
                lines.append("    Client --> Backend")

        # Database layer
        if "database" in layers:
            lines.append('    subgraph Database["Database / Storage Layer"]')
            for i, f in enumerate(layers["database"][:4]):
                lines.append(f'        db{i}[("{_short_label(f)}")]')
            lines.append("    end")
            if "backend" in layers:
                lines.append("    Backend --> Database")

        # External services
        if summary.databases:
            lines.append('    subgraph External["External Services"]')
            for i, db in enumerate(summary.databases[:4]):
                lines.append(f'        ext{i}["{db}"]')
            lines.append("    end")
            if "database" in layers:
                lines.append("    Database --> External")
            elif "backend" in layers:
                lines.append("    Backend --> External")

        # Frameworks annotation
        if summary.frameworks:
            fw_names = ", ".join(fw.name for fw in summary.frameworks[:5])
            lines.append(f'    Stack["Tech: {fw_names}"]')
            lines.append("    style Stack fill:#2d333b,stroke:#444,color:#8b949e")

        return "\n".join(lines)

    def generate_call_graph(self, graph: nx.DiGraph) -> str:
        """
        Render the top-N most connected function nodes as a call graph.
        """
        # Pick nodes with highest combined degree
        degrees = [(n, graph.in_degree(n) + graph.out_degree(n)) for n in graph.nodes()]
        top_nodes = {n for n, _ in sorted(degrees, key=lambda x: x[1], reverse=True)[:MERMAID_MAX_NODES]}

        if not top_nodes:
            return "graph TD\n    empty[\"No call data\"]"

        lines = ["graph TD"]

        for node in sorted(top_nodes):
            nid = _safe_id(node)
            # Show just the function name for readability
            parts = node.split(".")
            label = parts[-1] if len(parts) > 1 else node
            lines.append(f'    {nid}["{label}"]')

        for u, v in graph.edges():
            if u in top_nodes and v in top_nodes:
                lines.append(f"    {_safe_id(u)} --> {_safe_id(v)}")

        return "\n".join(lines)
