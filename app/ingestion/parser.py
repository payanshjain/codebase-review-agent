from pathlib import Path

from llama_index.core import Document

from app.ast_analysis.languages import is_ast_parseable
from app.ingestion.file_loader import list_source_files, read_text_file


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
}


def _language_from_suffix(path: Path) -> str:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "unknown")


def parse_repository_to_documents(repo_path: Path) -> list[Document]:
    """
    Convert repository files into LlamaIndex Documents with useful metadata.

    Each document now includes an ``is_ast_parseable`` flag and the raw file
    extension so that the hybrid chunker can route it to AST-based or
    text-based chunking.
    """
    files = list_source_files(repo_path)
    documents: list[Document] = []

    for file_path in files:
        text = read_text_file(file_path)
        rel_path = str(file_path.relative_to(repo_path))
        language = _language_from_suffix(file_path)
        extension = file_path.suffix.lower()

        if not text.strip():
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "file_path": rel_path,
                    "language": language,
                    "char_count": len(text),
                    "file_extension": extension,
                    "is_ast_parseable": is_ast_parseable(extension),
                },
            )
        )

    return documents
