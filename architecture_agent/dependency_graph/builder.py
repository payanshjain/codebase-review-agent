"""
Dependency graph builder using NetworkX.

Constructs a directed graph where:
- Nodes = source files (relative paths)
- Edges = import relationships (A imports from B → edge A→B)

Provides PageRank-based importance ranking, impact analysis,
and dependency/dependent queries.
"""

from __future__ import annotations

import logging

import networkx as nx

from architecture_agent.ast_parser.ast_parser import FileAST
from architecture_agent.config import DEFAULT_TOP_N_FILES, MAX_IMPACT_DEPTH

logger = logging.getLogger(__name__)


class DependencyGraphBuilder:
    """Builds and queries a file-level dependency graph."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    def build(self, file_asts: list[FileAST]) -> nx.DiGraph:
        """
        Construct the dependency graph from parsed AST metadata.
        """
        self.graph = nx.DiGraph()

        # Add all files as nodes
        for f in file_asts:
            self.graph.add_node(
                f.rel_path,
                language=f.language,
                loc=f.loc,
                class_count=len(f.classes),
                function_count=len(f.functions),
            )

        # Add import edges
        known_files = {f.rel_path for f in file_asts}
        for f in file_asts:
            for target in f.resolved_imports:
                if target in known_files and target != f.rel_path:
                    self.graph.add_edge(f.rel_path, target)

        logger.info(
            "Dependency graph built: %d nodes, %d edges",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return self.graph

    def get_file_dependencies(self, file_path: str) -> list[str]:
        """Return files that this file directly imports."""
        if file_path not in self.graph:
            return []
        return list(self.graph.successors(file_path))

    def get_file_dependents(self, file_path: str) -> list[str]:
        """Return files that directly import this file."""
        if file_path not in self.graph:
            return []
        return list(self.graph.predecessors(file_path))

    def get_most_important_files(self, top_n: int = DEFAULT_TOP_N_FILES) -> list[tuple[str, float]]:
        """
        Rank files by PageRank centrality.
        Files that are imported by many other important files rank highest.
        """
        if self.graph.number_of_nodes() == 0:
            return []
        try:
            ranks = nx.pagerank(self.graph)
        except nx.NetworkXError:
            # Fallback to in-degree if PageRank fails
            ranks = {node: self.graph.in_degree(node) for node in self.graph.nodes()}

        sorted_ranks = sorted(ranks.items(), key=lambda x: x[1], reverse=True)
        return sorted_ranks[:top_n]

    def get_impact_analysis(self, file_path: str) -> list[str]:
        """
        Return all files transitively affected if file_path changes.
        Uses reverse BFS to find all transitive dependents.
        """
        if file_path not in self.graph:
            return []

        # BFS on the reverse graph (predecessors)
        affected: set[str] = set()
        queue: list[tuple[str, int]] = [(file_path, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth > MAX_IMPACT_DEPTH:
                continue
            for pred in self.graph.predecessors(current):
                if pred not in affected:
                    affected.add(pred)
                    queue.append((pred, depth + 1))

        return sorted(affected)

    def get_connected_components(self) -> list[set[str]]:
        """Return weakly connected components (groups of related files)."""
        return [comp for comp in nx.weakly_connected_components(self.graph)]

    def get_graph_stats(self) -> dict[str, int]:
        """Return basic graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "components": nx.number_weakly_connected_components(self.graph),
            "density": round(nx.density(self.graph), 4),
        }
