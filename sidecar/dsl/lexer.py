"""Tokenizer for the Mimicry Pseudocode DSL."""
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    STRING = auto()
    NUMBER = auto()
    VARIABLE = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    EQUALS = auto()
    CHAIN = auto()     # >>
    ASSIGN = auto()    # = (in SET)
    NEWLINE = auto()
    EOF = auto()
    IDENT = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int


KEYWORDS = {
    "WORKFLOW", "OPEN", "BACK", "FORWARD", "RELOAD",
    "CLICK", "DBLCLICK", "TYPE", "CLEAR", "SELECT", "HOVER", "SCROLL", "FOCUS",
    "WAIT", "EXTRACT", "SET",
    "IF", "ELSE", "LOOP",
    "SCREENSHOT", "LOG", "SLEEP", "FAIL",
}

_TOKEN_PATTERN = re.compile(r"""
    (?P<STRING>"(?:[^"\\]|\\.)*")    |
    (?P<CHAIN>>>)                     |
    (?P<ASSIGN>=)                     |
    (?P<LBRACE>\{)                    |
    (?P<RBRACE>\})                    |
    (?P<LPAREN>\()                    |
    (?P<RPAREN>\))                    |
    (?P<VARIABLE>\$\w+)              |
    (?P<NUMBER>\d+(?:\.\d+)?[a-zA-Z]*) |
    (?P<WORD>[a-zA-Z_]\w*(?:\.\w+)*) |
    (?P<SKIP>[ \t]+)                 |
    (?P<COMMENT>\#[^\n]*)            |
    (?P<NEWLINE>\n)                  |
    (?P<MISMATCH>.)
""", re.VERBOSE)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    for m in _TOKEN_PATTERN.finditer(source):
        kind = m.lastgroup
        value = m.group()
        if kind == "NEWLINE":
            tokens.append(Token(TokenType.NEWLINE, "\n", line))
            line += 1
        elif kind == "SKIP" or kind == "COMMENT":
            continue
        elif kind == "STRING":
            tokens.append(Token(TokenType.STRING, value[1:-1], line))
        elif kind == "CHAIN":
            tokens.append(Token(TokenType.CHAIN, value, line))
        elif kind == "ASSIGN":
            tokens.append(Token(TokenType.EQUALS, value, line))
        elif kind == "LBRACE":
            tokens.append(Token(TokenType.LBRACE, value, line))
        elif kind == "RBRACE":
            tokens.append(Token(TokenType.RBRACE, value, line))
        elif kind == "LPAREN":
            tokens.append(Token(TokenType.LPAREN, value, line))
        elif kind == "RPAREN":
            tokens.append(Token(TokenType.RPAREN, value, line))
        elif kind == "VARIABLE":
            tokens.append(Token(TokenType.VARIABLE, value, line))
        elif kind == "NUMBER":
            tokens.append(Token(TokenType.NUMBER, value, line))
        elif kind == "WORD":
            if value.upper() in KEYWORDS:
                tokens.append(Token(TokenType.KEYWORD, value.upper(), line))
            else:
                tokens.append(Token(TokenType.IDENT, value, line))
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character {value!r} at line {line}")
    tokens.append(Token(TokenType.EOF, "", line))
    return tokens
