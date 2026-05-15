"""Tests for DivergentChangeDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.divergent_change_detector import (
    DivergentChangeDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_focused_module() -> None:
    code = "function validateEmail(email: string) { return true; }"
    smells = DivergentChangeDetector(reason_threshold=5).detect(_u(code))
    assert smells == ()


def test_divergent_change_detected() -> None:
    code = (
        "function validate(s) { return true; }\n"
        "function save(data) { return true; }\n"
        "function render() { return ''; }\n"
        "function compute(x) { return x + 1; }\n"
        "function format(value) { return value; }"
    )
    smells = DivergentChangeDetector(reason_threshold=3).detect(_u(code))
    assert any(s.kind == "divergent_change" for s in smells)


def test_empty_source() -> None:
    smells = DivergentChangeDetector().detect(_u(""))
    assert smells == ()


def test_custom_threshold() -> None:
    code = """
        function validate(s) { return true; }
        function save(data) { return true; }
    """
    smells = DivergentChangeDetector(reason_threshold=5).detect(_u(code))
    assert smells == ()


def test_location_ok() -> None:
    smells = DivergentChangeDetector().detect(_u("function x(a) {}"))
    for smell in smells:
        assert smell.location == "example.ts"
