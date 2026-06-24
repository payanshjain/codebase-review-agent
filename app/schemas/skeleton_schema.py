"""
Pydantic models for the repository skeleton endpoint.
"""

from pydantic import BaseModel, Field


class SymbolInfo(BaseModel):
    """One code symbol in the skeleton (function, class, method)."""

    symbol_type: str = Field(..., description="function, class, or method")
    name: str
    line: int = Field(..., description="Line number where the symbol starts")
    signature: str = Field(default="", description="Full signature line")
    parent_class: str | None = Field(default=None, description="Enclosing class for methods")
    children: list[str] = Field(
        default_factory=list,
        description="Method names (for class symbols)",
    )


class FileSkeletonInfo(BaseModel):
    """Structural summary of one file."""

    path: str
    language: str
    symbols: list[SymbolInfo] = Field(default_factory=list)


class SkeletonResponse(BaseModel):
    """Full repository skeleton — returned by GET /repositories/{repo_id}/skeleton."""

    repo_id: str
    total_files: int
    total_symbols: int
    ast_parsed_files: int = Field(
        ...,
        description="Number of files that were parsed with tree-sitter",
    )
    files: list[FileSkeletonInfo]
