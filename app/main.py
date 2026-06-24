from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.api.repository_routes import router as repo_router
from app.api.review_routes import router as review_router
from app.core.config import ENV_FILE, SettingsNotConfiguredError, get_settings

app = FastAPI(
    title="Codebase Q&A RAG — Multi-Repository Platform",
    description="Multi-repository code intelligence with hybrid retrieval and AI code review",
    version="0.3.0",
)
app.include_router(api_router)
app.include_router(repo_router)
app.include_router(review_router)


@app.exception_handler(SettingsNotConfiguredError)
async def settings_not_configured_handler(
    _request: Request,
    exc: SettingsNotConfiguredError,
) -> JSONResponse:
    """Return a clear 503 instead of an unhandled 500 when .env is missing."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.message,
            "hint": f"Expected config file at: {ENV_FILE}",
        },
    )


@app.get("/health")
def health() -> dict:
    """Health check — works even when Groq is not configured yet."""
    try:
        settings = get_settings()
        return {
            "status": "ok",
            "configured": True,
            "llm_provider": "groq",
            "embed_provider": "huggingface",
            "llm_model": settings.groq_model,
            "embed_model": settings.huggingface_embed_model,
        }
    except SettingsNotConfiguredError as exc:
        return {
            "status": "ok",
            "configured": False,
            "message": exc.message,
        }
