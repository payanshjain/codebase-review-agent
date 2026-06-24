"""
ChromaDB setup for local, persistent vector storage.

each repository gets its own Chroma collection named ``repo_{repo_id}``,
providing clean isolation and easy deletion.

Why Chroma here?
- Runs locally with no extra server (good for MVP / learning).
- Persists to disk so embeddings survive server restarts.
- LlamaIndex has a first-class adapter (ChromaVectorStore).
"""

from pathlib import Path

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.core.config import Settings


def _collection_name(repo_id: str) -> str:
    """Derive the Chroma collection name for a repository."""
    return f"repo_{repo_id}"


def create_chroma_vector_store(
    settings: Settings,
    repo_id: str,
    *,
    reset_collection: bool = True,
) -> ChromaVectorStore:
    """
    Open (or recreate) a per-repo Chroma collection backed by the shared
    persist directory.

    reset_collection=True clears the named collection before indexing so
    re-runs do not duplicate old chunks.
    """
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_dir))
    col_name = _collection_name(repo_id)

    if reset_collection:
        try:
            client.delete_collection(name=col_name)
        except Exception:
            # Collection may not exist on first run — safe to continue.
            pass

    collection = client.get_or_create_collection(name=col_name)
    return ChromaVectorStore(chroma_collection=collection)


def delete_chroma_collection(settings: Settings, repo_id: str) -> None:
    """
    Remove the Chroma collection for a repository.

    Called during DELETE /repositories/{repo_id} to free stored vectors.
    """
    persist_dir = Path(settings.chroma_persist_dir)
    if not persist_dir.exists():
        return

    client = chromadb.PersistentClient(path=str(persist_dir))
    col_name = _collection_name(repo_id)

    try:
        client.delete_collection(name=col_name)
    except Exception:
        # Collection may already be gone — not an error.
        pass


def chroma_collection_count(settings: Settings, repo_id: str) -> int:
    """Return the number of vectors in a repo's collection (0 if missing)."""
    persist_dir = Path(settings.chroma_persist_dir)
    if not persist_dir.exists():
        return 0

    client = chromadb.PersistentClient(path=str(persist_dir))
    col_name = _collection_name(repo_id)

    try:
        collection = client.get_collection(name=col_name)
        return collection.count()
    except Exception:
        return 0
