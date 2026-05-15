"""Tests for DataClumpsDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.data_clumps_detector import DataClumpsDetector


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_clump_when_groups_are_unique() -> None:
    code = "function foo(a, b, c) {}\nfunction bar(d, e, f) {}"
    smells = DataClumpsDetector().detect(_u(code))
    assert smells == ()


def test_repeated_group_detected() -> None:
    code = "function foo(a, b) {}\nfunction bar(a, b) {}"
    smells = DataClumpsDetector().detect(_u(code))
    assert len(smells) >= 1
    assert "a" in smells[0].message and "b" in smells[0].message


def test_clump_kind() -> None:
    smells = DataClumpsDetector().detect(_u("function foo(x, y) {}\nfunction bar(x, y) {}"))
    assert smells[0].kind == "data_clumps"


def test_empty_source_unit_returns_empty() -> None:
    smells = DataClumpsDetector().detect(_u(""))
    assert smells == ()


def test_single_function_returns_empty() -> None:
    smells = DataClumpsDetector().detect(_u("function foo(a, b) {}"))
    assert smells == ()


def test_location_preserved() -> None:
    smells = DataClumpsDetector().detect(_u("function foo(a, b) {}\nfunction bar(a, b) {}"))
    assert smells[0].location == "example.ts"
