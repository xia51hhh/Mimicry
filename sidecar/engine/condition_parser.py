"""Recursive descent parser for condition expressions.

Grammar:
    expr       -> or_expr
    or_expr    -> and_expr ('or' and_expr)*
    and_expr   -> not_expr ('and' not_expr)*
    not_expr   -> 'not' not_expr | comparison
    comparison -> value (('==' | '!=' | '>' | '<' | '>=' | '<=') value)?
    value      -> function_call | variable | string | number | '(' expr ')'
    function_call -> IDENT '(' args ')'
    args       -> (string | variable | number) (',' (string | variable | number))*
    variable   -> '$' IDENT
    string     -> '"' ... '"'
    number     -> DIGIT+
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<STRING>"(?:[^"\\]|\\.)*")   |  # "string"
    (?P<NUMBER>\d+(?:\.\d+)?)       |  # 123 or 12.5
    (?P<VAR>\$\w+)                  |  # $var
    (?P<OP>==|!=|>=|<=|>|<)         |  # comparison operators
    (?P<LPAREN>\()                  |
    (?P<RPAREN>\))                  |
    (?P<COMMA>,)                    |
    (?P<IDENT>[a-zA-Z_]\w*)        |  # identifiers / keywords
    (?P<WS>\s+)                       # whitespace (skipped)
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and", "or", "not"}


class _Token:
    __slots__ = ("type", "value")

    def __init__(self, type_: str, value: str):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(source):
        m = _TOKEN_RE.match(source, pos)
        if m is None:
            raise ValueError(f"Unexpected character at position {pos}: {source[pos]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "WS":
            continue
        value = m.group()
        if kind == "IDENT" and value in _KEYWORDS:
            kind = value.upper()  # AND, OR, NOT
        tokens.append(_Token(kind, value))
    return tokens


# ---------------------------------------------------------------------------
# Parser / evaluator
# ---------------------------------------------------------------------------

class _Parser:
    """Recursive descent parser that evaluates in-place."""

    def __init__(self, tokens: list[_Token], ctrl: Any, ctx: Any):
        self._tokens = tokens
        self._pos = 0
        self._ctrl = ctrl
        self._ctx = ctx

    # -- helpers -----------------------------------------------------------

    def _peek(self) -> _Token | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> _Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type_: str) -> _Token:
        tok = self._peek()
        if tok is None or tok.type != type_:
            expected = type_
            got = tok.type if tok else "EOF"
            raise ValueError(f"Expected {expected}, got {got}")
        return self._advance()

    # -- grammar rules -----------------------------------------------------

    def parse(self) -> Any:
        result = self._or_expr()
        if self._pos < len(self._tokens):
            raise ValueError(f"Unexpected token: {self._tokens[self._pos]}")
        return result

    def _or_expr(self) -> Any:
        left = self._and_expr()
        while self._peek() and self._peek().type == "OR":
            self._advance()
            if left:
                # Short-circuit: skip right side parsing by consuming tokens
                self._and_expr()  # parse but discard
            else:
                left = self._and_expr()
        return left

    def _and_expr(self) -> Any:
        left = self._not_expr()
        while self._peek() and self._peek().type == "AND":
            self._advance()
            if not left:
                # Short-circuit: skip right side
                self._not_expr()  # parse but discard
            else:
                left = self._not_expr()
        return left

    def _not_expr(self) -> Any:
        if self._peek() and self._peek().type == "NOT":
            self._advance()
            return not self._not_expr()
        return self._comparison()

    def _comparison(self) -> Any:
        left = self._value()
        tok = self._peek()
        if tok and tok.type == "OP":
            op = self._advance().value
            right = self._value()
            return _compare(left, op, right)
        return left

    def _value(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of expression")

        if tok.type == "IDENT":
            # Could be a function call
            next_idx = self._pos + 1
            if next_idx < len(self._tokens) and self._tokens[next_idx].type == "LPAREN":
                return self._function_call()
            # Bare identifier — treat as truthy string
            return self._advance().value

        if tok.type == "STRING":
            return _unquote(self._advance().value)

        if tok.type == "NUMBER":
            raw = self._advance().value
            return float(raw) if "." in raw else int(raw)

        if tok.type == "VAR":
            name = self._advance().value
            return self._ctx.get_var(name)

        if tok.type == "LPAREN":
            self._advance()
            result = self._or_expr()
            self._expect("RPAREN")
            return result

        raise ValueError(f"Unexpected token: {tok}")

    def _function_call(self) -> Any:
        name = self._advance().value  # IDENT
        self._expect("LPAREN")
        args = self._arg_list()
        self._expect("RPAREN")
        return self._call_function(name, args)

    def _arg_list(self) -> list[Any]:
        args: list[Any] = []
        if self._peek() and self._peek().type == "RPAREN":
            return args
        args.append(self._arg_value())
        while self._peek() and self._peek().type == "COMMA":
            self._advance()
            args.append(self._arg_value())
        return args

    def _arg_value(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of expression in argument list")
        if tok.type == "STRING":
            raw = _unquote(self._advance().value)
            return self._ctx.resolve(raw)
        if tok.type == "NUMBER":
            raw = self._advance().value
            return float(raw) if "." in raw else int(raw)
        if tok.type == "VAR":
            name = self._advance().value
            return self._ctx.get_var(name)
        raise ValueError(f"Unexpected token in argument: {tok}")

    # -- function dispatch -------------------------------------------------

    def _call_function(self, name: str, args: list[Any]) -> Any:
        ctrl = self._ctrl
        try:
            if name == "exists":
                return ctrl.get_element_count(args[0]) > 0
            if name == "visible":
                return ctrl.is_visible(args[0])
            if name == "equals":
                return args[0] == args[1]
            if name == "contains":
                return args[1] in args[0]
            if name == "regex":
                return bool(re.search(args[1], args[0]))
            if name == "url_contains":
                return args[0] in ctrl.get_url()
            if name == "text":
                return ctrl.get_element_text(args[0])
        except Exception:
            return False
        raise ValueError(f"Unknown function: {name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unquote(s: str) -> str:
    """Remove surrounding quotes and unescape."""
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _compare(left: Any, op: str, right: Any) -> bool:
    # Coerce to comparable types
    left, right = _coerce_pair(left, right)
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    raise ValueError(f"Unknown operator: {op}")


def _coerce_pair(a: Any, b: Any) -> tuple[Any, Any]:
    """Try to coerce both values to numbers if possible."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a, b
    # If one is numeric and the other is a string representation of a number
    try:
        na = float(a) if not isinstance(a, (int, float)) else a
        nb = float(b) if not isinstance(b, (int, float)) else b
        # Convert to int if both are whole
        if na == int(na) and nb == int(nb):
            return int(na), int(nb)
        return na, nb
    except (ValueError, TypeError):
        return str(a) if a is not None else "", str(b) if b is not None else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_condition(condition: str, ctrl: Any, ctx: Any) -> bool:
    """Evaluate a condition string against browser state.

    Returns False for empty/whitespace conditions or on parse error.
    """
    if not condition or not condition.strip():
        return False
    try:
        tokens = _tokenize(condition.strip())
        if not tokens:
            return False
        parser = _Parser(tokens, ctrl, ctx)
        result = parser.parse()
        return bool(result)
    except Exception as exc:
        logger.warning(f"Condition parse error: {exc} | condition={condition!r}")
        return False
