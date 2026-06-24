"""
AST-aware chunking — turns CodeSymbols into embeddable chunks with context.

Each chunk represents a complete semantic unit (function, class skeleton,
method, or module header) with a structural context header prepended so the
LLM always knows where the code lives in the repository.

Oversized symbols (exceeding ast_max_chunk_tokens) are sub-split using the
existing SentenceSplitter while preserving the context header, so no chunk
ever loses its structural provenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import tiktoken

from app.ast_analysis.extractor import CodeSymbol

logger = logging.getLogger(__name__)

# Reuse the same tokeniser LlamaIndex uses for SentenceSplitter.
_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass
class ASTChunk:
    """A single embeddable chunk derived from an AST symbol."""

    text: str  # context header + symbol body
    metadata: dict = field(default_factory=dict)


def _count_tokens(text: str) -> int:
    """Count tokens using the same tokeniser as LlamaIndex."""
    return len(_ENCODER.encode(text))


def build_breadcrumb(
    repo_id: str | None,
    file_path: str,
    symbol: CodeSymbol,
) -> str:
    """
    Build a human-readable navigation breadcrumb.

    Example: repo:my_project → file:app/config.py → class:Settings → method:get_settings
    """
    parts: list[str] = []
    if repo_id:
        parts.append(f"repo:{repo_id}")
    parts.append(f"file:{file_path}")
    if symbol.parent_class:
        parts.append(f"class:{symbol.parent_class}")
    if symbol.symbol_type != "module_header":
        parts.append(f"{symbol.symbol_type}:{symbol.name}")
    return " → ".join(parts)


def _build_context_header(
    file_path: str,
    symbol: CodeSymbol,
    breadcrumb: str,
) -> str:
    """
    Create a concise context header prepended to every chunk.

    Example:
        # File: app/core/config.py | Class: Settings | Method: get_settings
        # Signature: def get_settings() -> Settings:
        # Breadcrumb: repo:my_project → file:app/core/config.py → class:Settings → method:get_settings
    """
    lines: list[str] = []

    # Location line.
    location_parts = [f"File: {file_path}"]
    if symbol.parent_class:
        location_parts.append(f"Class: {symbol.parent_class}")
    if symbol.symbol_type != "module_header":
        type_label = symbol.symbol_type.capitalize()
        location_parts.append(f"{type_label}: {symbol.name}")
    lines.append("# " + " | ".join(location_parts))

    # Signature line (for functions/methods/classes).
    if symbol.signature and symbol.symbol_type != "module_header":
        lines.append(f"# Signature: {symbol.signature}")

    # Breadcrumb line.
    lines.append(f"# Breadcrumb: {breadcrumb}")

    return "\n".join(lines)


def create_ast_chunks(
    symbols: list[CodeSymbol],
    file_path: str,
    language: str,
    repo_id: str | None = None,
    max_chunk_tokens: int = 1500,
    chunk_overlap: int = 128,
) -> list[ASTChunk]:
    """
    Convert extracted CodeSymbols into embeddable ASTChunks.

    Each symbol becomes one chunk unless it exceeds *max_chunk_tokens*, in
    which case it is sub-split using SentenceSplitter while keeping the
    context header on every sub-chunk.
    """
    chunks: list[ASTChunk] = []

    for symbol in symbols:
        breadcrumb = build_breadcrumb(repo_id, file_path, symbol)
        header = _build_context_header(file_path, symbol, breadcrumb)
        full_text = f"{header}\n\n{symbol.body}"

        metadata = {
            "file_path": file_path,
            "language": language,
            "symbol_type": symbol.symbol_type,
            "symbol_name": symbol.name,
            "signature": symbol.signature,
            "breadcrumb": breadcrumb,
            "line_start": symbol.line_start,
            "line_end": symbol.line_end,
            "chunk_strategy": "ast",
        }
        if symbol.parent_class:
            metadata["parent_class"] = symbol.parent_class
        if symbol.decorators:
            metadata["decorators"] = ", ".join(symbol.decorators)
        if symbol.children:
            metadata["children"] = ", ".join(symbol.children)
        if symbol.docstring:
            metadata["docstring"] = symbol.docstring[:200]  # truncate for metadata

        token_count = _count_tokens(full_text)

        if token_count <= max_chunk_tokens:
            # Single chunk — the common case.
            chunks.append(ASTChunk(text=full_text, metadata=metadata))
        else:
            # Oversized symbol — sub-split with SentenceSplitter.
            sub_chunks = _sub_split(
                symbol_body=symbol.body,
                header=header,
                metadata=metadata,
                max_tokens=max_chunk_tokens,
                overlap=chunk_overlap,
            )
            chunks.extend(sub_chunks)

    return chunks


def _sub_split(
    symbol_body: str,
    header: str,
    metadata: dict,
    max_tokens: int,
    overlap: int,
) -> list[ASTChunk]:
    """
    Split an oversized symbol body into sub-chunks, prepending the context
    header to each piece so structural context is never lost.
    """
    from llama_index.core.node_parser import SentenceSplitter

    header_tokens = _count_tokens(header) + 5  # +5 for separator newlines
    body_budget = max(max_tokens - header_tokens, 200)  # ensure minimum

    splitter = SentenceSplitter(
        chunk_size=body_budget,
        chunk_overlap=overlap,
        separator="\n",
    )

    # SentenceSplitter works on Documents, but we can use its split_text method.
    from llama_index.core import Document
    doc = Document(text=symbol_body)
    sub_nodes = splitter.get_nodes_from_documents([doc])

    sub_chunks: list[ASTChunk] = []
    for i, node in enumerate(sub_nodes):
        sub_text = getattr(node, "text", "") or ""
        full_text = f"{header}\n# Part {i + 1}/{len(sub_nodes)}\n\n{sub_text}"

        sub_meta = {
            **metadata,
            "chunk_part": i + 1,
            "chunk_total_parts": len(sub_nodes),
        }
        sub_chunks.append(ASTChunk(text=full_text, metadata=sub_meta))

    if not sub_chunks:
        # Fallback: if splitter produced nothing, emit the full body.
        sub_chunks.append(ASTChunk(
            text=f"{header}\n\n{symbol_body}",
            metadata=metadata,
        ))

    return sub_chunks
