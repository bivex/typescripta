"""Tests for ShotgunSurgeryDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.shotgun_surgery_detector import (
    ShotgunSurgeryDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_no_small_file() -> None:
    code = "class Foo {}\nclass Bar {}"
    smells = ShotgunSurgeryDetector(class_threshold=8).detect(_u(code))
    assert smells == ()


def test_many_classes_detected() -> None:
    classes = "\n".join(f"class Cls{i} {{}}" for i in range(10))
    smells = ShotgunSurgeryDetector(class_threshold=8).detect(_u(classes))
    assert any(s.kind == "shotgun_surgery" for s in smells)


def test_comments_ignored() -> None:
    code = "\n".join(f"class Cls{i} {{}}" for i in range(10))
    smells = ShotgunSurgeryDetector(class_threshold=8).detect(_u("// class\n" + code))
    assert any(s.kind == "shotgun_surgery" for s in smells)


def test_custom_threshold() -> None:
    code = "\n".join(f"class Cls{i} {{}}" for i in range(5))
    smells = ShotgunSurgeryDetector(class_threshold=4).detect(_u(code))
    assert any(s.kind == "shotgun_surgery" for s in smells)


def test_location_preserved() -> None:
    code = "\n".join(f"class Cls{i} {{}}" for i in range(10))
    smell = ShotgunSurgeryDetector(class_threshold=8).detect(_u(code))[0]
    assert smell.location == "example.ts"
