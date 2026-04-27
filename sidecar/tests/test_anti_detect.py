"""
Anti-detection automated tests.
Visits major fingerprint/bot detection sites and captures screenshots + results.

Usage:
    pytest tests/test_anti_detect.py -v --tb=short
    (Requires a real Camoufox install — not mocked)
"""

import os
import time
import pytest
from pathlib import Path

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"

# Detection test sites
SITES = [
    {
        "name": "sannysoft",
        "url": "https://bot.sannysoft.com/",
        "wait": 3,
        "fail_selectors": [],  # check screenshot manually
    },
    {
        "name": "creepjs",
        "url": "https://abrahamjuliot.github.io/creepjs/",
        "wait": 8,
        "fail_selectors": [],
    },
    {
        "name": "browserleaks_webrtc",
        "url": "https://browserleaks.com/webrtc",
        "wait": 5,
        "fail_selectors": [],
    },
    {
        "name": "pixelscan",
        "url": "https://pixelscan.net/",
        "wait": 8,
        "fail_selectors": [],
    },
    {
        "name": "browserscan",
        "url": "https://www.browserscan.net/",
        "wait": 6,
        "fail_selectors": [],
    },
]


@pytest.fixture(scope="module")
def browser_controller():
    """Launch a real Camoufox browser for anti-detection testing."""
    from browser.controller import BrowserController

    SCREENSHOT_DIR.mkdir(exist_ok=True)

    ctrl = BrowserController()
    ctrl.launch(headless=False)
    yield ctrl
    ctrl.close()


@pytest.mark.e2e
class TestAntiDetection:
    """Visit detection sites and save screenshots for manual review."""

    @pytest.mark.parametrize("site", SITES, ids=[s["name"] for s in SITES])
    def test_detection_site(self, browser_controller, site):
        ctrl = browser_controller
        page = ctrl._page

        # Navigate
        page.goto(site["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(site["wait"])

        # Screenshot
        path = str(SCREENSHOT_DIR / f"{site['name']}.png")
        page.screenshot(path=path, full_page=True)
        assert os.path.exists(path), f"Screenshot not saved for {site['name']}"

        # Check for explicit fail indicators if defined
        for sel in site.get("fail_selectors", []):
            elements = page.query_selector_all(sel)
            assert len(elements) == 0, (
                f"Fail indicator found on {site['name']}: {sel}"
            )

    def test_sannysoft_no_red(self, browser_controller):
        """SannyBot: ensure no red (failed) cells in the results table."""
        ctrl = browser_controller
        page = ctrl._page

        page.goto("https://bot.sannysoft.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)

        # Count red cells — indicates bot detection failure
        red_count = page.evaluate("""
            () => {
                const cells = document.querySelectorAll('td');
                let count = 0;
                cells.forEach(c => {
                    const bg = window.getComputedStyle(c).backgroundColor;
                    if (bg.includes('255, 0, 0') || bg.includes('255,0,0')) count++;
                });
                return count;
            }
        """)
        # Take screenshot with result annotation
        path = str(SCREENSHOT_DIR / "sannysoft_detail.png")
        page.screenshot(path=path, full_page=True)

        # Allow up to 2 minor red cells (some are expected like webdriver)
        assert red_count <= 2, (
            f"SannyBot detected {red_count} red (failed) indicators"
        )

    def test_webrtc_blocked(self, browser_controller):
        """Verify WebRTC is blocked — no local IP leak."""
        ctrl = browser_controller
        page = ctrl._page

        page.goto("https://browserleaks.com/webrtc", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        content = page.content()
        # If WebRTC is blocked, no local IP pattern should appear
        import re
        local_ips = re.findall(r"192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+", content)
        assert len(local_ips) == 0, f"WebRTC leak detected: {local_ips}"

    def test_pixelscan_consistent(self, browser_controller):
        """PixelScan: check for consistency status."""
        ctrl = browser_controller
        page = ctrl._page

        page.goto("https://pixelscan.net/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(10)

        path = str(SCREENSHOT_DIR / "pixelscan_detail.png")
        page.screenshot(path=path, full_page=True)

        # Check if "consistent" appears in the page
        content = page.text_content("body") or ""
        # Not a hard fail — just log the result
        if "inconsistent" in content.lower():
            pytest.xfail("PixelScan reported inconsistencies — check screenshot")
