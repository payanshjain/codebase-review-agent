"""
FastAPI route definitions for the Repository Architecture Agent.

Exposes:
- POST /analyze-repository → full architecture analysis
- POST /architecture-query → answer architecture questions
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from architecture_agent.schemas import (
    AnalyzeRepositoryRequest,
    ArchitectureOutput,
    ArchitectureQueryOutput,
    ArchitectureQueryRequest,
)
from architecture_agent.services.orchestrator import ArchitectureOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["architecture-agent"])
orchestrator = ArchitectureOrchestrator()


@router.post("/analyze-repository", response_model=ArchitectureOutput, status_code=200)
async def analyze_repository(request: AnalyzeRepositoryRequest) -> ArchitectureOutput:
    """
    Repository Architecture Agent — Full Analysis.

    Analyzes a repository (local path or GitHub URL) and produces:
    - Architecture summary
    - Layer classification
    - Dependency graph (Mermaid)
    - Call graph (Mermaid)
    - Important files ranking
    """
    try:
        output = await orchestrator.analyze(request)
        return output
    except ValueError as exc:
        logger.warning("Invalid input: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Analysis pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Architecture analysis failed: {exc}") from exc


@router.post("/architecture-query", response_model=ArchitectureQueryOutput, status_code=200)
async def architecture_query(request: ArchitectureQueryRequest) -> ArchitectureQueryOutput:
    """
    Repository Architecture Agent — Query.

    Answers architecture questions like:
    - Explain project architecture
    - Show dependencies of a file
    - What breaks if I change X?
    - Which files are most important?
    """
    try:
        output = await orchestrator.query(request)
        return output
    except ValueError as exc:
        logger.warning("Invalid query input: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Architecture query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Architecture query failed: {exc}") from exc
