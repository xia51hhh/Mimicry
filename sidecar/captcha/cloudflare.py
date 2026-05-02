"""Cloudflare Turnstile / Interstitial click-based captcha solver (sync API).

Adapted from techinz/playwright-captcha @ 56b93e716a1b86fbbed6399c4952b9337d4a6758
  - playwright_captcha/solvers/click/cloudflare/solve_by_click.py
  - playwright_captcha/solvers/click/cloudflare/utils/{detection,dom_helpers}.py
  - playwright_captcha/solvers/click/common/{detection,shadow_root}.py
  - playwright_captcha/utils/exceptions.py

Upstream license: Apache License 2.0 (see examples/external/playwright-captcha/LICENSE).
NOTE: upstream pyproject.toml advertises MIT but the LICENSE file is Apache-2.0
text — we follow the LICENSE file (Apache-2.0) as the source of truth.

Changes from upstream:
- Rewritten from async (playwright.async_api) to sync (playwright.sync_api) to
  match Mimicry's BrowserController which uses camoufox.sync_api.
- FrameworkType abstraction removed (Mimicry locks Camoufox).
- Logging uses loguru via Mimicry's logger.
- Returns simple dicts instead of raising on detection failure (lets RPC caller
  decide whether to abort or fallback).
- Refactored into CaptchaSolver three-phase base class (Detect→Solve→Apply).
"""
from __future__ import annotations

import time
from typing import Any, Literal, Optional

from loguru import logger
from playwright.sync_api import ElementHandle, Frame, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .base import CaptchaSolver


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CaptchaDetectionError(Exception):
    """Raised when there is an error in captcha detection."""


class CaptchaSolvingError(Exception):
    """Raised when there is an error in solving the captcha."""


class CaptchaApplyingError(Exception):
    """Raised when there is an error in applying the solved captcha."""


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

# Selectors that indicate a Cloudflare interstitial (full-page "Just a moment").
CF_INTERSTITIAL_INDICATORS = [
    'script[src*="/cdn-cgi/challenge-platform/"]',
]

# Selectors that indicate an embedded Cloudflare Turnstile widget.
CF_TURNSTILE_INDICATORS = [
    'input[name="cf-turnstile-response"]',
    'script[src*="challenges.cloudflare.com/turnstile/v0"]',
]


def detect_cloudflare_challenge(
    container: Page | Frame | ElementHandle,
    challenge_type: Literal["turnstile", "interstitial"] = "turnstile",
) -> bool:
    """Return True if a Cloudflare challenge is detected in `container`.

    Detection is purely DOM-based; no clicks, no waits beyond a single locator
    count. Safe to call repeatedly.
    """
    if challenge_type not in ("turnstile", "interstitial"):
        raise ValueError("challenge_type must be 'turnstile' or 'interstitial'")

    selectors = (
        CF_TURNSTILE_INDICATORS
        if challenge_type == "turnstile"
        else CF_INTERSTITIAL_INDICATORS
    )
    for selector in selectors:
        try:
            element = container.locator(selector)
            if element.count() == 0:
                continue
        except Exception as e:
            # If the page navigated mid-check, treat as not-detected.
            if "Execution context was destroyed" in str(e):
                logger.warning(
                    "captcha: execution context destroyed during detection — treating as not detected"
                )
                return False
            raise

        logger.debug(f"captcha: cloudflare {challenge_type} detected via {selector}")
        return True

    return False


def _detect_expected_content(
    page: Page,
    container: Page | Frame | ElementHandle,
    expected_content_selector: Optional[str],
) -> bool:
    """Return True if the expected post-solve content is already visible."""
    if not expected_content_selector:
        return False
    return bool(
        page.locator(expected_content_selector).count() > 0
        or container.locator(expected_content_selector).count() > 0
    )


# ---------------------------------------------------------------------------
# Shadow DOM traversal
# ---------------------------------------------------------------------------

_COLLECT_SHADOW_ROOTS_JS = """
() => {
    const roots = [];
    function collect(node) {
        if (!node) return;
        const shadow = node.shadowRoot;
        if (shadow) { roots.push(shadow); collect(shadow); }
        for (const el of node.querySelectorAll("*")) {
            if (el.shadowRoot) collect(el);
        }
    }
    collect(document);
    return roots;
}
"""


def _get_shadow_roots(queryable: Page | Frame | ElementHandle) -> list[ElementHandle]:
    handle = queryable.evaluate_handle(_COLLECT_SHADOW_ROOTS_JS)
    properties = handle.get_properties()
    roots: list[ElementHandle] = []
    for prop_handle in properties.values():
        element = prop_handle.as_element()
        if element:
            roots.append(element)
    return roots


