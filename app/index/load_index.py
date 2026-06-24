"""
Load a VectorStoreIndex for querying — from memory or from persisted Chroma + docstore.

Updated for multi-repository support: all operations are scoped by repo_id.
"""

from pathlib import Path

import chromadb
from llama_index.core import StorageContext
from llama_index.core import load_index_from_storage as load_llamaindex_from_storage

from app.core.config import Settings
from app.core.providers import configure_embedding_model
from app.index.chroma_store import create_chroma_vector_store
from app.index.index_state import clear_retriever_cache, get_stored_index, set_stored_index


def _repo_storage_dir(settings: Settings, repo_id: str) -> Path:
    """Return the per-repo docstore directory: data/storage/{repo_id}/."""
    return Path(settings.storage_persist_dir) / repo_id


def _chroma_collection_has_vectors(settings: Settings, repo_id: str) -> bool:
    """Return True if the repo's Chroma collection exists and has at least one vector."""
    persist_dir = Path(settings.chroma_persist_dir)
    if not persist_dir.exists():
        return False

    client = chromadb.PersistentClient(path=str(persist_dir))
    col_name = f"repo_{repo_id}"
    try:
        collection = client.get_collection(name=col_name)
    except Exception:
        return False

    return collection.count() > 0


def _storage_persist_exists(settings: Settings, repo_id: str) -> bool:
    storage_dir = _repo_storage_dir(settings, repo_id)
    return storage_dir.exists() and any(storage_dir.iterdir())


def load_index_from_disk(settings: Settings, repo_id: str):
    """Rebuild index from Chroma vectors + persisted docstore (for hybrid BM25)."""
    if not _chroma_collection_has_vectors(settings, repo_id):
        raise ValueError(
            f"No indexed data found for repo '{repo_id}'. "
            "Call POST /repositories/index or POST /index first."
        )
    if not _storage_persist_exists(settings, repo_id):
        raise ValueError(
            f"Docstore not found on disk for repo '{repo_id}'. "
            "Re-run indexing to rebuild hybrid retrieval data."
        )

    clear_retriever_cache(repo_id)
    configure_embedding_model(settings)
    vector_store = create_chroma_vector_store(settings, repo_id, reset_collection=False)
    storage_dir = _repo_storage_dir(settings, repo_id)

    storage_context = StorageContext.from_defaults(
        persist_dir=str(storage_dir),
        vector_store=vector_store,
    )
    index = load_llamaindex_from_storage(storage_context)
    set_stored_index(repo_id, index)
    return index


def get_or_load_index(settings: Settings, repo_id: str):
    """
    Prefer the in-memory index from the current server session; otherwise load from disk.
    """
    index = get_stored_index(repo_id)
    if index is not None:
        return index
    return load_index_from_disk(settings, repo_id)
