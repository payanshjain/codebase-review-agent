"""
Call graph builder using NetworkX.

Constructs a directed graph where:
- Nodes = function/method names (qualified with file or class)
- Edges = function A calls function B → edge A→B

Provides caller/callee queries and transitive call chain traversal.
"""

from __future__ import annotations

import logging

import networkx as nx

from architecture_agent.ast_parser.ast_parser import FileAST

logger = logging.getLogger(__name__)


class CallGraphBuilder:
    """Builds and queries a function-level call graph."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    def build(self, file_asts: list[FileAST]) -> nx.DiGraph:
        """
        Construct the call graph from per-file AST call site data.
        """
        self.graph = nx.DiGraph()

        # Collect all known function names across the repo for matching
        all_functions: dict[str, str] = {}  # short_name -> qualified_name
        for f in file_asts:
            module = f.rel_path.rsplit(".", 1)[0].replace("/", ".")
            for fn in f.functions:
                qualified = f"{module}.{fn}"
                self.graph.add_node(qualified, file=f.rel_path, kind="function")
                all_functions[fn] = qualified
            for cls in f.classes:
                qualified = f"{module}.{cls}"
                self.graph.add_node(qualified, file=f.rel_path, kind="class")

        # Add call edges
        for f in file_asts:
            module = f.rel_path.rsplit(".", 1)[0].replace("/", ".")
            for caller_name, callee_name in f.call_sites:
                # Qualify the caller
                if "." in caller_name and "<module" not in caller_name:
                    caller_qualified = f"{module}.{caller_name}"
                elif "<module" in caller_name:
                    caller_qualified = f"{module}.<module>"
                    if caller_qualified not in self.graph:
                        self.graph.add_node(caller_qualified, file=f.rel_path, kind="module")
                else:
                    caller_qualified = f"{module}.{caller_name}"

                # Resolve the callee
                callee_qualified = all_functions.get(callee_name, callee_name)

                if caller_qualified != callee_qualified:
                    if self.graph.has_edge(caller_qualified, callee_qualified):
                        self.graph[caller_qualified][callee_qualified]["count"] += 1
                    else:
                        self.graph.add_edge(caller_qualified, callee_qualified, count=1)

        logger.info(
            "Call graph built: %d nodes, %d edges",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return self.graph

    def get_callers(self, function_name: str) -> list[str]:
        """Return functions that call the given function."""
        # Try exact match first, then partial match
        target = self._resolve_name(function_name)
        if not target:
            return []
        return list(self.graph.predecessors(target))

    def get_callees(self, function_name: str) -> list[str]:
        """Return functions called by the given function."""
        target = self._resolve_name(function_name)
        if not target:
            return []
        return list(self.graph.successors(target))

    def get_call_chains(self, function_name: str, depth: int = 3) -> list[list[str]]:
        """
        Return transitive call paths from the given function up to depth.
        """
        target = self._resolve_name(function_name)
        if not target:
            return []

        chains: list[list[str]] = []
        self._dfs_chains(target, [target], depth, chains)
        return chains

    def get_most_called(self, top_n: int = 15) -> list[tuple[str, int]]:
        """Return functions with the highest in-degree (most called)."""
        in_deg = [(node, self.graph.in_degree(node)) for node in self.graph.nodes()]
        return sorted(in_deg, key=lambda x: x[1], reverse=True)[:top_n]

    def _resolve_name(self, name: str) -> str | None:
        """Resolve a short or qualified name to a graph node."""
        if name in self.graph:
            return name
        # Partial match: find nodes ending with the given name
        for node in self.graph.nodes():
            if node.endswith(f".{name}") or node == name:
                return node
        return None

    def _dfs_chains(self, node: str, path: list[str], depth: int, results: list[list[str]]) -> None:
        """DFS to collect call chains."""
        if depth <= 0:
            if len(path) > 1:
                results.append(list(path))
            return

        successors = list(self.graph.successors(node))
        if not successors:
            if len(path) > 1:
                results.append(list(path))
            return

        for succ in successors:
            if succ not in path:  # Avoid cycles
                path.append(succ)
                self._dfs_chains(succ, path, depth - 1, results)
                path.pop()
