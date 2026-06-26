"""
Pydantic models and schemas for the Documentation Generator Agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── API Request & Response Schemas ────────────────────────────────


class GenerateDocsRequest(BaseModel):
    """Request body for POST /generate-docs endpoint."""

    repository_path: str = Field(
        ...,
        description="Local repository directory path or GitHub HTTPS URL",
        examples=["C:/Users/payan/Desktop/Codebase Agent", "https://github.com/tiangolo/fastapi"],
    )
    force_regenerate: bool = Field(
        default=False,
        description="Force full documentation regeneration ignoring incremental cache manifest.",
    )
    export_formats: list[str] = Field(
        default=["markdown", "html", "pdf"],
        description="List of export formats to generate on disk.",
    )


class DocumentationOutput(BaseModel):
    """Output documentation structure matching requirements 5 & 7."""

    readme: str = Field(default="", description="Generated README.md content")
    architecture_docs: str = Field(default="", description="System architecture documentation")
    api_docs: str = Field(default="", description="API endpoints and schema documentation")
    onboarding_guide: str = Field(default="", description="Developer onboarding guide")
    database_docs: str = Field(default="", description="Database tables, models, and relationships")
    exported_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of format ('markdown', 'html', 'pdf') to saved file path.",
    )


# ── Metadata Schemas ──────────────────────────────────────────────


class ClassMetadata(BaseModel):
    """Metadata extracted for a code class definition."""

    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    methods: list[str] = Field(default_factory=list)


class FunctionMetadata(BaseModel):
    """Metadata extracted for a function or method definition."""

    name: str
    file_path: str
    line_start: int
    line_end: int
    signature: str
    docstring: str | None = None
    decorators: list[str] = Field(default_factory=list)


class ApiRouteMetadata(BaseModel):
    """Metadata extracted for an HTTP API endpoint route."""

    method: str
    path: str
    function_name: str
    file_path: str
    line: int
    docstring: str | None = None


class DatabaseModelMetadata(BaseModel):
    """Metadata extracted for a database entity or ORM table model."""

    name: str
    file_path: str
    line: int
    columns: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class RepositoryMetadata(BaseModel):
    """Comprehensive repository metadata gathered from parser and extractor."""

    repo_id: str
    repo_name: str
    local_path: str
    folder_structure: str = ""
    files_scanned: int = 0
    languages: list[str] = Field(default_factory=list)
    classes: list[ClassMetadata] = Field(default_factory=list)
    functions: list[FunctionMetadata] = Field(default_factory=list)
    api_endpoints: list[ApiRouteMetadata] = Field(default_factory=list)
    configuration_files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    databases: list[DatabaseModelMetadata] = Field(default_factory=list)


class ManifestRecord(BaseModel):
    """Incremental cache manifest record stored on disk."""

    repo_id: str
    sha256_hash: str
    generated_at: str
    documentation: DocumentationOutput
