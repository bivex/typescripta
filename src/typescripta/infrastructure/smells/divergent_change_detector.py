"""Detects Divergent Change — a class or module changed for different reasons."""

from __future__ import annotations

from collections import Counter

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


_REASON_KEYWORDS: dict[str, tuple[str, ...]] = {
    "validation": ("validate", "sanitize", "escape", "check", "assert"),
    "persistence": ("save", "load", "fetch", "serialize", "deserialize", "store"),
    "ui": ("render", "display", "show", "view", "component"),
    "business_logic": ("compute", "calculate", "determine", "process", "derive"),
    "utility": ("format", "parse", "split", "join", "replace"),
}


class DivergentChangeDetector(CodeSmellDetector):
    """Flag files whose functions or methods span too many different reason categories."""

    _kind = "divergent_change"
    _DEFAULT_THRESHOLD = 3

    def __init__(self, reason_threshold: int = _DEFAULT_THRESHOLD) -> None:
        self._reason_threshold = reason_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()
        counter: Counter[str] = Counter()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ")):
                continue
            matched = _categorise_line(stripped)
            counter.update(matched)

        active_reasons = [r for r, c in counter.items() if c > 0]
        if len(active_reasons) > self._reason_threshold:
            smells.append(
                CodeSmell(
                    kind=self._kind,
                    message=(
                        f"module touches {len(active_reasons)} distinct reason areas "
                        f"({', '.join(active_reasons)}) — possible divergent change"
                    ),
                    location=source_unit.location,
                    line=1,
                    column=0,
                )
            )

        return tuple(smells)


def _categorise_line(line: str) -> list[str]:
    matched: list[str] = []
    for reason, keywords in _REASON_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", line, re.IGNORECASE):
                matched.append(reason)
                break
    return matched
