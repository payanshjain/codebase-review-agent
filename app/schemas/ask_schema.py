from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for asking a question against indexed repositories."""

    question: str = Field(..., min_length=1, description="Natural-language question about the codebase")
    repo_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of repo IDs to search. "
            "If omitted, all indexed repositories are queried."
        ),
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Optional override for number of chunks to retrieve (default from env)",
    )


class SourceChunk(BaseModel):
    """One retrieved chunk used as evidence for the answer."""

    repo_id: str = Field(default="unknown", description="Repository this chunk belongs to")
    file_path: str
    relevance_score: float | None = None
    text_preview: str = Field(..., description="First ~300 chars of the retrieved chunk")
    # AST metadata (populated for code chunks, None for text-fallback chunks)
    symbol_type: str | None = Field(default=None, description="function, class, method, or module_header")
    symbol_name: str | None = Field(default=None, description="Name of the code symbol")
    breadcrumb: str | None = Field(default=None, description="Structural navigation path")
    chunk_strategy: str = Field(default="text", description="ast or text")


class AskResponse(BaseModel):
    """Grounded answer plus the sources that informed it."""

    question: str
    answer: str
    sources: list[SourceChunk]
    retrieval_mode: str = Field(
        default="hybrid",
        description="How chunks were retrieved (vector + BM25 fusion)",
    )
    retrieval_top_k: int
    llm_model: str
