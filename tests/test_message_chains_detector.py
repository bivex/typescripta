"""Tests for MessageChainsDetector."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit, SourceUnitId
from typescripta.infrastructure.smells.message_chains_detector import (
    MessageChainsDetector,
)


def _u(content: str) -> SourceUnit:
    return SourceUnit(
        identifier=SourceUnitId("example.ts"),
        location="example.ts",
        content=content,
    )


def test_short_chain_passes() -> None:
    smells = MessageChainsDetector(chain_threshold=3).detect(_u("const x = obj.a.b;"))
    assert smells == ()


def test_long_chain_detected() -> None:
    smells = MessageChainsDetector(chain_threshold=3).detect(_u("const x = a.b.c.d;"))
    assert len(smells) == 1
    assert smells[0].kind == "message_chain"


def test_custom_threshold() -> None:
    smells = MessageChainsDetector(chain_threshold=1).detect(_u("const x = a.b;"))
    assert len(smells) == 1


def test_chain_in_comment_ignored() -> None:
    smells = MessageChainsDetector().detect(_u("// a.b.c.d\nconst x = 1;"))
    assert smells == ()


def test_empty_source_unit() -> None:
    smells = MessageChainsDetector().detect(_u(""))
    assert smells == ()


def test_smell_location() -> None:
    smells = MessageChainsDetector().detect(_u("const x = a.b.c.d;"))
    assert smells[0].location == "example.ts"
    assert smells[0].line >= 1
