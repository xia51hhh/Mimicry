"""AST node definitions for the Mimicry Pseudocode DSL."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    line: int = 0


@dataclass
class Workflow(Node):
    name: str = ""
    body: list[Node] = field(default_factory=list)


@dataclass
class Open(Node):
    url: str = ""


@dataclass
class Back(Node):
    pass


@dataclass
class Forward(Node):
    pass


@dataclass
class Reload(Node):
    pass


@dataclass
class Click(Node):
    selector: str = ""


@dataclass
class DblClick(Node):
    selector: str = ""


@dataclass
class Type(Node):
    selector: str = ""
    text: str = ""


@dataclass
class Clear(Node):
    selector: str = ""


@dataclass
class Select(Node):
    selector: str = ""
    value: str = ""


@dataclass
class Hover(Node):
    selector: str = ""


@dataclass
class Scroll(Node):
    selector: str = ""
    direction: str = "down"
    amount: int = 300


@dataclass
class Focus(Node):
    selector: str = ""


@dataclass
class Wait(Node):
    selector: str | None = None
    url_contains: str | None = None
    time: str | None = None
    timeout: str = "5s"


@dataclass
class Extract(Node):
    mode: str = "text"  # text | attr | count
    selector: str = ""
    attr_name: str | None = None
    into: str = ""


@dataclass
class SetVar(Node):
    name: str = ""
    value: Any = None


@dataclass
class If(Node):
    condition: str = ""
    body: list[Node] = field(default_factory=list)
    else_body: list[Node] = field(default_factory=list)


@dataclass
class Loop(Node):
    loop_type: str = "items"  # items | count | while
    items_selector: str | None = None
    count: int | None = None
    while_condition: str | None = None
    variable: str | None = None
    max: int | None = None
    body: list[Node] = field(default_factory=list)


@dataclass
class Screenshot(Node):
    filename: str = "screenshot.png"


@dataclass
class Log(Node):
    parts: list[str] = field(default_factory=list)


@dataclass
class Sleep(Node):
    duration: str = "1s"


@dataclass
class Fail(Node):
    message: str = ""
