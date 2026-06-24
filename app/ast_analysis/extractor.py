"""
Core AST extraction engine — turns source code into structured CodeSymbol lists.

Uses tree-sitter 0.25.x API:
  - Parser(Language) constructor
  - parser.parse(bytes)
  - node.type, node.children, node.text, node.start_point (tuple), node.parent
  - QueryCursor for running queries (dict[str, list[Node]] from cursor.captures())

Design choices:
- Methods are detected by walking up the node's parent chain looking for
  class_definition / class_declaration nodes.
- Class chunks contain a skeleton (signature + attribute lines + method stubs),
  NOT the full method bodies — avoids duplication since methods become their
  own chunks.
- Module-level header captures imports and top-level code outside definitions.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field

from app.ast_analysis.languages import get_parser, get_ts_language
from app.ast_analysis.queries import get_query_for_language

logger = logging.getLogger(__name__)


@dataclass
class CodeSymbol:
    """A single semantic unit extracted from source code via AST parsing."""

    name: str
    symbol_type: str       # "function", "class", "method", "module_header"
    signature: str         # first line(s) of the definition
    body: str              # full source text of the symbol
    docstring: str | None = None
    line_start: int = 0
    line_end: int = 0
    parent_class: str | None = None   # enclosing class (for methods)
    decorators: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)  # method names (for classes)


# ── Public entry points ──────────────────────────────────────────


def extract_symbols(source: str, language: str) -> list[CodeSymbol]:
    """
    Parse *source* with tree-sitter and extract all semantic code symbols.

    Returns a list of CodeSymbol objects for functions, classes, methods, and
    a module_header (imports + top-level code outside definitions).
    """
    query_text = get_query_for_language(language)
    if query_text is None:
        logger.warning("No AST query defined for language '%s'; skipping.", language)
        return []

    try:
        parser = get_parser(language)
        lang_obj = get_ts_language(language)
    except Exception:
        logger.warning("Could not load parser for '%s'.", language, exc_info=True)
        return []

    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    # Run the tree-sitter query via QueryCursor.
    try:
        from tree_sitter import QueryCursor
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            query = lang_obj.query(query_text)
        cursor = QueryCursor(query)
        captures = cursor.captures(root)
        # captures → dict[str, list[Node]]
    except Exception:
        logger.warning("Query execution failed for '%s'.", language, exc_info=True)
        return []

    definition_functions: list = captures.get("definition.function", [])
    name_functions: list     = captures.get("name.function", [])
    definition_classes: list = captures.get("definition.class", [])
    name_classes: list       = captures.get("name.class", [])
    import_nodes: list       = captures.get("import", [])

    symbols: list[CodeSymbol] = []
    seen_ranges: set[tuple[int, int]] = set()

    # ── Extract classes ──────────────────────────────────────────

    for cls_node, cls_name_node in zip(definition_classes, name_classes):
        cls_name = _node_text(cls_name_node, source_bytes)
        cls_sig  = _extract_signature(cls_node, source_bytes)
        cls_doc  = _extract_docstring(cls_node, source_bytes, language)

        # Find method names belonging to this class.
        method_names: list[str] = []
        for fn_node, fn_name_node in zip(definition_functions, name_functions):
            if _is_child_of(fn_node, cls_node):
                method_names.append(_node_text(fn_name_node, source_bytes))

        skeleton = _build_class_skeleton(cls_node, source_bytes, language, cls_sig, cls_doc)

        symbols.append(CodeSymbol(
            name=cls_name,
            symbol_type="class",
            signature=cls_sig,
            body=skeleton,
            docstring=cls_doc,
            line_start=cls_node.start_point[0] + 1,
            line_end=cls_node.end_point[0] + 1,
            decorators=_extract_decorators(cls_node, source_bytes, language),
            children=method_names,
        ))
        seen_ranges.add((cls_node.start_byte, cls_node.end_byte))

    # ── Extract functions and methods ────────────────────────────

    for fn_node, fn_name_node in zip(definition_functions, name_functions):
        fn_name = _node_text(fn_name_node, source_bytes)
        fn_body = _node_text(fn_node, source_bytes)
        fn_sig  = _extract_signature(fn_node, source_bytes)
        fn_doc  = _extract_docstring(fn_node, source_bytes, language)
        parent_cls = _find_parent_class(fn_node, source_bytes)

        symbols.append(CodeSymbol(
            name=fn_name,
            symbol_type="method" if parent_cls else "function",
            signature=fn_sig,
            body=fn_body,
            docstring=fn_doc,
            line_start=fn_node.start_point[0] + 1,
            line_end=fn_node.end_point[0] + 1,
            parent_class=parent_cls,
            decorators=_extract_decorators(fn_node, source_bytes, language),
        ))
        seen_ranges.add((fn_node.start_byte, fn_node.end_byte))

    # ── Module header (imports + top-level code) ─────────────────

    module_header = _build_module_header(root, source_bytes, seen_ranges)
    if module_header.strip():
        symbols.insert(0, CodeSymbol(
            name="<module>",
            symbol_type="module_header",
            signature="",
            body=module_header,
            line_start=1,
            line_end=module_header.count("\n") + 1,
        ))

    return symbols


def extract_imports(source: str, language: str) -> list[str]:
    """Return import statements from *source* as a list of strings."""
    query_text = get_query_for_language(language)
    if query_text is None:
        return []

    try:
        parser = get_parser(language)
        lang_obj = get_ts_language(language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        from tree_sitter import QueryCursor
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            query = lang_obj.query(query_text)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
    except Exception:
        return []

    import_nodes = captures.get("import", [])
    return [_node_text(node, source_bytes) for node in import_nodes]


# ── Private helpers ───────────────────────────────────────────────


def _node_text(node, source_bytes: bytes) -> str:
    """Extract the source text for a tree-sitter node (0.25.x: node.text is bytes)."""
    raw = node.text
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    # Fallback: slice from source bytes
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_signature(node, source_bytes: bytes) -> str:
    """Extract the first line of a definition as its signature."""
    text = _node_text(node, source_bytes)
    first_line = text.split("\n")[0].strip()
    return first_line


def _extract_docstring(node, source_bytes: bytes, language: str) -> str | None:
    """
    Extract docstring from a function/class node.

    For Python: looks for the first expression_statement containing a string
    in the body block.  For JS/TS: looks for preceding JSDoc comment.
    """
    if language == "python":
        body_node = node.child_by_field_name("body")
        if body_node is None:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw = _node_text(sub, source_bytes)
                        return raw.strip('"\' \n').split('"""')[0].split("'''")[0].strip()
                break  # docstring must be first statement
    elif language in ("javascript", "typescript"):
        prev = node.prev_sibling
        if prev and prev.type == "comment":
            return _node_text(prev, source_bytes).strip("/* \n")
    return None


