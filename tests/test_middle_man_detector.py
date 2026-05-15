"""Tests for MiddleManDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.middle_man_detector import MiddleManDetector


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_non_delegating_method() -> None:
    code = "function compute(x: number) { return x * 2; }"
    smells = MiddleManDetector().detect(_u(code))
    assert smells == ()


def test_delegating_method_detected() -> None:
    code = "function getValue() { return this.value; }"
    smells = MiddleManDetector().detect(_u(code))
    assert len(smells) == 1
    assert smells[0].kind == "middle_man"


def test_comment_ignored() -> None:
    smells = MiddleManDetector().detect(_u("// return other.doWork();\nfunction foo() {}"))
    assert smells == ()


def test_empty_source_unit() -> None:
    smells = MiddleManDetector().detect(_u(""))
    assert smells == ()


def test_location_set() -> None:
    smells = MiddleManDetector().detect(_u("function getValue() { return this.value; }"))
    assert smells[0].location == "example.ts"
