"""Tests for RefusedBequestDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.refused_bequest_detector import (
    RefusedBequestDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_without_extends() -> None:
    code = "class Base { greet(): string { return 'hi'; } }"
    smells = RefusedBequestDetector().detect(_u(code))
    assert smells == ()


def test_subclass_without_override_no_smell() -> None:
    code = "class Child extends Base { x: number; }"
    smells = RefusedBequestDetector().detect(_u(code))
    assert smells == ()


def test_override_without_throw_no_smell() -> None:
    code = (
        "class Base { greet(): string { return 'hi'; } }\n"
        "class Child extends Base { override greet(): string { return 'hello'; } }"
    )
    smells = RefusedBequestDetector().detect(_u(code))
    assert smells == ()


def test_override_that_throws_detected() -> None:
    code = (
        "class Base { process(): void {}\n"
        "class Child extends Base { override process(): void { throw new Error('no'); } }"
    )
    smells = RefusedBequestDetector().detect(_u(code))
    assert any(s.kind == "refused_bequest" for s in smells)


def test_empty_source_unit() -> None:
    smells = RefusedBequestDetector().detect(_u(""))
    assert smells == ()
