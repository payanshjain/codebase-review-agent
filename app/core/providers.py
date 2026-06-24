"""
Create embedding + LLM clients for Path B:
  - Embeddings: HuggingFace (local, free)
  - Answers: Groq (cloud API, generous free tier)

IMPORTANT: We always set both LlamaSettings.embed_model AND LlamaSettings.llm
to prevent LlamaIndex from falling back to OpenAI for internal operations
(e.g. QueryFusionRetriever uses the global LLM for query expansion).
"""

from llama_index.core import Settings as LlamaSettings
from llama_index.core.llms import LLM
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq

from app.core.config import Settings


def configure_embedding_model(settings: Settings) -> None:
    """
    Set local HuggingFace embeddings AND Groq as the global LLM.

    Both must be set together: LlamaIndex components like QueryFusionRetriever
    use LlamaSettings.llm internally — if it's not set, LlamaIndex tries OpenAI.
    """
    LlamaSettings.embed_model = HuggingFaceEmbedding(
        model_name=settings.huggingface_embed_model,
        device=settings.embedding_device,
    )
    # Always override the global LLM so no component ever falls back to OpenAI.
    LlamaSettings.llm = Groq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
    )


def create_llm(settings: Settings) -> LLM:
    """Groq chat model for grounded answers (requires GROQ_API_KEY)."""
    return Groq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
    )
