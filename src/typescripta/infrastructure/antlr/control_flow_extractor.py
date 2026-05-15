"""Extract structured control flow from TypeScript source through ANTLR."""

from __future__ import annotations

import re
from dataclasses import dataclass

from antlr4 import CommonTokenStream, InputStream
from antlr4.Token import Token

from typescripta.domain.control_flow import (
    ActionFlowStep,
    CatchClauseFlow,
    ControlFlowDiagram,
    ControlFlowStep,
    CStyleForFlowStep,
    DoWhileFlowStep,
    ForInFlowStep,
    ForOfFlowStep,
    FunctionControlFlow,
    IfFlowStep,
    SwitchCaseFlow,
    SwitchFlowStep,
    TryCatchFlowStep,
    WhileFlowStep,
)
from typescripta.domain.model import SourceUnit
from typescripta.domain.ports import TypeScriptControlFlowExtractor
from typescripta.infrastructure.antlr.runtime import (
    load_generated_types,
    parse_code_block_text,
    parse_source_text,
    parse_statement_text,
)


@dataclass(frozen=True, slots=True)
class _ExtractorContext:
    token_stream: object

    def text(self, ctx) -> str:
        if ctx is None:
            return ""
        return self.token_stream.getText(
            start=ctx.start.tokenIndex,
            stop=ctx.stop.tokenIndex,
        )

    def compact(self, ctx, *, limit: int = 96) -> str:
        text = re.sub(r"\s+", " ", self.text(ctx)).strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 1]}..."


@dataclass(frozen=True, slots=True)
class _ContainerScope:
    name: str
    body_depth: int


@dataclass(frozen=True, slots=True)
class _PendingContainer:
    name: str


@dataclass(frozen=True, slots=True)
class _FunctionSlice:
    name: str
    signature: str
    container: str | None
    body_text: str


_MAX_STRUCTURED_PARSE_CHARS = 1400
_MAX_STRUCTURED_PARSE_TOKENS = 220
_MAX_STRUCTURED_PARSE_LINES = 24
_MAX_EXPANDED_CLOSURE_CHARS = 1800
_MAX_EXPANDED_CLOSURE_LINES = 36
_SUMMARY_LABEL_LIMIT = 96


class AntlrTypeScriptControlFlowExtractor(TypeScriptControlFlowExtractor):
    def __init__(self) -> None:
        self._generated = load_generated_types()
        self._lexer_type = self._generated.lexer_type

    def extract(self, source_unit: SourceUnit) -> ControlFlowDiagram:
        return self._extract_via_full_parse(source_unit)

    def _extract_function_slice(self, function_slice: _FunctionSlice) -> FunctionControlFlow:
        quick_steps = _extract_lightweight_steps(
            function_slice.body_text,
            self._generated,
            self._generated.visitor_type,
            self._lexer_type,
        )
        if quick_steps is not None:
            return FunctionControlFlow(
                name=function_slice.name,
                signature=function_slice.signature,
                container=function_slice.container,
                steps=quick_steps,
            )

        parse_result = parse_code_block_text(function_slice.body_text, self._generated)
        visitor = _build_control_flow_visitor(
            self._generated.visitor_type,
            _ExtractorContext(token_stream=parse_result.token_stream),
        )()
        return FunctionControlFlow(
            name=function_slice.name,
            signature=function_slice.signature,
            container=function_slice.container,
            steps=visitor._extract_block(parse_result.tree),
        )

    def _extract_via_full_parse(self, source_unit: SourceUnit) -> ControlFlowDiagram:
        parse_result = parse_source_text(source_unit.content, self._generated)
        visitor = _build_control_flow_visitor(
            self._generated.visitor_type,
            _ExtractorContext(token_stream=parse_result.token_stream),
        )()
        visitor.visit(parse_result.tree)
        return ControlFlowDiagram(
            source_location=source_unit.location,
            functions=tuple(visitor.functions),
        )


# ---------------------------------------------------------------------------
# Token-level function scanner
# ---------------------------------------------------------------------------

_CONTAINER_TOKEN_TYPES_ATTRS = ("Class", "Enum", "Interface", "Namespace")