def _extract_decorators(node, source_bytes: bytes, language: str) -> list[str]:
    """Extract decorator names for a function/class (Python)."""
    decorators: list[str] = []
    if language == "python":
        prev = node.prev_sibling
        while prev and prev.type == "decorator":
            text = _node_text(prev, source_bytes).strip()
            decorators.insert(0, text)
            prev = prev.prev_sibling
    return decorators


def _is_child_of(child_node, parent_node) -> bool:
    """Check if *child_node* is a descendant of *parent_node* via byte ranges."""
    return (
        child_node.start_byte >= parent_node.start_byte
        and child_node.end_byte <= parent_node.end_byte
        and child_node.id != parent_node.id
    )


def _find_parent_class(fn_node, source_bytes: bytes) -> str | None:
    """Walk up the parent chain to find an enclosing class name."""
    current = fn_node.parent
    while current is not None:
        if current.type in (
            "class_definition", "class_declaration",
            "impl_item",   # Rust
        ):
            name_node = current.child_by_field_name("name")
            if name_node:
                return _node_text(name_node, source_bytes)
        current = current.parent
    return None


def _build_class_skeleton(
    cls_node,
    source_bytes: bytes,
    language: str,
    signature: str,
    docstring: str | None,
) -> str:
    """
    Build a class skeleton: signature + docstring + attribute assignments +
    method stubs (signature only, no bodies).
    """
    lines: list[str] = [signature]

    if docstring and language == "python":
        lines.append(f'    """{docstring[:120]}"""')

    body_node = cls_node.child_by_field_name("body")
    if body_node is None:
        return "\n".join(lines)

    for child in body_node.children:
        if child.type in ("expression_statement", "assignment"):
            text = _node_text(child, source_bytes).strip()
            if text and not text.startswith(('"""', "'''")):
                lines.append(f"    {text}")
        elif child.type in ("function_definition", "method_definition", "method_declaration"):
            method_sig = _extract_signature(child, source_bytes)
            lines.append(f"    {method_sig} ...")

    return "\n".join(lines)


def _build_module_header(
    root_node,
    source_bytes: bytes,
    seen_ranges: set[tuple[int, int]],
) -> str:
    """
    Collect module-level code that is not inside any function/class definition.
    """
    IMPORT_TYPES = {
        "import_statement", "import_from_statement",   # Python
        "import_declaration",                           # Java
        "use_declaration",                              # Rust
    }
    INCLUDE_TYPES = IMPORT_TYPES | {
        "expression_statement", "comment",
        "package_declaration", "module",
    }

    parts: list[str] = []
    for child in root_node.children:
        is_captured = any(
            child.start_byte >= s and child.end_byte <= e
            for s, e in seen_ranges
        )
        if is_captured:
            continue
        if child.type in INCLUDE_TYPES:
            parts.append(_node_text(child, source_bytes))
        elif child.type in ("assignment", "augmented_assignment"):
            parts.append(_node_text(child, source_bytes))

    return "\n".join(parts)
