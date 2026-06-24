"""
Repository management API — CRUD for multi-repository indexing + skeleton.

Endpoints:
    POST   /repositories/index              Clone a GitHub repo and index it
    GET    /repositories                    List all indexed repositories
    GET    /repositories/{repo_id}          Get detailed statistics for one repo
    GET    /repositories/{repo_id}/skeleton Get structural code map
    DELETE /repositories/{repo_id}          Remove repo data
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.ast_analysis.skeleton import build_repository_skeleton
from app.core.config import get_settings
from app.core.provider_errors import provider_error_response
from app.index.build_index import build_and_store_index
from app.index.chroma_store import delete_chroma_collection
from app.index.index_state import clear_repo_cache
from app.ingestion.chunker import chunk_documents_hybrid
from app.ingestion.parser import parse_repository_to_documents
from app.repositories.clone import clone_repository, generate_repo_id, parse_github_url
from app.repositories.metadata import RepositoryMetadataStore, RepositoryRecord
from app.schemas.repository_schema import (
    RepoDeleteResponse,
    RepoDetailResponse,
    RepoIndexRequest,
    RepoIndexResponse,
    RepoListResponse,
    RepoSummary,
)
from app.schemas.skeleton_schema import (
    FileSkeletonInfo,
    SkeletonResponse,
    SymbolInfo,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


# ── POST /repositories/index ──────────────────────────────────────


@router.post("/index", response_model=RepoIndexResponse)
def index_github_repository(request: RepoIndexRequest) -> RepoIndexResponse:
    """
    Clone a GitHub repository and run the full indexing pipeline.

    Uses hybrid chunking: tree-sitter AST for code files, SentenceSplitter
    for non-code files (markdown, JSON, config, etc.).

    If the repo is already indexed, returns existing stats unless ``force=True``.
    """
    settings = get_settings()
    store = RepositoryMetadataStore(settings.repos_metadata_file)

    # Validate URL and derive a deterministic repo_id.
    try:
        owner, repo_name = parse_github_url(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo_id = generate_repo_id(request.url)

    # Skip if already indexed (unless forced).
    existing = store.get(repo_id)
    if existing and existing.status == "indexed" and not request.force:
        return RepoIndexResponse(
            repo_id=repo_id,
            name=existing.name,
            url=request.url,
            status="already_indexed",
            files_scanned=existing.files_count,
            chunks_created=existing.chunks_count,
            vectors_stored=existing.chunks_count,
            languages=existing.languages,
            message="Repository is already indexed. Use force=true to re-index.",
        )

    # Clone the repository.
    clone_dir = Path(settings.repos_clone_dir) / repo_id
    try:
        # If force, remove old clone to get a fresh copy.
        if request.force and clone_dir.exists():
            shutil.rmtree(clone_dir)
        clone_repository(request.url, clone_dir)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Save metadata early (status=indexing) so partial state is visible.
    record = RepositoryRecord(
        repo_id=repo_id,
        name=f"{owner}/{repo_name}",
        url=request.url,
        local_path=str(clone_dir),
        source="github",
        status="indexing",
    )
    store.save(record)

    # Run the indexing pipeline: parse → hybrid chunk → embed → store.
    try:
        documents = parse_repository_to_documents(clone_dir)

        # Inject repo_id into every document's metadata for downstream attribution.
        for doc in documents:
            doc.metadata["repo_id"] = repo_id

        nodes = chunk_documents_hybrid(
            documents,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            ast_max_chunk_tokens=settings.ast_max_chunk_tokens,
            repo_id=repo_id,
        )

        build_and_store_index(nodes, settings, repo_id)
    except ValueError as exc:
        record.mark_error(str(exc))
        store.save(record)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        record.mark_error(str(exc))
        store.save(record)
        status, detail = provider_error_response(exc)
        raise HTTPException(status_code=status, detail=detail) from exc

    # Collect language statistics from parsed documents.
    languages = sorted({
        str(doc.metadata.get("language", "unknown"))
        for doc in documents
        if doc.metadata.get("language") != "unknown"
    })

    record.mark_indexed(
        files_count=len(documents),
        chunks_count=len(nodes),
        languages=languages,
    )
    store.save(record)

    return RepoIndexResponse(
        repo_id=repo_id,
        name=record.name,
        url=request.url,
        status="indexed",
        files_scanned=len(documents),
        chunks_created=len(nodes),
        vectors_stored=len(nodes),
        languages=languages,
        message="Repository indexed successfully.",
    )


# ── GET /repositories ─────────────────────────────────────────────


@router.get("", response_model=RepoListResponse)
def list_repositories() -> RepoListResponse:
    """Return all tracked repositories with summary info."""
    settings = get_settings()
    store = RepositoryMetadataStore(settings.repos_metadata_file)
    repos = store.load_all()

    summaries = [
        RepoSummary(
            repo_id=rec.repo_id,
            name=rec.name,
            url=rec.url,
            source=rec.source,
            status=rec.status,
            files_count=rec.files_count,
            chunks_count=rec.chunks_count,
            indexed_at=rec.indexed_at,
        )
        for rec in repos.values()
    ]
    return RepoListResponse(repositories=summaries, total=len(summaries))


# ── GET /repositories/{repo_id} ──────────────────────────────────


@router.get("/{repo_id}", response_model=RepoDetailResponse)
def get_repository(repo_id: str) -> RepoDetailResponse:
    """Return detailed statistics for a single repository."""
    settings = get_settings()
    store = RepositoryMetadataStore(settings.repos_metadata_file)
    record = store.get(repo_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    return RepoDetailResponse(
        repo_id=record.repo_id,
        name=record.name,
        url=record.url,
        local_path=record.local_path,
        source=record.source,
        status=record.status,
        files_count=record.files_count,
        chunks_count=record.chunks_count,
        languages=record.languages,
        indexed_at=record.indexed_at,
    )


# ── GET /repositories/{repo_id}/skeleton ──────────────────────────


@router.get("/{repo_id}/skeleton", response_model=SkeletonResponse)
def get_repository_skeleton(repo_id: str) -> SkeletonResponse:
    """
    Return a structural code map of the repository.

    Walks all AST-parseable files and extracts function/class/method
    signatures (without bodies) to give a bird's-eye view of the codebase.
    """
    settings = get_settings()
    store = RepositoryMetadataStore(settings.repos_metadata_file)
    record = store.get(repo_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    repo_path = Path(record.local_path)
    if not repo_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Repository directory not found at '{record.local_path}'. "
                   "Re-index the repository to regenerate.",
        )

    skeleton_entries = build_repository_skeleton(repo_path)

    files = [
        FileSkeletonInfo(
            path=entry.path,
            language=entry.language,
            symbols=[
                SymbolInfo(
                    symbol_type=s.symbol_type,
                    name=s.name,
                    line=s.line,
                    signature=s.signature,
                    parent_class=s.parent_class,
                    children=s.children,
                )
                for s in entry.symbols
            ],
        )
        for entry in skeleton_entries
    ]

    total_symbols = sum(len(f.symbols) for f in files)
    ast_parsed = sum(1 for f in files if f.symbols)

    return SkeletonResponse(
        repo_id=repo_id,
        total_files=len(files),
        total_symbols=total_symbols,
        ast_parsed_files=ast_parsed,
        files=files,
    )


# ── DELETE /repositories/{repo_id} ───────────────────────────────


@router.delete("/{repo_id}", response_model=RepoDeleteResponse)
def delete_repository(repo_id: str) -> RepoDeleteResponse:
    """
    Remove a repository and all its associated data:
    - Chroma collection (vectors)
    - Docstore directory (BM25 text)
    - Cloned repository files
    - Metadata record
    - In-memory caches
    """
    settings = get_settings()
    store = RepositoryMetadataStore(settings.repos_metadata_file)
    record = store.get(repo_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    # 1. Remove Chroma collection.
    delete_chroma_collection(settings, repo_id)

    # 2. Remove docstore directory.
    storage_dir = Path(settings.storage_persist_dir) / repo_id
    if storage_dir.exists():
        shutil.rmtree(storage_dir)

    # 3. Remove cloned repo (only for GitHub-sourced repos).
    if record.source == "github":
        clone_dir = Path(settings.repos_clone_dir) / repo_id
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

    # 4. Clear in-memory caches.
    clear_repo_cache(repo_id)

    # 5. Remove metadata record.
    store.delete(repo_id)

    return RepoDeleteResponse(
        repo_id=repo_id,
        message=f"Repository '{record.name}' and all associated data have been removed.",
    )
