"""Tests for sidecar.captcha — Cloudflare click solver primitives.

Uses fake objects (no real browser, no network) to validate:
- detect_cloudflare_challenge returns True/False based on DOM selectors
- solve_cloudflare_by_click short-circuits when challenge isn't present
- exception types are raised on detection failure
"""
import sys
from pathlib import Path

import pytest

# Make sidecar root importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from captcha.cloudflare import (  # noqa: E402
    CaptchaDetectionError,
    detect_cloudflare_challenge,
    solve_cloudflare_by_click,
)


class _FakeLocator:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class _FakeContainer:
    """Mimics Playwright Page/Frame .locator(selector).count() interface."""

    def __init__(self, selectors_with_matches: dict[str, int]):
        self._matches = selectors_with_matches

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._matches.get(selector, 0))

    # solve_cloudflare_by_click also calls page.wait_for_load_state etc.,
    # but we only test the early-exit path here.


def test_detect_returns_false_when_no_indicators():
    container = _FakeContainer({})
    assert detect_cloudflare_challenge(container, "turnstile") is False
    assert detect_cloudflare_challenge(container, "interstitial") is False


def test_detect_turnstile_via_input_indicator():
    container = _FakeContainer({'input[name="cf-turnstile-response"]': 1})
    assert detect_cloudflare_challenge(container, "turnstile") is True


def test_detect_turnstile_via_script_indicator():
    container = _FakeContainer(
        {'script[src*="challenges.cloudflare.com/turnstile/v0"]': 2}
    )
    assert detect_cloudflare_challenge(container, "turnstile") is True


def test_detect_interstitial_via_script_indicator():
    container = _FakeContainer({'script[src*="/cdn-cgi/challenge-platform/"]': 1})
    assert detect_cloudflare_challenge(container, "interstitial") is True


def test_detect_invalid_challenge_type_raises():
    container = _FakeContainer({})
    with pytest.raises(ValueError, match="challenge_type must be"):
        detect_cloudflare_challenge(container, "hcaptcha")  # type: ignore[arg-type]


def test_detect_swallows_navigation_destroyed_error():
    """Navigation in the middle of detection should return False, not raise."""

    class _NavLocator:
        def count(self):
            raise RuntimeError("Execution context was destroyed, navigated away")

    class _NavContainer:
        def locator(self, selector):  # noqa: ARG002
            return _NavLocator()

    assert detect_cloudflare_challenge(_NavContainer(), "turnstile") is False


def test_detect_other_runtime_error_propagates():
    """Non-navigation runtime errors should bubble up — they hide real bugs otherwise."""

    class _BadLocator:
        def count(self):
            raise RuntimeError("Something else went wrong")

    class _BadContainer:
        def locator(self, selector):  # noqa: ARG002
            return _BadLocator()

    with pytest.raises(RuntimeError, match="Something else went wrong"):
        detect_cloudflare_challenge(_BadContainer(), "turnstile")


def test_solve_short_circuits_when_no_challenge():
    """If neither challenge nor expected content present, solver returns
    `solved=True, skipped='no_challenge'` without touching shadow DOM."""
    container = _FakeContainer({})
    result = solve_cloudflare_by_click(
        page=container,  # acts as `page` for the locator-only paths
        container=container,
        challenge_type="turnstile",
    )
    assert result == {"solved": True, "skipped": "no_challenge"}


def test_exception_hierarchy():
    # All Mimicry captcha errors are plain Exceptions with stable names so
    # callers can `except CaptchaDetectionError`.
    from captcha import (
        CaptchaApplyingError,
        CaptchaDetectionError as DE,
        CaptchaSolvingError,
    )

    assert issubclass(CaptchaDetectionError, Exception)
    assert issubclass(CaptchaSolvingError, Exception)
    assert issubclass(CaptchaApplyingError, Exception)
    assert DE is CaptchaDetectionError
