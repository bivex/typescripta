"""Tests for SwitchStatementsDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.switch_statements_detector import (
    SwitchStatementsDetector,
)


def _source(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_clean_switch_no_smell() -> None:
    src = _source("switch (x) { case 1: break; case 2: break; }")
    smells = SwitchStatementsDetector(case_threshold=5).detect(src)
    assert smells == ()


def test_too_many_cases_detected() -> None:
    cases = " ".join(f"case {i}: break;" for i in range(10))
    src = _source(f"switch (x) {{ {cases} }}")
    smells = SwitchStatementsDetector(case_threshold=5).detect(src)
    assert len(smells) == 1
    assert smells[0].kind == "switch_statements"


def test_custom_threshold() -> None:
    cases = " ".join(f"case {i}: break;" for i in range(3))
    src = _source(f"switch (x) {{ {cases} }}")
    smells = SwitchStatementsDetector(case_threshold=2).detect(src)
    assert len(smells) == 1


def test_no_switch_returns_empty() -> None:
    src = _source("const x = 1;")
    smells = SwitchStatementsDetector().detect(src)
    assert smells == ()


def test_smell_has_correct_location() -> None:
    cases = " ".join(f"case {i}: break;" for i in range(10))
    src = _source(f"switch (x) {{ {cases} }}")
    smell = SwitchStatementsDetector(case_threshold=5).detect(src)[0]
    assert smell.location == "example.ts"
    assert smell.line >= 1
