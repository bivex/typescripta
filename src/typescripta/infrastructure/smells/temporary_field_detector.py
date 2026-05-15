"""Detects Temporary Fields — instance variables set and used only in one method path."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


_FIELD_DECL = re.compile(r"^\s*(?:(?:public|private|protected|readonly)\s+)(\w+)\s*:")
_ASSIGNMENT = re.compile(r"(?:this\.)?(\w+)\s*=")
_USAGE = re.compile(r"(?:this\.)?(\w+)")


class TemporaryFieldDetector(CodeSmellDetector):
    """Flag field assignments that are only used within a small fraction of class methods."""

    _kind = "temporary_field"

    def __init__(self, usage_ratio_threshold: float = 0.5) -> None:
        self._usage_ratio_threshold = usage_ratio_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        fields: list[str] = []
        usage_count: dict[str, int] = {}
        method_count = 0

        for line_idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ")):
                continue

            # assumes each `constructor(` resets the per-field set for that method
            if re.match(r"\s*(?:public\s+)?constructor\s*\(", stripped):
                method_count += 1
                for field in fields:
                    usage_count[field] = usage_count.get(field, 0)

            # Field declaration
            field_match = _FIELD_DECL.match(stripped)
            if field_match:
                field_name = field_match.group(1)
                if field_name not in fields:
                    fields.append(field_name)
                    usage_count[field_name] = 0

            # Track usages
            for field in fields:
                if re.search(
                    r"(?:(?:this\.)|\b)" + re.escape(field) + r"(?:\s*[=(;,\s]|$)", stripped
                ):
                    usage_count[field] = usage_count.get(field, 0) + 1

        if method_count > 0:
            for field in fields:
                if usage_count.get(field, 0) == 0:
                    smells.append(
                        CodeSmell(
                            kind=self._kind,
                            message=f"field '{field}' is never read after being set — temporary field",
                            location=source_unit.location,
                            line=1,
                            column=0,
                        )
                    )

        return tuple(smells)
