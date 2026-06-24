"""
Core API routes — backward-compatible /index and /ask endpoints.

Updated for AST-based repository understanding:
- POST /index uses hybrid chunking (AST for code, text for non-code)
- POST /ask exposes AST metadata (symbol_type, breadcrumb) in SourceChunk
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.provider_errors import provider_error_response
from app.index.build_index import build_and_store_index
from app.ingestion.chunker import chunk_documents_hybrid
from app.ingestion.file_loader import resolve_repo_path
from app.ingestion.parser import parse_repository_to_documents
from app.qa.answer import generate_grounded_answer
from app.repositories.clone import generate_repo_id_from_path
from app.repositories.metadata import RepositoryMetadataStore, RepositoryRecord
from app.retrieval.retriever import retrieve_relevant_chunks
from app.schemas.ask_schema import AskRequest, AskResponse, SourceChunk
from app.schemas.index_schema import (
    ChunkPreview,
    IndexRequest,
    IndexResponse,
    IndexedFilePreview,
)

router = APIRouter()


@router.post("/index", response_model=IndexResponse)
def index_repository(request: IndexRequest) -> IndexResponse:
    """
    Full indexing pipeline:
    - validate repo path → read files → AST/text chunk → embed → persist in Chroma

    Uses hybrid chunking: tree-sitter AST for code files, SentenceSplitter
    for non-code files (markdown, JSON, config, etc.).
    """
    settings = get_settings()
    try:
        repo_path = resolve_repo_path(request.repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Generate a deterministic repo_id from the local path.
    repo_id = generate_repo_id_from_path(repo_path)

    documents = parse_repository_to_documents(repo_path)

    # Inject repo_id into every document's metadata for downstream attribution.
    for doc in documents:
        doc.metadata["repo_id"] = repo_id

    # Hybrid chunking: AST for code files, text-based for everything else.
    nodes = chunk_documents_hybrid(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        ast_max_chunk_tokens=settings.ast_max_chunk_tokens,
        repo_id=repo_id,
    )

    try:
        build_and_store_index(nodes, settings, repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        status, detail = provider_error_response(exc)
        if status == 502:
            detail = f"Embedding or vector store failed: {exc}"
        raise HTTPException(status_code=status, detail=detail) from exc

    # Collect language statistics.
    languages = sorted({
        str(doc.metadata.get("language", "unknown"))
        for doc in documents
        if doc.metadata.get("language") != "unknown"
    })

    # Register in the metadata store.
    store = RepositoryMetadataStore(settings.repos_metadata_file)
    record = RepositoryRecord(
        repo_id=repo_id,
        name=repo_path.name,
        url=None,
        local_path=str(repo_path),
        source="local",
    )
    record.mark_indexed(
        files_count=len(documents),
        chunks_count=len(nodes),
        languages=languages,
    )
    store.save(record)

    # Count AST vs text chunks.
    ast_count = sum(1 for n in nodes if n.metadata.get("chunk_strategy") == "ast")
    text_count = len(nodes) - ast_count

    previews = [
        IndexedFilePreview(
            file_path=str(doc.metadata.get("file_path", "")),
            language=str(doc.metadata.get("language", "unknown")),
            chars=int(doc.metadata.get("char_count", 0)),
        )
        for doc in documents[:10]
    ]

    chunk_previews: list[ChunkPreview] = []
    for i, node in enumerate(nodes[:5]):
        text = getattr(node, "text", "") or ""
        chunk_previews.append(
            ChunkPreview(
                file_path=str(node.metadata.get("file_path", "")),
                chunk_index=i,
                text_preview=text[:200] + ("..." if len(text) > 200 else ""),
                symbol_type=node.metadata.get("symbol_type"),
                breadcrumb=node.metadata.get("breadcrumb"),
                chunk_strategy=node.metadata.get("chunk_strategy", "text"),
            )
        )

    return IndexResponse(
        repo_id=repo_id,
        repo_path=str(repo_path),
        files_scanned=len(documents),
        documents_created=len(documents),
        chunks_created=len(nodes),
        vectors_stored=len(nodes),
        ast_chunks=ast_count,
        text_chunks=text_count,
        chunk_size_tokens=settings.chunk_size,
        chunk_overlap_tokens=settings.chunk_overlap,
        embed_model=settings.huggingface_embed_model,
        chroma_persist_dir=settings.chroma_persist_dir,
        chroma_collection_name=f"repo_{repo_id}",
        previews=previews,
        chunk_previews=chunk_previews,
    )


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    """
    RAG query endpoint:
    - hybrid retrieve (vector + BM25) from indexed chunks
    - send context + question to Groq
    - return grounded answer with cited source previews

    Supports optional repo_ids to search specific repositories.
    If omitted, all indexed repositories are queried.
    """
    settings = get_settings()
    top_k = request.top_k or settings.retrieval_top_k

    try:
        scored_nodes, retrieval_mode = retrieve_relevant_chunks(
            request.question,
            settings,
            top_k=top_k,
            repo_ids=request.repo_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        status, detail = provider_error_response(exc)
        if status == 502:
            detail = f"Retrieval failed: {exc}"
        raise HTTPException(status_code=status, detail=detail) from exc

    try:
        answer = generate_grounded_answer(request.question, scored_nodes, settings)
    except Exception as exc:
        status, detail = provider_error_response(exc)
        if status == 502:
            detail = f"Answer generation failed: {exc}"
        raise HTTPException(status_code=status, detail=detail) from exc

    sources: list[SourceChunk] = []
    for scored in scored_nodes:
        node = scored.node
        meta = node.metadata
        text = getattr(node, "text", "") or ""
        sources.append(
            SourceChunk(
                repo_id=str(meta.get("repo_id", "unknown")),
                file_path=str(meta.get("file_path", "unknown")),
                relevance_score=scored.score,
                text_preview=text[:300] + ("..." if len(text) > 300 else ""),
                symbol_type=meta.get("symbol_type"),
                symbol_name=meta.get("symbol_name"),
                breadcrumb=meta.get("breadcrumb"),
                chunk_strategy=meta.get("chunk_strategy", "text"),
            )
        )

    return AskResponse(
        question=request.question,
        answer=answer,
        sources=sources,
        retrieval_mode=retrieval_mode,
        retrieval_top_k=top_k,
        llm_model=settings.groq_model,
    )
