"""AI Code Review Assistant -- Streamlit entry point.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from core.ai_reviewer import PROVIDERS, REASONING_EFFORTS, AIReviewer, ModelChoice, ReviewError
from core.models import ReviewResult
from core.report import build_markdown_report
from core.static_analysis import StaticAnalysisResult, format_static_context, run_flake8, run_pylint
from ui.components import (
    render_empty_state,
    render_eyebrow,
    render_hero,
    render_issue_card,
    render_model_picker,
    render_static_table,
    render_verdict_stamp,
)
from ui.styles import inject_global_styles

EXAMPLE_CODE = '''\
import os

def calculate_average(numbers=[]):
    total = 0
    for i in range(len(numbers)):
        total = total + numbers[i]
    return total / len(numbers)


class dataProcessor:
    def __init__(self, data):
        self.data = data
        self.password = "admin123"

    def process(self):
        try:
            result = self.data['value'] * 2
        except:
            pass
        return result

    def load_file(self, path):
        f = open(path)
        content = f.read()
        return content


def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return query
'''

ENV_KEY_NAMES = {"OpenAI": "OPENAI_API_KEY", "Gemini": "GEMINI_API_KEY"}

load_dotenv()


@st.cache_data(show_spinner=False)
def _cached_pylint(code: str) -> StaticAnalysisResult:
    return run_pylint(code)


@st.cache_data(show_spinner=False)
def _cached_flake8(code: str) -> StaticAnalysisResult:
    return run_flake8(code)


def _init_state() -> None:
    defaults = {
        "code_input": "",
        "filename": "snippet.py",
        "_last_uploaded_name": None,
        "review_result": None,
        "pylint_result": None,
        "flake8_result": None,
        "provider_label": None,
        "model_choice": None,
        "last_error": None,
        "review_fingerprint": None,
        "review_status": "idle",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _sidebar() -> tuple[str, AIReviewer | None, ModelChoice | None, str, bool, bool]:
    with st.sidebar:
        render_eyebrow("Review setup")
        with st.expander("Review settings", expanded=True):
            provider_label = st.radio("AI provider", options=list(PROVIDERS.keys()), horizontal=True)
            provider = PROVIDERS[provider_label]
            model_choice = render_model_picker(
                "Model", provider["models"], key=f"model_{provider_label}"
            )
            reasoning_effort = st.select_slider(
                "Analysis depth", options=REASONING_EFFORTS, value="medium",
                help="Higher depth reasons more carefully before answering. Slower and costs more per review.",
            )
            st.divider()
            render_eyebrow("Static analysis")
            run_pylint_flag = st.checkbox("Run Pylint", value=True)
            run_flake8_flag = st.checkbox("Run Flake8", value=True)

        st.divider()
        with st.expander("About this tool"):
            st.markdown(
                "Pastes or uploads a Python file, runs Pylint and Flake8 for static "
                "analysis, then sends the code (plus those findings, for grounding) to "
                "an LLM for a structured review: bugs, security and performance issues, "
                "and the reasoning behind each one.\n\n"
                "**Stack:** Python, Streamlit, OpenAI / Gemini APIs, Pylint, Flake8."
            )

        key_name = ENV_KEY_NAMES[provider_label]
        api_key = os.environ.get(key_name, "")
        if not api_key:
            try:
                api_key = st.secrets.get(key_name, "")
            except StreamlitSecretNotFoundError:
                api_key = ""

        reviewer: AIReviewer | None = None
        if api_key.strip():
            reviewer = provider["reviewer"](
                api_key=api_key,
                model=model_choice.id,
                reasoning_effort=reasoning_effort,
            )

        if reviewer is None:
            st.warning(
                f"AI review unavailable: configure {key_name} in the server environment or Streamlit secrets. "
                "Static analysis is still available."
            )
        else:
            st.success(f"{provider_label} AI review is ready.")
        return (
            provider_label,
            reviewer,
            model_choice,
            reasoning_effort,
            run_pylint_flag,
            run_flake8_flag,
        )


def _code_input_area() -> str:
    render_eyebrow("Source")
    col_upload, col_example = st.columns([3, 1])
    with col_upload:
        uploaded = st.file_uploader("Upload a .py file", type=["py"], label_visibility="collapsed")
    with col_example:
        if st.button("Load example", use_container_width=True):
            st.session_state["code_input"] = EXAMPLE_CODE
            st.session_state["filename"] = "example.py"
            st.session_state["_last_uploaded_name"] = None

    if uploaded is not None and uploaded.name != st.session_state.get("_last_uploaded_name"):
        st.session_state["code_input"] = uploaded.read().decode("utf-8", errors="replace")
        st.session_state["filename"] = uploaded.name
        st.session_state["_last_uploaded_name"] = uploaded.name

    code = st.text_area(
        "Paste Python code",
        key="code_input",
        height=340,
        placeholder="Paste a Python file here, or upload one above...",
        label_visibility="collapsed",
    )
    char_count = len(code)
    caption = f"`{st.session_state['filename']}` \u00b7 {char_count:,} characters"
    if char_count > 20_000:
        caption += "  \u2014  large file: review may be slow and cost more."
    st.caption(caption)
    return code


def _run_review(
    code: str,
    reviewer: AIReviewer | None,
    provider_label: str,
    model_choice: ModelChoice | None,
    run_pylint_flag: bool,
    run_flake8_flag: bool,
) -> None:
    st.session_state["review_result"] = None
    st.session_state["pylint_result"] = None
    st.session_state["flake8_result"] = None
    st.session_state["provider_label"] = None
    st.session_state["model_choice"] = None
    st.session_state["last_error"] = None
    st.session_state["review_status"] = "running"

    stripped = code.strip()
    if not stripped:
        st.session_state["review_status"] = "error"
        st.session_state["last_error"] = "Paste or upload some Python code first."
        st.warning("Paste or upload some Python code first.")
        return

    try:
        ast.parse(stripped)
    except SyntaxError as exc:
        message = f"That isn't valid Python yet \u2014 line {exc.lineno}, column {exc.offset}: {exc.msg}"
        st.session_state["review_status"] = "error"
        st.session_state["last_error"] = message
        st.error(message)
        return

    with st.status("Review in progress", expanded=True) as progress:
        progress.write("Running the selected static analyzers...")
        pylint_result = _cached_pylint(stripped) if run_pylint_flag else None
        flake8_result = _cached_flake8(stripped) if run_flake8_flag else None
        st.session_state["pylint_result"] = pylint_result
        st.session_state["flake8_result"] = flake8_result

        if reviewer is None:
            st.session_state["review_status"] = "static_only"
            progress.update(label="Static analysis complete", state="complete")
            return

        static_context = format_static_context([r for r in (pylint_result, flake8_result) if r is not None])
        progress.write(f"Requesting structured review from {provider_label}...")
        try:
            result = reviewer.review(stripped, st.session_state["filename"], static_context)
        except ReviewError as exc:
            st.session_state["last_error"] = str(exc)
            st.session_state["review_status"] = "error"
            progress.update(label="AI review failed", state="error")
            return

        st.session_state["review_result"] = result
        st.session_state["review_status"] = "success"
        st.session_state["provider_label"] = provider_label
        st.session_state["model_choice"] = model_choice
        progress.update(label="Review complete", state="complete")


def _review_fingerprint(
    code: str,
    filename: str,
    provider_label: str,
    model_choice: ModelChoice | None,
    reasoning_effort: str,
    run_pylint_flag: bool,
    run_flake8_flag: bool,
    ai_available: bool,
) -> str:
    values = (
        code,
        filename,
        provider_label,
        model_choice.id if model_choice else "",
        reasoning_effort,
        run_pylint_flag,
        run_flake8_flag,
        ai_available,
    )
    serialized = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _clear_stale_results(fingerprint: str) -> None:
    has_results = any(
        st.session_state.get(key) is not None
        for key in ("review_result", "pylint_result", "flake8_result")
    )
    if has_results:
        st.session_state["review_result"] = None
        st.session_state["pylint_result"] = None
        st.session_state["flake8_result"] = None
        st.session_state["provider_label"] = None
        st.session_state["model_choice"] = None
        st.session_state["last_error"] = None
        st.session_state["review_status"] = "stale"
    elif st.session_state.get("review_status") == "error":
        st.session_state["last_error"] = None
        st.session_state["review_status"] = "idle"
    st.session_state["review_fingerprint"] = fingerprint


def _render_review_status(reviewer: AIReviewer | None) -> None:
    status = st.session_state.get("review_status", "idle")
    if status == "stale":
        st.warning("Source or review settings changed. Previous results were cleared; run a new review.")
    elif status == "success":
        st.success("Review complete. Findings match the current source and settings.")
    elif status == "static_only":
        st.info("Static analysis complete. AI review is unavailable until a server API key is configured.")
    elif status == "error":
        st.error(st.session_state.get("last_error") or "The review could not be completed.")
    elif reviewer is not None:
        st.caption("Ready to review with the selected provider.")


def _results() -> None:
    review_result: ReviewResult | None = st.session_state.get("review_result")
    pylint_result: StaticAnalysisResult | None = st.session_state.get("pylint_result")
    flake8_result: StaticAnalysisResult | None = st.session_state.get("flake8_result")

    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])

    if review_result is None and pylint_result is None and flake8_result is None:
        render_empty_state("Run a review to see findings here.")
        return

    tab_labels = ["AI Review"]
    if pylint_result is not None:
        tab_labels.append("Pylint")
    if flake8_result is not None:
        tab_labels.append("Flake8")
    tab_labels.append("Report")
    tabs = st.tabs(tab_labels)
    tab_map = dict(zip(tab_labels, tabs))

    with tab_map["AI Review"]:
        if review_result is None:
            render_empty_state("No AI review yet \u2014 configure the provider API key on the server and run again.")
        else:
            render_verdict_stamp(review_result)
            if review_result.strengths:
                with st.expander(f"Strengths ({len(review_result.strengths)})", icon=":material/check_circle:"):
                    for s in review_result.strengths:
                        st.markdown(f"- {s}")
            st.write("")
            if not review_result.issues:
                render_empty_state("No issues flagged.")
            else:
                for i, issue in enumerate(
                    sorted(review_result.issues, key=lambda x: x.line_start)
                ):
                    render_issue_card(issue, i)
            if review_result.best_practice_notes:
                st.write("")
                render_eyebrow("Best practice notes")
                for note in review_result.best_practice_notes:
                    st.markdown(f"- {note}")

    if pylint_result is not None:
        with tab_map["Pylint"]:
            render_static_table(pylint_result, "Pylint found no issues.")

    if flake8_result is not None:
        with tab_map["Flake8"]:
            render_static_table(flake8_result, "Flake8 found no issues.")

    with tab_map["Report"]:
        report_md = build_markdown_report(
            filename=st.session_state["filename"],
            code=st.session_state["code_input"],
            ai_result=review_result,
            provider_label=st.session_state.get("provider_label") or "",
            model=st.session_state.get("model_choice"),
            pylint_result=pylint_result,
            flake8_result=flake8_result,
        )
        st.download_button(
            "Download report (.md)",
            data=report_md,
            file_name=f"{st.session_state['filename'].rsplit('.', 1)[0]}_review.md",
            mime="text/markdown",
            icon=":material/download:",
        )
        st.markdown(report_md)


def main() -> None:
    st.set_page_config(page_title="AI Code Review Assistant", page_icon="\U0001f40d", layout="wide")
    inject_global_styles()
    _init_state()

    (
        provider_label,
        reviewer,
        model_choice,
        reasoning_effort,
        run_pylint_flag,
        run_flake8_flag,
    ) = _sidebar()

    render_hero()

    left, right = st.columns([2, 1], gap="large")
    with left:
        code = _code_input_area()
        run_clicked = st.button("Run review", type="primary", use_container_width=True)
    with right:
        render_eyebrow("Status")
        st.markdown(f"**Provider:** {provider_label}")
        st.markdown(f"**Model:** {model_choice.label if model_choice else '\u2014'}")
        st.markdown(f"**Pylint:** {'on' if run_pylint_flag else 'off'}  \u00b7  **Flake8:** {'on' if run_flake8_flag else 'off'}")

    fingerprint = _review_fingerprint(
        code,
        st.session_state["filename"],
        provider_label,
        model_choice,
        reasoning_effort,
        run_pylint_flag,
        run_flake8_flag,
        reviewer is not None,
    )
    if fingerprint != st.session_state["review_fingerprint"]:
        _clear_stale_results(fingerprint)

    if run_clicked:
        _run_review(code, reviewer, provider_label, model_choice, run_pylint_flag, run_flake8_flag)

    _render_review_status(reviewer)
    st.write("")
    render_eyebrow("Findings")
    _results()


if __name__ == "__main__":
    main()
