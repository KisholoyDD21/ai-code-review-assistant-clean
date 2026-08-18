"""AI-powered code review, backed by either OpenAI or Gemini.

Both providers are driven through their current structured-output surface
so the model's reply is constrained to the `ReviewResult` schema in
`core.models` and comes back as a parsed, validated object rather than text
to hand-parse:

- OpenAI: the Responses API's `.parse()` helper (`client.responses.parse`),
  passing `ReviewResult` directly as `text_format`.
- Gemini: the Interactions API (`client.interactions.create`), passing the
  model's JSON schema via `response_format`.

Verified directly against the installed `openai` (3.2.0) and `google-genai`
(2.18.1) packages -- see README for details. If you're on materially older
versions of either SDK, upgrade rather than adapting this code downward;
both providers moved their recommended entry point in the last year.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import ValidationError

from core.models import ReviewResult

SYSTEM_PROMPT = """\
You are a senior Python engineer conducting a thorough, honest code review. \
You review for correctness, security, performance, readability, and idiomatic Python style.

For every issue you report:
- Give the exact 1-indexed line range where it occurs.
- Classify its severity (critical/high/medium/low/info) based on real-world impact, not style \
pedantry dressed up as urgency.
- Classify its category (bug/security/performance/style/best_practice/maintainability).
- Explain WHY it's a problem in a way that teaches the underlying principle, not just a restatement \
of what's wrong.
- Give a concrete, specific suggestion. Include a short corrected code snippet only when it \
clarifies the fix; leave fixed_code empty otherwise.

