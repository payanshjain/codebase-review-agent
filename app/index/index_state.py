"""
In-memory holders for per-repository indexes and BM25 retrievers.

Changed from single globals to dictionaries keyed by repo_id so that
multiple repositories can be indexed and queried independently within
the same server process.
"""

from llama_index.core import VectorStoreIndex
from llama_index.retrievers.bm25 import BM25Retriever

_stored_indexes: dict[str, VectorStoreIndex] = {}
_bm25_retrievers: dict[str, BM25Retriever] = {}


# ── VectorStoreIndex cache ─────────────────────────────────────────


def set_stored_index(repo_id: str, index: VectorStoreIndex) -> None:
    _stored_indexes[repo_id] = index


def get_stored_index(repo_id: str) -> VectorStoreIndex | None:
    return _stored_indexes.get(repo_id)


# ── BM25 retriever cache ──────────────────────────────────────────


def set_bm25_retriever(repo_id: str, retriever: BM25Retriever) -> None:
    _bm25_retrievers[repo_id] = retriever


def get_bm25_retriever(repo_id: str) -> BM25Retriever | None:
    return _bm25_retrievers.get(repo_id)


# ── cache management ──────────────────────────────────────────────

def clear_retriever_cache(repo_id: str) -> None:
    """Drop cached BM25 retriever for a single repo (e.g. after re-indexing)."""
    _bm25_retrievers.pop(repo_id, None)


def clear_repo_cache(repo_id: str) -> None:
    """Drop all cached objects for a single repository."""
    _stored_indexes.pop(repo_id, None)
    _bm25_retrievers.pop(repo_id, None)


def clear_all_caches() -> None:
    """Drop every cached index and retriever (e.g. during shutdown)."""
    _stored_indexes.clear()
    _bm25_retrievers.clear()


def get_all_cached_repo_ids() -> list[str]:
    """Return repo IDs that have an in-memory index."""
    return list(_stored_indexes.keys())
