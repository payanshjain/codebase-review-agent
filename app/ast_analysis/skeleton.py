"""
Repository skeleton generation — structural overview of an entire codebase.

Produces a lightweight map of files and their symbols (classes, functions,
methods) with signatures only (no bodies).  This gives the LLM and users
a bird's-eye view of repository structure before performing deep retrieval.

Used by the GET /repositories/{repo_id}/skeleton endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.ast_analysis.extractor import extract_symbols
from app.ast_analysis.languages import get_language_name, is_ast_parseable
from app.ingestion.file_loader import list_source_files, read_text_file
from app.ingestion.parser import LANGUAGE_BY_EXTENSION

logger = logging.getLogger(__name__)


@dataclass
class SymbolSummary:
    """Lightweight summary of one code symbol (no body text)."""

    symbol_type: str  # "function", "class", "method", "module_header"
    name: str
    line: int
    signature: str = ""
    parent_class: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass
class FileSkeletonEntry:
    """Structural summary of one file in the repository."""

    path: str
    language: str
    symbols: list[SymbolSummary] = field(default_factory=list)


def build_repository_skeleton(repo_path: Path) -> list[FileSkeletonEntry]:
    """
    Walk the repository and produce a structural skeleton for every
    AST-parseable file.

    Non-parseable files (markdown, JSON, etc.) are included with an
    empty symbols list so the skeleton still reflects the full file tree.
    """
    files = list_source_files(repo_path)
    entries: list[FileSkeletonEntry] = []

    for file_path in files:
        rel_path = str(file_path.relative_to(repo_path))
        extension = file_path.suffix.lower()
        lang_name = get_language_name(extension)
        display_lang = LANGUAGE_BY_EXTENSION.get(extension, lang_name or "unknown")

        if lang_name and is_ast_parseable(extension):
            source = read_text_file(file_path)
            if not source.strip():
                continue

            try:
                symbols = extract_symbols(source, lang_name)
            except Exception:
                logger.warning("AST extraction failed for %s", rel_path, exc_info=True)
                symbols = []

            symbol_summaries = [
                SymbolSummary(
                    symbol_type=s.symbol_type,
                    name=s.name,
                    line=s.line_start,
                    signature=s.signature,
                    parent_class=s.parent_class,
                    children=s.children,
                )
                for s in symbols
                if s.symbol_type != "module_header"  # skip headers in skeleton
            ]

            entries.append(FileSkeletonEntry(
                path=rel_path,
                language=display_lang,
                symbols=symbol_summaries,
            ))
        else:
            entries.append(FileSkeletonEntry(
                path=rel_path,
                language=display_lang,
            ))

    return entries
