"""
FastAPI route definitions for the Documentation Generator Agent.

Exposes POST /generate-docs endpoint to autonomously analyze repositories
and generate multi-format documentation reports.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from documentation_agent.schemas import DocumentationOutput, GenerateDocsRequest
from documentation_agent.services.orchestrator import DocumentationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documentation-generator"])
orchestrator = DocumentationOrchestrator()


@router.post("/generate-docs", response_model=DocumentationOutput, status_code=200)
async def generate_repository_documentation(request: GenerateDocsRequest) -> DocumentationOutput:
    """
    Documentation Generator Agent Endpoint.

    Analyzes a target repository (local directory path or GitHub URL) and generates:
    - README.md
    - Architecture Documentation
    - API Documentation
    - Developer Onboarding Guide
    - Database Documentation
    """
    try:
        output = await orchestrator.generate_documentation(request)
        return output
    except ValueError as exc:
        logger.warning("Invalid input provided to generate-docs: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unhandled exception during documentation generation: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Documentation pipeline failed: {exc}") from exc
