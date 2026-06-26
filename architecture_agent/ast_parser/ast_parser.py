"""
AST parser for the Architecture Agent.

Wraps the existing tree-sitter AST infrastructure to extract per-file:
- Import statements (resolved to relative file paths where possible)
- Function/class definitions
- Function call sites (caller → callee edges)
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from app.ast_analysis.extractor import extract_symbols, extract_imports, CodeSymbol
from app.ast_analysis.languages import get_language_name, get_parser, get_ts_language

logger = logging.getLogger(__name__)


@dataclass
class FileAST:
    """Structured AST extraction result for a single source file."""

    rel_path: str
    language: str | None
    loc: int = 0
    imports: list[str] = field(default_factory=list)          # raw import strings
    resolved_imports: list[str] = field(default_factory=list)  # resolved to relative file paths
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    call_sites: list[tuple[str, str]] = field(default_factory=list)  # (caller_fn, callee_fn)


class ASTParser:
    """Extracts structured AST metadata from all code files in a repository."""

    def parse_all(self, code_files: list[Path], repo_root: Path) -> list[FileAST]:
        """Parse all code files and produce per-file AST metadata."""
        results: list[FileAST] = []
        # Build a lookup map for import resolution
        file_stems = self._build_file_stem_map(code_files, repo_root)

        for file_path in code_files:
            try:
                result = self._parse_single(file_path, repo_root, file_stems)
                if result:
                    results.append(result)
            except Exception:
                logger.debug("AST parse failed for: %s", file_path, exc_info=True)

        return results

    def _parse_single(self, file_path: Path, repo_root: Path, file_stems: dict[str, str]) -> FileAST | None:
        """Parse a single file."""
        ext = file_path.suffix.lower()
        lang = get_language_name(ext)
        if not lang:
            return None

        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        loc = len(content.splitlines())

        # Extract imports
        raw_imports = extract_imports(content, lang)

        # Resolve imports to file paths
        resolved = self._resolve_imports(raw_imports, lang, file_stems)

        # Extract symbols (classes, functions)
        symbols = extract_symbols(content, lang)
        classes = [s.name for s in symbols if s.symbol_type == "class"]
        functions = [s.name for s in symbols if s.symbol_type in ("function", "method")]

        # Extract call sites
        call_sites = self._extract_call_sites(content, lang, symbols, rel_path)

        return FileAST(
            rel_path=rel_path,
            language=lang,
            loc=loc,
            imports=raw_imports,
            resolved_imports=resolved,
            classes=classes,
            functions=functions,
            call_sites=call_sites,
        )

    def _build_file_stem_map(self, code_files: list[Path], repo_root: Path) -> dict[str, str]:
        """
        Build a map from module-style names to relative file paths.
        e.g., "app.core.config" -> "app/core/config.py"
        """
        stem_map: dict[str, str] = {}
        for fp in code_files:
            rel = str(fp.relative_to(repo_root)).replace("\\", "/")
            # Strip extension for module name
            no_ext = rel.rsplit(".", 1)[0] if "." in rel else rel
            module_name = no_ext.replace("/", ".")
            stem_map[module_name] = rel
            # Also add the last component for short imports
            parts = module_name.split(".")
            if len(parts) > 1:
                stem_map[parts[-1]] = rel
        return stem_map

    def _resolve_imports(self, raw_imports: list[str], lang: str, file_stems: dict[str, str]) -> list[str]:
        """Attempt to resolve import statements to relative file paths."""
        resolved: list[str] = []

        for imp in raw_imports:
            if lang == "python":
                # Handle "from X import Y" and "import X"
                match = re.match(r"(?:from\s+)?([\w.]+)\s*(?:import)?", imp)
                if match:
                    module = match.group(1)
                    if module in file_stems:
                        resolved.append(file_stems[module])
                    else:
                        # Try progressively shorter prefixes
                        parts = module.split(".")
                        for i in range(len(parts), 0, -1):
                            sub = ".".join(parts[:i])
                            if sub in file_stems:
                                resolved.append(file_stems[sub])
                                break
            elif lang in ("javascript", "typescript"):
                # Handle import ... from "./module"
                match = re.search(r"""(?:from|require)\s*\(?\s*['"](\.{1,2}/[^'"]+)""", imp)
                if match:
                    target = match.group(1)
                    # Normalize by removing leading ./ and adding extensions
                    clean = target.lstrip("./")
                    for ext in ("", ".js", ".ts", ".jsx", ".tsx"):
                        candidate = clean + ext
                        for key, val in file_stems.items():
                            if val.endswith(candidate):
                                resolved.append(val)
                                break

        return resolved

    def _extract_call_sites(
        self, content: str, lang: str, symbols: list[CodeSymbol], file_path: str
    ) -> list[tuple[str, str]]:
        """
        Extract function call sites using tree-sitter call_expression nodes.
        Returns list of (caller_function, callee_name) tuples.
        """
        call_sites: list[tuple[str, str]] = []

        try:
            parser = get_parser(lang)
            source_bytes = content.encode("utf-8")
            tree = parser.parse(source_bytes)
            root = tree.root_node

            # Collect all call expressions via recursive walk
            call_nodes = []
            self._walk_for_calls(root, call_nodes)

            # Build line -> enclosing function map
            line_to_fn = self._build_line_function_map(symbols)

            for node in call_nodes:
                callee_name = self._extract_callee_name(node, source_bytes)
                if not callee_name or callee_name.startswith("_") and callee_name.startswith("__"):
                    continue
                # Skip common builtins
                if callee_name in ("print", "len", "range", "str", "int", "float", "list", "dict",
                                   "set", "tuple", "type", "isinstance", "hasattr", "getattr",
                                   "super", "enumerate", "zip", "map", "filter", "sorted",
                                   "open", "any", "all", "min", "max", "abs", "round"):
                    continue

                line = node.start_point[0] + 1
                caller = line_to_fn.get(line, f"<module:{file_path}>")
                call_sites.append((caller, callee_name))

        except Exception:
            logger.debug("Call extraction failed for %s", file_path, exc_info=True)

        return call_sites

    def _walk_for_calls(self, node, results: list) -> None:
        """Recursively walk the tree to find call_expression nodes."""
        if node.type == "call":  # Python
            results.append(node)
        elif node.type == "call_expression":  # JS/TS/Java/Go
            results.append(node)
        for child in node.children:
            self._walk_for_calls(child, results)

    def _extract_callee_name(self, call_node, source_bytes: bytes) -> str | None:
        """Extract the function name being called from a call node."""
        # For Python: call node has function child
        fn_node = call_node.child_by_field_name("function")
        if fn_node is None:
            # JS/TS: might be named "function" or first child
            for child in call_node.children:
                if child.type in ("identifier", "member_expression", "attribute",
                                  "property_identifier", "field_expression"):
                    fn_node = child
                    break
        if fn_node is None:
            return None

        text = fn_node.text
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")

        # For attribute/member access like obj.method, take the last part
        if "." in text:
            return text.split(".")[-1]
        return text

    def _build_line_function_map(self, symbols: list[CodeSymbol]) -> dict[int, str]:
        """Map line numbers to enclosing function/method names."""
        line_map: dict[int, str] = {}
        for sym in symbols:
            if sym.symbol_type in ("function", "method"):
                name = f"{sym.parent_class}.{sym.name}" if sym.parent_class else sym.name
                for line in range(sym.line_start, sym.line_end + 1):
                    line_map[line] = name
        return line_map
