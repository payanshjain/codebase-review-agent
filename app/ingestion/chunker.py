"""
Hybrid chunking — routes documents to AST-based or text-based chunking.

This is the upgraded entry point for the ingestion pipeline.  It inspects
each document's metadata to determine the chunking strategy:

- **AST-parseable files** (Python, JS, TS, Java, Go, Rust) are parsed with
  tree-sitter and chunked at semantic boundaries (functions, classes, methods).
- **Non-parseable files** (markdown, JSON, YAML, config, etc.) fall back to
  the original SentenceSplitter text-based chunking.

The original chunk_documents() function is preserved for backward compatibility
but the new chunk_documents_hybrid() is the primary entry point.
"""

from __future__ import annotations

import logging

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode

from app.ast_analysis.chunker import create_ast_chunks
from app.ast_analysis.extractor import extract_symbols
from app.ast_analysis.languages import get_language_name

logger = logging.getLogger(__name__)


def build_sentence_splitter(*, chunk_size: int, chunk_overlap: int) -> SentenceSplitter:
    """
    Token-based splitting via tiktoken (LlamaIndex default for SentenceSplitter).

    chunk_size / chunk_overlap are in *tokens*, not characters — closer to LLM context limits.
    """
    return SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator=" ",
    )


def chunk_documents(
    documents: list[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
):
    """
    Legacy text-only chunking (preserved for backward compatibility).

    Turn one Document per file into many nodes (chunks), preserving file metadata on each node.
    """
    if not documents:
        return []

    splitter = build_sentence_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.get_nodes_from_documents(documents)


def chunk_documents_hybrid(
    documents: list[Document],
    *,
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
    ast_max_chunk_tokens: int = 1500,
    repo_id: str | None = None,
) -> list[TextNode]:
    """
    Hybrid chunking: AST-based for code files, text-based for everything else.

    This is the primary entry point for the upgraded ingestion pipeline.

    For AST-parseable files:
      1. Parse source with tree-sitter
      2. Extract semantic symbols (functions, classes, methods)
      3. Create chunks at symbol boundaries with rich structural metadata
      4. Sub-split oversized symbols using SentenceSplitter

    For non-parseable files:
      Use the original SentenceSplitter text-based chunking.

    Returns a flat list of TextNode objects compatible with LlamaIndex indexing.
    """
    if not documents:
        return []

    ast_docs: list[Document] = []
    text_docs: list[Document] = []

    for doc in documents:
        if doc.metadata.get("is_ast_parseable", False):
            ast_docs.append(doc)
        else:
            text_docs.append(doc)

    all_nodes: list[TextNode] = []
    # ── AST-based chunking ────────────────────────────────────────

    for doc in ast_docs:
        file_path = doc.metadata.get("file_path", "unknown")
        extension = doc.metadata.get("file_extension", "")
        language = get_language_name(extension)

        if language is None:
            # Fallback: shouldn't happen, but be safe.
            text_docs.append(doc)
            continue

        try:
            symbols = extract_symbols(doc.text, language)
        except Exception:
            logger.warning(
                "AST extraction failed for %s; falling back to text chunking.",
                file_path,
                exc_info=True,
            )
            text_docs.append(doc)
            continue

        if not symbols:
            # No symbols extracted — fall back to text chunking.
            logger.info("No AST symbols found in %s; using text chunking.", file_path)
            text_docs.append(doc)
            continue

        ast_chunks = create_ast_chunks(
            symbols,
            file_path=file_path,
            language=language,
            repo_id=repo_id,
            max_chunk_tokens=ast_max_chunk_tokens,
            chunk_overlap=chunk_overlap,
        )

        for chunk in ast_chunks:
            # Merge the AST chunk metadata with any existing document metadata
            # (e.g., repo_id injected upstream).
            merged_metadata = {**doc.metadata, **chunk.metadata}
            # Remove the raw is_ast_parseable flag — not needed in stored nodes.
            merged_metadata.pop("is_ast_parseable", None)

            node = TextNode(
                text=chunk.text,
                metadata=merged_metadata,
            )
            all_nodes.append(node)

        logger.info(
            "AST chunked %s: %d symbols → %d chunks",
            file_path, len(symbols), len(ast_chunks),
        )

    # ── Text-based chunking (fallback) ────────────────────────────

    if text_docs:
        splitter = build_sentence_splitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        text_nodes = splitter.get_nodes_from_documents(text_docs)

        # Tag text-based chunks with chunk_strategy metadata.
        for node in text_nodes:
            node.metadata["chunk_strategy"] = "text"

        all_nodes.extend(text_nodes)

        logger.info(
            "Text chunked %d files → %d chunks",
            len(text_docs), len(text_nodes),
        )

    return all_nodes
