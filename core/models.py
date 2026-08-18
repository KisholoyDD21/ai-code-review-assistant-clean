"""Shared data models.

`Severity`, `IssueCategory`, `CodeIssue`, and `ReviewResult` double as the
JSON schema both the OpenAI and Gemini structured-output modes are
constrained to -- the field names, types, and descriptions here are sent to
the model, so they're written to guide the model's output, not just to
satisfy a type checker.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """How urgently a finding should be addressed."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    """What kind of problem a finding represents."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    BEST_PRACTICE = "best_practice"
    MAINTAINABILITY = "maintainability"


class CodeIssue(BaseModel):
    """A single finding raised by the AI reviewer."""

    line_start: int = Field(..., description="1-indexed line where the issue begins.")
    line_end: int = Field(
        ..., description="1-indexed line where the issue ends. Equal to line_start for single-line issues."
    )
    severity: Severity
    category: IssueCategory
    title: str = Field(..., description="Short, specific title, e.g. 'Mutable default argument'.")
    explanation: str = Field(
        ..., description="Why this is a problem, teaching the underlying principle rather than just naming it."
    )
    suggestion: str = Field(..., description="Concrete, actionable guidance on how to fix it.")
    fixed_code: str = Field(
        "", description="A short corrected code snippet, if one clarifies the fix. Empty string otherwise."
    )


class ReviewResult(BaseModel):
    """The complete structured output of one AI review pass."""

    overall_summary: str = Field(
        ..., description="A 2-4 sentence human-readable summary of the code's quality and main themes."
    )
    quality_score: int = Field(..., ge=0, le=100, description="Overall quality score from 0 (unusable) to 100 (exemplary).")
    issues: list[CodeIssue] = Field(default_factory=list)
    strengths: list[str] = Field(
        default_factory=list, description="Genuine, specific strengths of the code. Empty list if there are none worth naming."
    )
    best_practice_notes: list[str] = Field(
        default_factory=list,
        description="General best-practice teaching points relevant specifically to this code, not generic Python trivia.",
    )
