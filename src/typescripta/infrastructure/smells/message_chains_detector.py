"""Detects long message chains (Law of Demeter violations) per Martin Fowler's Refactoring."""

from __future__ import annotations

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector


class MessageChainsDetector(CodeSmellDetector):
    """Flag dot-chained access expressions longer than the threshold."""

    _kind = "message_chain"
    _smell = "message chain of length {count} exceeds threshold of {threshold}"

    def __init__(self, chain_threshold: int = 3) -> None:
        self._chain_threshold = chain_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        lines = source_unit.content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            stripped = _strip_string_and_comment(line)
            for chain in _find_chains(stripped):
                if chain > self._chain_threshold:
                    smells.append(
                        CodeSmell(
                            kind=self._kind,
                            message=self._smell.format(
                                count=chain, threshold=self._chain_threshold
                            ),
                            location=source_unit.location,
                            line=line_idx,
                            column=0,
                        )
                    )

        return tuple(smells)


def _strip_string_and_comment(line: str) -> str:
    result = []
    i = 0
    while i < len(line):
        c = line[i]
        if c in ('"', "'", "`"):
            quote = c
            i += 1
            while i < len(line):
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == quote:
                    i += 1
                    break
                i += 1
            result.append(" ")
        elif c == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        else:
            result.append(c)
            i += 1
    return "".join(result)


def _find_chains(code: str) -> list[int]:
    import re

    chains: list[int] = []
    for match in re.finditer(r"\w(?:\.\w)+", code):
        segments = match.group().count(".") + 1
        chains.append(segments)
    return chains
