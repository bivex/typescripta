"""Detects High Comment Density — too many comments relative to code indicates unclear code."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector

_COMMENT_TOKEN = re.compile(r"//|/\*|\*")


class CommentDensityDetector(CodeSmellDetector):
    """Flag source files where comments exceed a configurable ratio of code lines."""

    _kind = "comment_density"
    _DEFAULT_THRESHOLD = 0.5

    def __init__(self, comment_threshold: float = _DEFAULT_THRESHOLD) -> None:
        if not 0.0 <= comment_threshold <= 1.0:
            raise ValueError(
                f"comment_threshold must be between 0.0 and 1.0, got {comment_threshold}"
            )
        self._comment_threshold = comment_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        lines = source_unit.content.splitlines()
        if not lines:
            return ()

        comment_lines = 0
        code_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _COMMENT_TOKEN.match(stripped):
                comment_lines += 1
            else:
                code_lines += 1

        total = comment_lines + code_lines
        if total == 0:
            return ()

        ratio = comment_lines / total
        if ratio > self._comment_threshold:
            return (
                CodeSmell(
                    kind=self._kind,
                    message=(
                        f"comment density {ratio:.1%} exceeds threshold "
                        f"{self._comment_threshold:.1%} ({comment_lines}/{total} lines)"
                    ),
                    location=source_unit.location,
                    line=1,
                    column=0,
                ),
            )

        return ()
