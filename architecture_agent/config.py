"""
Configuration constants for the Repository Architecture Agent.
"""

from pathlib import Path

# Persistent cache directory for analysis manifests
ARCH_STORE_DIR = Path("./data/architecture_store")

# Maximum nodes rendered in Mermaid diagrams to keep them readable
MERMAID_MAX_NODES = 30

# Maximum depth for transitive impact analysis traversal
MAX_IMPACT_DEPTH = 10

# Top-N files returned by importance ranking
DEFAULT_TOP_N_FILES = 15
