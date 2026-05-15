"""Tests for PrimitiveObsessionDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.primitive_obsession_detector import (
    PrimitiveObsessionDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_on_clean_code() -> None:
    code = "const x = computeValue();"
    smells = PrimitiveObsessionDetector().detect(_u(code))
    assert smells == ()


def test_magic_boolean_detected() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("if (true) { console.log('hi'); }"))
    assert any(s.kind == "primitive_obsession" for s in smells)


def test_magic_zero_detected() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("if (count == 0) {}"))
    assert any(s.kind == "primitive_obsession" for s in smells)


def test_string_literal_number_detected() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("const s = '123.45';"))
    assert any(s.kind == "primitive_obsession" for s in smells)


def test_comment_lines_ignored() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("// if (true) {}\nconst x = 1;"))
    assert smells == ()


def test_kind_correct() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("if (true) {}\nif (false) {}"))
    for smell in smells:
        assert smell.kind == "primitive_obsession"


def test_location_set() -> None:
    smells = PrimitiveObsessionDetector().detect(_u("if (true) {}"))
    assert smells[0].location == "example.ts"
