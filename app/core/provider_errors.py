"""
Map provider errors (Groq, HuggingFace) to HTTP status + beginner-friendly messages.
"""


def provider_error_response(exc: Exception) -> tuple[int, str]:
    """Return (http_status, detail_message) for common LLM / embedding failures."""
    message = str(exc).lower()

    if "invalid_api_key" in message or "incorrect api key" in message or "unauthorized" in message:
        return (
            401,
            "Invalid GROQ_API_KEY. Get a free key at https://console.groq.com/keys "
            "and set it in .env, then restart the server.",
        )

    if "insufficient_quota" in message or "exceeded your current quota" in message:
        return (
            402,
            "Groq quota exceeded. Check usage at https://console.groq.com/ "
            "or wait for your free-tier limit to reset.",
        )

    if "429" in message or "rate_limit" in message:
        return (
            429,
            "Rate limit reached. Wait a minute and retry, or index a smaller repo.",
        )

    if "out of memory" in message or "cuda" in message:
        return (
            503,
            "Embedding model ran out of memory. Set EMBEDDING_DEVICE=cpu in .env "
            "or use a smaller HUGGINGFACE_EMBED_MODEL.",
        )

    return (502, f"Provider request failed: {exc}")
