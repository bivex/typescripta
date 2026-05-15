"""Tests for FeatureEnvyDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.feature_envy_detector import (
    FeatureEnvyDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_method_using_own_fields_no_smell() -> None:
    code = "\n".join(
        [
            "class Foo {",
            "    private x: number;",
            "    getX(): number { return this.x; }",
            "}",
        ]
    )
    smells = FeatureEnvyDetector().detect(_u(code))
    assert smells == ()


def test_method_accessing_others_envy_detected() -> None:
    code = "\n".join(
        [
            "class Foo {",
            "    compute(other: Bar): void {",
            "        const a = other.name;",
            "        const b = other.value;",
            "        const c = other.label;",
            "        const d = other.title;",
            "        const e = other.count;",
            "        const f = other.score;",
            "    }",
            "}",
        ]
    )
    smells = FeatureEnvyDetector(other_field_threshold=3).detect(_u(code))
    assert any(s.kind == "feature_envy" for s in smells)


def test_empty_source_unit() -> None:
    smells = FeatureEnvyDetector().detect(_u(""))
    assert smells == ()


def test_kind_is_feature_envy() -> None:
    envy_code = "\n".join(
        [
            "class X {",
            "    convert(other: Y): string {",
            "        return other.label + other.title + other.code + other.id;",
            "    }",
            "}",
        ]
    )
    smells = FeatureEnvyDetector(other_field_threshold=3).detect(_u(envy_code))
    assert smells[0].kind == "feature_envy"


def test_location_preserved() -> None:
    code = (
        "class X { m(o: Y): void { const a = o.x; const b = o.y; const c = o.z; const d = o.w; } }"
    )
    smells = FeatureEnvyDetector().detect(_u(code))
    assert smells[0].location == "example.ts"
