"""
Retrieve the most relevant code/doc chunks for a user question.

Supports multi-repository queries with hybrid (vector + BM25) retrieval.
"""

from llama_index.core.schema import NodeWithScore

from app.core.config import Settings
from app.core.providers import configure_embedding_model
from app.index.load_index import get_or_load_index
from app.repositories.metadata import RepositoryMetadataStore
from app.retrieval.hybrid_retriever import create_hybrid_retriever


def _resolve_repo_ids(settings: Settings, repo_ids: list[str] | None) -> list[str]:
    """Return indexed repo IDs to query, validating explicit filters."""
    store = RepositoryMetadataStore(settings.repos_metadata_file)

    if repo_ids is None:
        return [
            rid for rid, rec in store.load_all().items() if rec.status == "indexed"
        ]

    missing: list[str] = []
    not_indexed: list[str] = []
    resolved: list[str] = []

    for rid in repo_ids:
        record = store.get(rid)
        if record is None:
            missing.append(rid)
        elif record.status != "indexed":
            not_indexed.append(rid)
        else:
            resolved.append(rid)

    if missing:
        raise ValueError(
            f"Unknown repo_id(s): {', '.join(missing)}. "
            "Use GET /repositories to list indexed repos."
        )
    if not_indexed:
        raise ValueError(
            f"Repo(s) not indexed yet: {', '.join(not_indexed)}. "
            "Call POST /index or POST /repositories/index first."
        )
    return resolved


def retrieve_relevant_chunks(
    question: str,
    settings: Settings,
    *,
    top_k: int | None = None,
    repo_ids: list[str] | None = None,
) -> tuple[list[NodeWithScore], str]:
    """
    Hybrid search across one or more repositories.

    Returns (scored_nodes, retrieval_mode) where retrieval_mode reflects
    whether BM25 was available or vector-only fallback was used.
    """
    k = top_k if top_k is not None else settings.retrieval_top_k
    configure_embedding_model(settings)

    target_repo_ids = _resolve_repo_ids(settings, repo_ids)
    if not target_repo_ids:
        raise ValueError(
            "No indexed repositories found. "
            "Call POST /repositories/index or POST /index first."
        )

    all_scored: list[NodeWithScore] = []
    modes: set[str] = set()

    for rid in target_repo_ids:
        index = get_or_load_index(settings, rid)
        retriever, mode = create_hybrid_retriever(index, settings, top_k=k, repo_id=rid)
        modes.add(mode)
        nodes = retriever.retrieve(question)

        for n in nodes:
            n.node.metadata["repo_id"] = rid

        all_scored.extend(nodes)

    all_scored.sort(key=lambda n: n.score if n.score is not None else 0.0, reverse=True)

    if modes == {"hybrid (vector + bm25)"}:
        retrieval_mode = "hybrid (vector + bm25)"
    elif modes == {"vector"}:
        retrieval_mode = "vector"
    else:
        retrieval_mode = "hybrid (vector + bm25, partial)"

    return all_scored[:k], retrieval_mode
