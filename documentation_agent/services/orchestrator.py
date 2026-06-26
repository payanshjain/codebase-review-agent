"""
Documentation Orchestrator service implementation.

Coordinates asynchronous repository parsing, AST metadata extraction,
diagram generation, incremental cache check, and multi-format document export.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from documentation_agent.api_doc_generator.generator import ApiDocGenerator
from documentation_agent.architecture_doc_generator.generator import ArchitectureDocGenerator
from documentation_agent.diagram_generator.diagram_generator import DiagramGenerator
from documentation_agent.metadata_extractor.extractor import MetadataExtractor
from documentation_agent.onboarding_generator.generator import OnboardingGenerator
from documentation_agent.readme_generator.generator import ReadmeGenerator
from documentation_agent.repository_parser.parser import RepositoryParser
from documentation_agent.schemas import DocumentationOutput, GenerateDocsRequest
from documentation_agent.services.database_doc_generator import DatabaseDocGenerator
from documentation_agent.services.export_service import ExportService
from documentation_agent.services.incremental_service import IncrementalService
from documentation_agent.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class DocumentationOrchestrator:
    """
    Orchestrates autonomous documentation generation across all specialist sub-generators.
    """

    def __init__(self) -> None:
        self.parser = RepositoryParser()
        self.extractor = MetadataExtractor()
        self.diagram_gen = DiagramGenerator()
        self.readme_gen = ReadmeGenerator()
        self.arch_gen = ArchitectureDocGenerator()
        self.api_gen = ApiDocGenerator()
        self.onboarding_gen = OnboardingGenerator()
        self.db_gen = DatabaseDocGenerator()
        self.incremental_svc = IncrementalService()
        self.storage_svc = StorageService()
        self.export_svc = ExportService()

    async def generate_documentation(self, request: GenerateDocsRequest) -> DocumentationOutput:
        """
        Execute full documentation generation lifecycle.
        """
        logger.info("Starting documentation generation pipeline for: %s", request.repository_path)

        # 1. Parse Input Structure
        parsed = await asyncio.to_thread(self.parser.parse, request.repository_path)

        # 2. Check Incremental Manifest Cache
        repo_hash = self.incremental_svc.compute_repo_hash(parsed)
        if not request.force_regenerate:
            cached = self.incremental_svc.check_cache(parsed.repo_id, repo_hash)
            if cached:
                return cached

        # 3. Extract Deep AST Metadata
        metadata = await asyncio.to_thread(self.extractor.extract, parsed)

        # 4. Synthesize Mermaid Diagrams
        diagrams = await asyncio.to_thread(self.diagram_gen.generate_all_diagrams, metadata)

        # 5. Concurrent Document Generation
        logger.info("Executing concurrent generation across all 5 specialist generators...")
        readme_task = asyncio.create_task(self.readme_gen.generate(metadata))
        arch_task = asyncio.create_task(self.arch_gen.generate(metadata, diagrams))
        api_task = asyncio.create_task(self.api_gen.generate(metadata))
        onboarding_task = asyncio.create_task(self.onboarding_gen.generate(metadata))
        db_task = asyncio.create_task(self.db_gen.generate(metadata))

        readme_str, arch_str, api_str, onboarding_str, db_str = await asyncio.gather(
            readme_task, arch_task, api_task, onboarding_task, db_task
        )

        output = DocumentationOutput(
            readme=readme_str,
            architecture_docs=arch_str,
            api_docs=api_str,
            onboarding_guide=onboarding_str,
            database_docs=db_str,
        )

        # 6. Save Markdown Files
        await asyncio.to_thread(self.storage_svc.save_all, parsed.repo_id, output)

        # 7. Multi-Format Exports (.md, .html, .pdf)
        exported_map = await asyncio.to_thread(
            self.export_svc.export, parsed.repo_id, parsed.repo_name, output, request.export_formats
        )
        output.exported_files = exported_map

        # 8. Update Manifest Record
        await asyncio.to_thread(self.incremental_svc.save_manifest, parsed.repo_id, repo_hash, output)

        logger.info("Completed documentation generation pipeline successfully for %s", parsed.repo_name)
        return output
