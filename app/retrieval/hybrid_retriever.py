"""
Hybrid retrieval: dense vector search (semantic) + BM25 (keyword).

Updated for multi-repository support + AST-based node handling.

Why both?
- Vector search finds conceptually similar code even when wording differs.
- BM25 excels at exact identifiers: function names, class names, env vars, error strings.
- Fusion (reciprocal rank) merges ranked lists without needing comparable raw scores.

BM25 fallback behavior:
- If the docstore has no nodes (common on first index without disk reload),
  falls back to vector-only retrieval to avoid the bm25s empty-corpus error.
"""

import logging

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever

from app.core.config import Settings
from app.index.index_state import get_bm25_retriever, set_bm25_retriever

logger = logging.getLogger(__name__)


def _build_bm25_retriever(
    index: VectorStoreIndex,
    similarity_top_k: int,
    repo_id: str,
) -> BM25Retriever | None:
    """
    Build a BM25Retriever, preferring nodes from the index docstore.

    Returns None (with a warning) if the docstore is empty, so the caller
    can gracefully degrade to vector-only retrieval.
    """
    docstore = index.docstore
    all_nodes = list(docstore.docs.values()) if docstore and hasattr(docstore, "docs") else []

    if not all_nodes:
        # Docstore not populated yet (e.g., in-memory index without disk persist load).
        # Fall back to vector-only retrieval for this request.
        logger.warning(
            "BM25 docstore is empty for repo '%s'; using vector-only retrieval. "
            "This resolves automatically after restarting the server (index loaded from disk).",
            repo_id,
        )
        return None

    try:
        return BM25Retriever.from_defaults(
            nodes=all_nodes,
            similarity_top_k=similarity_top_k,
        )
    except Exception:
        logger.warning(
            "Failed to build BM25 retriever for repo '%s'; using vector-only retrieval.",
            repo_id,
            exc_info=True,
        )
        return None


def create_hybrid_retriever(
    index: VectorStoreIndex,
    settings: Settings,
    *,
    top_k: int,
    repo_id: str,
) -> tuple[QueryFusionRetriever, str]:
    """
    Build (or reuse) BM25 + vector retrievers and fuse with reciprocal rank reranking.

    The BM25 retriever is cached per repo_id because building it from the
    docstore is expensive.  If BM25 is unavailable (empty docstore), falls
    back gracefully to vector-only retrieval.
    """
    vector_retriever = index.as_retriever(similarity_top_k=settings.vector_top_k)

    bm25_retriever = get_bm25_retriever(repo_id)
    if bm25_retriever is None:
        bm25_retriever = _build_bm25_retriever(index, settings.bm25_top_k, repo_id)
        if bm25_retriever is not None:
            set_bm25_retriever(repo_id, bm25_retriever)

    retrievers = [vector_retriever]
    if bm25_retriever is not None:
        retrievers.append(bm25_retriever)

    mode = "hybrid (vector + bm25)" if len(retrievers) > 1 else "vector"

    retriever = QueryFusionRetriever(
        retrievers,
        similarity_top_k=top_k,
        num_queries=1,   # no query expansion — keeps responses predictable
        mode=settings.hybrid_fusion_mode,
        use_async=False,
    )
    return retriever, mode
