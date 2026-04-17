"""Tests for the Pseudocode DSL engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dsl.lexer import tokenize, TokenType
from dsl.parser import parse
from dsl.compiler import compile_to_json, decompile_from_json


def test_tokenize_basic():
    tokens = tokenize('WORKFLOW "Test" { OPEN "https://example.com" }')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.KEYWORD in types
    assert TokenType.STRING in types
    assert TokenType.LBRACE in types
    assert TokenType.RBRACE in types


def test_parse_simple_workflow():
    src = '''WORKFLOW "Login" {
  OPEN "https://example.com"
  CLICK "#btn"
  TYPE "#input" "hello"
}'''
    wf = parse(src)
    assert wf.name == "Login"
    assert len(wf.body) == 3


def test_parse_wait():
    src = '''WORKFLOW "W" {
  WAIT selector="#el" timeout=10s
}'''
    wf = parse(src)
    assert wf.body[0].selector == "#el"
    assert wf.body[0].timeout == "10s"


def test_parse_extract():
    src = '''WORKFLOW "W" {
  EXTRACT text=".title" into=$name
}'''
    wf = parse(src)
    node = wf.body[0]
    assert node.mode == "text"
    assert node.selector == ".title"
    assert node.into == "$name"


def test_parse_if_else():
    src = '''WORKFLOW "W" {
  IF exists("#modal") {
    CLICK "#close"
  } ELSE {
    CLICK "#next"
  }
}'''
    wf = parse(src)
    if_node = wf.body[0]
    assert "exists" in if_node.condition
    assert len(if_node.body) == 1
    assert len(if_node.else_body) == 1


def test_parse_loop_items():
    src = '''WORKFLOW "W" {
  LOOP items=".card" as=$card max=10 {
    CLICK $card >> ".link"
  }
}'''
    wf = parse(src)
    loop = wf.body[0]
    assert loop.loop_type == "items"
    assert loop.items_selector == ".card"
    assert loop.variable == "$card"
    assert loop.max == 10
    assert len(loop.body) == 1


def test_parse_loop_count():
    src = '''WORKFLOW "W" {
  LOOP count=5 as=$i {
    LOG "iteration" $i
  }
}'''
    wf = parse(src)
    loop = wf.body[0]
    assert loop.loop_type == "count"
    assert loop.count == 5


def test_parse_set():
    src = '''WORKFLOW "W" {
  SET $name = "hello"
  SET $count = 42
}'''
    wf = parse(src)
    assert wf.body[0].name == "$name"
    assert wf.body[0].value == "hello"
    assert wf.body[1].value == 42


def test_compile_roundtrip():
    src = '''WORKFLOW "Test" {
  OPEN "https://example.com"
  CLICK "#btn"
  TYPE "#input" "world"
  WAIT selector=".done" timeout=5s
}'''
    wf = parse(src)
    json_out = compile_to_json(wf)
    assert json_out["name"] == "Test"
    assert len(json_out["nodes"]) == 4
    assert json_out["nodes"][0]["action"] == "open"
    assert json_out["nodes"][1]["action"] == "click"
    assert json_out["nodes"][2]["action"] == "type"
    assert json_out["nodes"][3]["action"] == "wait"


def test_decompile():
    workflow_json = {
        "name": "Demo",
        "nodes": [
            {"type": "action", "action": "open", "url": "https://example.com"},
            {"type": "action", "action": "click", "selector": "#btn"},
        ]
    }
    pseudo = decompile_from_json(workflow_json)
    assert 'WORKFLOW "Demo"' in pseudo
    assert 'OPEN "https://example.com"' in pseudo
    assert 'CLICK "#btn"' in pseudo


def test_full_roundtrip():
    """Parse → JSON → decompile → re-parse → JSON should produce equivalent output."""
    src = '''WORKFLOW "Roundtrip" {
  OPEN "https://example.com"
  CLICK ".btn"
  TYPE "#search" "hello"
  IF exists("#modal") {
    CLICK "#close"
  }
  LOOP count=3 as=$i {
    LOG "step" $i
  }
}'''
    wf1 = parse(src)
    json1 = compile_to_json(wf1)
    pseudo = decompile_from_json(json1)
    wf2 = parse(pseudo)
    json2 = compile_to_json(wf2)

    assert json1["name"] == json2["name"]
    assert len(json1["nodes"]) == len(json2["nodes"])
    for n1, n2 in zip(json1["nodes"], json2["nodes"]):
        assert n1["type"] == n2["type"]
        if "action" in n1:
            assert n1["action"] == n2["action"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
