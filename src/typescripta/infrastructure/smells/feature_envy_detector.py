"""Detects Feature Envy — a method uses data from another object more than its own."""

from __future__ import annotations

import re

from typescripta.domain.model import CodeSmell, SourceUnit
from typescripta.domain.ports import CodeSmellDetector

_THIS_RE = re.compile(r"\bthis\b")
_OTHER_RE = re.compile(r"\b[a-z_]\w*\.")

# Combined header matcher: group(1) is always the method name
_HEADER_RE = re.compile(
    r"(?:(?:public|private|protected|static|async|get|set)\s+)*"
    r"(\w+)\s*\("
)


class FeatureEnvyDetector(CodeSmellDetector):
    """Flag methods that access another object's fields more than their own."""

    _kind = "feature_envy"
    _THRESHOLD = 3

    def __init__(self, other_field_threshold: int = _THRESHOLD) -> None:
        self._other_field_threshold = other_field_threshold

    def detect(self, source_unit: SourceUnit) -> tuple[CodeSmell, ...]:
        smells: list[CodeSmell] = []
        code = source_unit.content or ""
        n = len(code)

        for m_start, m_end, name, body_start, body_end in _iter_bodies(code):
            line = code[:m_start].count("\n") + 1
            body_text = code[body_start:body_end].strip()
            if not body_text:
                continue
            if _check_envy(body_text, self._other_field_threshold):
                smells.append(
                    CodeSmell(
                        kind=self._kind,
                        message=(
                            f"method {name} accesses another object's fields "
                            f"more than its own (feature envy)"
                        ),
                        location=source_unit.location,
                        line=line,
                        column=0,
                    )
                )

        return tuple(smells)


def _iter_bodies(
    code: str,
) -> list[tuple[int, int, str, int, int]]:
    """Yield (match_start, match_end, name, body_content_start, body_content_end)."""
    bodies: list[tuple[int, int, str, int, int]] = []
    lines = code.splitlines()
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)
    offsets.pop()

    for idx, raw in enumerate(lines):
        absolute_start = offsets[idx]
        s = raw.strip()

        # Debug: detect inline methods within class/interface bodies
        if _should_scan_inline(s):
            # Find first '{' and last '}' in this line or body
            brace_open = raw.find("{")
            if brace_open >= 0:
                body_close = _find_matching_brace(raw, brace_open)
                if body_close is not None:
                    inline_src = raw[brace_open + 1 : body_close]
                    # Try to detect inline method headers
                    name = _find_method_name(inline_src)
                    if name is not None:
                        try:
                            meth_open = raw.index("{", brace_open + 1)
                        except ValueError:
                            meth_open = brace_open
                        meth_close = _find_matching_brace(code, absolute_start + meth_open)
                        if meth_close is not None:
                            bs = absolute_start + meth_open + 1
                            bodies.append(
                                (absolute_start, absolute_start + len(raw), name, bs, meth_close)
                            )
                            continue
                continue

        if not s or s.startswith(("//", "/*", "type ", "interface ", "class ", "export ")):
            continue

        name = _find_method_name(s)
        if name is None:
            continue

        try:
            opener_col = raw.index("{")
        except ValueError:
            continue

        brace_abs = absolute_start + opener_col
        body_end = _find_matching_brace(code, brace_abs)
        if body_end is None:
            continue

        body_content_start = brace_abs + 1
        body_content_end = body_end
        bodies.append(
            (absolute_start, absolute_start + len(raw), name, body_content_start, body_content_end)
        )

    return bodies


def _should_scan_inline(s: str) -> bool:
    """Return True if this line should be scanned for inline method declarations."""
    return s.startswith(("class ", "interface "))


def _find_method_name(s: str) -> str | None:
    """Return method name from a stripped source line, or None."""
    s = s.strip()
    # Pattern 1: function name(  — function is a word, is consumed as name
    m = re.search(r"(?:^|\b)function\s+(\w+)\s*\(", s)
    if m is None:
        m = _HEADER_RE.match(s)
    return m.group(1) if m else None


def _find_matching_brace(code: str, open_pos: int) -> int | None:
    """Walk braces from open_pos to find the matching close brace."""
    i = code.index("{", open_pos) if open_pos < len(code) else -1
    if i < 0:
        return None
    depth = 0
    j = i
    while j < len(code):
        c = code[j]
        if c in ('"', "'", "`"):
            q = c
            j += 1
            while j < len(code) and code[j] != q:
                j += 2 if code[j] == "\\" else 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _check_envy(body: str, threshold: int) -> bool:
    this_raw = len(_THIS_RE.findall(body))
    clean = _strip_strings(body)
    other_count = len(_OTHER_RE.findall(clean))
    return other_count >= threshold and other_count > this_raw


def _strip_strings(code: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(code):
        c = code[i]
        if c in ('"', "'", "`"):
            q = c
            i += 1
            while i < len(code) and code[i] != q:
                i += 2 if code[i] == "\\" else 1
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)
