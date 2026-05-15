"""Detects switch statements with more than 5 cases per Martin Fowler's Refactoring."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector

_DEFAULT_CASE_THRESHOLD = 5


class SwitchStatementsDetector(CodeSmellDetector):
    """Flag switch statements with too many case branches."""

    _kind = "switch_statements"
    _smell = "switch statement with {count} cases exceeds threshold of {threshold}"

    def __init__(self, case_threshold: int = _DEFAULT_CASE_THRESHOLD) -> None:
        self._case_threshold = case_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()
        in_switch = False
        switch_start = 0
        case_count = 0
        brace_depth = 0

        for line_idx, raw in enumerate(lines, start=1):
            s = raw.strip()

            if not in_switch:
                if _is_switch_statement(s):
                    in_switch = True
                    switch_start = line_idx
                    case_count = 0
                if in_switch:
                    opens = raw.count("{")
                    closes = raw.count("}")
                    case_count += sum(
                        1 for token in s.split() if token == "case" or token == "default:"
                    )
                    brace_depth += opens - closes
                    if brace_depth <= 0 and in_switch:
                        if case_count > self._case_threshold:
                            smells.append(
                                CodeSmell(
                                    kind=self._kind,
                                    message=self._smell.format(
                                        count=case_count,
                                        threshold=self._case_threshold,
                                    ),
                                    location=source_unit.location,
                                    line=switch_start,
                                    column=0,
                                )
                            )
                        in_switch = False
            else:
                case_count += sum(
                    1 for token in s.split() if token == "case" or token == "default:"
                )
                opens = raw.count("{")
                closes = raw.count("}")
                brace_depth += opens - closes
                if closes > 0 and brace_depth <= 0:
                    if case_count > self._case_threshold:
                        smells.append(
                            CodeSmell(
                                kind=self._kind,
                                message=self._smell.format(
                                    count=case_count,
                                    threshold=self._case_threshold,
                                ),
                                location=source_unit.location,
                                line=switch_start,
                                column=0,
                            )
                        )
                    in_switch = False

        return tuple(smells)


def _is_switch_statement(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("/*"):
        return False
    return stripped.startswith("switch ")


def _is_case_statement(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("/*"):
        return False
    return stripped.startswith("case ") or stripped == "default:"