You may be given findings from Pylint and/or Flake8 as additional context. Treat them as a starting \
point, not a checklist to restate: verify them against the actual code, add your own independent \
findings (especially logic bugs, security issues, and design problems static analyzers can't see), \
and feel free to note if a static-analysis finding is a false positive or a low-value nitpick.

Be honest and specific to this code. If the code is genuinely solid, say so plainly and keep the \
issues list short rather than inventing problems to fill space. Don't pad the review with generic \
Python trivia that doesn't apply to what's actually in front of you.
"""


class ReviewError(RuntimeError):
    """Raised when an AI review call fails in a way the UI should explain to the user."""


@dataclass(frozen=True)
class ModelChoice:
    id: str
    label: str
    blurb: str


# Current as of August 2026. OpenAI's GPT-5.6 family (Sol/Terra/Luna) is the
# flagship generation; Gemini's is 3.7/3.6/3.5/3.1. Both APIs 404 cleanly on
# a retired model ID, so if these have moved on, the sidebar error message
# will say so -- update the id here and everything else keeps working.
OPENAI_MODELS: list[ModelChoice] = [
    ModelChoice("gpt-5.6-terra", "GPT-5.6 Terra — recommended", "Balances intelligence and cost. Good default for most reviews."),
    ModelChoice("gpt-5.6-sol", "GPT-5.6 Sol — deepest", "OpenAI's frontier model. Slower and pricier; best for complex or security-critical code."),
    ModelChoice("gpt-5.6-luna", "GPT-5.6 Luna — fastest", "Optimized for cost and speed on high-volume, simpler reviews."),
]

GEMINI_MODELS: list[ModelChoice] = [
    ModelChoice("gemini-3.7-flash", "Gemini 3.7 Flash — recommended", "Google's latest workhorse model, tuned for coding and agentic workflows."),
    ModelChoice("gemini-3.1-pro-preview", "Gemini 3.1 Pro — deepest", "Google's strongest reasoning model. Slower; best for complex or security-critical code."),
    ModelChoice("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite — fastest", "Lightweight and cheap for quick, high-volume reviews."),
]

REASONING_EFFORTS = ["low", "medium", "high"]
MAX_OUTPUT_TOKENS = 8000


def build_user_prompt(code: str, filename: str, static_context: str) -> str:
    parts = [f"Review the following Python file (`{filename}`).", "", "```python", code, "```"]
    if static_context:
        parts += ["", "Static analysis findings for additional context (verify, don't just restate):", static_context]
    return "\n".join(parts)


class AIReviewer(ABC):
    """Common interface both providers implement."""

    provider_name: str = "AI"

    def __init__(self, api_key: str, model: str, reasoning_effort: str = "medium") -> None:
        if not api_key or not api_key.strip():
            raise ReviewError(f"No {self.provider_name} API key was provided.")
        self.api_key = api_key.strip()
        self.model = model
        self.reasoning_effort = reasoning_effort if reasoning_effort in REASONING_EFFORTS else "medium"

    @abstractmethod
    def review(self, code: str, filename: str, static_context: str) -> ReviewResult:
        """Run a review and return a validated ReviewResult, or raise ReviewError."""


class OpenAIReviewer(AIReviewer):
    provider_name = "OpenAI"

    def review(self, code: str, filename: str, static_context: str) -> ReviewResult:
        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AuthenticationError,
                OpenAI,
                RateLimitError,
            )
        except ImportError as exc:
            raise ReviewError("The `openai` package isn't installed. Run `pip install openai`.") from exc

        client = OpenAI(api_key=self.api_key)
        user_prompt = build_user_prompt(code, filename, static_context)

        try:
            response = client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text_format=ReviewResult,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
        except AuthenticationError as exc:
            raise ReviewError("OpenAI rejected the API key. Double-check it in the sidebar.") from exc
        except RateLimitError as exc:
            raise ReviewError("OpenAI rate-limited this request. Wait a moment and try again.") from exc
        except APITimeoutError as exc:
            raise ReviewError("The request to OpenAI timed out. Try again, or switch to a faster model.") from exc
        except APIConnectionError as exc:
            raise ReviewError(f"Couldn't reach OpenAI: {exc}") from exc
        except APIStatusError as exc:
            raise ReviewError(f"OpenAI API error ({exc.status_code}): {exc.message}") from exc

        if response.status == "incomplete":
            reason = getattr(response.incomplete_details, "reason", "unknown reason")
            raise ReviewError(f"The response was cut off ({reason}). Try a smaller file.")

        parsed = response.output_parsed
        if parsed is None:
            raise ReviewError(
                "OpenAI didn't return a structured review (it may have refused the request). "
                "Try again or switch providers."
            )
        return parsed


class GeminiReviewer(AIReviewer):
    provider_name = "Gemini"

    def review(self, code: str, filename: str, static_context: str) -> ReviewResult:
        try:
            from google import genai
            from google.genai import errors as genai_errors
        except ImportError as exc:
            raise ReviewError("The `google-genai` package isn't installed. Run `pip install google-genai`.") from exc

        client = genai.Client(api_key=self.api_key)
        user_prompt = build_user_prompt(code, filename, static_context)

        try:
            interaction = client.interactions.create(
                model=self.model,
                system_instruction=SYSTEM_PROMPT,
                input=user_prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ReviewResult.model_json_schema(),
                },
                generation_config={
                    "thinking_level": self.reasoning_effort,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
        except genai_errors.ClientError as exc:
            raise ReviewError(f"Gemini rejected the request (check your API key): {exc}") from exc
        except genai_errors.ServerError as exc:
            raise ReviewError(f"Gemini's servers had an error: {exc}") from exc
        except genai_errors.APIError as exc:
            raise ReviewError(f"Gemini API error: {exc}") from exc

        if interaction.status != "completed":
            detail_parts = [e.message for e in (interaction.errors or []) if getattr(e, "message", None)]
            detail = "; ".join(detail_parts) or interaction.status
            raise ReviewError(f"Gemini didn't complete the review ({detail}).")

        if not interaction.output_text:
            raise ReviewError("Gemini returned an empty response. Try again or switch providers.")

        try:
            return ReviewResult.model_validate_json(interaction.output_text)
        except ValidationError as exc:
            raise ReviewError(f"Gemini's response didn't match the expected structure: {exc}") from exc


PROVIDERS = {
    "OpenAI": {"reviewer": OpenAIReviewer, "models": OPENAI_MODELS},
    "Gemini": {"reviewer": GeminiReviewer, "models": GEMINI_MODELS},
}
