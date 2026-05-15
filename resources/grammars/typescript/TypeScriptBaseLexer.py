from __future__ import annotations

import sys
from typing import TextIO

from antlr4 import Lexer, Token


class TypeScriptBaseLexer(Lexer):
    def __init__(self, input=None, output: TextIO = sys.stdout):
        super().__init__(input, output)
        self.scope_strict_modes: list[bool] = []
        self.last_token: Token | None = None
        self.use_strict_default: bool = False
        self.use_strict_current: bool = False

    @property
    def strict_default(self) -> bool:
        return self.use_strict_default

    @strict_default.setter
    def strict_default(self, value: bool) -> None:
        self.use_strict_default = value
        self.use_strict_current = value

    def IsStrictMode(self) -> bool:
        return self.use_strict_current

    def nextToken(self):
        next_token = super().nextToken()
        if next_token.channel == Token.DEFAULT_CHANNEL:
            self.last_token = next_token
        return next_token

    def ProcessOpenBrace(self) -> None:
        if self.scope_strict_modes:
            self.use_strict_current = self.scope_strict_modes[-1]
        else:
            self.use_strict_current = self.use_strict_default
        self.scope_strict_modes.append(self.use_strict_current)

    def ProcessCloseBrace(self) -> None:
        if self.scope_strict_modes:
            self.use_strict_current = self.scope_strict_modes.pop()
        else:
            self.use_strict_current = self.use_strict_default

    def ProcessStringLiteral(self) -> None:
        if self.last_token is None or self.last_token.type == self.OPEN_BRACE:
            text = self.text
            if text in ('"use strict"', "'use strict'"):
                if self.scope_strict_modes:
                    self.scope_strict_modes.pop()
                self.use_strict_current = True
                self.scope_strict_modes.append(self.use_strict_current)

    def IsRegexPossible(self) -> bool:
        if self.last_token is None:
            return True
        token_type = self.last_token.type
        no_regex_types = {
            self.IDENTIFIER,
            self.NULL_LITERAL,
            self.BOOLEAN_LITERAL,
            self.THIS,
            self.CLOSE_BRACKET,
            self.CLOSE_PAREN,
            self.OCTAL_INTEGER_LITERAL,
            self.DECIMAL_LITERAL,
            self.HEX_INTEGER_LITERAL,
            self.STRING_LITERAL,
            self.PLUS_PLUS,
            self.MINUS_MINUS,
        }
        return token_type not in no_regex_types
