"""Reusable rendering pieces built on top of the design system in styles.py.

Every dynamic string that gets interpolated into HTML here goes through
`html.escape()` first. The text comes from an LLM and, less often, from a
linter message -- neither is attacker-controlled in the traditional sense,
but escaping is what stops a stray `<` or `&` in generated text (e.g. code
mentioning `List<int>` or `a && b`) from corrupting the layout.
"""
from __future__ import annotations

import html as _html

import streamlit as st

from core.ai_reviewer import ModelChoice
from core.models import CodeIssue, ReviewResult
from core.static_analysis import StaticAnalysisResult
from ui.styles import CATEGORY_LABELS, GOOD, SEVERITY_COLORS, SEVERITY_LABELS


def _esc(text: str) -> str:
    return _html.escape(text, quote=True)


def render_hero() -> None:
    st.markdown(
        """
        <div class="acra-hero">
            <span class="acra-hero-mark">AI Code <em>Review</em></span>
        </div>
        <div class="acra-tagline">the red pen for python</div>
        <hr class="acra-rule" />
        """,
        unsafe_allow_html=True,
    )


def render_eyebrow(text: str) -> None:
    st.markdown(f'<div class="acra-eyebrow">{_esc(text)}</div>', unsafe_allow_html=True)


def _badge_html(text: str, color: str) -> str:
    return f'<span class="acra-badge" style="--badge-color:{color};">{_esc(text)}</span>'


def render_verdict_stamp(result: ReviewResult) -> None:
    score = max(0, min(100, result.quality_score))
    if score >= 85:
        color = GOOD
    elif score >= 60:
        color = SEVERITY_COLORS["medium"]
    else:
        color = SEVERITY_COLORS["critical"]

    counts: dict[str, int] = {}
    for issue in result.issues:
        counts[issue.severity.value] = counts.get(issue.severity.value, 0) + 1
    count_badges = "".join(
        _badge_html(f"{counts[s]} {SEVERITY_LABELS[s].lower()}", SEVERITY_COLORS[s])
        for s in ("critical", "high", "medium", "low", "info")
        if counts.get(s)
    )
    if not result.issues:
        count_badges = _badge_html("no issues found", GOOD)

    st.markdown(
        f"""
        <div class="acra-stamp-row">
            <div class="acra-stamp" style="--stamp-color:{color};">
                <span class="acra-stamp-score">{score}</span>
                <span class="acra-stamp-max">/ 100</span>
            </div>
            <div class="acra-verdict-summary">
                {_esc(result.overall_summary)}
                <div style="margin-top:0.6rem;">{count_badges}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_issue_card(issue: CodeIssue, index: int) -> None:
    color = SEVERITY_COLORS.get(issue.severity.value, "#8B8F99")
    span = f"L{issue.line_start}" if issue.line_start == issue.line_end else f"L{issue.line_start}\u2013{issue.line_end}"
    badges = _badge_html(SEVERITY_LABELS[issue.severity.value], color) + _badge_html(
        CATEGORY_LABELS.get(issue.category.value, issue.category.value), "#8B8F99"
    )
    st.markdown(
        f"""
        <div class="acra-issue" style="--issue-color:{color};">
            <div class="acra-issue-gutter">{_esc(span)}</div>
            <div class="acra-issue-body">
                <div class="acra-issue-title">{_esc(issue.title)}</div>
                <div class="acra-issue-meta">{badges}</div>
                <div class="acra-issue-text">{_esc(issue.explanation)}</div>
                <div class="acra-issue-suggestion">{_esc(issue.suggestion)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if issue.fixed_code.strip():
        with st.expander("Suggested fix", expanded=False, icon=":material/edit:"):
            st.code(issue.fixed_code.strip(), language="python")


def render_static_table(result: StaticAnalysisResult, empty_message: str) -> None:
    if not result.ran_successfully:
        st.warning(f"{result.tool} couldn't run: {result.error_message}")
        return
    if not result.issues:
        st.markdown(f'<div class="acra-empty">{_esc(empty_message)}</div>', unsafe_allow_html=True)
        return

    rows = []
    for issue in result.issues:
        label = _esc(issue.symbol or issue.code)
        rows.append(
            f"""<div class="acra-static-row">
                <span class="acra-static-line">L{issue.line}:{issue.column}</span>
                <span class="acra-static-code">{label}</span>
                <span class="acra-static-msg">{_esc(issue.message)}</span>
            </div>"""
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def render_empty_state(message: str) -> None:
    st.markdown(f'<div class="acra-empty">{_esc(message)}</div>', unsafe_allow_html=True)


def render_model_picker(label: str, models: list[ModelChoice], key: str) -> ModelChoice:
    choice_label = st.selectbox(label, options=[m.label for m in models], key=key)
    chosen = next(m for m in models if m.label == choice_label)
    st.caption(chosen.blurb)
    return chosen