def _scan_function_slices(
    source_text: str,
    generated: object,
) -> tuple[_FunctionSlice, ...]:
    lexer = generated.lexer_type(InputStream(source_text))
    token_stream = CommonTokenStream(lexer)
    token_stream.fill()
    tokens = tuple(
        token
        for token in token_stream.tokens
        if token.type != Token.EOF and token.channel == Token.DEFAULT_CHANNEL
    )
    lexer_type = generated.lexer_type

    container_types = {
        getattr(lexer_type, attr)
        for attr in _CONTAINER_TOKEN_TYPES_ATTRS
        if hasattr(lexer_type, attr)
    }

    functions: list[_FunctionSlice] = []
    container_stack: list[_ContainerScope] = []
    pending_container: _PendingContainer | None = None
    brace_depth = 0
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token.type == lexer_type.OpenBrace:
            brace_depth += 1
            if pending_container is not None:
                container_stack.append(
                    _ContainerScope(name=pending_container.name, body_depth=brace_depth)
                )
                pending_container = None
            index += 1
            continue

        if token.type == lexer_type.CloseBrace:
            if container_stack and container_stack[-1].body_depth == brace_depth:
                container_stack.pop()
            brace_depth = max(brace_depth - 1, 0)
            index += 1
            continue

        if token.type in container_types:
            pending_container = _PendingContainer(
                name=_extract_container_name(tokens, index + 1, lexer_type)
            )
            index += 1
            continue

        if token.type == lexer_type.Function:
            function_slice, next_index = _try_scan_function_slice(
                source_text,
                tokens,
                index,
                container_stack,
                lexer_type,
            )
            if function_slice is not None:
                functions.append(function_slice)
                index = next_index
                continue

        index += 1

    return tuple(functions)


def _extract_container_name(
    tokens: tuple[object, ...], start_index: int, lexer_type: object
) -> str:
    if start_index >= len(tokens):
        return "anonymous"

    token = tokens[start_index]
    if token.type != lexer_type.Identifier:
        return "anonymous"

    parts = [token.text]
    index = start_index + 1
    while index + 1 < len(tokens):
        if tokens[index].text != "." or tokens[index + 1].type != lexer_type.Identifier:
            break
        parts.append(tokens[index].text)
        parts.append(tokens[index + 1].text)
        index += 2

    return "".join(parts)


def _try_scan_function_slice(
    source_text: str,
    tokens: tuple[object, ...],
    func_index: int,
    container_stack: list[_ContainerScope],
    lexer_type: object,
) -> tuple[_FunctionSlice | None, int]:
    name = _extract_function_name(tokens, func_index + 1, lexer_type)
    if name is None:
        return None, func_index + 1

    body_open_index = _find_function_body_open(tokens, func_index + 1, lexer_type)
    if body_open_index is None:
        return None, func_index + 1

    body_close_index = _find_matching_brace(tokens, body_open_index, lexer_type)
    if body_close_index is None:
        return None, func_index + 1

    signature_text = source_text[tokens[func_index].start : tokens[body_open_index].start]
    body_text = source_text[
        tokens[body_open_index].start : tokens[body_close_index].stop + 1
    ]
    container = ".".join(scope.name for scope in container_stack) or None

    return (
        _FunctionSlice(
            name=name,
            signature=_compact_source_text(signature_text),
            container=container,
            body_text=body_text,
        ),
        body_close_index + 1,
    )


def _extract_function_name(
    tokens: tuple[object, ...],
    start_index: int,
    lexer_type: object,
) -> str | None:
    index = start_index
    while index < len(tokens):
        token = tokens[index]
        if token.type == lexer_type.Identifier:
            return token.text
        if token.type == lexer_type.OpenParen:
            return None
        if token.type in {lexer_type.OpenBrace, lexer_type.CloseBrace}:
            return None
        index += 1
    return None


