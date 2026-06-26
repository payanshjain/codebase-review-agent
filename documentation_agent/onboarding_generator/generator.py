"""
Developer onboarding guide generator implementation.

Synthesizes onboarding guide covering repository structure, important files,
how to run locally, debugging notes, and how to contribute effectively.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class OnboardingGenerator:
    """
    Generates Developer Onboarding Guide markdown report.
    """

    async def generate(self, metadata: RepositoryMetadata) -> str:
        """
        Synthesize developer onboarding guide.
        """
        logger.info("Synthesizing Onboarding Guide for repo: %s", metadata.repo_name)

        important_files = "\n".join(f"- `{cf}`" for cf in metadata.configuration_files) or "- Standard Repository Root Files"
        core_files = "\n".join(f"- `{cls.file_path}` -> Defines `{cls.name}`" for cls in metadata.classes[:8]) or "- Application Entry Source Modules"

        guide = f"""# 🧭 {metadata.repo_name} — Developer Onboarding Guide

Welcome to the engineering team for **{metadata.repo_name}**! This guide is designed to accelerate your onboarding by detailing repository layout, critical entry points, local development setup, and code contribution standards.

---

## 📁 1. Repository Structure

The codebase is organized logically into dedicated modules:

```text
{metadata.folder_structure}
```

---

## ⭐ 2. Important Files & Modules

Familiarize yourself with these critical operational files before making code edits:

### Configuration & Entry Points
{important_files}

### Core Service Modules
{core_files}

---

## 💻 3. How to Run Locally

Follow this systematic checklist to spin up your local development environment:

1. **Clone & Virtual Environment**:
```bash
git clone <remote_url>
cd "{metadata.repo_name}"
python -m venv .venv
.venv\\Scripts\\activate  # Windows
```

2. **Dependencies & Environment Configuration**:
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and supply required provider API keys
```

3. **Launch Dev Server**:
```bash
python run.py
```
Verify the health endpoint responds at `http://127.0.0.1:8000/health`.

---

## 🤝 4. How to Contribute

We follow strict engineering standards to maintain code cleanliness and SOLID architecture:

- **Branching**: Create feature branches from `main` (`feature/descriptive-name`).
- **Formatting & Typing**: Ensure all new Python code includes explicit type hints (`list[str]`, `dict`, `str | None`).
- **Documentation**: Preserve all existing docstrings. Add Google-style docstrings to any new classes or functions.
- **Verification**: Run pre-flight validation and automated unit tests before requesting review:
```bash
pytest
python scripts/validate.py
```
"""
        return guide
