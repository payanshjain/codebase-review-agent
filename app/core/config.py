from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (where .env should live when you run `python run.py`)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class SettingsNotConfiguredError(Exception):
    """Raised when required environment variables are missing."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groq — cloud LLM for answers (free tier at console.groq.com)
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")

    # HuggingFace — local embeddings (no API key)
    huggingface_embed_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        alias="HUGGINGFACE_EMBED_MODEL",
    )
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(
        default="codebase_qa_mvp",
        alias="CHROMA_COLLECTION_NAME",
    )
    chunk_size: int = Field(default=1024, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=128, alias="CHUNK_OVERLAP")
    # Hybrid retrieval: vector + BM25 fused → final top_k chunks for the LLM
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    vector_top_k: int = Field(
        default=10,
        alias="VECTOR_TOP_K",
        description="Candidate pool size from dense vector search before fusion",
    )
    bm25_top_k: int = Field(
        default=10,
        alias="BM25_TOP_K",
        description="Candidate pool size from BM25 keyword search before fusion",
    )
    hybrid_fusion_mode: str = Field(
        default="reciprocal_rerank",
        alias="HYBRID_FUSION_MODE",
    )
    storage_persist_dir: str = Field(default="./data/storage", alias="STORAGE_PERSIST_DIR")

    # Multi-repository management
    repos_clone_dir: str = Field(
        default="./data/repos",
        alias="REPOS_CLONE_DIR",
        description="Directory where GitHub repositories are cloned to",
    )
    repos_metadata_file: str = Field(
        default="./data/repositories.json",
        alias="REPOS_METADATA_FILE",
        description="JSON file storing metadata for all indexed repositories",
    )

    # AST-based chunking
    ast_max_chunk_tokens: int = Field(
        default=1500,
        alias="AST_MAX_CHUNK_TOKENS",
        description="Max tokens per AST code chunk before sub-splitting with SentenceSplitter",
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so env is loaded once per process."""
    if not ENV_FILE.exists():
        raise SettingsNotConfiguredError(
            "Missing .env file. Copy .env.example to .env in the project root, "
            "then set GROQ_API_KEY=your_key."
        )
    try:
        settings = Settings()
    except ValidationError as exc:
        raise SettingsNotConfiguredError(
            "GROQ_API_KEY is not set in .env. "
            "Get a free key at https://console.groq.com/keys and add it to .env."
        ) from exc

    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        raise SettingsNotConfiguredError(
            "GROQ_API_KEY is still the placeholder. "
            "Set a real key in .env and restart the server."
        )

    return settings
