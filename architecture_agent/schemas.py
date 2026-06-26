"""
Pydantic models and schemas for the Repository Architecture Agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── API Request / Response ────────────────────────────────────────


class AnalyzeRepositoryRequest(BaseModel):
    """Request body for POST /analyze-repository."""

    repository_path: str = Field(
        ...,
        description="Local directory path or GitHub HTTPS URL",
        examples=["C:/Users/payan/Desktop/Codebase Agent", "https://github.com/tiangolo/fastapi"],
    )
    force_reanalyze: bool = Field(
        default=False,
        description="Force full re-analysis ignoring cache.",
    )


class ArchitectureQueryRequest(BaseModel):
    """Request body for POST /architecture-query."""

    repository_path: str = Field(
        ...,
        description="Local directory path or GitHub HTTPS URL (must have been analyzed first).",
    )
    query: str = Field(
        ...,
        description="Natural-language architecture question.",
        examples=[
            "Explain project architecture",
            "Show dependencies of app/main.py",
            "What breaks if I change app/core/config.py",
            "Which files are most important?",
        ],
    )


class ArchitectureOutput(BaseModel):
    """Top-level output matching the required schema."""

    summary: str = Field(default="", description="Architecture summary prose")
    architecture: str = Field(default="", description="Layer/component classification")
    dependency_graph: str = Field(default="", description="Mermaid dependency diagram")
    call_graph: str = Field(default="", description="Mermaid call graph diagram")
    important_files: list[str] = Field(default_factory=list, description="Files ranked by centrality")


class ArchitectureQueryOutput(BaseModel):
    """Response for architecture-query endpoint."""

    query: str
    answer: str


# ── Internal Metadata ─────────────────────────────────────────────


class FileNode(BaseModel):
    """Metadata for a single source file in the graph."""

    rel_path: str
    language: str | None = None
    loc: int = 0
    class_count: int = 0
    function_count: int = 0
    is_entry_point: bool = False


class ImportEdge(BaseModel):
    """An import relationship between two files."""

    source: str       # file that contains the import
    target: str       # file being imported
    symbols: list[str] = Field(default_factory=list)


class CallEdge(BaseModel):
    """A function-call relationship."""

    caller: str       # fully qualified caller name
    callee: str       # fully qualified callee name
    caller_file: str
    count: int = 1


class FrameworkDetection(BaseModel):
    """Detected framework/technology."""

    name: str
    category: str     # "web_framework", "orm", "frontend", "testing", etc.
    evidence: str     # import or config line that triggered detection


class EntryPointDetection(BaseModel):
    """Detected application entry point."""

    file_path: str
    kind: str         # "main_guard", "fastapi_app", "script_entry", "package_json"
    evidence: str


class ServiceNode(BaseModel):
    """A detected microservice or major component."""

    name: str
    root_dir: str
    has_dockerfile: bool = False
    has_package_json: bool = False
    entry_points: list[str] = Field(default_factory=list)


class ArchitectureSummary(BaseModel):
    """Full intermediate analysis result from architecture builder."""

    repo_name: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[FrameworkDetection] = Field(default_factory=list)
    entry_points: list[EntryPointDetection] = Field(default_factory=list)
    services: list[ServiceNode] = Field(default_factory=list)
    layers: dict[str, list[str]] = Field(default_factory=dict)
    package_managers: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    api_routes: list[str] = Field(default_factory=list)


class CacheManifest(BaseModel):
    """Serializable cache record for incremental analysis."""

    repo_id: str
    sha256_hash: str
    analyzed_at: str
    output: ArchitectureOutput
