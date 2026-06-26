"""
Metadata extractor implementation.

Analyzes folder structure, classes, functions, HTTP API endpoints,
and database ORM models/tables across scanned repository files.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.ast_analysis.extractor import extract_symbols
from app.ast_analysis.languages import get_language_name
from documentation_agent.repository_parser.parser import ParsedRepository
from documentation_agent.schemas import (
    ApiRouteMetadata,
    ClassMetadata,
    DatabaseModelMetadata,
    FunctionMetadata,
    RepositoryMetadata,
)

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """
    Extracts deep semantic metadata from a ParsedRepository.
    """

    def extract(self, parsed: ParsedRepository) -> RepositoryMetadata:
        """
        Run AST extraction and regex scanning across repository code files.
        """
        logger.info("Extracting deep metadata for repo: %s", parsed.repo_name)
        folder_tree = self._build_folder_tree(parsed.local_path, parsed.all_files)

        classes: list[ClassMetadata] = []
        functions: list[FunctionMetadata] = []
        api_endpoints: list[ApiRouteMetadata] = []
        databases: list[DatabaseModelMetadata] = []
        languages: set[str] = set()

        for file_path in parsed.code_files:
            rel_path = str(file_path.relative_to(parsed.local_path)).replace("\\", "/")
            ext = file_path.suffix.lower()
            lang = get_language_name(ext)
            if lang:
                languages.add(lang)

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # AST symbol extraction
            if lang:
                try:
                    symbols = extract_symbols(content, lang)
                    for sym in symbols:
                        if sym.symbol_type == "class":
                            classes.append(
                                ClassMetadata(
                                    name=sym.name,
                                    file_path=rel_path,
                                    line_start=sym.line_start,
                                    line_end=sym.line_end,
                                    docstring=sym.docstring,
                                    methods=sym.children,
                                )
                            )
                        elif sym.symbol_type in ("function", "method"):
                            functions.append(
                                FunctionMetadata(
                                    name=sym.name,
                                    file_path=rel_path,
                                    line_start=sym.line_start,
                                    line_end=sym.line_end,
                                    signature=sym.signature,
                                    docstring=sym.docstring,
                                    decorators=sym.decorators,
                                )
                            )
                except Exception:
                    logger.debug("AST extraction failed for: %s", rel_path)

            # API Route detection via regex
            routes = self._scan_api_routes(content, rel_path)
            api_endpoints.extend(routes)

            # Database model detection
            db_models = self._scan_database_models(content, rel_path)
            databases.extend(db_models)

        # Also scan dedicated DB SQL files
        for db_file in parsed.db_files:
            if db_file not in parsed.code_files:
                rel_path = str(db_file.relative_to(parsed.local_path)).replace("\\", "/")
                try:
                    content = db_file.read_text(encoding="utf-8", errors="replace")
                    db_models = self._scan_database_models(content, rel_path)
                    databases.extend(db_models)
                except Exception:
                    pass

        config_rel_paths = [str(f.relative_to(parsed.local_path)).replace("\\", "/") for f in parsed.config_files]

        return RepositoryMetadata(
            repo_id=parsed.repo_id,
            repo_name=parsed.repo_name,
            local_path=str(parsed.local_path),
            folder_structure=folder_tree,
            files_scanned=len(parsed.all_files),
            languages=sorted(languages),
            classes=classes,
            functions=functions,
            api_endpoints=api_endpoints,
            configuration_files=config_rel_paths,
            dependencies=parsed.dependencies,
            databases=databases,
        )

    def _build_folder_tree(self, root: Path, files: list[Path]) -> str:
        """Create a clean ASCII folder tree string."""
        tree_lines: list[str] = [f"{root.name}/"]
        dirs: set[str] = set()

        for file_path in files:
            rel = file_path.relative_to(root)
            parts = rel.parts
            for i in range(len(parts) - 1):
                sub_dir = "/".join(parts[: i + 1])
                if sub_dir not in dirs:
                    dirs.add(sub_dir)
                    indent = "    " * i
                    tree_lines.append(f"{indent}├── {parts[i]}/")
            indent = "    " * (len(parts) - 1)
            tree_lines.append(f"{indent}└── {parts[-1]}")

        return "\n".join(tree_lines[:200])  # Cap at 200 lines

    def _scan_api_routes(self, content: str, file_path: str) -> list[ApiRouteMetadata]:
        """Scan source code for HTTP route decorators and method definitions."""
        routes: list[ApiRouteMetadata] = []
        lines = content.splitlines()

        # Matches Python FastAPI/Flask decorators like @app.get("/path"), @router.post("/items")
        py_route_re = re.compile(r"@(app|router|api|bp)\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']")

        for i, line in enumerate(lines):
            match = py_route_re.search(line)
            if match:
                method = match.group(2).upper()
                path = match.group(3)
                fn_name = "handler"
                docstring = None

                # Look ahead for def function_name(...)
                for j in range(i + 1, min(i + 5, len(lines))):
                    def_match = re.search(r"async\s+def\s+([a-zA-Z0-9_]+)|def\s+([a-zA-Z0-9_]+)", lines[j])
                    if def_match:
                        fn_name = def_match.group(1) or def_match.group(2)
                        # Check docstring on next line
                        if j + 1 < len(lines) and ("\"\"\"" in lines[j + 1] or "'''" in lines[j + 1]):
                            docstring = lines[j + 1].strip(" \"'\t\r\n")
                        break

                routes.append(
                    ApiRouteMetadata(
                        method=method,
                        path=path,
                        function_name=fn_name,
                        file_path=file_path,
                        line=i + 1,
                        docstring=docstring,
                    )
                )

        return routes

    def _scan_database_models(self, content: str, file_path: str) -> list[DatabaseModelMetadata]:
        """Scan source code or SQL files for database entity models and tables."""
        models: list[DatabaseModelMetadata] = []
        lines = content.splitlines()

        # Matches class ModelName(Base): or class ModelName(models.Model):
        orm_class_re = re.compile(r"class\s+([a-zA-Z0-9_]+)\s*\(([^)]*Model[^)]*|[^)]*Base[^)]*|SQLModel)\)\s*:")
        # Matches SQL CREATE TABLE table_name
        sql_table_re = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)", re.IGNORECASE)

        current_model: DatabaseModelMetadata | None = None

        for i, line in enumerate(lines):
            orm_match = orm_class_re.search(line)
            sql_match = sql_table_re.search(line)

            if orm_match or sql_match:
                if current_model:
                    models.append(current_model)
                name = orm_match.group(1) if orm_match else sql_match.group(1)
                current_model = DatabaseModelMetadata(name=name, file_path=file_path, line=i + 1)
            elif current_model:
                # Detect columns and relationships
                if "Column(" in line or "Field(" in line or re.search(r"^[a-zA-Z0-9_]+\s+[A-Z]+(?:[(, ]|$)", line.strip()):
                    col_name = line.strip().split("=")[0].split()[0].strip()
                    if col_name and col_name not in ("class", "def", "return", "pass", "__tablename__"):
                        current_model.columns.append(col_name)
                if "relationship(" in line or "ForeignKey(" in line or "REFERENCES" in line.upper():
                    rel_target = "ForeignKey/Relationship"
                    fk_match = re.search(r"(?:ForeignKey|REFERENCES)\s*\(\s*[\"']?([a-zA-Z0-9_.]+)", line, re.IGNORECASE)
                    if fk_match:
                        rel_target = fk_match.group(1)
                    current_model.relationships.append(rel_target)

        if current_model:
            models.append(current_model)

        return models
