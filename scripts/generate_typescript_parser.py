"""Generate Python parser artifacts from the vendored TypeScript grammar."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "build" / "tools"
GRAMMAR_DIR = ROOT / "resources" / "grammars" / "typescript"
OUTPUT_DIR = ROOT / "src" / "typescripta" / "infrastructure" / "antlr" / "generated" / "typescript"
ANTLR_VERSION = "4.13.2"
ANTLR_JAR = TOOLS_DIR / f"antlr-{ANTLR_VERSION}-complete.jar"
ANTLR_JAR_URL = f"https://www.antlr.org/download/antlr-{ANTLR_VERSION}-complete.jar"


def main() -> None:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _ensure_grammar_exists()
    _ensure_antlr_jar_exists()
    _generate_parser()
    _write_base_lexer()
    _write_base_parser()
    _patch_generated_parser()
    _patch_generated_lexer()
    _ensure_package_files()


def _ensure_grammar_exists() -> None:
    required = (
        GRAMMAR_DIR / "TypeScriptLexer.g4",
        GRAMMAR_DIR / "TypeScriptParser.g4",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"missing grammar files: {', '.join(missing)}")


def _ensure_antlr_jar_exists() -> None:
    if ANTLR_JAR.exists():
        return
    print(f"Downloading ANTLR {ANTLR_VERSION}...")
    urlretrieve(ANTLR_JAR_URL, ANTLR_JAR)


def _generate_parser() -> None:
    command = [
        "java",
        "-jar",
        str(ANTLR_JAR),
        "-Dlanguage=Python3",
        "-visitor",
        "-no-listener",
        "-o",
        str(OUTPUT_DIR),
        str(GRAMMAR_DIR / "TypeScriptLexer.g4"),
        str(GRAMMAR_DIR / "TypeScriptParser.g4"),
    ]
    subprocess.run(command, check=True, cwd=ROOT)


def _ensure_package_files() -> None:
    init_file = OUTPUT_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Generated TypeScript ANTLR parser."""\n', encoding="utf-8")


def _write_base_lexer() -> None:
    (OUTPUT_DIR / "TypeScriptBaseLexer.py").write_text(
        dedent(
            '''
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
                    if self.last_token is None or self.last_token.type == self.OpenBrace:
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
                        self.Identifier,
                        self.NullLiteral,
                        self.BooleanLiteral,
                        self.This,
                        self.CloseBracket,
                        self.CloseParen,
                        self.OctalIntegerLiteral,
                        self.DecimalLiteral,
                        self.HexIntegerLiteral,
                        self.StringLiteral,
                        self.PlusPlus,
                        self.MinusMinus,
                    }
                    return token_type not in no_regex_types
            '''
        ).lstrip(),
        encoding="utf-8",
    )


def _write_base_parser() -> None:
    (OUTPUT_DIR / "TypeScriptBaseParser.py").write_text(
        dedent(
            '''
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
                    possible_index = self.getCurrentToken().tokenIndex - 1
                    ahead = self._input.get(possible_index)
                    return ahead.channel == Lexer.HIDDEN and ahead.type == token_type

                def lineTerminatorAhead(self) -> bool:
                    possible_index = self.getCurrentToken().tokenIndex - 1
                    ahead = self._input.get(possible_index)

                    if ahead.channel != Lexer.HIDDEN:
                        return False

                    if ahead.type == self.LineTerminator:
                        return True

                    if ahead.type == self.WhiteSpaces:
                        possible_index = self.getCurrentToken().tokenIndex - 2
                        ahead = self._input.get(possible_index)

                    text = ahead.text
                    token_type = ahead.type

                    return (
                        token_type == self.MultiLineComment
                        and ("\\r" in text or "\\n" in text)
                    ) or token_type == self.LineTerminator
            '''
        ).lstrip(),
        encoding="utf-8",
    )


def _patch_generated_parser() -> None:
    parser_path = OUTPUT_DIR / "TypeScriptParser.py"
    content = parser_path.read_text(encoding="utf-8")
    content = content.replace("this.", "self.")
    content = content.replace("self.notLineTerminator()", "notLineTerminator()")
    content = content.replace("notLineTerminator()", "self.notLineTerminator()")
    content = content.replace("self.closeBrace()", "closeBrace()")
    content = content.replace("closeBrace()", "self.closeBrace()")
    content = content.replace("self.lineTerminatorAhead()", "lineTerminatorAhead()")
    content = content.replace("lineTerminatorAhead()", "self.lineTerminatorAhead()")
    parser_path.write_text(content, encoding="utf-8")


def _patch_generated_lexer() -> None:
    lexer_path = OUTPUT_DIR / "TypeScriptLexer.py"
    content = lexer_path.read_text(encoding="utf-8")
    content = content.replace("this.", "self.")
    content = content.replace("!self.IsStrictMode()", "not self.IsStrictMode()")
    lexer_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
