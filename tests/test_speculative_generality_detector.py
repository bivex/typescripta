"""Tests for SpeculativeGeneralityDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.speculative_generality_detector import (
    SpeculativeGeneralityDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_on_normal_code() -> None:
    smells = SpeculativeGeneralityDetector().detect(_u("function foo() { return 1; }"))
    assert smells == ()


def test_empty_interface_detected() -> None:
    smells = SpeculativeGeneralityDetector().detect(_u("interface Placeholder {}"))
    assert any(s.kind == "speculative_generality" for s in smells)


def test_throw_not_implemented_detected() -> None:
    smells = SpeculativeGeneralityDetector().detect(
        _u("function stub() { throw new Error('Not implemented'); }")
    )
    assert any(s.kind == "speculative_generality" for s in smells)


def test_comment_lines_ignored() -> None:
    smells = SpeculativeGeneralityDetector().detect(_u("// throw new Error()\nfunction foo() {}"))
    assert smells == ()


def test_empty_class_detected() -> None:
    smells = SpeculativeGeneralityDetector().detect(_u("class Empty {}"))
    assert len(smells) >= 1


def test_location_preserved() -> None:
    smells = SpeculativeGeneralityDetector().detect(_u("interface Unused {}"))
    assert smells[0].location == "example.ts"
