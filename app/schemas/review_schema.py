from pydantic import BaseModel, Field


class CodeReviewRequest(BaseModel):
    """Submit source code for an AI-powered review."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=80_000,
        description="Source code to review",
    )
    language: str = Field(
        default="python",
        description="Programming language (python, javascript, typescript, java, go, rust, etc.)",
    )
    filename: str | None = Field(
        default=None,
        description="Optional filename for context, e.g. auth.py",
    )
    context: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional note about what this code does or your concerns",
    )


class ReviewIssue(BaseModel):
    """One finding from the code review."""

    category: str = Field(
        ...,
        description="bug | security | complexity | refactoring | performance | style",
    )
    severity: str = Field(
        ...,
        description="critical | high | medium | low | info",
    )
    title: str
    description: str
    line_hint: str | None = Field(
        default=None,
        description="Approximate line number or code snippet reference",
    )
    suggestion: str | None = Field(
        default=None,
        description="Concrete fix or improvement",
    )


class CodeReviewResponse(BaseModel):
    """Structured code review output."""

    summary: str
    overall_assessment: str = Field(
        ...,
        description="Short verdict: e.g. 'needs work', 'good with minor fixes', 'production-ready'",
    )
    issues: list[ReviewIssue]
    strengths: list[str] = Field(default_factory=list)
    llm_model: str
