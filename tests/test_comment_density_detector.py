"""Tests for CommentDensityDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.comment_density_detector import (
    CommentDensityDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_clean_code_passes_default_threshold() -> None:
    code = "function foo(a: number): number { return a * 2; }"
    smells = CommentDensityDetector(comment_threshold=0.5).detect(_u(code))
    assert smells == ()


def test_all_comments_detected() -> None:
    lines = "\n".join(f"// comment {i}" for i in range(10))
    smells = CommentDensityDetector(comment_threshold=0.5).detect(_u(lines))
    assert len(smells) == 1
    assert smells[0].kind == "comment_density"


def test_empty_source_unit() -> None:
    smells = CommentDensityDetector().detect(_u(""))
    assert smells == ()


def test_location_set() -> None:
    smells = CommentDensityDetector().detect(_u("// l1\n// l2\n// l3\ncode = 1;\n"))
    assert smells[0].location == "example.ts"


def test_high_density_above_default_threshold() -> None:
    smells = CommentDensityDetector().detect(_u("// a\n// b\n// c\n"))
    assert len(smells) >= 1


def test_custom_threshold_high_doesnt_trigger() -> None:
    # density 1/3 ≈ 0.33 is not > 0.9
    smells = CommentDensityDetector(comment_threshold=0.9).detect(_u("doThing(); // a comment\n"))
    assert smells == ()


def test_invalid_threshold_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        CommentDensityDetector(comment_threshold=1.5)
