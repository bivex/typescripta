from __future__ import annotations

from antlr4 import Lexer, Parser


class TypeScriptBaseParser(Parser):

    def p(self, s: str) -> bool:
        return self.prev(s)

    def prev(self, s: str) -> bool:
        return self._input.LT(-1).text == s

    def n(self, s: str) -> bool:
        return self.next(s)

    def next(self, s: str) -> bool:
        return self._input.LT(1).text == s

    def notLineTerminator(self) -> bool:
        return not self._here(self.LineTerminator)

    def notOpenBraceAndNotFunction(self) -> bool:
        next_type = self._input.LT(1).type
        return next_type != self.OpenBrace and next_type != self.Function

    def closeBrace(self) -> bool:
        return self._input.LT(1).type == self.CloseBrace

    def _here(self, token_type: int) -> bool:
        possible_index = self.currentToken.tokenIndex - 1
        ahead = self._input.get(possible_index)
        return ahead.channel == Lexer.HIDDEN and ahead.type == token_type

    def lineTerminatorAhead(self) -> bool:
        possible_index = self.currentToken.tokenIndex - 1
        ahead = self._input.get(possible_index)

        if ahead.channel != Lexer.HIDDEN:
            return False

        if ahead.type == self.LineTerminator:
            return True

        if ahead.type == self.WhiteSpaces:
            possible_index = self.currentToken.tokenIndex - 2
            ahead = self._input.get(possible_index)

        text = ahead.text
        token_type = ahead.type

        return (
            token_type == self.MultiLineComment
            and ("\r" in text or "\n" in text)
        ) or token_type == self.LineTerminator
