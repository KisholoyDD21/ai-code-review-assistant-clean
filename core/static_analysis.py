"""Runs Pylint and Flake8 against submitted code and parses their output.

Both tools are invoked as subprocesses against a file written to a fresh
temporary directory, rather than imported and run in-process. Two reasons:

1. Isolation. A subprocess with a timeout can't wedge the Streamlit server,
   and each run starts from a clean interpreter instead of sharing astroid's
   caches across requests.
2. Neither tool executes the code it's analyzing -- both build an AST
   (astroid for Pylint, ast/tokenize for Flake8's pyflakes/pycodestyle) and
   never call exec() or import the submitted file as live code. That's what
   makes it safe to run either one against arbitrary, untrusted input.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT_SECONDS = 30

# Matches Flake8's default output: "path:line:col: CODE message"
_FLAKE8_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>\S+) (?P<text>.*)$")

# Pylint message types, in the order they're worth reading.
_PYLINT_TYPE_ORDER = {"fatal": 0, "error": 1, "warning": 2, "refactor": 3, "convention": 4}


@dataclass
class StaticIssue:
    """A single finding from a static analysis tool."""

    line: int
    column: int
    code: str
    message: str
    symbol: str = ""
    issue_type: str = ""  # pylint: convention/refactor/warning/error/fatal


@dataclass
class StaticAnalysisResult:
    """The outcome of running one static analysis tool over the submitted code."""

    tool: str
    ran_successfully: bool
    issues: list[StaticIssue] = field(default_factory=list)
    error_message: str = ""

    @property
    def issue_count(self) -> int:
        return len(self.issues)


def _write_temp_module(code: str, tmpdir: str) -> Path:
    file_path = Path(tmpdir) / "submission.py"
    file_path.write_text(code, encoding="utf-8")
    return file_path


def run_pylint(code: str, timeout: int = TIMEOUT_SECONDS) -> StaticAnalysisResult:
    """Run Pylint on `code` and return its findings.

    Uses `--output-format=json` so stdout is a pure JSON array -- no report
    banner or score line to strip out. Pylint's exit code is a bitmask of
    which message categories fired (not a crash signal), so success is
    judged by whether stdout parsed as JSON, not by the return code.
    """
    with tempfile.TemporaryDirectory(prefix="acra_pylint_") as tmpdir:
        file_path = _write_temp_module(code, tmpdir)
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pylint",
                    "--output-format=json",
                    "--disable=C0114",  # missing-module-docstring: noise for a pasted snippet
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return StaticAnalysisResult("Pylint", False, error_message=f"Pylint timed out after {timeout}s.")
        except FileNotFoundError:
            return StaticAnalysisResult("Pylint", False, error_message="Pylint isn't installed in this environment.")

        try:
            raw_issues = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            detail = (proc.stderr or proc.stdout or "unknown error").strip()[:500]
            return StaticAnalysisResult("Pylint", False, error_message=f"Pylint produced unreadable output: {detail}")

        issues = [
            StaticIssue(
                line=item.get("line", 0),
                column=item.get("column", 0),
                code=item.get("message-id", ""),
                message=item.get("message", ""),
                symbol=item.get("symbol", ""),
                issue_type=item.get("type", ""),
            )
            for item in raw_issues
        ]
        issues.sort(key=lambda i: (_PYLINT_TYPE_ORDER.get(i.issue_type, 9), i.line))
        return StaticAnalysisResult("Pylint", True, issues=issues)


def run_flake8(code: str, timeout: int = TIMEOUT_SECONDS) -> StaticAnalysisResult:
    """Run Flake8 on `code` and return its findings.

    Flake8 has no built-in JSON formatter, so this parses its well-defined
    default text format (`path:line:col: CODE message`) with a regex. Exit
    code 1 means "issues found", not a crash -- only a genuine subprocess
    failure or unparseable output is treated as an error here.
    """
    with tempfile.TemporaryDirectory(prefix="acra_flake8_") as tmpdir:
        file_path = _write_temp_module(code, tmpdir)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "flake8", str(file_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return StaticAnalysisResult("Flake8", False, error_message=f"Flake8 timed out after {timeout}s.")
        except FileNotFoundError:
            return StaticAnalysisResult("Flake8", False, error_message="Flake8 isn't installed in this environment.")

        if proc.returncode not in (0, 1):
            detail = (proc.stderr or "unknown error").strip()[:500]
            return StaticAnalysisResult("Flake8", False, error_message=f"Flake8 failed to run: {detail}")

        issues: list[StaticIssue] = []
        for line in proc.stdout.splitlines():
            match = _FLAKE8_LINE_RE.match(line)
            if not match:
                continue
            issues.append(
                StaticIssue(
                    line=int(match.group("line")),
                    column=int(match.group("col")),
                    code=match.group("code"),
                    message=match.group("text"),
                )
            )
        return StaticAnalysisResult("Flake8", True, issues=issues)


def format_static_context(results: list[StaticAnalysisResult]) -> str:
    """Render static analysis results as compact text for the AI prompt."""
    blocks = []
    for result in results:
        if not result.ran_successfully:
            continue
        if not result.issues:
            blocks.append(f"{result.tool}: no findings.")
            continue
        lines = [f"{result.tool} ({result.issue_count} finding{'s' if result.issue_count != 1 else ''}):"]
        for issue in result.issues[:60]:  # keep the prompt bounded on very messy files
            label = issue.symbol or issue.code
            lines.append(f"- L{issue.line}: [{issue.code}] {label}: {issue.message}")
        if result.issue_count > 60:
            lines.append(f"- ...and {result.issue_count - 60} more.")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
