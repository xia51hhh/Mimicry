"""Unit tests for browser/selector.py — pure-function tests (no browser needed)."""
import pytest
from browser.selector import (
    _looks_dynamic,
    generate_candidates,
    score_candidate,
    SelectorCandidate,
)


# ── _looks_dynamic ──────────────────────────────────────────────────

class TestLooksDynamic:
    def test_empty_string(self):
        assert not _looks_dynamic("")

    def test_normal_id(self):
        assert not _looks_dynamic("login-btn")

    def test_long_hex(self):
        assert _looks_dynamic("a1b2c3d4e5f6")

    def test_uuid_style(self):
        assert _looks_dynamic("550e8400-e29b-41d4-a716-446655440000")

    def test_many_digits(self):
        assert _looks_dynamic("item-12345")

    def test_css_module_hash(self):
        assert _looks_dynamic("_a1b2c3d4e5")

    def test_short_number_ok(self):
        assert not _looks_dynamic("col-3")

    def test_normal_class(self):
        assert not _looks_dynamic("btn-primary")


# ── generate_candidates ────────────────────────────────────────────

class TestGenerateCandidates:
    def _base_element(self, **overrides) -> dict:
        info = {
            "tagName": "button",
            "id": "",
            "className": "",
            "name": "",
            "type": "",
            "role": "",
            "ariaLabel": "",
            "dataTestId": "",
            "dataAttrs": {},
            "textContent": "",
            "innerText": "",
            "placeholder": "",
            "href": "",
            "src": "",
            "depth": 3,
            "childIndex": 0,
            "siblingCount": 1,
        }
        info.update(overrides)
        return info

    def test_id_selector(self):
        candidates = generate_candidates(self._base_element(id="submit-btn"))
        selectors = [c["selector"] for c in candidates]
        assert "#submit-btn" in selectors

    def test_dynamic_id_excluded(self):
        candidates = generate_candidates(self._base_element(id="a1b2c3d4e5f6g7h8"))
        strategies = [c["strategy"] for c in candidates]
        assert "id" not in strategies

    def test_data_testid(self):
        candidates = generate_candidates(self._base_element(dataTestId="login-form"))
        selectors = [c["selector"] for c in candidates]
        assert '[data-testid="login-form"]' in selectors

    def test_text_selector(self):
        candidates = generate_candidates(self._base_element(innerText="Submit"))
        selectors = [c["selector"] for c in candidates]
        assert 'text="Submit"' in selectors

    def test_long_text_excluded(self):
        candidates = generate_candidates(self._base_element(innerText="x" * 60))
        strategies = [c["strategy"] for c in candidates]
        assert "text" not in strategies

    def test_name_attribute(self):
        candidates = generate_candidates(self._base_element(tagName="input", name="email"))
        selectors = [c["selector"] for c in candidates]
        assert 'input[name="email"]' in selectors

    def test_role_with_aria_label(self):
        candidates = generate_candidates(self._base_element(role="button", ariaLabel="Close"))
        selectors = [c["selector"] for c in candidates]
        assert 'role=button[name="Close"]' in selectors

    def test_role_without_aria_label(self):
        candidates = generate_candidates(self._base_element(role="navigation"))
        selectors = [c["selector"] for c in candidates]
        assert "role=navigation" in selectors

    def test_class_selector(self):
        candidates = generate_candidates(self._base_element(className="btn btn-primary"))
        selectors = [c["selector"] for c in candidates]
        assert "button.btn.btn-primary" in selectors

    def test_dynamic_classes_filtered(self):
        candidates = generate_candidates(self._base_element(className="_a1b2c3d4e5"))
        strategies = [c["strategy"] for c in candidates]
        assert "class" not in strategies

    def test_placeholder_for_input(self):
        candidates = generate_candidates(
            self._base_element(tagName="input", placeholder="Enter email")
        )
        selectors = [c["selector"] for c in candidates]
        assert 'input[placeholder="Enter email"]' in selectors

    def test_placeholder_ignored_for_div(self):
        candidates = generate_candidates(
            self._base_element(tagName="div", placeholder="Enter email")
        )
        selectors = [c["selector"] for c in candidates]
        assert all("placeholder" not in s for s in selectors)

    def test_empty_element_returns_empty(self):
        candidates = generate_candidates(self._base_element())
        assert candidates == []

    def test_multiple_strategies(self):
        candidates = generate_candidates(self._base_element(
            id="my-btn",
            dataTestId="submit",
            innerText="OK",
        ))
        strategies = {c["strategy"] for c in candidates}
        assert {"id", "data-testid", "text"}.issubset(strategies)


# ── score_candidate ────────────────────────────────────────────────

class TestScoreCandidate:
    def test_unique_id_high_score(self):
        cand = {"selector": "#login", "strategy": "id", "base_score": 95}
        result = score_candidate(cand, match_count=1, depth=2)
        assert isinstance(result, SelectorCandidate)
        assert result.is_unique is True
        assert result.score >= 80

    def test_non_unique_penalized(self):
        cand = {"selector": "div.card", "strategy": "class", "base_score": 55}
        unique = score_candidate(cand, match_count=1, depth=3)
        multiple = score_candidate(cand, match_count=10, depth=3)
        assert unique.score > multiple.score

    def test_deep_element_penalized(self):
        cand = {"selector": "#btn", "strategy": "id", "base_score": 95}
        shallow = score_candidate(cand, match_count=1, depth=2)
        deep = score_candidate(cand, match_count=1, depth=12)
        assert shallow.score >= deep.score

    def test_score_clamped_0_100(self):
        cand = {"selector": "x", "strategy": "xpath", "base_score": 25}
        result = score_candidate(cand, match_count=100, depth=20)
        assert 0 <= result.score <= 100

    def test_no_match_low_score(self):
        cand = {"selector": "#ghost", "strategy": "id", "base_score": 95}
        result = score_candidate(cand, match_count=0, depth=3)
        # Zero matches still gets partial score from high base_score (id=95)
        # but uniqueness component is 0 so score drops significantly
        unique_result = score_candidate(cand, match_count=1, depth=3)
        assert result.score < unique_result.score
