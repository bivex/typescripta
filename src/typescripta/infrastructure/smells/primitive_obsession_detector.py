"""Detects Primitive Obsession — overuse of primitive types for domain concepts."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


class PrimitiveObsessionDetector(CodeSmellDetector):
    """Flag excessive use of primitive-like patterns where objects would be better."""

    _kind = "primitive_obsession"

    # numeric/time patterns using strings for values that belong in a domain type
    _PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
        (
            "string-literal-date",
            re.compile(
                r"""['"]\d{4}-\d{2}-\d{2}['"]|['"]\d{2}/\d{2}/\d{4}['"]""",
            ),
        ),
        (
            "string-literal-number",
            re.compile(r"""['"][-+]?\d+\.?\d*['"]\s*(?:[=+\-*/]|[,;)])"""),
        ),
        (
            "magic-boolean",
            re.compile(r"if\s*\(\s*(?:true|false)\s*\)"),
        ),
        (
            "magic-zero",
            re.compile(r"==\s*0|==\s*0n|===\s*0|===\s*0n"),
        ),
    )

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ", "///")):
                continue
            for label, pattern in self._PATTERNS:
                if pattern.search(stripped):
                    smells.append(
                        CodeSmell(
                            kind=self._kind,
                            message=f"possible primitive obsession ({label}): {stripped.strip()}",
                            location=source_unit.location,
                            line=line_idx,
                            column=0,
                        )
                    )

        return tuple(smells)
