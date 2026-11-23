"""Privacy and terms information for the AI Code Review Assistant."""
from __future__ import annotations

import streamlit as st

from ui.components import render_eyebrow, render_hero
from ui.styles import inject_global_styles

st.set_page_config(
    page_title="Privacy & Terms · AI Code Review Assistant",
    page_icon="\U0001f40d",
    layout="wide",
)
inject_global_styles()
render_hero()

st.title("Privacy & Terms")
st.caption("A plain-language summary of how this app handles source code and AI-assisted reviews.")

st.subheader("Privacy")
st.markdown(
    """
**Source code and AI providers.** Pylint and Flake8 analyze submitted source on the app server.
When you run an AI review, the source code and selected static-analysis findings are sent to the
provider you selected (OpenAI or Google Gemini) so it can produce a review. Do not submit code
unless you are authorized to share it with that provider.

**API credentials.** The app reads provider keys from server environment variables or Streamlit
secrets. It does not provide a browser field for entering or revealing API keys. Never commit
credentials to the repository.

**Session data.** Review results and submitted source are held in the active Streamlit session to
render results and reports. This app does not implement a review-history database. The hosting
platform may process technical or operational data under its own policies; consult the policies of
your host and selected AI provider for details about their handling and retention.

**Your choices.** You can use static analysis without configuring an AI provider. AI requests are
made only when you run a review with a provider key configured.
"""
)

st.subheader("Terms of use")
st.markdown(
    """
- Use the app only with code you have permission to analyze and share with the configured provider.
- AI-generated findings and suggested fixes may be incomplete or incorrect. Review and test changes
  yourself before relying on them.
- This tool is provided as-is, without a guarantee of availability, accuracy, or fitness for a
  particular purpose. You are responsible for decisions made using its output.
- You are responsible for API usage and any charges incurred through your configured provider
  credentials.
- Do not use a public deployment for confidential code unless you trust and control its hosting,
  access controls, and provider configuration.
"""
)

st.caption(
    "This page is an informational summary, not legal advice. If you deploy this app as a service, "
    "have the applicable privacy notice and terms reviewed for your use case and jurisdiction."
)
