# AI Code Review Assistant

A Streamlit app that reviews Python code the way a thorough senior engineer would: it runs Pylint and Flake8 for static analysis, then hands the code — plus those findings, as grounding — to an LLM (OpenAI or Gemini, your choice) for a structured review that finds bugs, flags security and performance issues, and explains *why* each one matters, not just what to change. View the app from here: https://ai-code-review-assistant-clean.streamlit.app/

## Features

- **Two static analyzers, real subprocesses.** Pylint and Flake8 run against your code in an isolated temp directory with a timeout. Neither tool executes the code it's analyzing — see [Security notes](#security-notes).
- **Two AI providers, one schema.** Switch between OpenAI and Gemini per review. Both are constrained to the same structured output (severity, category, line range, explanation, suggestion, optional fixed snippet) via each provider's native structured-output mode — no regex-scraping free-form text.
- **Static analysis grounds the AI pass.** Pylint/Flake8 findings are passed into the prompt as context the model verifies rather than restates, so the AI review adds logic bugs, security issues, and design problems static analyzers can't see, instead of just repeating a linter in prose.
- **Adjustable reasoning depth.** A low/medium/high slider maps to OpenAI's `reasoning.effort` and Gemini's `thinking_level` — spend more compute on code you actually care about, less on a quick pass.
- **Downloadable report.** Every review can be exported as a single self-contained Markdown file (verdict, issues, static analysis tables, and the reviewed source).
- **Never executes your code.** Only static analysis, only in temp directories.

## Getting started

```bash
git clone <your-repo-url>
cd ai-code-review-assistant
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then fill in OPENAI_API_KEY and/or GEMINI_API_KEY in .env
# (or just paste a key into the sidebar at runtime -- either works)

streamlit run app.py
```

Open the URL Streamlit prints (defaults to `http://localhost:8501`). Paste code, click **Load example** to try it with a pre-built buggy snippet, or upload a `.py` file, then **Run review**.

## How it works

```
 code (paste / upload)
        │
        ├──► ast.parse() ── syntax check, fails fast with a precise line/col error
        │
        ├──► Pylint  ──┐
        ├──► Flake8  ──┤  (subprocess, JSON/text output, parsed into StaticIssue)
        │              │
        │              ▼
        └──────► prompt = code + static findings + review instructions
                        │
                        ▼
              OpenAI Responses API  or  Gemini Interactions API
                 (structured output, schema = ReviewResult)
                        │
                        ▼
                 Streamlit renders: verdict stamp, issue cards,
                 static analysis tables, downloadable report
```

## Project structure

```
ai-code-review-assistant/
├── app.py                      # Streamlit entry point / page composition
├── core/
│   ├── models.py                # Pydantic schema shared with the AI structured output
│   ├── static_analysis.py       # Pylint + Flake8 subprocess wrappers and parsers
│   ├── ai_reviewer.py            # Provider abstraction: OpenAIReviewer, GeminiReviewer
│   └── report.py                 # Markdown report builder
├── ui/
│   ├── styles.py                  # Design tokens + injected CSS
│   └── components.py              # Badges, issue cards, the verdict stamp
├── tests/
│   └── test_static_analysis.py    # Runs the real tools against known-buggy snippets
├── .streamlit/config.toml         # Theme
├── requirements.txt
└── .env.example
```

`core/` has no Streamlit import in it — the review pipeline is plain Python and could be driven from a CLI or a different frontend without changes.

## Tech stack

Python 3.10+ · Streamlit · OpenAI (GPT-5.6 family, Responses API) · Gemini (3.x family, Interactions API) · Pylint · Flake8 · Pydantic

Both AI integrations target each provider's *current* recommended entry point as of August 2026 — OpenAI's Responses API (`client.responses.parse`) rather than the older Chat Completions helper, and Gemini's Interactions API (`client.interactions.create`, GA since June 2026) rather than `generateContent`. Model IDs and SDK surfaces move fast; if a model in `core/ai_reviewer.py` (`OPENAI_MODELS` / `GEMINI_MODELS`) gets deprecated, that's the only place you need to update.

## Testing

```bash
pytest tests/ -v
```

The tests run the actual `pylint` and `flake8` binaries against fixed snippets (no mocking), including a check that a snippet designed to `sys.exit()` and write a file never actually does either — confirming the "these tools never execute your code" claim in code, not just in a comment.

There's no automated test for the AI review path, since that requires a live API key and a non-deterministic model response. `core/ai_reviewer.py` is structured so the HTTP-calling code is thin and isolated if you want to add a mocked test later.

## Security notes

- **Static analysis never executes your code.** Pylint (via astroid) and Flake8 (via `ast`/`tokenize`) both build a syntax tree and analyze it; neither calls `exec()` or imports the submitted file as live code. `tests/test_static_analysis.py::test_analyzers_never_execute_the_submitted_code` checks this directly.
- **API keys aren't persisted.** A key typed into the sidebar lives only in that Streamlit session's memory. Nothing is written to disk. Prefer `.env` (gitignored) over pasting keys on a shared machine.
- **This is a single-user local tool, not a multi-tenant service.** If you deploy it somewhere public, put auth in front of it — anyone who can reach the app can spend your API budget.

## Known limitations

- Reviews one file at a time; no cross-file or whole-repository context.
- Static analysis is Pylint + Flake8 only — no type checking (mypy) or dedicated security scanning (Bandit, Semgrep) yet.
- No review history — each session starts clean. Persisting past reviews would need a small database (SQLite is enough) behind `core/`.
- The quality score is model-assigned, not calibrated against a rubric. Treat it as a relative signal, not ground truth.
