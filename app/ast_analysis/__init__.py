"""
AST-based code analysis — tree-sitter powered multi-language parsing.

This package replaces naive text-based chunking with structure-aware code
understanding.  It parses source files into Abstract Syntax Trees, extracts
semantic units (functions, classes, methods), and produces chunks that
respect code boundaries with rich structural metadata.

Supported languages: Python, JavaScript, TypeScript, Java, Go, Rust.
Non-parseable files (markdown, JSON, YAML, etc.) fall back to text chunking.
"""
