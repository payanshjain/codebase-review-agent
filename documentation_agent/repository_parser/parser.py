"""
Repository parser implementation.

Resolves input path (local directory vs GitHub URL), clones remote repos,
scans folder tree, and identifies configuration and source files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.repositories.clone import (
    clone_repository,
    generate_repo_id,
    generate_repo_id_from_path,
)

logger = logging.getLogger(__name__)

IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "data", ".idea", ".vscode", "dist", "build"}
CONFIG_FILENAMES = {
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env",
    ".env.example",
    "tsconfig.json",
    "alembic.ini",
}


@dataclass
class ParsedRepository:
    """Raw structure and file lists scanned from a repository."""

    repo_id: str
    repo_name: str
    local_path: Path
    all_files: list[Path] = field(default_factory=list)
    code_files: list[Path] = field(default_factory=list)
    config_files: list[Path] = field(default_factory=list)
    db_files: list[Path] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class RepositoryParser:
    """
    Parses a target repository path or remote GitHub URL into structured lists.
    """

    def parse(self, repository_path: str) -> ParsedRepository:
        """
        Main parsing routine. Resolves local path or clones GitHub repo.
        """
        stripped = repository_path.strip()
        settings = get_settings()

        if stripped.startswith(("http://", "https://")):
            logger.info("Cloning remote GitHub repository: %s", stripped)
            repo_id = generate_repo_id(stripped)
            clone_dir = Path(settings.repos_clone_dir) / repo_id
            local_path = clone_repository(stripped, clone_dir)
            repo_name = stripped.rstrip("/").split("/")[-2:]
            repo_name_str = "/".join(repo_name).replace(".git", "")
        else:
            local_path = Path(stripped).resolve()
            if not local_path.exists():
                raise ValueError(f"Repository directory does not exist: {local_path}")
            repo_id = generate_repo_id_from_path(local_path)
            repo_name_str = local_path.name

        logger.info("Scanning repository files at: %s", local_path)
        all_files: list[Path] = []
        code_files: list[Path] = []
        config_files: list[Path] = []
        db_files: list[Path] = []

        code_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"}

        for path in local_path.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if path.is_file():
                all_files.append(path)
                ext = path.suffix.lower()
                name = path.name

                if ext in code_exts:
                    code_files.append(path)
                if name in CONFIG_FILENAMES or ext in {".toml", ".ini", ".yaml", ".yml"}:
                    config_files.append(path)

                # Check if file seems database related
                if ext == ".sql" or "models" in path.stem.lower() or "schema" in path.stem.lower() or "db" in path.stem.lower() or "database" in path.stem.lower():
                    db_files.append(path)

        dependencies = self._extract_dependencies(config_files)

        return ParsedRepository(
            repo_id=repo_id,
            repo_name=repo_name_str,
            local_path=local_path,
            all_files=all_files,
            code_files=code_files,
            config_files=config_files,
            db_files=db_files,
            dependencies=dependencies,
        )

    def _extract_dependencies(self, config_files: list[Path]) -> list[str]:
        """Extract dependency package names from standard config files."""
        deps: set[str] = set()

        for file_path in config_files:
            name = file_path.name
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if name == "requirements.txt":
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                            if pkg:
                                deps.add(pkg)
                elif name == "package.json":
                    data = json.loads(content)
                    for key in ("dependencies", "devDependencies"):
                        if key in data and isinstance(data[key], dict):
                            deps.update(data[key].keys())
            except Exception:
                logger.debug("Failed to parse dependency file: %s", file_path)

        return sorted(deps)
