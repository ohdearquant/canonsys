"""Tests for Charter DSL lexer."""

from __future__ import annotations

import pytest

from canon.dsl.errors import LexError
from canon.dsl.lexer import Lexer
from canon.dsl.tokens import TokenType


def _types(source: str) -> list[TokenType]:
    """Tokenize and return just token types (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.type for t in tokens if t.type != TokenType.EOF]


def _values(source: str) -> list[str]:
    """Tokenize and return token values (excluding NEWLINE/INDENT/DEDENT/EOF)."""
    tokens = Lexer(source).tokenize()
    skip = {TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.EOF}
    return [t.value for t in tokens if t.type not in skip]


class TestKeywords:
    def test_charter_keyword(self):
        tokens = Lexer("charter").tokenize()
        assert tokens[0].type == TokenType.CHARTER
        assert tokens[0].value == "charter"

    def test_all_keywords(self):
        keywords = [
            "charter",
            "schemas",
            "policies",
            "workflow",
            "phase",
            "require",
            "action",
            "output",
            "certify",
            "evidence",
            "situations",
            "when",
            "waiting_period",
            "roles",
            "break_glass",
            "requires_mfa",
            "actions",
            "immutable",
            "days",
            "hours",
            "passed",
            "complete",
            "true",
            "false",
        ]
        for kw in keywords:
            tokens = Lexer(kw).tokenize()
            assert tokens[0].value == kw
            assert tokens[0].type != TokenType.IDENT, f"{kw} should be keyword"

    def test_identifier(self):
        tokens = Lexer("my_feature").tokenize()
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "my_feature"


class TestLiterals:
    def test_integer(self):
        tokens = Lexer("42").tokenize()
        assert tokens[0].type == TokenType.INT
        assert tokens[0].value == "42"

    def test_float(self):
        tokens = Lexer("3.14").tokenize()
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == "3.14"

    def test_string_double_quotes(self):
        tokens = Lexer('"hello world"').tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_string_single_quotes(self):
        tokens = Lexer("'hello'").tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"

    def test_string_escape(self):
        tokens = Lexer(r'"hello\nworld"').tokenize()
        assert tokens[0].value == "hello\nworld"

    def test_unterminated_string(self):
        with pytest.raises(LexError, match="Unterminated"):
            Lexer('"unclosed').tokenize()


class TestPunctuation:
    def test_colon(self):
        assert _types("x:")[0:2] == [TokenType.IDENT, TokenType.COLON]

    def test_comma(self):
        assert _types("a, b") == [
            TokenType.IDENT,
            TokenType.COMMA,
            TokenType.IDENT,
            TokenType.NEWLINE,
        ]

    def test_dot(self):
        assert _types("a.b") == [
            TokenType.IDENT,
            TokenType.DOT,
            TokenType.IDENT,
            TokenType.NEWLINE,
        ]

    def test_dotdot_range(self):
        assert _types("1..10") == [
            TokenType.INT,
            TokenType.DOTDOT,
            TokenType.INT,
            TokenType.NEWLINE,
        ]

    def test_parens(self):
        types = _types("f(x)")
        assert TokenType.LPAREN in types
        assert TokenType.RPAREN in types

    def test_brackets(self):
        types = _types("[a, b]")
        assert TokenType.LBRACKET in types
        assert TokenType.RBRACKET in types

    def test_at_sign(self):
        assert TokenType.AT in _types("ns@ver")

    def test_dash(self):
        assert TokenType.DASH in _types("- item")


class TestComparators:
    @pytest.mark.parametrize(
        "op, expected",
        [
            ("==", TokenType.EQ),
            ("!=", TokenType.NEQ),
            (">=", TokenType.GTE),
            ("<=", TokenType.LTE),
            (">", TokenType.GT),
            ("<", TokenType.LT),
        ],
    )
    def test_comparator(self, op: str, expected: TokenType):
        tokens = Lexer(f"x {op} 1").tokenize()
        op_tokens = [t for t in tokens if t.type == expected]
        assert len(op_tokens) == 1


class TestIndentation:
    def test_single_indent(self):
        source = "block:\n    item\n"
        types = _types(source)
        assert TokenType.INDENT in types
        assert TokenType.DEDENT in types

    def test_nested_indent(self):
        source = "a:\n    b:\n        c\n"
        types = _types(source)
        indent_count = types.count(TokenType.INDENT)
        dedent_count = types.count(TokenType.DEDENT)
        assert indent_count == 2
        assert dedent_count == 2

    def test_multi_dedent(self):
        source = "a:\n    b:\n        c\nd\n"
        types = _types(source)
        # After c, two dedents before d
        dedent_count = types.count(TokenType.DEDENT)
        assert dedent_count == 2

    def test_eof_emits_remaining_dedents(self):
        source = "a:\n    b"
        types = _types(source)
        assert types.count(TokenType.DEDENT) >= 1

    def test_blank_lines_ignored(self):
        source = "a\n\n\nb\n"
        types = _types(source)
        # Blank lines should not produce extra tokens
        ident_count = sum(1 for t in types if t == TokenType.IDENT)
        assert ident_count == 2

    def test_tabs_rejected(self):
        with pytest.raises(LexError, match="Tabs"):
            Lexer("a:\n\tb\n").tokenize()


class TestComments:
    def test_comment_skipped(self):
        source = "# this is a comment\ncharter\n"
        tokens = Lexer(source).tokenize()
        values = [t.value for t in tokens if t.type not in {TokenType.NEWLINE, TokenType.EOF}]
        assert values == ["charter"]

    def test_inline_comment_not_supported_at_line_start(self):
        # Comments at line start are handled as "comment-only lines"
        source = "x # comment\n"
        tokens = Lexer(source).tokenize()
        # x should be there, comment should be skipped
        ident_tokens = [t for t in tokens if t.type == TokenType.IDENT]
        assert len(ident_tokens) == 1
        assert ident_tokens[0].value == "x"


class TestPositionTracking:
    def test_first_token_position(self):
        tokens = Lexer("charter").tokenize()
        assert tokens[0].line == 1
        assert tokens[0].column == 1

    def test_multiline_position(self):
        source = "a\nb\nc\n"
        tokens = Lexer(source).tokenize()
        idents = [t for t in tokens if t.type == TokenType.IDENT]
        assert idents[0].line == 1
        assert idents[1].line == 2
        assert idents[2].line == 3

    def test_column_position(self):
        source = "    x"
        tokens = Lexer(source).tokenize()
        ident = [t for t in tokens if t.type == TokenType.IDENT][0]
        assert ident.column == 5


class TestErrorPositions:
    def test_error_has_line_column(self):
        with pytest.raises(LexError) as exc_info:
            Lexer("a\nb\n\tc").tokenize()
        assert exc_info.value.line == 3
