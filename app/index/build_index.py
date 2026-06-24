"""
Build a LlamaIndex VectorStoreIndex from chunked nodes and store embeddings in Chroma.

Updated for multi-repository support + AST-based node handling:
- Each repo_id gets its own Chroma collection and docstore directory.
- Nodes are explicitly added to the SimpleDocumentStore before persisting,
  so that BM25Retriever can load them from disk after server restart.
"""

import shutil
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.storage.docstore import SimpleDocumentStore

from app.core.config import Settings
from app.core.providers import configure_embedding_model
from app.index.chroma_store import create_chroma_vector_store
from app.index.index_state import clear_retriever_cache, set_stored_index
from app.index.metadata_utils import sanitize_nodes


def _repo_storage_dir(settings: Settings, repo_id: str) -> Path:
    """Return the per-repo docstore directory: data/storage/{repo_id}/."""
    return Path(settings.storage_persist_dir) / repo_id


def _prepare_storage_dir(storage_dir: Path) -> None:
    """Wipe prior docstore files so BM25 stays in sync with a fresh Chroma collection."""
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)


def build_and_store_index(
    nodes: list,
    settings: Settings,
    repo_id: str,
) -> VectorStoreIndex:
    """
    Embed chunk nodes with HuggingFace, persist vectors in Chroma, and persist
    the docstore to disk (required for BM25 after server restart).

    Key fix: explicitly populate the SimpleDocumentStore with all nodes before
    building the VectorStoreIndex.  Without this, index.docstore is empty when
    using an external vector store (Chroma), causing BM25 to fail.
    """
    if not nodes:
        raise ValueError("No chunks to index. Repository may be empty or all files were skipped.")

    sanitize_nodes(nodes)
    clear_retriever_cache(repo_id)
    configure_embedding_model(settings)
    vector_store = create_chroma_vector_store(settings, repo_id, reset_collection=True)

    storage_dir = _repo_storage_dir(settings, repo_id)
    _prepare_storage_dir(storage_dir)

    # Explicitly populate the docstore so BM25 has access to node texts.
    docstore = SimpleDocumentStore()
    docstore.add_documents(nodes)

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore,
    )
    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    # Persist docstore + index metadata to disk (vectors already persisted in Chroma).
    index.storage_context.persist(persist_dir=str(storage_dir))

    set_stored_index(repo_id, index)
    return index
