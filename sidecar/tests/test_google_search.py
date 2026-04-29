"""Manual test: Google search detection.
Run: python -m pytest tests/test_google_search.py -v -s
Requires a running display (headless=False).
"""
import pytest
import time


@pytest.mark.skipif(True, reason="Manual E2E test — run explicitly with -k test_google")
def test_google_search_via_typing():
    """Test Google search by typing into the search box (not direct URL).

    Issue daijro/camoufox#388 shows that direct page.goto("/search?q=...")
    triggers detection. Typing into the search field and pressing Enter is the
    correct approach.
    """
    from camoufox.sync_api import Camoufox

    with Camoufox(
        headless=False,
        humanize=True,
        geoip=False,
        block_webrtc=True,
        enable_cache=True,
        disable_coop=True,
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()

        # Go to Google homepage first (not /search?q=)
        page.goto("https://www.google.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Check if CAPTCHA already shown
        content = page.content()
        if "unusual traffic" in content.lower() or "captcha" in content.lower():
            page.screenshot(path="tests/screenshots/google_captcha_homepage.png")
            pytest.fail("Google CAPTCHA triggered on homepage")

        # Find search input and type
        search_input = page.locator('textarea[name="q"], input[name="q"]')
        search_input.click()
        page.wait_for_timeout(500)

        # Type character by character with random delays
        import random
        for char in "zlib python":
            search_input.type(char, delay=random.randint(50, 150))
            time.sleep(random.uniform(0.05, 0.15))

        page.wait_for_timeout(1000)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        # Check results
        content = page.content()
        page.screenshot(path="tests/screenshots/google_search_result.png")

        if "unusual traffic" in content.lower():
            pytest.fail("Google CAPTCHA triggered on search results")

        # Verify search results loaded
        assert "zlib" in content.lower() or "python" in content.lower(), \
            "Search results did not load properly"
        print("✅ Google search passed without CAPTCHA")
