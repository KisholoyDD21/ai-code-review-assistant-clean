"""Tests for core.static_analysis.

These exercise the real `pylint` and `flake8` subprocesses (no mocking) so a
green run means the JSON/text parsing actually matches what the installed
tool versions emit, not just what the docs say they emit.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.static_analysis import format_static_context, run_flake8, run_pylint  # noqa: E402

BUGGY_CODE = """\
import os
import json

def add_item(item, items=[]):
    items.append(item)
    return items
"""

CLEAN_CODE = '''\
"""A trivially clean module."""


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b
'''

SIDE_EFFECT_MARKER = "/tmp/acra_side_effect_marker_should_never_exist.txt"

DANGEROUS_CODE = f"""\
with open("{SIDE_EFFECT_MARKER}", "w") as f:
    f.write("if you can read this, the linter executed the file")
import sys
sys.exit(1)
"""


def test_pylint_finds_dangerous_default_value():
    result = run_pylint(BUGGY_CODE)
    assert result.ran_successfully
    symbols = {issue.symbol for issue in result.issues}
    assert "dangerous-default-value" in symbols
    assert "unused-import" in symbols


def test_flake8_finds_unused_imports():
    result = run_flake8(BUGGY_CODE)
    assert result.ran_successfully
    codes = {issue.code for issue in result.issues}
    assert "F401" in codes
    # Both unused imports should be reported, on the lines they're declared.
    lines = {issue.line for issue in result.issues if issue.code == "F401"}
    assert lines == {1, 2}


def test_clean_code_has_no_findings():
    pylint_result = run_pylint(CLEAN_CODE)
    flake8_result = run_flake8(CLEAN_CODE)
    assert pylint_result.ran_successfully and pylint_result.issues == []
    assert flake8_result.ran_successfully and flake8_result.issues == []


def test_analyzers_never_execute_the_submitted_code():
    """Pylint and Flake8 must stay static: analyzing code that would exit
    the process or write a file must not actually do either."""
    if os.path.exists(SIDE_EFFECT_MARKER):
        os.remove(SIDE_EFFECT_MARKER)

    pylint_result = run_pylint(DANGEROUS_CODE)
    flake8_result = run_flake8(DANGEROUS_CODE)

    assert pylint_result.ran_successfully
    assert flake8_result.ran_successfully
    assert not os.path.exists(SIDE_EFFECT_MARKER), "static analysis executed the submitted code"


def test_format_static_context_reads_reasonably():
    pylint_result = run_pylint(BUGGY_CODE)
    flake8_result = run_flake8(BUGGY_CODE)
    context = format_static_context([pylint_result, flake8_result])
    assert "Pylint" in context
    assert "Flake8" in context
    assert "dangerous-default-value" in context


def test_syntax_error_reported_not_crashed():
    result = run_pylint("def broken(:\n    pass\n")
    assert result.ran_successfully
    assert any(issue.issue_type in ("error", "fatal") for issue in result.issues)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
