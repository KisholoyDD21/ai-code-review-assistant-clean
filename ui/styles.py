"""Design system for the app: an editor's red pen on a dark page.

The concept: this tool marks up code the way an editor marks up a
manuscript -- a ledger-dark page, warm paper-toned panels, and a red-ink
accent reserved for what actually needs attention. Severity colors carry
real information (they're the same hierarchy Pylint's own terminal reporter
uses: convention < refactor < warning < error), not decoration. The one
indulgence is a rotated "grade stamp" for the quality score, because this is
fundamentally a tool that grades your code.

Streamlit's generated class names churn between versions, so this only
targets stable `data-testid` hooks for native widgets and otherwise renders
its own HTML (badges, cards, the stamp) that it fully controls.
"""
from __future__ import annotations

import streamlit as st

INK = "#110F0C"
PAPER = "#1B1814"
PAPER_RAISED = "#221E18"
HAIRLINE = "#35312A"
TEXT = "#ECE7DD"
TEXT_DIM = "#9B9484"
TEXT_FAINT = "#6E6858"
RED_INK = "#E13A50"
GOOD = "#4FAE7C"

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#E13A50",
    "high": "#E8793C",
    "medium": "#E4B73E",
    "low": "#5B8FD1",
    "info": "#8B8F99",
}

SEVERITY_LABELS: dict[str, str] = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}

CATEGORY_LABELS: dict[str, str] = {
    "bug": "Bug",
    "security": "Security",
    "performance": "Performance",
    "style": "Style",
    "best_practice": "Best practice",
    "maintainability": "Maintainability",
}


