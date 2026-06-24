from pathlib import Path


DEFAULT_ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
}

DEFAULT_IGNORED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".pytest_cache",
    # Avoid indexing our own vector/docstore output when indexing this project.
    ".cursor",
    "data",
}


def resolve_repo_path(repo_path: str) -> Path:
    """Validate and normalize the repository path provided by user."""
    resolved = Path(repo_path).expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"Repository path does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Repository path is not a directory: {resolved}")
    return resolved


def _is_probably_binary(file_path: Path) -> bool:
    """Simple binary detection by checking null bytes in first chunk."""
    try:
        with file_path.open("rb") as f:
            sample = f.read(1024)
        return b"\x00" in sample
    except OSError:
        # Treat unreadable files as non-text candidates to be skipped later.
        return True


def list_source_files(
    repo_path: Path,
    allowed_extensions: set[str] | None = None,
    ignored_dirs: set[str] | None = None,
) -> list[Path]:
    """Return text-like source/documentation files from repository."""
    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    ignored = ignored_dirs or DEFAULT_IGNORED_DIRS

    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue

        # Skip files inside ignored directories.
        if any(part in ignored for part in path.parts):
            continue

        if path.suffix.lower() not in allowed:
            continue

        if _is_probably_binary(path):
            continue

        files.append(path)

    return files


def read_text_file(file_path: Path) -> str:
    """Read UTF-8 text safely. Invalid bytes are replaced, not fatal."""
    return file_path.read_text(encoding="utf-8", errors="replace")
