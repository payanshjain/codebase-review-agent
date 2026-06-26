"""
Repository parser for the Architecture Agent.

Scans local or cloned repository and produces a structured ParsedRepo
with files grouped by language, detected entry points, package managers,
and configuration artifacts.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ast_analysis.languages import get_language_name
from app.repositories.clone import (
    clone_repository,
    generate_repo_id,
    generate_repo_id_from_path,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

IGNORE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".idea", ".vscode", "dist", "build", ".tox", ".mypy_cache",
    ".pytest_cache", "egg-info",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java",
    ".go", ".rs", ".cpp", ".c", ".h", ".rb", ".php",
}

CONFIG_FILENAMES = {
    "requirements.txt", "package.json", "pyproject.toml", "setup.py",
    "setup.cfg", "Cargo.toml", "go.mod", "Gemfile", "composer.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env", ".env.example", "tsconfig.json", "alembic.ini",
    "Makefile", "Procfile", ".github",
}

ENTRY_POINT_PATTERNS = [
    (re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']'), "main_guard"),
    (re.compile(r'app\s*=\s*FastAPI\s*\('), "fastapi_app"),
    (re.compile(r'app\s*=\s*Flask\s*\('), "flask_app"),
    (re.compile(r'create_app\s*\('), "factory_app"),
    (re.compile(r'express\s*\(\s*\)'), "express_app"),
    (re.compile(r'def\s+main\s*\('), "main_function"),
    (re.compile(r'func\s+main\s*\('), "main_function"),
    (re.compile(r'public\s+static\s+void\s+main'), "java_main"),
    (re.compile(r'fn\s+main\s*\('), "rust_main"),
]

PACKAGE_MANAGER_MAP = {
    "requirements.txt": "pip",
    "pyproject.toml": "pip/poetry",
    "setup.py": "pip/setuptools",
    "package.json": "npm/yarn",
    "Cargo.toml": "cargo",
    "go.mod": "go modules",
    "Gemfile": "bundler",
    "composer.json": "composer",
}


@dataclass
class ParsedRepo:
    """Structured scan result of a repository."""

    repo_id: str
    repo_name: str
    local_path: Path
    all_files: list[Path] = field(default_factory=list)
    code_files: list[Path] = field(default_factory=list)
    config_files: list[Path] = field(default_factory=list)
    languages: set[str] = field(default_factory=set)
    package_managers: list[str] = field(default_factory=list)
    entry_points: list[tuple[str, str, str]] = field(default_factory=list)  # (rel_path, kind, evidence)
    dockerfiles: list[Path] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class RepositoryParser:
    """Scans a repository path or GitHub URL into a structured ParsedRepo."""

    def parse(self, repository_path: str) -> ParsedRepo:
        """Resolve input and scan the repo."""
        stripped = repository_path.strip()
        settings = get_settings()

        if stripped.startswith(("http://", "https://")):
            logger.info("Cloning remote repository: %s", stripped)
            repo_id = generate_repo_id(stripped)
            clone_dir = Path(settings.repos_clone_dir) / repo_id
            local_path = clone_repository(stripped, clone_dir)
            repo_name = stripped.rstrip("/").split("/")[-1].replace(".git", "")
        else:
            local_path = Path(stripped).resolve()
            if not local_path.exists():
                raise ValueError(f"Repository path does not exist: {local_path}")
            repo_id = generate_repo_id_from_path(local_path)
            repo_name = local_path.name

        logger.info("Scanning repository at: %s", local_path)

        all_files: list[Path] = []
        code_files: list[Path] = []
        config_files: list[Path] = []
        dockerfiles: list[Path] = []
        languages: set[str] = set()
        pkg_managers: set[str] = set()
        entry_points: list[tuple[str, str, str]] = []

        for path in local_path.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue

            all_files.append(path)
            ext = path.suffix.lower()
            name = path.name

            # Code files
            if ext in CODE_EXTENSIONS:
                code_files.append(path)
                lang = get_language_name(ext)
                if lang:
                    languages.add(lang)

            # Config files
            if name in CONFIG_FILENAMES or ext in {".toml", ".ini", ".yaml", ".yml", ".cfg"}:
                config_files.append(path)

            # Dockerfiles
            if name.lower().startswith("dockerfile") or name == "docker-compose.yml" or name == "docker-compose.yaml":
                dockerfiles.append(path)

            # Package managers
            if name in PACKAGE_MANAGER_MAP:
                pkg_managers.add(PACKAGE_MANAGER_MAP[name])

            # Entry point detection
            if ext in CODE_EXTENSIONS:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    rel = str(path.relative_to(local_path)).replace("\\", "/")
                    for pattern, kind in ENTRY_POINT_PATTERNS:
                        match = pattern.search(content)
                        if match:
                            entry_points.append((rel, kind, match.group(0).strip()))
                            break
                except Exception:
                    pass

        deps = self._extract_dependencies(config_files)

        return ParsedRepo(
            repo_id=repo_id,
            repo_name=repo_name,
            local_path=local_path,
            all_files=all_files,
            code_files=code_files,
            config_files=config_files,
            languages=languages,
            package_managers=sorted(pkg_managers),
            entry_points=entry_points,
            dockerfiles=dockerfiles,
            dependencies=deps,
        )

    def _extract_dependencies(self, config_files: list[Path]) -> list[str]:
        """Extract dependency names from config files."""
        deps: set[str] = set()
        for fp in config_files:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                if fp.name == "requirements.txt":
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip()
                            if pkg:
                                deps.add(pkg)
                elif fp.name == "package.json":
                    data = json.loads(content)
                    for key in ("dependencies", "devDependencies"):
                        if key in data and isinstance(data[key], dict):
                            deps.update(data[key].keys())
            except Exception:
                logger.debug("Failed to parse deps from: %s", fp)
        return sorted(deps)