def inject_global_styles() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600..900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        :root {{
            --ink: {INK};
            --paper: {PAPER};
            --paper-raised: {PAPER_RAISED};
            --hairline: {HAIRLINE};
            --text: {TEXT};
            --text-dim: {TEXT_DIM};
            --text-faint: {TEXT_FAINT};
            --red-ink: {RED_INK};
            --good: {GOOD};
        }}

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background-color: var(--ink) !important;
            color: var(--text);
        }}
        [data-testid="stHeader"] {{ background-color: transparent !important; }}
        [data-testid="stSidebar"] {{
            background-color: var(--paper) !important;
            border-right: 1px solid var(--hairline);
        }}
        [data-testid="stSidebar"] * {{ color: var(--text) !important; }}

        html, body, p, div, span, label, li {{
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
        }}
        h1, h2, h3, h4 {{
            font-family: 'IBM Plex Sans', sans-serif;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        code, pre, .stCodeBlock, textarea, [data-testid="stMetricValue"] {{
            font-family: 'IBM Plex Mono', 'SF Mono', monospace !important;
        }}

        /* ---- Hero ---- */
        .acra-hero {{
            display: flex;
            align-items: baseline;
            gap: 0.6rem;
            margin-bottom: 0.1rem;
            flex-wrap: wrap;
        }}
        .acra-hero-mark {{
            font-family: 'Fraunces', serif;
            font-weight: 800;
            font-size: 2.1rem;
            font-style: italic;
            color: var(--text);
            line-height: 1;
        }}
        .acra-hero-mark em {{ color: var(--red-ink); font-style: italic; }}
        .acra-tagline {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: var(--text-faint);
            text-transform: uppercase;
            letter-spacing: 0.09em;
        }}
        .acra-rule {{
            border: none;
            border-top: 1px solid var(--hairline);
            margin: 0.9rem 0 1.4rem 0;
        }}
        .acra-eyebrow {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            font-weight: 500;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--text-faint);
            margin-bottom: 0.35rem;
        }}

        /* ---- Buttons ---- */
        .stButton > button, .stDownloadButton > button {{
            background-color: var(--red-ink) !important;
            color: #100E0C !important;
            border: none !important;
            border-radius: 3px !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-weight: 600 !important;
            letter-spacing: 0.02em;
            transition: transform 0.12s ease, filter 0.12s ease;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            filter: brightness(1.12);
            transform: translateY(-1px);
        }}
        .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
        a:focus-visible, input:focus-visible, textarea:focus-visible {{
            outline: 2px solid var(--red-ink) !important;
            outline-offset: 2px;
        }}

        /* ---- Tabs ---- */
        [data-testid="stTabs"] button[role="tab"] {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-dim);
        }}
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
            color: var(--red-ink);
        }}

        /* ---- Verdict stamp ---- */
        .acra-stamp-row {{
            display: flex;
            align-items: center;
            gap: 1.75rem;
            background-color: var(--paper);
            border: 1px solid var(--hairline);
            border-radius: 6px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }}
        .acra-stamp {{
            flex-shrink: 0;
            width: 92px;
            height: 92px;
            border-radius: 50%;
            border: 3px double var(--stamp-color, var(--red-ink));
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transform: rotate(-7deg);
            color: var(--stamp-color, var(--red-ink));
            font-family: 'IBM Plex Mono', monospace;
            animation: acra-stamp-land 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.3);
        }}
        .acra-stamp-score {{ font-size: 1.7rem; font-weight: 700; line-height: 1; }}
        .acra-stamp-max {{ font-size: 0.62rem; letter-spacing: 0.05em; opacity: 0.85; }}
        @keyframes acra-stamp-land {{
            from {{ transform: rotate(-7deg) scale(1.5); opacity: 0; }}
            to {{ transform: rotate(-7deg) scale(1); opacity: 1; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .acra-stamp {{ animation: none; }}
        }}
        .acra-verdict-summary {{ color: var(--text); font-size: 0.95rem; line-height: 1.5; flex: 1; min-width: 240px; }}

        /* ---- Severity badge ---- */
        .acra-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 0.15rem 0.5rem;
            border-radius: 3px;
            border: 1px solid var(--badge-color, var(--text-dim));
            color: var(--badge-color, var(--text-dim));
            background: color-mix(in srgb, var(--badge-color, var(--text-dim)) 12%, transparent);
        }}

        /* ---- Issue card ---- */
        .acra-issue {{
            display: flex;
            border: 1px solid var(--hairline);
            border-left: 4px solid var(--issue-color, var(--text-dim));
            border-radius: 4px;
            background-color: var(--paper);
            margin-bottom: 0.7rem;
            overflow: hidden;
        }}
        .acra-issue-gutter {{
            flex-shrink: 0;
            width: 4.2rem;
            padding: 0.85rem 0.5rem;
            text-align: center;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: var(--text-faint);
            background-color: var(--paper-raised);
            border-right: 1px solid var(--hairline);
        }}
        .acra-issue-body {{ padding: 0.85rem 1rem; flex: 1; min-width: 0; }}
        .acra-issue-title {{ font-weight: 600; color: var(--text); margin: 0 0 0.4rem 0; font-size: 0.95rem; }}
        .acra-issue-meta {{ display: flex; gap: 0.4rem; margin-bottom: 0.55rem; flex-wrap: wrap; }}
        .acra-issue-text {{ color: var(--text-dim); font-size: 0.88rem; line-height: 1.55; margin-bottom: 0.5rem; }}
        .acra-issue-suggestion {{
            font-size: 0.88rem; line-height: 1.55; color: var(--text);
            border-left: 2px solid var(--issue-color, var(--text-dim));
            padding-left: 0.6rem;
        }}

        /* ---- Static analysis table rows ---- */
        .acra-static-row {{
            display: grid;
            grid-template-columns: 3.5rem 5rem 1fr;
            gap: 0.6rem;
            padding: 0.4rem 0.2rem;
            border-bottom: 1px solid var(--hairline);
            font-size: 0.85rem;
            align-items: baseline;
        }}
        .acra-static-row:last-child {{ border-bottom: none; }}
        .acra-static-line {{ font-family: 'IBM Plex Mono', monospace; color: var(--text-faint); }}
        .acra-static-code {{ font-family: 'IBM Plex Mono', monospace; color: var(--red-ink); font-size: 0.78rem; }}
        .acra-static-msg {{ color: var(--text-dim); }}

        .acra-empty {{
            border: 1px dashed var(--hairline);
            border-radius: 6px;
            padding: 2rem 1.2rem;
            text-align: center;
            color: var(--text-faint);
            font-size: 0.9rem;
        }}

        ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: var(--ink); }}
        ::-webkit-scrollbar-thumb {{ background: var(--hairline); border-radius: 5px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-faint); }}
        </style>
        """,
        unsafe_allow_html=True,
    )
