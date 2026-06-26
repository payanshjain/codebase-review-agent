"""
Query service for the Architecture Agent.

Answers natural-language architecture queries by pattern-matching against
known question templates and querying the dependency/call graphs.
"""

from __future__ import annotations

import logging
import re

from architecture_agent.call_graph.builder import CallGraphBuilder
from architecture_agent.dependency_graph.builder import DependencyGraphBuilder
from architecture_agent.schemas import ArchitectureOutput, ArchitectureSummary

logger = logging.getLogger(__name__)


class QueryService:
    """Answers architecture questions against a cached analysis."""

    def __init__(
        self,
        dep_graph: DependencyGraphBuilder,
        call_graph: CallGraphBuilder,
        summary: ArchitectureSummary,
        output: ArchitectureOutput,
    ) -> None:
        self.dep_graph = dep_graph
        self.call_graph = call_graph
        self.summary = summary
        self.output = output

    def answer(self, query: str) -> str:
        """Route a query to the appropriate handler."""
        q = query.strip().lower()

        # Pattern matching dispatch
        if re.search(r"explain\s+(project\s+)?architecture", q):
            return self._explain_architecture()
        if re.search(r"explain\s+authentication\s+flow", q):
            return self._explain_auth_flow()
        if re.search(r"explain\s+request\s+lifecycle", q):
            return self._explain_request_lifecycle()
        if re.search(r"(show\s+)?dependenc(ies|y)\s+of\s+(.+)", q):
            match = re.search(r"dependenc(?:ies|y)\s+of\s+(.+)", q)
            file_path = match.group(1).strip().strip("'\"") if match else ""
            return self._show_dependencies(file_path)
        if re.search(r"which\s+(?:services|files)\s+depend\s+on\s+(.+)", q):
            match = re.search(r"depend\s+on\s+(.+)", q)
            target = match.group(1).strip().strip("'\"?") if match else ""
            return self._which_depend_on(target)
        if re.search(r"what\s+breaks\s+if\s+(?:i\s+)?change\s+(.+)", q):
            match = re.search(r"change\s+(.+)", q)
            target = match.group(1).strip().strip("'\"?") if match else ""
            return self._what_breaks(target)
        if re.search(r"(?:which|most)\s+(?:files?\s+are\s+)?(?:most\s+)?important", q):
            return self._most_important()
        if re.search(r"call(?:ers?|ed\s+by)\s+(.+)", q):
            match = re.search(r"call(?:ers?|ed\s+by)\s+(.+)", q)
            fn = match.group(1).strip().strip("'\"?") if match else ""
            return self._who_calls(fn)

        # Default: return full summary
        return self._explain_architecture()

    def _explain_architecture(self) -> str:
        """Return the full architecture summary."""
        lines = [f"## Architecture of {self.summary.repo_name}\n"]
        lines.append(self.output.summary)
        lines.append("\n### Layer Classification\n")
        lines.append(self.output.architecture)
        return "\n".join(lines)

    def _explain_auth_flow(self) -> str:
        """Trace authentication-related symbols through the call graph."""
        auth_keywords = {"auth", "login", "token", "jwt", "oauth", "session", "password", "authenticate"}
        auth_nodes = [n for n in self.call_graph.graph.nodes() if any(k in n.lower() for k in auth_keywords)]

        if not auth_nodes:
            return "No authentication-related functions were detected in the codebase."

        lines = ["## Authentication Flow\n"]
        lines.append(f"Found **{len(auth_nodes)}** auth-related functions:\n")
        for node in sorted(auth_nodes)[:15]:
            callers = self.call_graph.get_callers(node)
            callees = self.call_graph.get_callees(node)
            lines.append(f"- `{node}`")
            if callers:
                lines.append(f"  - Called by: {', '.join(f'`{c}`' for c in callers[:5])}")
            if callees:
                lines.append(f"  - Calls: {', '.join(f'`{c}`' for c in callees[:5])}")

        return "\n".join(lines)

    def _explain_request_lifecycle(self) -> str:
        """Trace a typical request through route → service → database."""
        lines = ["## Request Lifecycle\n"]

        # Find route handlers
        route_nodes = [n for n in self.call_graph.graph.nodes()
                       if any(k in n.lower() for k in ("route", "handler", "endpoint", "view"))]
        if not route_nodes:
            # Fall back to any function with HTTP method names nearby
            route_nodes = list(self.call_graph.graph.nodes())[:5]

        for node in route_nodes[:3]:
            chains = self.call_graph.get_call_chains(node, depth=4)
            if chains:
                lines.append(f"### Starting from `{node}`:\n")
                for chain in chains[:3]:
                    lines.append("  → ".join(f"`{c.split('.')[-1]}`" for c in chain))
                lines.append("")

        return "\n".join(lines) if len(lines) > 1 else "No clear request lifecycle chain detected."

    def _show_dependencies(self, file_path: str) -> str:
        """Show what a file depends on."""
        # Try exact and fuzzy match
        target = self._resolve_file(file_path)
        if not target:
            return f"File `{file_path}` not found in the dependency graph."

        deps = self.dep_graph.get_file_dependencies(target)
        if not deps:
            return f"`{target}` has no file-level dependencies."

        lines = [f"## Dependencies of `{target}`\n"]
        for d in sorted(deps):
            lines.append(f"- `{d}`")
        return "\n".join(lines)

    def _which_depend_on(self, target: str) -> str:
        """Show files that depend on the target."""
        resolved = self._resolve_file(target)
        if not resolved:
            return f"Target `{target}` not found in the dependency graph."

        dependents = self.dep_graph.get_file_dependents(resolved)
        if not dependents:
            return f"No files directly depend on `{resolved}`."

        lines = [f"## Files that depend on `{resolved}`\n"]
        for d in sorted(dependents):
            lines.append(f"- `{d}`")
        return "\n".join(lines)

    def _what_breaks(self, target: str) -> str:
        """Transitive impact analysis."""
        resolved = self._resolve_file(target)
        if not resolved:
            return f"Target `{target}` not found in the dependency graph."

        affected = self.dep_graph.get_impact_analysis(resolved)
        if not affected:
            return f"No files would be affected by changes to `{resolved}`."

        lines = [f"## Impact Analysis: Changing `{resolved}`\n"]
        lines.append(f"**{len(affected)}** files would be transitively affected:\n")
        for f in affected:
            lines.append(f"- `{f}`")
        return "\n".join(lines)

    def _most_important(self) -> str:
        """Return PageRank-ranked important files."""
        ranked = self.dep_graph.get_most_important_files()
        if not ranked:
            return "No files in the dependency graph."

        lines = ["## Most Important Files (by PageRank)\n"]
        lines.append("| Rank | File | Score |")
        lines.append("|------|------|-------|")
        for i, (f, score) in enumerate(ranked, 1):
            lines.append(f"| {i} | `{f}` | {score:.4f} |")
        return "\n".join(lines)

    def _who_calls(self, fn_name: str) -> str:
        """Show callers of a function."""
        callers = self.call_graph.get_callers(fn_name)
        if not callers:
            return f"No callers found for `{fn_name}` (or function not found)."

        lines = [f"## Callers of `{fn_name}`\n"]
        for c in sorted(callers):
            lines.append(f"- `{c}`")
        return "\n".join(lines)

    def _resolve_file(self, name: str) -> str | None:
        """Fuzzy-match a file name to a dependency graph node."""
        name = name.strip().replace("\\", "/")
        if name in self.dep_graph.graph:
            return name
        # Partial match
        for node in self.dep_graph.graph.nodes():
            if node.endswith(name) or name in node:
                return node
        return None
