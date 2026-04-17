"""Parser: tokens -> AST for the Mimicry Pseudocode DSL."""
from __future__ import annotations
from . import ast_nodes as ast
from .lexer import Token, TokenType, tokenize


class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(f"Line {line}: {msg}")
        self.line = line


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    @property
    def _current(self) -> Token:
        return self._tokens[min(self._pos, len(self._tokens) - 1)]

    def _peek(self) -> Token:
        return self._current

    def _advance(self) -> Token:
        tok = self._current
        self._pos += 1
        return tok

    def _expect(self, ttype: TokenType, value: str | None = None) -> Token:
        tok = self._current
        if tok.type != ttype or (value and tok.value != value):
            expected = value or ttype.name
            raise ParseError(f"Expected {expected}, got {tok.value!r}", tok.line)
        return self._advance()

    def _skip_newlines(self):
        while self._current.type == TokenType.NEWLINE:
            self._advance()

    def _is_keyword(self, *names: str) -> bool:
        t = self._current
        return t.type == TokenType.KEYWORD and t.value in names

    def _parse_selector_with_chain(self) -> str:
        """Parse a selector that may include >> chaining."""
        tok = self._current
        if tok.type == TokenType.STRING:
            sel = self._advance().value
        elif tok.type == TokenType.VARIABLE:
            sel = self._advance().value
        else:
            raise ParseError(f"Expected selector, got {tok.value!r}", tok.line)

        if self._current.type == TokenType.CHAIN:
            self._advance()
            right = self._current
            if right.type == TokenType.STRING:
                sel += f" >> {self._advance().value}"
            else:
                raise ParseError("Expected string after >>", right.line)
        return sel

    def _parse_kv_args(self) -> dict[str, str]:
        """Parse key=value pairs until newline/EOF/brace."""
        args: dict[str, str] = {}
        while self._current.type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.LBRACE, TokenType.RBRACE):
            if self._current.type == TokenType.IDENT:
                key = self._advance().value
                self._expect(TokenType.EQUALS)
                val_tok = self._current
                if val_tok.type in (TokenType.STRING, TokenType.NUMBER, TokenType.VARIABLE, TokenType.IDENT):
                    args[key] = self._advance().value
                else:
                    raise ParseError(f"Expected value for {key}", val_tok.line)
            else:
                break
        return args

    def _parse_block(self) -> list[ast.Node]:
        self._skip_newlines()
        self._expect(TokenType.LBRACE)
        self._skip_newlines()
        stmts = []
        while self._current.type != TokenType.RBRACE:
            if self._current.type == TokenType.EOF:
                raise ParseError("Unexpected end of input, missing }", self._current.line)
            stmt = self._parse_statement()
            if stmt:
                stmts.append(stmt)
            self._skip_newlines()
        self._expect(TokenType.RBRACE)
        return stmts

    def _parse_statement(self) -> ast.Node | None:
        self._skip_newlines()
        tok = self._current
        if tok.type == TokenType.EOF or tok.type == TokenType.RBRACE:
            return None
        if tok.type != TokenType.KEYWORD:
            raise ParseError(f"Expected keyword, got {tok.value!r}", tok.line)

        kw = tok.value
        line = tok.line
        self._advance()

        match kw:
            case "WORKFLOW":
                return self._parse_workflow(line)
            case "OPEN":
                url = self._expect(TokenType.STRING).value
                return ast.Open(line=line, url=url)
            case "BACK":
                return ast.Back(line=line)
            case "FORWARD":
                return ast.Forward(line=line)
            case "RELOAD":
                return ast.Reload(line=line)
            case "CLICK":
                sel = self._parse_selector_with_chain()
                return ast.Click(line=line, selector=sel)
            case "DBLCLICK":
                sel = self._parse_selector_with_chain()
                return ast.DblClick(line=line, selector=sel)
            case "TYPE":
                sel = self._parse_selector_with_chain()
                text = self._expect(TokenType.STRING).value
                return ast.Type(line=line, selector=sel, text=text)
            case "CLEAR":
                sel = self._parse_selector_with_chain()
                return ast.Clear(line=line, selector=sel)
            case "SELECT":
                sel = self._parse_selector_with_chain()
                val = self._expect(TokenType.STRING).value
                return ast.Select(line=line, selector=sel, value=val)
            case "HOVER":
                sel = self._parse_selector_with_chain()
                return ast.Hover(line=line, selector=sel)
            case "SCROLL":
                sel = self._parse_selector_with_chain()
                args = self._parse_kv_args()
                return ast.Scroll(
                    line=line, selector=sel,
                    direction=args.get("direction", "down"),
                    amount=int(args.get("amount", "300")),
                )
            case "FOCUS":
                sel = self._parse_selector_with_chain()
                return ast.Focus(line=line, selector=sel)
            case "WAIT":
                return self._parse_wait(line)
            case "EXTRACT":
                return self._parse_extract(line)
            case "SET":
                return self._parse_set(line)
            case "IF":
                return self._parse_if(line)
            case "LOOP":
                return self._parse_loop(line)
            case "SCREENSHOT":
                fname = "screenshot.png"
                if self._current.type == TokenType.STRING:
                    fname = self._advance().value
                return ast.Screenshot(line=line, filename=fname)
            case "LOG":
                parts = []
                while self._current.type in (TokenType.STRING, TokenType.VARIABLE):
                    parts.append(self._advance().value)
                return ast.Log(line=line, parts=parts)
            case "SLEEP":
                dur = self._current
                if dur.type in (TokenType.NUMBER, TokenType.IDENT):
                    return ast.Sleep(line=line, duration=self._advance().value)
                raise ParseError("Expected duration after SLEEP", line)
            case "FAIL":
                msg = self._expect(TokenType.STRING).value
                return ast.Fail(line=line, message=msg)
            case _:
                raise ParseError(f"Unknown keyword {kw}", line)

    def _parse_workflow(self, line: int) -> ast.Workflow:
        name = self._expect(TokenType.STRING).value
        body = self._parse_block()
        return ast.Workflow(line=line, name=name, body=body)

    def _parse_wait(self, line: int) -> ast.Wait:
        args = self._parse_kv_args()
        return ast.Wait(
            line=line,
            selector=args.get("selector"),
            url_contains=args.get("url_contains"),
            time=args.get("time"),
            timeout=args.get("timeout", "5s"),
        )

    def _parse_extract(self, line: int) -> ast.Extract:
        args = self._parse_kv_args()
        if "text" in args:
            return ast.Extract(line=line, mode="text", selector=args["text"], into=args.get("into", ""))
        elif "attr" in args:
            return ast.Extract(line=line, mode="attr", selector=args["attr"],
                               attr_name=args.get("name"), into=args.get("into", ""))
        elif "count" in args:
            return ast.Extract(line=line, mode="count", selector=args["count"], into=args.get("into", ""))
        raise ParseError("EXTRACT requires text=, attr=, or count=", line)

    def _parse_set(self, line: int) -> ast.SetVar:
        name_tok = self._expect(TokenType.VARIABLE)
        self._expect(TokenType.EQUALS)
        val_tok = self._current
        if val_tok.type == TokenType.STRING:
            value = self._advance().value
        elif val_tok.type == TokenType.NUMBER:
            raw = self._advance().value
            value = float(raw) if "." in raw else int(raw)
        else:
            raise ParseError("Expected string or number value for SET", val_tok.line)
        return ast.SetVar(line=line, name=name_tok.value, value=value)

    def _parse_if(self, line: int) -> ast.If:
        cond_parts = []
        while self._current.type not in (TokenType.LBRACE, TokenType.NEWLINE, TokenType.EOF):
            tok = self._advance()
            if tok.type == TokenType.STRING:
                cond_parts.append(f'"{tok.value}"')
            else:
                cond_parts.append(tok.value)
        condition = " ".join(cond_parts)
        body = self._parse_block()
        else_body: list[ast.Node] = []
        self._skip_newlines()
        if self._is_keyword("ELSE"):
            self._advance()
            else_body = self._parse_block()
        return ast.If(line=line, condition=condition, body=body, else_body=else_body)

    def _parse_loop(self, line: int) -> ast.Loop:
        args = self._parse_kv_args()
        body = self._parse_block()
        if "items" in args:
            return ast.Loop(
                line=line, loop_type="items",
                items_selector=args["items"], variable=args.get("as"),
                max=int(args["max"]) if "max" in args else None,
                body=body,
            )
        elif "count" in args:
            return ast.Loop(
                line=line, loop_type="count",
                count=int(args["count"]), variable=args.get("as"),
                body=body,
            )
        elif "while" in args:
            return ast.Loop(
                line=line, loop_type="while",
                while_condition=args["while"], variable=args.get("as"),
                max=int(args["max"]) if "max" in args else None,
                body=body,
            )
        raise ParseError("LOOP requires items=, count=, or while=", line)


def parse(source: str) -> ast.Workflow:
    tokens = tokenize(source)
    parser = Parser(tokens)
    parser._skip_newlines()
    stmt = parser._parse_statement()
    if not isinstance(stmt, ast.Workflow):
        raise ParseError("Top-level must be a WORKFLOW block", 1)
    return stmt
