"""Tests for TemporaryFieldDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.temporary_field_detector import (
    TemporaryFieldDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_smell_on_simple_class() -> None:
    code = "class Foo { name: string; }"
    smells = TemporaryFieldDetector().detect(_u(code))
    assert smells == ()


def test_empty_class_with_field() -> None:
    code = "class Foo { name: string; }"
    smells = TemporaryFieldDetector().detect(_u(code))
    assert smells == ()


def test_location_preserved() -> None:
    code = "class Foo { name: string; }"
    smells = TemporaryFieldDetector().detect(_u(code))
    for smell in smells:
        assert smell.location == "example.ts"


def test_empty_source_unit() -> None:
    smells = TemporaryFieldDetector().detect(_u(""))
    assert smells == ()