def _search_shadow_root_elements(
    queryable: Page | Frame | ElementHandle,
    selector: str,
    timeout_ms: int = 10000,
) -> list[ElementHandle]:
    """Find elements by CSS selector across all shadow roots in `queryable`.

    Sync version: iterates shadow roots and tries `wait_for_selector` on each
    with a per-root timeout. Returns the first match found in each root.
    """
    elements: list[ElementHandle] = []
    try:
        for root in _get_shadow_roots(queryable):
            try:
                el = root.wait_for_selector(selector, timeout=timeout_ms)
                if el:
                    elements.append(el)
                    # First match is enough for our use case (CF iframe / checkbox).
                    break
            except PlaywrightTimeoutError:
                continue
    except Exception as e:
        logger.error(f"captcha: error searching shadow roots: {e}")
    return elements


def _search_shadow_root_iframes(
    container: Page | Frame | ElementHandle,
    src_filter: str,
) -> list[Frame]:
    """Find iframes inside shadow roots whose `src` contains `src_filter`."""
    matched: list[Frame] = []
    try:
        for iframe_el in _search_shadow_root_elements(container, "iframe"):
            src = iframe_el.get_property("src").json_value()
            if src_filter in (src or ""):
                cf_frame = iframe_el.content_frame()
                if cf_frame and not cf_frame.is_detached():
                    matched.append(cf_frame)
    except Exception as e:
        logger.error(f"captcha: error searching shadow iframes: {e}")
    return matched


def _get_ready_checkbox(
    iframes: list[Frame],
    delay_s: int,
    attempts: int,
) -> Optional[tuple[Frame, ElementHandle]]:
    """Wait for a visible checkbox in any of the CF iframes.

    Returns (iframe, checkbox) or None on timeout.
    """
    if attempts <= 0:
        attempts = 1
    for _ in range(attempts):
        candidates: list[tuple[Frame, ElementHandle]] = []
        for iframe in iframes:
            try:
                if iframe.is_detached():
                    continue
                for cb in _search_shadow_root_elements(iframe, 'input[type="checkbox"]'):
                    candidates.append((iframe, cb))
            except Exception as e:
                logger.error(f"captcha: error finding checkboxes in iframe: {e}")

        for iframe, cb in candidates:
            try:
                if cb.is_visible():
                    return iframe, cb
            except Exception:
                continue

        time.sleep(delay_s)
    return None


def _click_checkbox(checkbox: ElementHandle, attempts: int) -> None:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            checkbox.click()
            logger.info("captcha: checkbox clicked")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning(f"captcha: click attempt {i + 1}/{attempts} failed: {e}")
    raise CaptchaSolvingError(
        f"Failed to click checkbox after {attempts} attempts: {last_err}"
    )


# ---------------------------------------------------------------------------
# Public solver
# ---------------------------------------------------------------------------

def solve_cloudflare_by_click(
    page: Page,
    container: Page | Frame | ElementHandle | None = None,
    challenge_type: Literal["turnstile", "interstitial"] = "turnstile",
    expected_content_selector: Optional[str] = None,
    solve_click_delay_s: int = 6,
    wait_checkbox_attempts: int = 10,
    wait_checkbox_delay_s: int = 6,
    checkbox_click_attempts: int = 3,
) -> dict:
    """Solve a Cloudflare Turnstile or Interstitial challenge by clicking the
    checkbox inside its shadow-DOM iframe.

    Args:
        page: Playwright sync Page.
        container: Page, Frame, or ElementHandle that wraps the captcha.
            Defaults to `page`.
        challenge_type: "turnstile" (embedded widget) or "interstitial"
            (full-page "Just a moment" challenge).
        expected_content_selector: Optional CSS selector that proves the
            challenge is over (e.g. main app content). If present, treated
            as success even when the challenge widget is still in DOM.
        solve_click_delay_s: How long to wait after clicking before checking
            success. Default 6s.
        wait_checkbox_attempts / wait_checkbox_delay_s: retry budget for
            locating a visible checkbox.
        checkbox_click_attempts: how many times to retry the click itself.

    Returns:
        dict with at least `solved: bool`. On success may include
        `challenge_type`. On failure, raises CaptchaSolvingError or
        CaptchaDetectionError.
    """
    container = container or page
    logger.info(f"captcha: starting cloudflare {challenge_type} click solver")

    # 1. Skip if no challenge present (or expected content already visible).
    if not detect_cloudflare_challenge(container, challenge_type):
        if _detect_expected_content(page, container, expected_content_selector):
            logger.info("captcha: expected content already present, nothing to solve")
            return {"solved": True, "skipped": "no_challenge"}
        logger.info("captcha: no cloudflare challenge detected")
        return {"solved": True, "skipped": "no_challenge"}

    # 2. Find Cloudflare challenge iframes in shadow DOM.
    cf_iframes = _search_shadow_root_iframes(
        container,
        src_filter="https://challenges.cloudflare.com/cdn-cgi/challenge-platform/",
    )
    if not cf_iframes:
        raise CaptchaDetectionError("Cloudflare iframes not found in shadow DOM")

    # 3. Wait for a ready, visible checkbox.
    checkbox_data = _get_ready_checkbox(
        cf_iframes,
        delay_s=wait_checkbox_delay_s,
        attempts=wait_checkbox_attempts,
    )
    if not checkbox_data:
        raise CaptchaDetectionError(
            "Cloudflare checkbox not ready after waiting"
        )
    iframe, checkbox = checkbox_data

    # 4. Click and verify.
    if challenge_type == "interstitial":
        _click_checkbox(checkbox, checkbox_click_attempts)
        try:
            page.wait_for_load_state(
                "networkidle", timeout=solve_click_delay_s * 1000
            )
        except PlaywrightTimeoutError:
            logger.debug("captcha: networkidle timeout, will check challenge state directly")
        challenge_solved = not detect_cloudflare_challenge(container, "interstitial")
    else:  # turnstile
        _click_checkbox(checkbox, checkbox_click_attempts)
        success_elements = _search_shadow_root_elements(iframe, 'div[id="success"]')
        success_el = next(iter(success_elements), None)
        if success_el is None:
            raise CaptchaDetectionError(
                "Cloudflare turnstile success element not present"
            )
        try:
            success_el.wait_for_element_state(
                "visible", timeout=solve_click_delay_s * 1000
            )
            challenge_solved = True
        except PlaywrightTimeoutError:
            challenge_solved = False

    # 5. Final verification — either success element / cleared challenge,
    # or the user-provided expected content appeared.
    if challenge_solved or _detect_expected_content(
        page, container, expected_content_selector
    ):
        logger.info(f"captcha: cloudflare {challenge_type} solved")
        return {"solved": True, "challenge_type": challenge_type}

    raise CaptchaSolvingError(
        f"Failed to solve cloudflare {challenge_type}: "
        "challenge still present and expected content not detected"
    )


