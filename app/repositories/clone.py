"""
GitHub repository cloning via subprocess (no extra dependency — uses system git).

Why subprocess over gitpython?
- Zero new dependencies.
- Shallow clone (--depth 1) minimises disk usage and clone time.
- git CLI is universally available on developer machines.
"""

import re
import subprocess
from pathlib import Path


# Matches HTTPS GitHub URLs like https://github.com/owner/repo or
# https://github.com/owner/repo.git (with optional trailing slash).
_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+?)(?:\.git)?/?$"
)


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Validate a GitHub HTTPS URL and extract (owner, repo_name).

    Raises ValueError for non-GitHub or malformed URLs.
    """
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        raise ValueError(
            f"Invalid GitHub URL: {url!r}. "
            "Expected format: https://github.com/owner/repo"
        )
    return match.group("owner"), match.group("repo")


def generate_repo_id(url: str) -> str:
    """
    Deterministic, URL-safe repo identifier from a GitHub URL.

    Example: 'https://github.com/tiangolo/fastapi' → 'tiangolo__fastapi'

    Double-underscore separates owner and repo to avoid collisions with repos
    that contain single underscores in their names.
    """
    owner, repo = parse_github_url(url)
    return f"{owner}__{repo}".lower()


def generate_repo_id_from_path(local_path: Path) -> str:
    """
    Generate a repo_id from a local filesystem path.

    Uses the last two path components (parent + folder name) to create a
    human-readable slug, falling back to just the folder name.
    """
    parts = local_path.resolve().parts
    if len(parts) >= 2:
        slug = f"local__{parts[-2]}__{parts[-1]}"
    else:
        slug = f"local__{parts[-1]}"
    # Sanitise to URL-safe chars
    return re.sub(r"[^a-z0-9_]", "_", slug.lower())


def clone_repository(url: str, target_dir: Path) -> Path:
    """
    Shallow-clone a GitHub repository into *target_dir*.

    If the directory already exists and is non-empty, it is assumed to be a
    valid prior clone and is returned as-is (supports skip-if-exists).

    Returns the path to the cloned repository root.
    """
    if is_already_cloned(target_dir):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout for large repos
        )
    except FileNotFoundError:
        raise RuntimeError(
            "git is not installed or not on PATH. "
            "Install git and try again: https://git-scm.com/downloads"
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"git clone failed (exit {exc.returncode}): {exc.stderr.strip()}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"git clone timed out after 5 minutes for {url}. "
            "The repository may be too large or the network is slow."
        )

    return target_dir


def is_already_cloned(target_dir: Path) -> bool:
    """Return True if *target_dir* looks like an existing clone."""
    if not target_dir.exists():
        return False
    # A valid git clone has at least a .git directory
    return (target_dir / ".git").is_dir()
