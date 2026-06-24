"""
Sanitize node metadata before Chroma persistence.

Chroma only accepts scalar metadata values (str, int, float, bool).
LlamaIndex AST chunks may attach None or complex types — strip or stringify them.
"""


def sanitize_metadata(metadata: dict) -> dict:
    """Return a Chroma-safe copy of node metadata."""
    clean: dict = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def sanitize_nodes(nodes: list) -> None:
    """Mutate nodes in-place so their metadata is safe for Chroma."""
    for node in nodes:
        if hasattr(node, "metadata") and node.metadata:
            node.metadata = sanitize_metadata(node.metadata)