# ---------------------------------------------------------------------------
# Three-phase solver class
# ---------------------------------------------------------------------------

class CloudflareSolver(CaptchaSolver):
    """Cloudflare captcha solver implementing the Detect→Solve→Apply pipeline."""

    def __init__(
        self,
        challenge_type: Literal["turnstile", "interstitial"] = "turnstile",
        expected_content_selector: str | None = None,
        solve_click_delay_s: int = 6,
        wait_checkbox_attempts: int = 10,
        wait_checkbox_delay_s: int = 6,
        checkbox_click_attempts: int = 3,
    ):
        self.challenge_type = challenge_type
        self.expected_content_selector = expected_content_selector
        self.solve_click_delay_s = solve_click_delay_s
        self.wait_checkbox_attempts = wait_checkbox_attempts
        self.wait_checkbox_delay_s = wait_checkbox_delay_s
        self.checkbox_click_attempts = checkbox_click_attempts

    def detect(self, page: Page, **kwargs: Any) -> dict:
        container = kwargs.get("container", page)
        detected = detect_cloudflare_challenge(container, self.challenge_type)
        if not detected and _detect_expected_content(page, container, self.expected_content_selector):
            return {"detected": False, "reason": "expected_content_present"}
        return {"detected": detected, "challenge_type": self.challenge_type}

    def solve(self, page: Page, detection: dict, **kwargs: Any) -> dict:
        container = kwargs.get("container", page)
        cf_iframes = _search_shadow_root_iframes(
            container,
            src_filter="https://challenges.cloudflare.com/cdn-cgi/challenge-platform/",
        )
        if not cf_iframes:
            return {"solved": False, "error": "iframes_not_found"}

        checkbox_data = _get_ready_checkbox(
            cf_iframes,
            delay_s=self.wait_checkbox_delay_s,
            attempts=self.wait_checkbox_attempts,
        )
        if not checkbox_data:
            return {"solved": False, "error": "checkbox_not_ready"}

        iframe, checkbox = checkbox_data
        try:
            _click_checkbox(checkbox, self.checkbox_click_attempts)
        except CaptchaSolvingError as e:
            return {"solved": False, "error": str(e)}

        return {"solved": True, "iframe": iframe, "checkbox": checkbox}

    def apply(self, page: Page, solution: dict, **kwargs: Any) -> dict:
        container = kwargs.get("container", page)
        iframe = solution.get("iframe")

        if self.challenge_type == "interstitial":
            try:
                page.wait_for_load_state("networkidle", timeout=self.solve_click_delay_s * 1000)
            except PlaywrightTimeoutError:
                pass
            resolved = not detect_cloudflare_challenge(container, "interstitial")
        else:
            success_elements = _search_shadow_root_elements(iframe, 'div[id="success"]') if iframe else []
            success_el = next(iter(success_elements), None)
            if success_el is None:
                return {"applied": False, "error": "success_element_missing"}
            try:
                success_el.wait_for_element_state("visible", timeout=self.solve_click_delay_s * 1000)
                resolved = True
            except PlaywrightTimeoutError:
                resolved = False

        applied = resolved or _detect_expected_content(page, container, self.expected_content_selector)
        return {"applied": applied, "challenge_type": self.challenge_type}