def _find_function_body_open(
    tokens: tuple[object, ...],
    start_index: int,
    lexer_type: object,
) -> int | None:
    paren_depth = 0
    square_depth = 0
    angle_depth = 0
    index = start_index

    while index < len(tokens):
        token = tokens[index]
        text = token.text
        if token.type == lexer_type.OpenParen:
            paren_depth += 1
        elif token.type == lexer_type.CloseParen:
            paren_depth = max(paren_depth - 1, 0)
        elif text == "<":
            angle_depth += 1
        elif text == ">":
            angle_depth = max(angle_depth - 1, 0)
        elif (
            token.type == lexer_type.OpenBrace
            and paren_depth == square_depth == angle_depth == 0
        ):
            return index
        elif (
            token.type == lexer_type.CloseBrace
            and paren_depth == square_depth == angle_depth == 0
        ):
            return None

        index += 1

    return None


def _find_matching_brace(
    tokens: tuple[object, ...],
    open_index: int,
    lexer_type: object,
) -> int | None:
    depth = 1
    index = open_index + 1
    while index < len(tokens):
        token = tokens[index]
        if token.type == lexer_type.OpenBrace:
            depth += 1
        elif token.type == lexer_type.CloseBrace:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _compact_source_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Lightweight step extraction (token-level, no full parse)
# ---------------------------------------------------------------------------


def _extract_lightweight_steps(
    body_text: str,
    generated: object,
    visitor_type: type,
    lexer_type: object,
) -> tuple[ControlFlowStep, ...] | None:
    statement_spans = _split_top_level_statement_spans(body_text, lexer_type)
    if statement_spans is None:
        return None

    steps: list[ControlFlowStep] = []
    structured_starters = _structured_token_types(lexer_type)

    for statement_text, tokens, base_offset in statement_spans:
        if not tokens:
            continue

        trailing_body = _extract_trailing_block_body(
            statement_text,
            tokens,
            base_offset,
            lexer_type,
        )
        if trailing_body is not None:
            if _should_summarize_code_block(trailing_body):
                steps.extend(_summarize_code_block_steps(trailing_body, lexer_type))
                continue
            nested_steps = _extract_lightweight_steps(
                trailing_body,
                generated,
                visitor_type,
                lexer_type,
            )
            if nested_steps is None:
                parse_result = parse_code_block_text(trailing_body, generated)
                visitor = _build_control_flow_visitor(
                    visitor_type,
                    _ExtractorContext(token_stream=parse_result.token_stream),
                )()
                nested_steps = visitor._extract_block(parse_result.tree)
            steps.extend(nested_steps)
            continue

        if tokens[0].type in structured_starters:
            if _should_summarize_structured_statement(statement_text, tokens):
                steps.append(
                    _build_summarized_structured_step(
                        statement_text,
                        tokens,
                        base_offset,
                        lexer_type,
                    )
                )
                continue
            parse_result = parse_statement_text(statement_text, generated)
            visitor = _build_control_flow_visitor(
                visitor_type,
                _ExtractorContext(token_stream=parse_result.token_stream),
            )()
            extracted = visitor._extract_statement(parse_result.tree)
            if extracted is not None:
                steps.append(extracted)
            continue

        steps.append(ActionFlowStep(_compact_source_text(statement_text.strip().removesuffix(";"))))

    return tuple(steps)


def _should_summarize_structured_statement(
    statement_text: str,
    tokens: tuple[object, ...],
) -> bool:
    return (
        len(statement_text) > _MAX_STRUCTURED_PARSE_CHARS
        or len(tokens) > _MAX_STRUCTURED_PARSE_TOKENS
        or statement_text.count("\n") > _MAX_STRUCTURED_PARSE_LINES
    )


def _should_summarize_code_block(body_text: str) -> bool:
    return (
        len(body_text) > _MAX_EXPANDED_CLOSURE_CHARS
        or body_text.count("\n") > _MAX_EXPANDED_CLOSURE_LINES
    )


