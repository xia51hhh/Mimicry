"""Tests for the recursive descent condition parser."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from engine.condition_parser import evaluate_condition


def _make_mocks():
    ctrl = MagicMock()
    ctrl.get_element_count.return_value = 1
    ctrl.is_visible.return_value = True
    ctrl.get_url.return_value = "https://example.com/dashboard"
    ctrl.get_element_text.return_value = "Hello"

    ctx = MagicMock()
    ctx.get_var.side_effect = lambda name, default=None: {
        "$count": 5,
        "$name": "alice",
    }.get(name, default)
    ctx.resolve.side_effect = lambda s: s
    return ctrl, ctx


class TestSimpleConditions(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.ctx = _make_mocks()

    def test_exists_true(self):
        self.assertTrue(evaluate_condition('exists(".btn")', self.ctrl, self.ctx))
        self.ctrl.get_element_count.assert_called_with(".btn")

    def test_exists_false(self):
        self.ctrl.get_element_count.return_value = 0
        self.assertFalse(evaluate_condition('exists(".btn")', self.ctrl, self.ctx))

    def test_exists_exception(self):
        self.ctrl.get_element_count.side_effect = Exception("no page")
        self.assertFalse(evaluate_condition('exists(".btn")', self.ctrl, self.ctx))

    def test_visible(self):
        self.assertTrue(evaluate_condition('visible("#header")', self.ctrl, self.ctx))
        self.ctrl.is_visible.assert_called_with("#header")

    def test_visible_false(self):
        self.ctrl.is_visible.return_value = False
        self.assertFalse(evaluate_condition('visible("#header")', self.ctrl, self.ctx))

    def test_equals_true(self):
        self.assertTrue(evaluate_condition('equals("abc","abc")', self.ctrl, self.ctx))

    def test_equals_false(self):
        self.assertFalse(evaluate_condition('equals("abc","xyz")', self.ctrl, self.ctx))

    def test_contains_true(self):
        self.assertTrue(evaluate_condition('contains("hello world","world")', self.ctrl, self.ctx))

    def test_contains_false(self):
        self.assertFalse(evaluate_condition('contains("hello","xyz")', self.ctrl, self.ctx))

    def test_regex_true(self):
        self.assertTrue(evaluate_condition('regex("abc123","\\d+")', self.ctrl, self.ctx))

    def test_regex_false(self):
        self.assertFalse(evaluate_condition('regex("abcdef","\\d+")', self.ctrl, self.ctx))

    def test_url_contains_true(self):
        self.assertTrue(evaluate_condition('url_contains("dashboard")', self.ctrl, self.ctx))

    def test_url_contains_false(self):
        self.assertFalse(evaluate_condition('url_contains("settings")', self.ctrl, self.ctx))

    def test_text_comparison(self):
        self.assertTrue(evaluate_condition('text(".title") == "Hello"', self.ctrl, self.ctx))

    def test_text_comparison_false(self):
        self.assertFalse(evaluate_condition('text(".title") == "Bye"', self.ctrl, self.ctx))

    def test_text_exception(self):
        self.ctrl.get_element_text.side_effect = Exception("not found")
        self.assertFalse(evaluate_condition('text(".title") == "Hello"', self.ctrl, self.ctx))

    def test_variable_eq_string(self):
        self.assertTrue(evaluate_condition('$name == "alice"', self.ctrl, self.ctx))

    def test_variable_eq_string_false(self):
        self.assertFalse(evaluate_condition('$name == "bob"', self.ctrl, self.ctx))

    def test_variable_eq_number(self):
        self.assertTrue(evaluate_condition('$count == 5', self.ctrl, self.ctx))

    def test_variable_eq_number_false(self):
        self.assertFalse(evaluate_condition('$count == 3', self.ctrl, self.ctx))


class TestComparisonOperators(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.ctx = _make_mocks()

    def test_not_equal(self):
        self.assertTrue(evaluate_condition('$count != 3', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$count != 5', self.ctrl, self.ctx))

    def test_greater_than(self):
        self.assertTrue(evaluate_condition('$count > 3', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$count > 5', self.ctrl, self.ctx))

    def test_less_than(self):
        self.assertTrue(evaluate_condition('$count < 10', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$count < 5', self.ctrl, self.ctx))

    def test_greater_equal(self):
        self.assertTrue(evaluate_condition('$count >= 5', self.ctrl, self.ctx))
        self.assertTrue(evaluate_condition('$count >= 4', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$count >= 6', self.ctrl, self.ctx))

    def test_less_equal(self):
        self.assertTrue(evaluate_condition('$count <= 5', self.ctrl, self.ctx))
        self.assertTrue(evaluate_condition('$count <= 6', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$count <= 4', self.ctrl, self.ctx))

    def test_string_not_equal(self):
        self.assertTrue(evaluate_condition('$name != "bob"', self.ctrl, self.ctx))
        self.assertFalse(evaluate_condition('$name != "alice"', self.ctrl, self.ctx))


class TestLogicalOperators(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.ctx = _make_mocks()

    def test_not(self):
        self.ctrl.get_element_count.return_value = 0
        self.assertTrue(evaluate_condition('not exists(".btn")', self.ctrl, self.ctx))

    def test_not_true_becomes_false(self):
        self.assertFalse(evaluate_condition('not exists(".btn")', self.ctrl, self.ctx))

    def test_and_both_true(self):
        self.assertTrue(evaluate_condition('exists(".btn") and visible("#header")', self.ctrl, self.ctx))

    def test_and_one_false(self):
        self.ctrl.is_visible.return_value = False
        self.assertFalse(evaluate_condition('exists(".btn") and visible("#header")', self.ctrl, self.ctx))

    def test_or_one_true(self):
        self.ctrl.is_visible.return_value = False
        self.assertTrue(evaluate_condition('exists(".btn") or visible("#header")', self.ctrl, self.ctx))

    def test_or_both_false(self):
        self.ctrl.get_element_count.return_value = 0
        self.ctrl.is_visible.return_value = False
        self.assertFalse(evaluate_condition('exists(".btn") or visible("#header")', self.ctrl, self.ctx))

    def test_and_or_precedence(self):
        # and binds tighter: a or (b and c)
        self.ctrl.get_element_count.return_value = 0  # exists = False
        self.ctrl.is_visible.return_value = True       # visible = True
        # False or (True and 5==5) => False or True => True
        result = evaluate_condition('exists(".x") or visible("#y") and $count == 5', self.ctrl, self.ctx)
        self.assertTrue(result)

    def test_parentheses_override_precedence(self):
        self.ctrl.get_element_count.return_value = 0
        self.ctrl.is_visible.return_value = True
        # (False or True) and 5==3 => True and False => False
        result = evaluate_condition('(exists(".x") or visible("#y")) and $count == 3', self.ctrl, self.ctx)
        self.assertFalse(result)

    def test_complex_nested(self):
        # not (False and True) => not False => True
        self.ctrl.get_element_count.return_value = 0
        result = evaluate_condition('not (exists(".x") and visible("#y"))', self.ctrl, self.ctx)
        self.assertTrue(result)

    def test_multiple_and(self):
        self.assertTrue(evaluate_condition(
            'exists(".a") and visible("#b") and $count == 5', self.ctrl, self.ctx
        ))

    def test_multiple_or(self):
        self.ctrl.get_element_count.return_value = 0
        self.ctrl.is_visible.return_value = False
        # all false except last
        self.assertTrue(evaluate_condition(
            'exists(".a") or visible("#b") or $count == 5', self.ctrl, self.ctx
        ))


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.ctx = _make_mocks()

    def test_empty_string(self):
        self.assertFalse(evaluate_condition("", self.ctrl, self.ctx))

    def test_whitespace_only(self):
        self.assertFalse(evaluate_condition("   ", self.ctrl, self.ctx))

    def test_none_condition(self):
        self.assertFalse(evaluate_condition(None, self.ctrl, self.ctx))

    def test_parse_error_returns_false(self):
        self.assertFalse(evaluate_condition("??? invalid", self.ctrl, self.ctx))

    def test_unknown_function_returns_false(self):
        self.assertFalse(evaluate_condition('bogus("x")', self.ctrl, self.ctx))

    def test_variable_resolve_in_args(self):
        """ctx.resolve is called on string arguments."""
        self.ctx.resolve.side_effect = lambda s: s.replace("$var", "resolved")
        result = evaluate_condition('equals("$var","resolved")', self.ctrl, self.ctx)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
