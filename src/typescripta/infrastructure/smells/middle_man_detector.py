"""Detects Middle Man — methods that just delegate to another object without extra logic."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector

# Match a pure pass-through body: return this.x; return obj.method(...);
_RETURN_DELEGATE_PATTERN = re.compile(
    r"return\s+(?:this\.)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?:\([^)]*\))?\s*;"
)

# Match function / class method declarations
_RX_FUNC_PATTERN = re.compile(r"function\s+(\w+)\s*\(")
_RX_METHOD_PATTERN = re.compile(r"(?:public|private|protected|static|async|get|set)\s+(\w+)\s*\(")


class MiddleManDetector(CodeSmellDetector):
    """Flag methods whose entire body is a single pass-through call."""

    _kind = "middle_man"

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        code = source_unit.content

        for m_start, m_end, name in _find_method_spans(code):
            body = _extract_body(code, m_start, m_end)
            if body and _RETURN_DELEGATE_PATTERN.fullmatch(_strip_comments(body)):
                line = code[:m_start].count("\n") + 1
                smells.append(
                    CodeSmell(
                        kind=self._kind,
                        message="method is a middle man — just delegates to another object",
                        location=source_unit.location,
                        line=line,
                        column=0,
                    )
                )

        return tuple(smells)


def _find_method_spans(code: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []

    # 1. function name(...) — mainly for standalone functions
    for m in _RX_FUNC_PATTERN.finditer(code):
        start = m.start()
        body_span = _find_body_span(code, m.end() - 1)
        if body_span is not None:
            _, body_end = body_span
            spans.append((start, body_end, m.group(1)))

    # 2. class-style methods: modifier name(\, ...
    for m in _RX_METHOD_PATTERN.finditer(code):
        start = m.start()
        body_span = _find_body_span(code, m.end() - 1)
        if body_span is not None:
            _, body_end = body_span
            spans.append((start, body_end, m.group(1)))

    return spans


def _find_body_span(code: str, open_paren_at: int) -> tuple[int, int] | None:
    """Find (body_open, body_close) by walking braces from the open-paren position."""
    # Find the first `{` on or after open_paren_at
    body_open = code.find("{", open_paren_at)
    if body_open < 0:
        return None
    depth = 0
    i = body_open
    while i < len(code):
        if code[i] == '"':
            i += 1
            while i < len(code) and code[i] != '"':
                i += 2 if code[i] == "\\" else 1
        elif code[i] == "'":
            i += 1
            while i < len(code) and code[i] != "'":
                i += 1
        elif code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return (body_open, i + 1)
        i += 1
    return (body_open, len(code))


def _extract_body(code: str, m_start: int, m_end: int) -> str:
    """Return text between the method's opening and closing braces."""
    segment = code[m_start:m_end]
    lbi = segment.find("{")
    lbr = segment.rfind("}")
    if lbi >= 0 and lbr > lbi:
        return segment[lbi + 1 : lbr].strip()
    return ""


def _strip_comments(body: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(body):
        if body[i : i + 2] == "//":
            break
        if body[i : i + 2] == "/*":
            end = body.index("*/", i + 2)
            i = end + 2
        elif body[i] in ('"', "'", "`"):
            q = body[i]
            i += 1
            while i < len(body) and body[i] != q:
                i += 2 if body[i] == "\\" else 1
            i += 1
        else:
            out.append(body[i])
            i += 1
    return "".join(out)
