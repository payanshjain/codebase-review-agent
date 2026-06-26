"""
README generator implementation.

Synthesizes high-quality README.md covering project overview, features,
tech stack, installation, setup instructions, usage examples, and contributing.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class ReadmeGenerator:
    """
    Generates a production-ready README.md from RepositoryMetadata.
    """

    async def generate(self, metadata: RepositoryMetadata) -> str:
        """
        Synthesize comprehensive README markdown.
        """
        logger.info("Synthesizing README.md for repo: %s", metadata.repo_name)

        stack_str = ", ".join(f"`{d}`" for d in metadata.dependencies[:15]) or "`Standard Library`"
        lang_str = ", ".join(f"**{lang}**" for lang in metadata.languages) or "Multi-Language"
        features = [
            f"**Autonomous AST Parsing**: Extracts clean code structures across {len(metadata.classes)} classes and {len(metadata.functions)} functions.",
            f"**API Route Detection**: Identifies {len(metadata.api_endpoints)} HTTP endpoints automatically.",
            "**Multi-Format Export**: Generates Markdown, styled HTML, and PDF documentation reports.",
            "**Incremental Synchronization**: Calculates SHA256 hashes to intelligently cache and update docs.",
        ]

        api_section = ""
        if metadata.api_endpoints:
            api_items = "\n".join(f"- `{ep.method} {ep.path}` -> {ep.docstring or ep.function_name}" for ep in metadata.api_endpoints[:5])
            api_section = f"""## 🌐 API Overview\n\n{api_items}\n\n*For detailed endpoint schemas, refer to the API Documentation report.*\n"""

        md = f"""# 🚀 {metadata.repo_name}

> Grounded codebase intelligence and automated technical documentation repository.

## 📖 Project Overview

**{metadata.repo_name}** is built using {lang_str}. It provides comprehensive agentic code understanding, semantic retrieval, and multi-repository management capabilities designed to streamline engineering workflows.

## ✨ Features

{chr(10).join(f'- {f}' for f in features)}

## 🛠️ Tech Stack

- **Core Languages**: {lang_str}
- **Dependencies**: {stack_str}
- **Architecture Pattern**: Clean Architecture & SOLID Principles

## 📦 Installation

1. Clone the repository to your local workspace:
```bash
git clone <repository_url>
cd "{metadata.repo_name}"
```

2. Create and activate a Python virtual environment:
```bash
python -m venv .venv
# On Windows
.venv\\Scripts\\activate
# On macOS/Linux
source .venv/bin/activate
```

3. Install project dependencies:
```bash
pip install -r requirements.txt
```

## ⚙️ Setup Instructions

Ensure your environment variables are configured correctly before launching the service:
```bash
cp .env.example .env
# Edit .env and supply required provider keys (e.g., GROQ_API_KEY)
```

## 💡 Usage Examples

Run the application locally via Uvicorn dev server:
```bash
python run.py
# Or directly
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running, navigate to `http://127.0.0.1:8000/docs` to interact with the Swagger API interface.

{api_section}
## 🤝 Contributing Guide

1. Fork the repository and create your feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes following conventional commit formatting.
3. Ensure all unit tests pass before submitting (`pytest`).
4. Push to the branch (`git push origin feature/amazing-feature`) and open a Pull Request.

## 📄 License

This project is licensed under the MIT License.
"""
        return md
