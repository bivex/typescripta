"""Detects Data Clumps — groups of fields or parameters that appear together in multiple places."""

from __future__ import annotations

import re
from collections import Counter

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector

_PARAM_STRUCT = re.compile(r"(?:function\s+\w+\s*\(|(?:public|private|protected)\s+)?\(([^)]+)\)")
_DEFAULT_THRESHOLD = 2


class DataClumpsDetector(CodeSmellDetector):
    """Flag groups of parameters or fields that appear together in multiple functions."""

    _kind = "data_clumps"

    def __init__(self, group_threshold: int = _DEFAULT_THRESHOLD, min_group_size: int = 2) -> None:
        self._group_threshold = group_threshold
        self._min_group_size = min_group_size

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()
        group_counter: Counter[tuple[str, ...]] = Counter()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "* ")):
                continue

            structs = _PARAM_STRUCT.findall(stripped)
            for params_str in structs:
                raw_params = [p.strip() for p in params_str.split(",") if p.strip()]
                if len(raw_params) >= self._min_group_size:
                    sorted_key = tuple(sorted(raw_params))
                    group_counter[sorted_key] += 1

        for group, count in group_counter.items():
            if count >= self._group_threshold:
                smells.append(
                    CodeSmell(
                        kind=self._kind,
                        message=(
                            f"group {list(group)} appears as parameters together in "
                            f"{count} places — possible data clump"
                        ),
                        location=source_unit.location,
                        line=1,
                        column=0,
                    )
                )

        return tuple(smells)