def _summarize_code_block_steps(
    body_text: str,
    lexer_type: object,
) -> tuple[ControlFlowStep, ...]:
    statement_spans = _split_top_level_statement_spans(body_text, lexer_type)
    if statement_spans is None:
        label = _compact_label_text(body_text.strip().strip("{}"))
        return (ActionFlowStep(label),) if label else ()

    steps: list[ControlFlowStep] = []
    structured_starters = _structured_token_types(lexer_type)

    for statement_text, tokens, base_offset in statement_spans:
        if not tokens:
            continue
        if tokens[0].type in structured_starters:
            steps.append(
                _build_summarized_structured_step(
                    statement_text,
                    tokens,
                    base_offset,
                    lexer_type,
                )
            )
            continue
        label = _compact_label_text(statement_text.strip().removesuffix(";"))
        if label:
            steps.append(ActionFlowStep(label))

    return tuple(steps)


def _build_summarized_structured_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    if not tokens:
        return ActionFlowStep(_compact_label_text(statement_text))

    starter = tokens[0].text
    if starter == "if":
        return _build_summarized_if_step(statement_text, tokens, base_offset, lexer_type)
    if starter == "for":
        return _build_summarized_for_step(statement_text, tokens, base_offset, lexer_type)
    if starter == "while":
        return _build_summarized_while_step(statement_text, tokens, base_offset, lexer_type)
    if starter == "do":
        return _build_summarized_do_while_step(statement_text, tokens, base_offset, lexer_type)
    if starter == "switch":
        return _build_summarized_switch_step(statement_text, tokens, base_offset, lexer_type)
    if starter == "try":
        return _build_summarized_try_step(statement_text, tokens, base_offset, lexer_type)
    return ActionFlowStep(
        _summarize_structured_header(statement_text, tokens, base_offset, lexer_type)
    )


def _build_summarized_if_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, close_index = block_range
    condition = _compact_label_text(
        _slice_token_text(statement_text, tokens, base_offset, 1, open_index - 1)
    )
    then_steps = _summarize_code_block_steps(
        _slice_token_text(statement_text, tokens, base_offset, open_index, close_index),
        lexer_type,
    )

    else_steps: tuple[ControlFlowStep, ...] = ()
    else_index = close_index + 1
    if else_index < len(tokens) and tokens[else_index].text == "else":
        next_index = else_index + 1
        if next_index < len(tokens) and tokens[next_index].text == "if":
            nested_text = _slice_token_text(
                statement_text,
                tokens,
                base_offset,
                next_index,
                len(tokens) - 1,
            )
            else_steps = (
                _build_summarized_structured_step(
                    nested_text,
                    tokens[next_index:],
                    tokens[next_index].start,
                    lexer_type,
                ),
            )
        else:
            else_block = _find_top_level_code_block(tokens, next_index, lexer_type)
            if else_block is not None:
                else_open, else_close = else_block
                else_steps = _summarize_code_block_steps(
                    _slice_token_text(
                        statement_text,
                        tokens,
                        base_offset,
                        else_open,
                        else_close,
                    ),
                    lexer_type,
                )

    return IfFlowStep(
        condition=condition or "condition",
        then_steps=then_steps,
        else_steps=else_steps,
    )


def _build_summarized_for_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, close_index = block_range
    header = _compact_label_text(
        _slice_token_text(statement_text, tokens, base_offset, 1, open_index - 1)
    )
    body_steps = _summarize_code_block_steps(
        _slice_token_text(statement_text, tokens, base_offset, open_index, close_index),
        lexer_type,
    )

    if " in " in header:
        return ForInFlowStep(header=header or "item in collection", body_steps=body_steps)
    if " of " in header:
        return ForOfFlowStep(header=header or "item of collection", body_steps=body_steps)
    return CStyleForFlowStep(header=header or "for (...)", body_steps=body_steps)


def _build_summarized_while_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, close_index = block_range
    condition = _compact_label_text(
        _slice_token_text(statement_text, tokens, base_offset, 1, open_index - 1)
    )
    return WhileFlowStep(
        condition=condition or "condition",
        body_steps=_summarize_code_block_steps(
            _slice_token_text(statement_text, tokens, base_offset, open_index, close_index),
            lexer_type,
        ),
    )


def _build_summarized_do_while_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, close_index = block_range
    while_index = close_index + 1
    condition = ""
    if while_index < len(tokens) and tokens[while_index].text == "while":
        condition = _compact_label_text(
            _slice_token_text(
                statement_text,
                tokens,
                base_offset,
                while_index + 1,
                len(tokens) - 1,
            ).removesuffix(";")
        )
    return DoWhileFlowStep(
        condition=condition or "condition",
        body_steps=_summarize_code_block_steps(
            _slice_token_text(statement_text, tokens, base_offset, open_index, close_index),
            lexer_type,
        ),
    )


