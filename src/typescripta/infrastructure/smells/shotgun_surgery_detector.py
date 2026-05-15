"""Detects Shotgun Surgery — a change requires touching many small, unrelated classes."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


class ShotgunSurgeryDetector(CodeSmellDetector):
    """Flag files with many unrelated top-level declarations of the same type."""

    _kind = "shotgun_surgery"

    _DECL_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
        ("class", re.compile(r"^class\s+")),
        ("export_interface", re.compile(r"^export\s+interface\s+")),
        ("export_type", re.compile(r"^export\s+type\s+")),
        ("function", re.compile(r"^function\s+")),
        ("export_function", re.compile(r"^export\s+(async\s+)?function\s+")),
        ("enum", re.compile(r"^enum\s+")),
    )

    def __init__(self, class_threshold: int = 8) -> None:
        self._class_threshold = class_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        top_level_counts: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ", "///")):
                continue
            if stripped.startswith(("export ", "import ", "declare ", "abstract ", "interface ")):
                pass
            for label, pattern in self._DECL_PATTERNS:
                if pattern.match(stripped):
                    top_level_counts[label] = top_level_counts.get(label, 0) + 1

        for label, count in top_level_counts.items():
            if count >= self._class_threshold:
                smells.append(
                    CodeSmell(
                        kind=self._kind,
                        message=(
                            f"{count} unrelated top-level {label}s in one file — "
                            f"changes will ripple across many small units (shotgun surgery)"
                        ),
                        location=source_unit.location,
                        line=1,
                        column=0,
                    )
                )

        return tuple(smells)
