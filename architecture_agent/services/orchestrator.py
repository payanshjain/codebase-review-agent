"""
Orchestrator for the Architecture Agent.

Coordinates the full analysis pipeline:
1. Parse repository
2. AST parse all code files
3. Build dependency graph (NetworkX)
4. Build call graph (NetworkX)
5. Run architecture builder
6. Generate Mermaid diagrams
7. Produce ArchitectureOutput

Also manages cached state for the query endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from architecture_agent.architecture_builder.builder import ArchitectureBuilder
from architecture_agent.ast_parser.ast_parser import ASTParser
from architecture_agent.call_graph.builder import CallGraphBuilder
from architecture_agent.dependency_graph.builder import DependencyGraphBuilder
from architecture_agent.mermaid_generator.generator import MermaidGenerator
from architecture_agent.repository_parser.parser import RepositoryParser
from architecture_agent.schemas import (
    AnalyzeRepositoryRequest,
    ArchitectureOutput,
    ArchitectureQueryRequest,
    ArchitectureQueryOutput,
    ArchitectureSummary,
)
from architecture_agent.services.cache_service import CacheService
from architecture_agent.services.query_service import QueryService

logger = logging.getLogger(__name__)


class ArchitectureOrchestrator:
    """Orchestrates the full repository architecture analysis pipeline."""

    def __init__(self) -> None:
        self.repo_parser = RepositoryParser()
        self.ast_parser = ASTParser()
        self.dep_builder = DependencyGraphBuilder()
        self.call_builder = CallGraphBuilder()
        self.arch_builder = ArchitectureBuilder()
        self.mermaid_gen = MermaidGenerator()
        self.cache_svc = CacheService()

        # In-memory state for query service (keyed by repo_id)
        self._query_services: dict[str, QueryService] = {}
        self._summaries: dict[str, ArchitectureSummary] = {}

    async def analyze(self, request: AnalyzeRepositoryRequest) -> ArchitectureOutput:
        """Execute the full analysis pipeline."""
        logger.info("Starting architecture analysis for: %s", request.repository_path)

        # 1. Parse repository structure
        parsed = await asyncio.to_thread(self.repo_parser.parse, request.repository_path)

        # 2. Check cache
        repo_hash = self.cache_svc.compute_repo_hash(parsed)
        if not request.force_reanalyze:
            cached = self.cache_svc.check_cache(parsed.repo_id, repo_hash)
            if cached:
                return cached

        # 3. AST parse all code files
        file_asts = await asyncio.to_thread(self.ast_parser.parse_all, parsed.code_files, parsed.local_path)

        # 4. Build dependency graph
        dep_graph = await asyncio.to_thread(self.dep_builder.build, file_asts)

        # 5. Build call graph
        call_graph = await asyncio.to_thread(self.call_builder.build, file_asts)

        # 6. Architecture inference
        arch_summary = await asyncio.to_thread(self.arch_builder.build, parsed, file_asts)

        # 7. Rank important files
        important = self.dep_builder.get_most_important_files()
        important_files = [f for f, _ in important]

        # 8. Generate Mermaid diagrams
        dep_mermaid = self.mermaid_gen.generate_dependency_graph(dep_graph, important)
        arch_mermaid = self.mermaid_gen.generate_system_architecture(arch_summary)
        call_mermaid = self.mermaid_gen.generate_call_graph(call_graph)

        # 9. Generate summary text
        summary_text = self._build_summary_text(parsed, arch_summary, file_asts)
        arch_text = self._build_architecture_text(arch_summary)

        output = ArchitectureOutput(
            summary=summary_text,
            architecture=arch_text,
            dependency_graph=dep_mermaid,
            call_graph=call_mermaid,
            important_files=important_files,
        )

        # 10. Cache result
        await asyncio.to_thread(self.cache_svc.save_cache, parsed.repo_id, repo_hash, output)

        # 11. Store in-memory for query service
        self._summaries[parsed.repo_id] = arch_summary
        self._query_services[parsed.repo_id] = QueryService(
            dep_graph=self.dep_builder,
            call_graph=self.call_builder,
            summary=arch_summary,
            output=output,
        )

        logger.info("Architecture analysis complete for %s", parsed.repo_name)
        return output

    async def query(self, request: ArchitectureQueryRequest) -> ArchitectureQueryOutput:
        """Answer an architecture question (requires prior analysis)."""
        # Resolve repo_id from path
        parsed = await asyncio.to_thread(self.repo_parser.parse, request.repository_path)

        query_svc = self._query_services.get(parsed.repo_id)
        if not query_svc:
            # Try to load from cache and re-analyze
            logger.info("No in-memory state for %s, running analysis first.", parsed.repo_id)
            await self.analyze(AnalyzeRepositoryRequest(repository_path=request.repository_path))
            query_svc = self._query_services.get(parsed.repo_id)

        if not query_svc:
            return ArchitectureQueryOutput(
                query=request.query,
                answer="Failed to analyze repository. Please run /analyze-repository first.",
            )

        answer = query_svc.answer(request.query)
        return ArchitectureQueryOutput(query=request.query, answer=answer)

    def _build_summary_text(self, parsed, summary: ArchitectureSummary, file_asts) -> str:
        """Build the human-readable architecture summary."""
        lang_str = ", ".join(f"**{l}**" for l in summary.languages) or "Unknown"
        fw_str = ", ".join(f"`{fw.name}`" for fw in summary.frameworks) or "None detected"
        pkg_str = ", ".join(f"`{p}`" for p in summary.package_managers) or "None detected"
        db_str = ", ".join(f"`{d}`" for d in summary.databases) or "None detected"
        dep_stats = self.dep_builder.get_graph_stats()
        total_loc = sum(f.loc for f in file_asts)

        ep_lines = ""
        if summary.entry_points:
            ep_items = "\n".join(f"  - `{ep.file_path}` ({ep.kind})" for ep in summary.entry_points[:8])
            ep_lines = f"\n### Entry Points\n{ep_items}"

        svc_lines = ""
        if summary.services:
            svc_items = "\n".join(f"  - **{s.name}** (root: `{s.root_dir}`)" for s in summary.services[:5])
            svc_lines = f"\n### Services / Components\n{svc_items}"

        return f"""# Architecture Summary: {summary.repo_name}

## Overview
- **Languages**: {lang_str}
- **Frameworks**: {fw_str}
- **Package Managers**: {pkg_str}
- **Databases**: {db_str}
- **Total Files Scanned**: {len(parsed.all_files)}
- **Code Files Analyzed**: {len(file_asts)}
- **Total Lines of Code**: {total_loc:,}

## Dependency Graph Stats
- **Nodes (files)**: {dep_stats['nodes']}
- **Edges (imports)**: {dep_stats['edges']}
- **Components**: {dep_stats['components']}
- **Density**: {dep_stats['density']}
{ep_lines}
{svc_lines}
"""

    def _build_architecture_text(self, summary: ArchitectureSummary) -> str:
        """Build the layer classification text."""
        lines = ["## Architectural Layers\n"]
        for layer, files in summary.layers.items():
            lines.append(f"### {layer.title()} ({len(files)} files)")
            for f in files[:10]:
                lines.append(f"  - `{f}`")
            if len(files) > 10:
                lines.append(f"  - ... and {len(files) - 10} more")
            lines.append("")
        return "\n".join(lines)