def _build_summarized_switch_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, _ = block_range
    expression = _compact_label_text(
        _slice_token_text(statement_text, tokens, base_offset, 1, open_index - 1)
    )
    return SwitchFlowStep(
        expression=expression or "expression",
        cases=(),
    )


def _build_summarized_try_step(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> ControlFlowStep:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return ActionFlowStep(_compact_label_text(statement_text.strip().removesuffix(";")))

    open_index, close_index = block_range
    body_steps = _summarize_code_block_steps(
        _slice_token_text(statement_text, tokens, base_offset, open_index, close_index),
        lexer_type,
    )

    catches: list[CatchClauseFlow] = []
    index = close_index + 1
    finally_steps: tuple[ControlFlowStep, ...] = ()

    while index < len(tokens):
        if tokens[index].text == "catch":
            catch_block = _find_top_level_code_block(tokens, index + 1, lexer_type)
            if catch_block is not None:
                catches.append(
                    CatchClauseFlow(
                        pattern="catch",
                        steps=_summarize_code_block_steps(
                            _slice_token_text(
                                statement_text, tokens, base_offset, *catch_block
                            ),
                            lexer_type,
                        ),
                    )
                )
                index = catch_block[1] + 1
            else:
                index += 1
        elif tokens[index].text == "finally":
            finally_block = _find_top_level_code_block(tokens, index + 1, lexer_type)
            if finally_block is not None:
                finally_steps = _summarize_code_block_steps(
                    _slice_token_text(
                        statement_text, tokens, base_offset, *finally_block
                    ),
                    lexer_type,
                )
                index = finally_block[1] + 1
            else:
                index += 1
        else:
            index += 1

    return TryCatchFlowStep(
        body_steps=body_steps,
        catches=tuple(catches),
        finally_steps=finally_steps,
    )


def _summarize_structured_header(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> str:
    block_range = _find_top_level_code_block(tokens, 1, lexer_type)
    if block_range is None:
        return _compact_label_text(statement_text.strip().removesuffix(";"))
    open_index, _ = block_range
    return _compact_label_text(
        _slice_token_text(statement_text, tokens, base_offset, 0, open_index - 1)
    )


def _find_top_level_code_block(
    tokens: tuple[object, ...],
    start_index: int,
    lexer_type: object,
) -> tuple[int, int] | None:
    paren_depth = 0

    for index in range(start_index, len(tokens)):
        token = tokens[index]
        if token.type == lexer_type.OpenParen:
            paren_depth += 1
        elif token.type == lexer_type.CloseParen:
            paren_depth = max(paren_depth - 1, 0)
        elif token.type == lexer_type.OpenBrace and paren_depth == 0:
            close_index = _find_matching_brace(tokens, index, lexer_type)
            if close_index is not None:
                return index, close_index
            return None

    return None


def _slice_token_text(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    start_index: int,
    end_index: int,
) -> str:
    if start_index < 0 or end_index < start_index or end_index >= len(tokens):
        return ""
    start = tokens[start_index].start - base_offset
    end = tokens[end_index].stop + 1 - base_offset
    return statement_text[start:end]


def _compact_label_text(text: str, *, limit: int = _SUMMARY_LABEL_LIMIT) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _split_top_level_statement_spans(
    body_text: str,
    lexer_type: object,
) -> tuple[tuple[str, tuple[object, ...], int], ...] | None:
    tokens = _lex_default_tokens(body_text, lexer_type)
    if not tokens or tokens[0].type != lexer_type.OpenBrace:
        return None

    close_index = _find_matching_brace(tokens, 0, lexer_type)
    if close_index is None:
        return None

    spans: list[tuple[str, tuple[object, ...], int]] = []
    brace_depth = 1
    paren_depth = 0
    statement_start_index: int | None = None

    for index in range(1, close_index):
        token = tokens[index]
        if statement_start_index is None:
            statement_start_index = index

        if token.type == lexer_type.OpenParen:
            paren_depth += 1
        elif token.type == lexer_type.CloseParen:
            paren_depth = max(paren_depth - 1, 0)
        elif token.type == lexer_type.OpenBrace:
            brace_depth += 1
        elif token.type == lexer_type.CloseBrace:
            brace_depth -= 1

        next_token = tokens[index + 1] if index + 1 < close_index else None
        at_statement_end = False

        if (
            token.text == ";"
            and brace_depth == 1
            and paren_depth == 0
        ):
            at_statement_end = True
        elif (
            next_token is not None
            and brace_depth == 1
            and paren_depth == 0
            and next_token.text not in {"else", "catch", "finally"}
            and next_token.line > token.line
        ):
            at_statement_end = True
        elif next_token is None:
            at_statement_end = True

        if at_statement_end and statement_start_index is not None:
            statement_tokens = tokens[statement_start_index : index + 1]
            statement_text = body_text[
                statement_tokens[0].start : statement_tokens[-1].stop + 1
            ]
            if statement_text.strip():
                spans.append((statement_text, statement_tokens, statement_tokens[0].start))
            statement_start_index = None

    return tuple(spans)


def _structured_token_types(lexer_type: object) -> set[int]:
    return {
        token_type
        for token_type in {
            getattr(lexer_type, "If", None),
            getattr(lexer_type, "For", None),
            getattr(lexer_type, "While", None),
            getattr(lexer_type, "Do", None),
            getattr(lexer_type, "Switch", None),
            getattr(lexer_type, "Try", None),
        }
        if token_type is not None
    }


def _extract_trailing_block_body(
    statement_text: str,
    tokens: tuple[object, ...],
    base_offset: int,
    lexer_type: object,
) -> str | None:
    if len(tokens) < 3:
        return None

    if tokens[-1].type != lexer_type.CloseBrace:
        return None

    structured = _structured_token_types(lexer_type)
    if tokens[0].type in structured:
        return None

    depth = 0
    open_index: int | None = None
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].type == lexer_type.CloseBrace:
            depth += 1
        elif tokens[i].type == lexer_type.OpenBrace:
            depth -= 1
            if depth == 0:
                open_index = i
                break

    if open_index is None or open_index == 0:
        return None

    return statement_text[
        tokens[open_index].start - base_offset : tokens[-1].stop + 1 - base_offset
    ]


def _lex_default_tokens(source_text: str, lexer_type: object) -> tuple[object, ...]:
    lexer = lexer_type(InputStream(source_text))
    token_stream = CommonTokenStream(lexer)
    token_stream.fill()
    return tuple(
        token
        for token in token_stream.tokens
        if token.type != Token.EOF and token.channel == Token.DEFAULT_CHANNEL
    )


# ---------------------------------------------------------------------------
# ANTLR visitor for structured control flow extraction
# ---------------------------------------------------------------------------


def _build_control_flow_visitor(visitor_base: type, context: _ExtractorContext) -> type:
    class TypeScriptControlFlowVisitor(visitor_base):
        def __init__(self) -> None:
            super().__init__()
            self.functions: list[FunctionControlFlow] = []
            self._containers: list[str] = []

        def visitClassDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitInterfaceDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitNamespaceDeclaration(self, ctx):
            name = ctx.namespaceName().getText()
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitEnumDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitFunctionDeclaration(self, ctx):
            if ctx.functionBody() is None and ctx.SemiColon() is None:
                return None

            name = ctx.Identifier().getText() if ctx.Identifier() else "<anonymous>"
            sig = context.compact(ctx.callSignature()) if ctx.callSignature() else ""
            block_ctx = ctx.functionBody()
            self.functions.append(
                FunctionControlFlow(
                    name=name,
                    signature=f"function {name}{sig}",
                    container=".".join(self._containers) if self._containers else None,
                    steps=self._extract_block_from_body(block_ctx),
                )
            )
            return None

        def visitPropertyMemberDeclaration(self, ctx):
            if ctx.callSignature() is None:
                return None
            
            name = ctx.propertyName().getText() if ctx.propertyName() else "<anonymous>"
            sig = context.compact(ctx.callSignature()) if ctx.callSignature() else ""
            block_ctx = ctx.functionBody()
            self.functions.append(
                FunctionControlFlow(
                    name=name,
                    signature=f"function {name}{sig}",
                    container=".".join(self._containers) if self._containers else None,
                    steps=self._extract_block_from_body(block_ctx),
                )
            )
            return None

        def _with_container(self, name: str, callback):
            self._containers.append(name)
            try:
                return callback()
            finally:
                self._containers.pop()

        def _extract_block(self, block_ctx) -> tuple[ControlFlowStep, ...]:
            if block_ctx is None:
                return ()
            statement_list = block_ctx.statementList()
            if statement_list is None:
                return ()
            return self._extract_statement_list(statement_list)

        def _extract_statement_as_steps(self, stmt_ctx) -> tuple[ControlFlowStep, ...]:
            if stmt_ctx is None:
                return ()
            if hasattr(stmt_ctx, "block") and stmt_ctx.block() is not None:
                return self._extract_block(stmt_ctx.block())
            extracted = self._extract_statement(stmt_ctx)
            return (extracted,) if extracted is not None else ()

        def _extract_block_from_body(self, body_ctx) -> tuple[ControlFlowStep, ...]:
            if body_ctx is None:
                return ()
            source_elements = body_ctx.sourceElements()
            if source_elements is None:
                return ()
            steps: list[ControlFlowStep] = []
            for source_element in source_elements.sourceElement():
                stmt = source_element.statement()
                if stmt is not None:
                    extracted = self._extract_statement(stmt)
                    if extracted is not None:
                        steps.append(extracted)
            return tuple(steps)

        def _extract_statement_list(self, statement_list_ctx) -> tuple[ControlFlowStep, ...]:
            steps: list[ControlFlowStep] = []
            for statement_ctx in statement_list_ctx.statement():
                extracted = self._extract_statement(statement_ctx)
                if extracted is not None:
                    steps.append(extracted)
            return tuple(steps)

        def _extract_statement(self, statement_ctx) -> ControlFlowStep | None:
            if statement_ctx.block() is not None:
                return ActionFlowStep(context.compact(statement_ctx.block()))
            if statement_ctx.ifStatement() is not None:
                return self._extract_if_statement(statement_ctx.ifStatement())
            if statement_ctx.iterationStatement() is not None:
                return self._extract_iteration_statement(statement_ctx.iterationStatement())
            if statement_ctx.switchStatement() is not None:
                return self._extract_switch_statement(statement_ctx.switchStatement())
            if statement_ctx.tryStatement() is not None:
                return self._extract_try_statement(statement_ctx.tryStatement())
            if statement_ctx.returnStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.returnStatement()))
            if statement_ctx.throwStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.throwStatement()))
            if statement_ctx.continueStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.continueStatement()))
            if statement_ctx.breakStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.breakStatement()))
            if statement_ctx.variableStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.variableStatement()))
            if statement_ctx.expressionStatement() is not None:
                return ActionFlowStep(context.compact(statement_ctx.expressionStatement()))
            if statement_ctx.functionDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.functionDeclaration()))
            if statement_ctx.classDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.classDeclaration()))
            if statement_ctx.interfaceDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.interfaceDeclaration()))
            if statement_ctx.namespaceDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.namespaceDeclaration()))
            if statement_ctx.enumDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.enumDeclaration()))
            if statement_ctx.typeAliasDeclaration() is not None:
                return ActionFlowStep(context.compact(statement_ctx.typeAliasDeclaration()))
            return ActionFlowStep(context.compact(statement_ctx))

        def _extract_if_statement(self, if_ctx) -> IfFlowStep:
            then_steps = self._extract_statement_as_steps(if_ctx.statement(0)) if if_ctx.statement(0) else ()
            else_steps: tuple[ControlFlowStep, ...] = ()
            if len(if_ctx.statement()) > 1 and if_ctx.statement(1) is not None:
                else_steps = self._extract_statement_as_steps(if_ctx.statement(1))
            return IfFlowStep(
                condition=context.compact(if_ctx.expressionSequence()),
                then_steps=then_steps,
                else_steps=else_steps,
            )

        def _extract_iteration_statement(self, iter_ctx) -> ControlFlowStep:
            name = type(iter_ctx).__name__
            if name == "DoStatementContext":
                return self._extract_do_statement(iter_ctx)
            if name == "WhileStatementContext":
                return self._extract_while_statement(iter_ctx)
            if name in ("ForInStatementContext", "ForVarInStatementContext"):
                return self._extract_for_in_statement(iter_ctx)
            return self._extract_c_style_for_statement(iter_ctx)

        def _extract_do_statement(self, do_ctx) -> DoWhileFlowStep:
            body_stmt = do_ctx.statement() if do_ctx.statement() else None
            return DoWhileFlowStep(
                condition=context.compact(do_ctx.expressionSequence())
                if do_ctx.expressionSequence()
                else "condition",
                body_steps=self._extract_statement_as_steps(body_stmt) if body_stmt else (),
            )

        def _extract_while_statement(self, while_ctx) -> WhileFlowStep:
            body_stmt = while_ctx.statement() if while_ctx.statement() else None
            return WhileFlowStep(
                condition=context.compact(while_ctx.expressionSequence()),
                body_steps=self._extract_statement_as_steps(body_stmt) if body_stmt else (),
            )

        def _extract_for_in_statement(self, for_ctx) -> ForInFlowStep | ForOfFlowStep:
            body_stmt = for_ctx.statement() if for_ctx.statement() else None
            header = context.compact(for_ctx)
            if " of " in header:
                return ForOfFlowStep(
                    header=header,
                    body_steps=self._extract_statement_as_steps(body_stmt) if body_stmt else (),
                )
            return ForInFlowStep(
                header=header,
                body_steps=self._extract_statement_as_steps(body_stmt) if body_stmt else (),
            )

        def _extract_c_style_for_statement(self, for_ctx) -> CStyleForFlowStep:
            body_stmt = for_ctx.statement() if for_ctx.statement() else None
            return CStyleForFlowStep(
                header=context.compact(for_ctx),
                body_steps=self._extract_statement_as_steps(body_stmt) if body_stmt else (),
            )

        def _extract_switch_statement(self, switch_ctx) -> SwitchFlowStep:
            cases: list[SwitchCaseFlow] = []
            case_block = switch_ctx.caseBlock()
            if case_block is not None:
                for case_clauses in case_block.caseClauses():
                    for case_clause in case_clauses.caseClause():
                        label = context.compact(case_clause.expressionSequence())
                        steps = ()
                        if case_clause.statementList() is not None:
                            steps = self._extract_statement_list(case_clause.statementList())
                        cases.append(SwitchCaseFlow(label=label or "case", steps=steps))
                if case_block.defaultClause() is not None:
                    default = case_block.defaultClause()
                    steps = ()
                    if default.statementList() is not None:
                        steps = self._extract_statement_list(default.statementList())
                    cases.append(SwitchCaseFlow(label="default", steps=steps))
            return SwitchFlowStep(
                expression=context.compact(switch_ctx.expressionSequence()),
                cases=tuple(cases),
            )

        def _extract_try_statement(self, try_ctx) -> TryCatchFlowStep:
            body_steps = self._extract_block(try_ctx.block())
            catches: list[CatchClauseFlow] = []
            finally_steps: tuple[ControlFlowStep, ...] = ()

            if try_ctx.catchProduction() is not None:
                catch = try_ctx.catchProduction()
                catch_block = catch.block()
                catches.append(
                    CatchClauseFlow(
                        pattern=catch.Identifier().getText() if hasattr(catch, 'Identifier') and catch.Identifier() else "catch",
                        steps=self._extract_block(catch_block),
                    )
                )

            if try_ctx.finallyProduction() is not None:
                finally_block = try_ctx.finallyProduction().block()
                finally_steps = self._extract_block(finally_block)

            return TryCatchFlowStep(
                body_steps=body_steps,
                catches=tuple(catches),
                finally_steps=finally_steps,
            )
    return TypeScriptControlFlowVisitor
