from pydantic import BaseModel, Field

class IndexRequest(BaseModel):
    """Request body for indexing a local repository path (not a GitHub URL)."""

    repo_path: str = Field(
        ...,
        description=(
            "Local folder path on your machine, e.g. "
            "C:/Users/you/projects/my-repo — clone the repo first if it is on GitHub"
        ),
        examples=["C:/Users/you/projects/project-name"],
    )

class IndexedFilePreview(BaseModel):
    """Lightweight preview of loaded file metadata for learning/debugging."""

    file_path: str
    language: str
    chars: int

class ChunkPreview(BaseModel):
    """Short preview of one chunk after splitting (for debugging / learning)."""

    file_path: str
    chunk_index: int
    text_preview: str = Field(
        ...,
        description="First ~200 chars of chunk text",
    )
    symbol_type: str | None = Field(default=None, description="AST symbol type if applicable")
    breadcrumb: str | None = Field(default=None, description="Structural navigation path")
    chunk_strategy: str = Field(default="text", description="ast or text")

class IndexResponse(BaseModel):
    """Response returned after parse, chunk, embed, and Chroma persistence."""

    repo_id: str
    repo_path: str
    files_scanned: int
    documents_created: int
    chunks_created: int
    vectors_stored: int
    ast_chunks: int = Field(default=0, description="Chunks created via AST parsing")
    text_chunks: int = Field(default=0, description="Chunks created via text fallback")
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    embed_model: str
    chroma_persist_dir: str
    chroma_collection_name: str
    previews: list[IndexedFilePreview]
    chunk_previews: list[ChunkPreview]