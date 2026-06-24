"""
AI code review — analyzes submitted source for bugs, security, complexity, and more.
"""

from __future__ import annotations

import json
import logging
import re

from llama_index.core.llms import ChatMessage

from app.core.config import Settings
from app.core.providers import create_llm
from app.schemas.review_schema import CodeReviewResponse, ReviewIssue

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """You are a senior staff engineer performing a thorough code review.
Analyze the submitted code carefully and return ONLY valid JSON (no markdown fences).

Be specific, actionable, and honest. Flag real problems — do not invent issues.
If the code is solid, say so with few or zero issues.

JSON schema:
{
  "summary": "2-4 sentence overview",
  "overall_assessment": "needs work | good with minor fixes | production-ready",
  "strengths": ["positive point 1", "positive point 2"],
  "issues": [
    {
      "category": "bug|security|complexity|refactoring|performance|style",
      "severity": "critical|high|medium|low|info",
      "title": "short title",
      "description": "what is wrong and why it matters",
      "line_hint": "line 12 or function foo",
      "suggestion": "how to fix it"
    }
  ]
}

Review dimensions (cover all that apply):
- **bug**: logic errors, edge cases, null/exception handling, race conditions
- **security**: injection, secrets, auth, unsafe deserialization, input validation
- **complexity**: deep nesting, long functions, unclear control flow
- **refactoring**: naming, duplication, separation of concerns, design patterns
- **performance**: unnecessary loops, N+1 patterns, memory leaks
- **style**: readability, conventions, missing types/docs (only if meaningful)"""


def _build_user_prompt(
    code: str,
    language: str,
    filename: str | None,
    context: str | None,
) -> str:
    header = f"Language: {language}"
    if filename:
        header += f"\nFilename: {filename}"
    if context:
        header += f"\nAuthor context: {context}"

    return f"""{header}

```{language}
{code}
```

Return the JSON review object now."""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown fences if present."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Try direct parse first, then find outermost { ... }.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _parse_review_response(raw: dict, llm_model: str) -> CodeReviewResponse:
    """Convert parsed JSON dict into a validated CodeReviewResponse."""
    issues_raw = raw.get("issues") or []
    issues: list[ReviewIssue] = []

    for item in issues_raw:
        if not isinstance(item, dict):
            continue
        try:
            issues.append(
                ReviewIssue(
                    category=str(item.get("category", "refactoring")),
                    severity=str(item.get("severity", "medium")),
                    title=str(item.get("title", "Issue")),
                    description=str(item.get("description", "")),
                    line_hint=item.get("line_hint"),
                    suggestion=item.get("suggestion"),
                )
            )
        except Exception:
            logger.warning("Skipping malformed review issue: %s", item)

    return CodeReviewResponse(
        summary=str(raw.get("summary", "Review completed.")),
        overall_assessment=str(raw.get("overall_assessment", "good with minor fixes")),
        issues=issues,
        strengths=[str(s) for s in (raw.get("strengths") or []) if s],
        llm_model=llm_model,
    )


def review_code(
    code: str,
    settings: Settings,
    *,
    language: str = "python",
    filename: str | None = None,
    context: str | None = None,
) -> CodeReviewResponse:
    """Run Groq LLM code review and return structured findings."""
    llm = create_llm(settings)
    response = llm.chat(
        [
            ChatMessage(role="system", content=REVIEW_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=_build_user_prompt(code, language, filename, context),
            ),
        ]
    )
    raw_text = str(response.message.content)

    try:
        parsed = _extract_json(raw_text)
        return _parse_review_response(parsed, settings.groq_model)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse structured review JSON: %s", exc)
        # Graceful fallback: wrap free-text review in a single issue bucket.
        return CodeReviewResponse(
            summary=raw_text[:1500],
            overall_assessment="review completed (unstructured)",
            issues=[],
            strengths=[],
            llm_model=settings.groq_model,
        )
