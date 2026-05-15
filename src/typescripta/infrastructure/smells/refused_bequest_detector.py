"""Detects Refused Bequest — a subclass inherits but ignores or rejects parent behaviour."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


_OVERRIDE_PATTERN = re.compile(r"override\s+\w+")
_THROW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"throw\s+new\s+\w*Error"),
    re.compile(r"throw\s+Error"),
    re.compile(r"throw\s+\w+"),
)


class RefusedBequestDetector(CodeSmellDetector):
    """Flag child classes that override parent methods but immediately throw."""

    _kind = "refused_bequest"

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        general_override = False

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ")):
                continue

            if stripped.startswith("class "):
                general_override = "extends" in stripped

            if general_override and _OVERRIDE_PATTERN.search(stripped):
                if _is_refusal_body(stripped):
                    smells.append(
                        CodeSmell(
                            kind=self._kind,
                            message="overridden method in subclass immediately throws — "
                            "refused bequest from parent",
                            location=source_unit.location,
                            line=line_idx,
                            column=0,
                        )
                    )

        return tuple(smells)


def _is_refusal_body(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.search(stripped) for pattern in _THROW_PATTERNS)
