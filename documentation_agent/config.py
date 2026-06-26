"""
Configuration settings for the Documentation Generator Agent.
"""

from pathlib import Path

# Base storage directory for generated documentation manifests and exports
DOCS_STORE_DIR = Path("./data/documentation_store")

# Maximum concurrent LLM calls during documentation generation to avoid rate limits
CONCURRENCY_LIMIT = 5

# Max tokens to include in prompt context when synthesizing documentation
MAX_CONTEXT_TOKENS = 6000
