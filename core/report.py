"""Builds a self-contained Markdown report from a completed review."""
from __future__ import annotations

from datetime import datetime, timezone

from core.ai_reviewer import ModelChoice
from core.models import ReviewResult
from core.static_analysis import StaticAnalysisResult

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _issue_section(result: ReviewResult) -> str:
    if not result.issues:
        return "No issues were flagged.\n"
    ordered = sorted(result.issues, key=lambda i: (_SEVERITY_ORDER.get(i.severity.value, 9), i.line_start))
    lines = []
    for issue in ordered:
        span = f"L{issue.line_start}" if issue.line_start == issue.line_end else f"L{issue.line_start}-{issue.line_end}"
        lines.append(f"### [{issue.severity.value.upper()}] {issue.title} ({span})")
        lines.append(f"*Category: {issue.category.value.replace('_', ' ')}*")
        lines.append("")
        lines.append(issue.explanation)
        lines.append("")
        lines.append(f"**Suggestion:** {issue.suggestion}")
        if issue.fixed_code.strip():
            lines.append("")
            lines.append("```python")
            lines.append(issue.fixed_code.strip())
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _static_section(result: StaticAnalysisResult) -> str:
    if not result.ran_successfully:
        return f"_{result.tool} did not run: {result.error_message}_\n"
    if not result.issues:
        return f"{result.tool} found no issues.\n"
    lines = [f"| Line | Code | Message |", "|---|---|---|"]
    for issue in result.issues:
        label = issue.symbol or issue.code
        message = issue.message.replace("|", "\\|")
        lines.append(f"| {issue.line} | `{label}` | {message} |")
    return "\n".join(lines)


def build_markdown_report(
    *,
    filename: str,
    code: str,
    ai_result: ReviewResult | None,
    provider_label: str,
    model: ModelChoice | None,
    pylint_result: StaticAnalysisResult | None,
    flake8_result: StaticAnalysisResult | None,
) -> str:
    """Assemble a complete, shareable Markdown report."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# AI Code Review Report",
        "",
        f"**File:** `{filename}`  ",
        f"**Generated:** {generated_at}  ",
    ]
    if ai_result is not None:
        lines.append(f"**Reviewer:** {provider_label} ({model.label if model else 'unknown model'})  ")
    lines.append("")

    if ai_result is not None:
        lines += [
            "## Verdict",
            "",
            f"**Quality score: {ai_result.quality_score}/100**",
            "",
            ai_result.overall_summary,
            "",
        ]
        if ai_result.strengths:
            lines += ["### Strengths", ""]
            lines += [f"- {s}" for s in ai_result.strengths]
            lines.append("")
        lines += ["## Issues", ""]
        lines.append(_issue_section(ai_result))
        if ai_result.best_practice_notes:
            lines += ["## Best practice notes", ""]
            lines += [f"- {n}" for n in ai_result.best_practice_notes]
            lines.append("")

    if pylint_result is not None:
        lines += ["## Pylint", "", _static_section(pylint_result), ""]
    if flake8_result is not None:
        lines += ["## Flake8", "", _static_section(flake8_result), ""]

    lines += ["## Reviewed source", "", "```python", code.rstrip("\n"), "```"]
    return "\n".join(lines)
