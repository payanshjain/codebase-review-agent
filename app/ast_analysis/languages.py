"""
Language registry — maps file extensions to tree-sitter Language objects and
provides properly constructed Parser instances.

API note (tree-sitter 0.25.x):
    Use `tree_sitter.Parser(language)` with a Language from tree_sitter_language_pack.
    This returns `tree_sitter.Tree` / `tree_sitter.Node` objects that are compatible
    with `tree_sitter.QueryCursor`.  The `get_parser()` shortcut from the pack returns
    a different Parser subclass whose nodes are incompatible with QueryCursor.
"""

from __future__ import annotations

from functools import lru_cache


# ── Extension → tree-sitter language name ─────────────────────────

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}

AST_PARSEABLE_EXTENSIONS: frozenset[str] = frozenset(LANGUAGE_MAP.keys())

# Extensions that should always use text-based (SentenceSplitter) chunking.
TEXT_ONLY_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html", ".css",
})


def is_ast_parseable(extension: str) -> bool:
    """Return True if the file extension can be parsed with tree-sitter."""
    return extension.lower() in AST_PARSEABLE_EXTENSIONS


def get_language_name(extension: str) -> str | None:
    """Return the tree-sitter language name for a file extension, or None."""
    return LANGUAGE_MAP.get(extension.lower())


# ── Language and Parser factory ───────────────────────────────────


@lru_cache(maxsize=16)
def get_ts_language(language: str):
    """
    Return a cached tree_sitter.Language for the given language name.

    Uses tree_sitter_language_pack.get_language() which returns a
    proper tree_sitter.Language object (not the pack's own subclass).
    """
    from tree_sitter_language_pack import get_language
    return get_language(language)


@lru_cache(maxsize=16)
def get_parser(language: str):
    """
    Return a cached tree_sitter.Parser for the given language name.

    Constructed via `tree_sitter.Parser(Language)` so that parse() returns
    tree_sitter.Tree / tree_sitter.Node objects compatible with QueryCursor.
    """
    from tree_sitter import Parser
    lang = get_ts_language(language)
    return Parser(lang)
