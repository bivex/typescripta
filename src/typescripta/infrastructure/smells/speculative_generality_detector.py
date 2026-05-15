"""Detects Speculative Generality — unused overrides, not-yet-needed abstractions."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


class SpeculativeGeneralityDetector(CodeSmellDetector):
    """Flag empty interfaces, empty override blocks, and not-yet-implemented stubs."""

    _kind = "speculative_generality"

    _STUB_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
        ("empty_interface", re.compile(r"interface\s+\w+\s*\{\s*\}")),
        ("empty_class", re.compile(r"class\s+\w+\s*\{\s*\}")),
        (
            "throw_not_implemented",
            re.compile(r"throw\s+(?:new\s+)?(?:Error|NotImplementedError|TODO)"),
        ),
        ("pass_body", re.compile(r"\{\s*pass\s*\}")),
        ("abstract_single_override", re.compile(r"abstract\s+\w+")),
    )

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ")):
                continue
            for label, pattern in self._STUB_PATTERNS:
                if pattern.search(stripped):
                    smells.append(
                        CodeSmell(
                            kind=self._kind,
                            message=f"speculative generality ({label}): {stripped.strip()}",
                            location=source_unit.location,
                            line=line_idx,
                            column=0,
                        )
                    )

        return tuple(smells)
