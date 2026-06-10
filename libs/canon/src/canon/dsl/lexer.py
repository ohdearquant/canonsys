"""Charter DSL lexer — indentation-aware tokenizer.

Produces a token stream with explicit INDENT/DEDENT tokens for
block structure (Python-style). Tracks line/column for error
reporting.

Usage:
    from canon.dsl.lexer import Lexer

    lexer = Lexer(source_text)
    tokens = lexer.tokenize()
"""

from __future__ import annotations

from .errors import LexError
from .tokens import KEYWORDS, Token, TokenType

__all__ = ("Lexer",)


class Lexer:
    """Indentation-aware tokenizer for Charter DSL.

    Follows the LNDL pattern: character-by-character with line/column
    tracking. Adds an indentation stack for INDENT/DEDENT emission
    (Python tokenizer algorithm).
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

        # Indentation tracking
        self._indent_stack: list[int] = [0]
        self._at_line_start = True

    # -----------------------------------------------------------------
    # Character access
    # -----------------------------------------------------------------

    def current_char(self) -> str | None:
        if self.pos >= len(self.text):
            return None
        return self.text[self.pos]

    def peek_char(self, offset: int = 1) -> str | None:
        peek_pos = self.pos + offset
        if peek_pos >= len(self.text):
            return None
        return self.text[peek_pos]

    def advance(self) -> None:
        """Advance position, tracking line and column."""
        if self.pos < len(self.text):
            if self.text[self.pos] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    # -----------------------------------------------------------------
    # Readers
    # -----------------------------------------------------------------

    def _read_identifier(self) -> str:
        """Read an identifier or keyword: [a-zA-Z_][a-zA-Z0-9_]*."""
        start = self.pos
        while (ch := self.current_char()) and (ch.isalnum() or ch == "_"):
            self.advance()
        return self.text[start : self.pos]

    def _read_number(self) -> tuple[str, bool]:
        """Read a number literal. Returns (value_str, is_float)."""
        start = self.pos
        is_float = False
        while (ch := self.current_char()) and ch.isdigit():
            self.advance()
        # Check for float (single dot followed by digit, NOT dotdot)
        if self.current_char() == "." and self.peek_char() not in (".", None):
            peek = self.peek_char()
            if peek is not None and peek.isdigit():
                is_float = True
                self.advance()  # consume '.'
                while (ch := self.current_char()) and ch.isdigit():
                    self.advance()
        return self.text[start : self.pos], is_float

    def _read_string(self) -> tuple[str, bool]:
        """Read a quoted string with escape sequence handling.

        Returns:
            (value, is_docstring): Value and whether it's a triple-quoted docstring.
        """
        quote = self.current_char()
        start_line = self.line

        # Check for triple-quoted string (docstring)
        if self.peek_char() == quote and self.peek_char(2) == quote:
            # Triple-quoted string
            self.advance()  # skip first quote
            self.advance()  # skip second quote
            self.advance()  # skip third quote
            return self._read_triple_quoted_string(quote), True

        # Single-quoted string
        self.advance()  # skip opening quote
        result: list[str] = []

        while (ch := self.current_char()) is not None and ch != quote:
            if ch == "\\":
                self.advance()
                esc = self.current_char()
                if esc is None:
                    break
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    '"': '"',
                    "'": "'",
                }
                result.append(escape_map.get(esc, esc))
                self.advance()
            else:
                result.append(ch)
                self.advance()

        if self.current_char() == quote:
            self.advance()  # skip closing quote
        else:
            raise LexError("Unterminated string literal", line=self.line, column=self.column)

        return "".join(result), False

    def _read_triple_quoted_string(self, quote: str) -> str:
        """Read a triple-quoted string (docstring).

        Triple-quoted strings can span multiple lines and preserve
        their content including newlines.
        """
        result: list[str] = []
        start_line = self.line

        while True:
            ch = self.current_char()
            if ch is None:
                raise LexError(
                    f"Unterminated docstring starting at line {start_line}",
                    line=self.line,
                    column=self.column,
                )

            # Check for closing triple quote
            if ch == quote and self.peek_char() == quote and self.peek_char(2) == quote:
                self.advance()  # skip first quote
                self.advance()  # skip second quote
                self.advance()  # skip third quote
                break

            result.append(ch)
            self.advance()

        return "".join(result)

    def _skip_comment(self) -> None:
        """Skip a # comment to end of line."""
        while (ch := self.current_char()) is not None and ch != "\n":
            self.advance()

    # -----------------------------------------------------------------
    # Indentation handling
    # -----------------------------------------------------------------

    def _measure_indent(self) -> int:
        """Measure the indentation level at the current position.

        Returns the number of spaces. Tabs are rejected.
        """
        spaces = 0
        while (ch := self.current_char()) is not None:
            if ch == " ":
                spaces += 1
                self.advance()
            elif ch == "\t":
                raise LexError(
                    "Tabs are not allowed; use spaces for indentation",
                    line=self.line,
                    column=self.column,
                )
            else:
                break
        return spaces

    def _handle_indentation(self, indent_level: int) -> None:
        """Emit INDENT/DEDENT tokens based on indentation change."""
        current_indent = self._indent_stack[-1]

        if indent_level > current_indent:
            self._indent_stack.append(indent_level)
            self.tokens.append(Token(TokenType.INDENT, "", self.line, 1))
        elif indent_level < current_indent:
            while self._indent_stack and self._indent_stack[-1] > indent_level:
                self._indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, "", self.line, 1))
            if self._indent_stack[-1] != indent_level:
                raise LexError(
                    f"Inconsistent indentation: expected {self._indent_stack[-1]} "
                    f"spaces, got {indent_level}",
                    line=self.line,
                    column=1,
                )

    def _emit_remaining_dedents(self) -> None:
        """Emit DEDENT tokens for all remaining indent levels at EOF."""
        while len(self._indent_stack) > 1:
            self._indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", self.line, self.column))

    # -----------------------------------------------------------------
    # Main tokenize loop
    # -----------------------------------------------------------------

    def tokenize(self) -> list[Token]:
        """Tokenize source text into a stream with INDENT/DEDENT.

        Returns:
            List of Token objects ending with EOF.
        """
        while self.pos < len(self.text):
            # --- Line start: handle indentation ---
            if self._at_line_start:
                self._at_line_start = False

                # Skip blank lines and comment-only lines
                indent_level = self._measure_indent()
                ch = self.current_char()

                if ch is None:
                    break
                if ch == "\n":
                    # Blank line — skip entirely
                    self.advance()
                    self._at_line_start = True
                    continue
                if ch == "#":
                    # Comment-only line — skip
                    self._skip_comment()
                    continue

                self._handle_indentation(indent_level)

            ch = self.current_char()
            if ch is None:
                break

            # --- Newline ---
            if ch == "\n":
                self.tokens.append(Token(TokenType.NEWLINE, "\n", self.line, self.column))
                self.advance()
                self._at_line_start = True
                continue

            # --- Inline whitespace ---
            if ch in " \t\r":
                self.advance()
                continue

            # --- Comment ---
            if ch == "#":
                self._skip_comment()
                continue

            # --- String literal (single or triple-quoted) ---
            if ch in ('"', "'"):
                start_line = self.line
                start_col = self.column
                value, is_docstring = self._read_string()
                tok_type = TokenType.DOCSTRING if is_docstring else TokenType.STRING
                self.tokens.append(Token(tok_type, value, start_line, start_col))
                continue

            # --- Number ---
            if ch.isdigit():
                start_line = self.line
                start_col = self.column
                value, is_float = self._read_number()
                tok_type = TokenType.FLOAT if is_float else TokenType.INT
                self.tokens.append(Token(tok_type, value, start_line, start_col))
                continue

            # --- Identifier / Keyword ---
            if ch.isalpha() or ch == "_":
                start_line = self.line
                start_col = self.column
                word = self._read_identifier()
                tok_type = KEYWORDS.get(word, TokenType.IDENT)
                self.tokens.append(Token(tok_type, word, start_line, start_col))
                continue

            # --- Two-character operators ---
            start_line = self.line
            start_col = self.column
            next_ch = self.peek_char()

            if ch == "." and next_ch == ".":
                self.tokens.append(Token(TokenType.DOTDOT, "..", start_line, start_col))
                self.advance()
                self.advance()
                continue

            if ch == "=" and next_ch == "=":
                self.tokens.append(Token(TokenType.EQ, "==", start_line, start_col))
                self.advance()
                self.advance()
                continue

            if ch == "!" and next_ch == "=":
                self.tokens.append(Token(TokenType.NEQ, "!=", start_line, start_col))
                self.advance()
                self.advance()
                continue

            if ch == ">" and next_ch == "=":
                self.tokens.append(Token(TokenType.GTE, ">=", start_line, start_col))
                self.advance()
                self.advance()
                continue

            if ch == "<" and next_ch == "=":
                self.tokens.append(Token(TokenType.LTE, "<=", start_line, start_col))
                self.advance()
                self.advance()
                continue

            # --- Single-character tokens ---
            single_char_tokens: dict[str, TokenType] = {
                ":": TokenType.COLON,
                ",": TokenType.COMMA,
                ".": TokenType.DOT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                "@": TokenType.AT,
                "-": TokenType.DASH,
                ">": TokenType.GT,
                "<": TokenType.LT,
            }

            if ch in single_char_tokens:
                self.tokens.append(Token(single_char_tokens[ch], ch, start_line, start_col))
                self.advance()
                continue

            # --- Unknown character ---
            raise LexError(
                f"Unexpected character: {ch!r}",
                line=self.line,
                column=self.column,
            )

        # Emit final NEWLINE if text doesn't end with one
        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self.tokens.append(Token(TokenType.NEWLINE, "\n", self.line, self.column))

        self._emit_remaining_dedents()
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
