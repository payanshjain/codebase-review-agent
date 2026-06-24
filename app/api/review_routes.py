"""
Code review API — submit code and receive structured feedback.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.provider_errors import provider_error_response
from app.review.reviewer import review_code
from app.schemas.review_schema import CodeReviewRequest, CodeReviewResponse

router = APIRouter(prefix="/review", tags=["code-review"])


@router.post("", response_model=CodeReviewResponse)
def review_source_code(request: CodeReviewRequest) -> CodeReviewResponse:
    """
    AI code review agent.

    Analyzes submitted source code and returns structured findings:
    - Possible bugs
    - Security issues
    - Complexity concerns
    - Refactoring suggestions
    - Performance and style notes
    """
    settings = get_settings()

    try:
        return review_code(
            request.code,
            settings,
            language=request.language,
            filename=request.filename,
            context=request.context,
        )
    except Exception as exc:
        status, detail = provider_error_response(exc)
        if status == 502:
            detail = f"Code review failed: {exc}"
        raise HTTPException(status_code=status, detail=detail) from exc
