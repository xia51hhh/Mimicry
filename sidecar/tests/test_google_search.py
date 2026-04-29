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
    """Type text character by character with random delays and human-like click."""
    # Click with slight offset from center to mimic real user
    box = locator.bounding_box()
    if box:
        x_offset = random.randint(-int(box["width"] * 0.2), int(box["width"] * 0.2))
        y_offset = random.randint(-int(box["height"] * 0.2), int(box["height"] * 0.2))
        locator.click(position={"x": box["width"] / 2 + x_offset, "y": box["height"] / 2 + y_offset})
    else:
        locator.click()
    page.wait_for_timeout(random.randint(300, 600))
    for char in text:
        locator.type(char, delay=random.randint(80, 200))
        time.sleep(random.uniform(0.05, 0.18))


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
    """Bing search — validates no CAPTCHA/challenge on search."""
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://www.bing.com", wait_until="domcontentloaded")
        page.wait_for_timeout(random.randint(3000, 5000))

        # Move mouse naturally before interacting
        page.mouse.move(random.randint(200, 600), random.randint(150, 400))
        page.wait_for_timeout(random.randint(500, 1000))

        search_input = page.locator('#sb_form_q')
        _human_type(page, search_input, "zlib compression library")
        page.wait_for_timeout(random.randint(800, 1500))
        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)

        content = page.content()
        page.screenshot(path="tests/screenshots/bing_search_result.png")

        # Detect Bing challenge page
        challenge_markers = ["one last step", "solve the challenge", "verifying"]
        is_challenged = any(m in content.lower() for m in challenge_markers)
        if is_challenged:
            # Wait for potential auto-resolution
            page.wait_for_timeout(12000)
            content = page.content()
            page.screenshot(path="tests/screenshots/bing_search_result_retry.png")
            is_challenged = any(m in content.lower() for m in challenge_markers)

        if is_challenged:
            pytest.fail("Bing CAPTCHA/challenge triggered — 'One last step' page shown")

        assert "zlib" in content.lower() or "compression" in content.lower(), \
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
    """Cloudflare Turnstile widget (non-interactive mode).
    Uses peet.ws test page — a real Turnstile widget, not a managed challenge.
    """
    with _launch_browser() as browser:
        page = browser.new_page()
        page.goto("https://peet.ws/turnstile-test/non-interactive.html", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)  # Turnstile needs time to verify

        content = page.content()
        title = page.title()
        page.screenshot(path="tests/screenshots/cloudflare_turnstile.png")

        # Check for challenge/block indicators
        challenge_markers = [
            "verify you are human",
            "just a moment",
            "checking if the site connection is secure",
        ]
        is_challenged = any(m in content.lower() for m in challenge_markers)
        is_blocked = "blocked" in content.lower() and "ray id" in content.lower()

        if is_blocked:
            pytest.fail("Cloudflare blocked the request (Ray ID page)")
        if is_challenged:
            pytest.fail(f"Cloudflare Turnstile challenge not auto-resolved (title: {title})")

        print("✅ Cloudflare Turnstile passed")


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
