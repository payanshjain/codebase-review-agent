"""
Pydantic models for repository management endpoints.
"""

from pydantic import BaseModel, Field


# ── Requests ───────────────────────────────────────────────────────


class RepoIndexRequest(BaseModel):
    """Request body for POST /repositories/index."""

    url: str = Field(
        ...,
        description="GitHub HTTPS URL, e.g. https://github.com/owner/repo",
        examples=["https://github.com/tiangolo/fastapi"],
    )
    force: bool = Field(
        default=False,
        description=(
            "Force re-index even if repository is already indexed. "
            "Deletes the old index and re-clones."
        ),
    )


# ── Responses ──────────────────────────────────────────────────────


class RepoSummary(BaseModel):
    """Lightweight summary used in list responses."""

    repo_id: str
    name: str
    url: str | None = None
    source: str
    status: str
    files_count: int = 0
    chunks_count: int = 0
    indexed_at: str | None = None


class RepoDetailResponse(BaseModel):
    """Full statistics for a single repository."""

    repo_id: str
    name: str
    url: str | None = None
    local_path: str
    source: str
    status: str
    files_count: int = 0
    chunks_count: int = 0
    languages: list[str] = []
    indexed_at: str | None = None


class RepoIndexResponse(BaseModel):
    """Response after indexing a repository via POST /repositories/index."""

    repo_id: str
    name: str
    url: str
    status: str
    files_scanned: int = 0
    chunks_created: int = 0
    vectors_stored: int = 0
    languages: list[str] = []
    message: str = ""


class RepoListResponse(BaseModel):
    """Wrapper for GET /repositories."""

    repositories: list[RepoSummary]
    total: int


class RepoDeleteResponse(BaseModel):
    """Confirmation after DELETE /repositories/{repo_id}."""

    repo_id: str
    message: str
