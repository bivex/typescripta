"""ANTLR-backed TypeScript parser adapter."""

from __future__ import annotations

from time import perf_counter

from typescripta.domain.model import (
    GrammarVersion,
    ParseOutcome,
    ParseStatistics,
    SourceUnit,
    StructuralElement,
    StructuralElementKind,
)
from typescripta.domain.ports import TypeScriptSyntaxParser
from typescripta.infrastructure.antlr.runtime import (
    ANTLR_GRAMMAR_VERSION,
    load_generated_types,
    parse_source_text,
)


class AntlrTypeScriptSyntaxParser(TypeScriptSyntaxParser):
    def __init__(self) -> None:
        self._generated = load_generated_types()

    @property
    def grammar_version(self) -> GrammarVersion:
        return ANTLR_GRAMMAR_VERSION

    def parse(self, source_unit: SourceUnit) -> ParseOutcome:
        started_at = perf_counter()
        try:
            parse_result = parse_source_text(source_unit.content, self._generated)
            structure_visitor = _build_structure_visitor(self._generated.visitor_type)()
            structure_visitor.visit(parse_result.tree)

            elements = tuple(structure_visitor.elements)
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)

            return ParseOutcome.success(
                source_unit=source_unit,
                grammar_version=self.grammar_version,
                diagnostics=parse_result.diagnostics,
                structural_elements=elements,
                statistics=ParseStatistics(
                    token_count=len(parse_result.token_stream.tokens),
                    structural_element_count=len(elements),
                    diagnostic_count=len(parse_result.diagnostics),
                    elapsed_ms=elapsed_ms,
                ),
            )
        except Exception as error:
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return ParseOutcome.technical_failure(
                source_unit=source_unit,
                grammar_version=self.grammar_version,
                message=str(error),
                elapsed_ms=elapsed_ms,
            )


def _build_structure_visitor(visitor_base: type) -> type:
    class TypeScriptStructureVisitor(visitor_base):
        def __init__(self) -> None:
            super().__init__()
            self.elements: list[StructuralElement] = []
            self._containers: list[str] = []

        def visitImportStatement(self, ctx):
            text = ctx.getText()
            self._append(
                StructuralElementKind.IMPORT,
                text,
                ctx,
                signature=text,
            )
            return None

        def visitTypeAliasDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            self._append(
                StructuralElementKind.TYPE_ALIAS,
                name,
                ctx,
                signature=f"type {name}",
            )
            return None

        def visitVariableStatement(self, ctx):
            var_decl_list = ctx.variableDeclarationList()
            if var_decl_list is not None:
                for var_decl in var_decl_list.variableDeclaration():
                    name = _first_identifier_text(var_decl)
                    if name:
                        self._append(
                            StructuralElementKind.VARIABLE_DECLARATION,
                            name,
                            ctx,
                            signature=f"var/let/const {name}",
                        )
            return None

        def visitFunctionDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            sig = ctx.callSignature().getText() if ctx.callSignature() else ""
            self._append(
                StructuralElementKind.FUNCTION,
                name,
                ctx,
                signature=f"function {name}{sig}",
            )
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitArrowFunctionDeclaration(self, ctx):
            params = ctx.arrowFunctionParameters()
            name = params.getText() if params else "<arrow>"
            self._append(
                StructuralElementKind.ARROW_FUNCTION,
                name,
                ctx,
                signature=f"{name} => ...",
            )
            return None

        def visitEnumDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            self._append(
                StructuralElementKind.ENUM,
                name,
                ctx,
                signature=f"enum {name}",
            )
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitClassDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            self._append(
                StructuralElementKind.CLASS,
                name,
                ctx,
                signature=f"class {name}",
            )
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitInterfaceDeclaration(self, ctx):
            name = ctx.Identifier().getText()
            self._append(
                StructuralElementKind.INTERFACE,
                name,
                ctx,
                signature=f"interface {name}",
            )
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitNamespaceDeclaration(self, ctx):
            name = ctx.namespaceName().getText()
            self._append(
                StructuralElementKind.NAMESPACE,
                name,
                ctx,
                signature=f"namespace {name}",
            )
            return self._with_container(name, lambda: self.visitChildren(ctx))

        def visitDecoratorList(self, ctx):
            for decorator in ctx.decorator():
                text = decorator.getText()
                self._append(
                    StructuralElementKind.DECORATOR,
                    text,
                    decorator,
                    signature=f"@{text}",
                )
            return None

        def _append(self, kind, name: str, ctx, signature: str | None = None) -> None:
            container = ".".join(self._containers) if self._containers else None
            self.elements.append(
                StructuralElement(
                    kind=kind,
                    name=name,
                    line=ctx.start.line,
                    column=ctx.start.column,
                    container=container,
                    signature=signature,
                )
            )

        def _with_container(self, name: str, callback):
            self._containers.append(name)
            try:
                return callback()
            finally:
                self._containers.pop()

    return TypeScriptStructureVisitor


def _first_identifier_text(var_decl_ctx) -> str | None:
    for child in getattr(var_decl_ctx, "children", []) or []:
        text = child.getText() if hasattr(child, "getText") else str(child)
        if text and not text.startswith("("):
            return text
    return var_decl_ctx.getText() if hasattr(var_decl_ctx, "getText") else None
