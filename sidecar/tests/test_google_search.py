"""Manual test: Anti-detection validation across multiple sites.
Run: python -m pytest tests/test_google_search.py -v -s -k "not skipif"
Requires a running display (headless=False).
"""
import pytest
import time
import random


def _launch_browser():
    """Create a Camoufox browser with anti-detection settings."""
    from camoufox.sync_api import Camoufox
    return Camoufox(
        headless=False,
        humanize=True,
        geoip=False,
        block_webrtc=True,
        enable_cache=True,
        disable_coop=True,
        i_know_what_im_doing=True,
    )


def _human_type(page, locator, text):
    """Type text character by character with random delays."""
    locator.click()
    page.wait_for_timeout(300)
    for char in text:
        locator.type(char, delay=random.randint(50, 150))
        time.sleep(random.uniform(0.03, 0.12))


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly")
def test_google_search_via_typing():
    """Google search by typing into the search box (not direct URL).
    Ref: daijro/camoufox#388 — direct goto(/search?q=) triggers 100% detection.
    """
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://www.google.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        content = page.content()
        if "unusual traffic" in content.lower():
            page.screenshot(path="tests/screenshots/google_captcha_homepage.png")
            pytest.fail("Google CAPTCHA triggered on homepage")

        search_input = page.locator('textarea[name="q"], input[name="q"]')
        _human_type(page, search_input, "zlib python")
        page.wait_for_timeout(1000)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        content = page.content()
        page.screenshot(path="tests/screenshots/google_search_result.png")

        if "unusual traffic" in content.lower():
            pytest.fail("Google CAPTCHA triggered on search results")
        assert "zlib" in content.lower() or "python" in content.lower()
        print("✅ Google search passed")


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly")
def test_bing_search():
    """Bing search — less aggressive than Google but still validates basics."""
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://www.bing.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        search_input = page.locator('#sb_form_q')
        _human_type(page, search_input, "playwright browser automation")
        page.wait_for_timeout(800)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        content = page.content()
        page.screenshot(path="tests/screenshots/bing_search_result.png")

        # Bing bot detection typically redirects or shows empty results
        assert "playwright" in content.lower() or "automation" in content.lower(), \
            "Bing search results did not load — possible detection"
        print("✅ Bing search passed")


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly")
def test_duckduckgo_search():
    """DuckDuckGo — privacy-focused, minimal bot detection."""
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://duckduckgo.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        search_input = page.locator('#searchbox_input, input[name="q"]')
        _human_type(page, search_input, "camoufox browser")
        page.wait_for_timeout(800)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        content = page.content()
        page.screenshot(path="tests/screenshots/ddg_search_result.png")

        assert "camoufox" in content.lower() or "browser" in content.lower()
        print("✅ DuckDuckGo search passed")


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly")
def test_cloudflare_turnstile():
    """Cloudflare Turnstile challenge page — tests JS challenge bypass."""
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://nopecha.com/demo/cloudflare", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)  # Turnstile needs time

        content = page.content()
        page.screenshot(path="tests/screenshots/cloudflare_turnstile.png")

        # Check if challenge was solved (success indicator varies by site)
        is_blocked = "blocked" in content.lower() and "ray id" in content.lower()
        if is_blocked:
            pytest.fail("Cloudflare blocked the request")
        print("✅ Cloudflare Turnstile page loaded (check screenshot for challenge status)")


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly")
def test_browserscan_fingerprint():
    """BrowserScan.net — comprehensive fingerprint analysis."""
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://www.browserscan.net", wait_until="domcontentloaded")
        page.wait_for_timeout(10000)  # Allow all fingerprint tests to run

        page.screenshot(path="tests/screenshots/browserscan_current.png", full_page=True)

        # Extract detection score if available
        try:
            score_el = page.locator('.score-value, [class*="score"]').first
            score_text = score_el.text_content(timeout=5000)
            print(f"📊 BrowserScan score: {score_text}")
        except Exception:
            print("📊 BrowserScan score: (could not extract, check screenshot)")
        print("✅ BrowserScan fingerprint test completed (check screenshot)")
