"""
Generate a grounded natural-language answer from retrieved chunks + Groq LLM.
"""

from llama_index.core.llms import ChatMessage
from llama_index.core.schema import NodeWithScore

from app.core.config import Settings
from app.core.providers import create_llm

GROUNDED_SYSTEM_PROMPT = """You are a helpful codebase assistant.
Answer the user's question using ONLY the provided context from the indexed repositories.
If the context is insufficient, clearly say you cannot answer from the indexed codebase.
When you use information from a source, mention the repository name, file path, and
function/class name in your answer.  Use the breadcrumb paths to explain where code lives."""


def _build_context_block(scored_nodes: list[NodeWithScore]) -> str:
    """Format retrieved chunks into one context string for the LLM."""
    parts: list[str] = []
    for i, scored in enumerate(scored_nodes, start=1):
        node = scored.node
        meta = node.metadata
        repo_id = str(meta.get("repo_id", "unknown"))
        file_path = str(meta.get("file_path", "unknown"))
        breadcrumb = meta.get("breadcrumb", "")
        symbol_type = meta.get("symbol_type", "")
        symbol_name = meta.get("symbol_name", "")
        text = getattr(node, "text", "") or ""
        score = scored.score
        score_text = f" (relevance: {score:.4f})" if score is not None else ""

        # Build a rich header line with AST context when available.
        header = f"--- Source {i}: [{repo_id}] {file_path}"
        if symbol_type and symbol_name:
            header += f" | {symbol_type}: {symbol_name}"
        header += f"{score_text} ---"
        if breadcrumb:
            header += f"\n# {breadcrumb}"

        parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)


def generate_grounded_answer(
    question: str,
    scored_nodes: list[NodeWithScore],
    settings: Settings,
) -> str:
    """Call Groq with retrieved context and return the final answer text."""
    if not scored_nodes:
        return (
            "I could not find relevant context in the indexed repositories for this question."
        )

    context = _build_context_block(scored_nodes)
    user_prompt = f"""Context from indexed repositories:

{context}

Question: {question}

Answer:"""

    llm = create_llm(settings)
    response = llm.chat(
        [
            ChatMessage(role="system", content=GROUNDED_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]
    )
    return str(response.message.content)
