"""Deep analysis of Bing detection mechanism."""
import sys, os, time, random, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.makedirs(os.path.join(os.path.dirname(__file__), 'screenshots'), exist_ok=True)

import pytest
pytest.mark.skipif = lambda *a, **kw: lambda fn: fn
from tests.test_google_search import _launch_browser, _human_type

with _launch_browser() as browser:
    page = browser.new_page()

    # Immediately check fingerprint BEFORE any navigation
    page.goto("about:blank")
    ua = page.evaluate("navigator.userAgent")
    plat = page.evaluate("navigator.platform")
    print(f"=== Fingerprint Check (os='linux' on {platform.system()}) ===")
    print(f"  UA: {ua}")
    print(f"  Platform: {plat}")

    # Check OS consistency
    is_linux_ua = "linux" in ua.lower() or "X11" in ua
    is_linux_plat = "linux" in plat.lower()
    print(f"  UA contains Linux: {is_linux_ua}")
    print(f"  Platform is Linux: {is_linux_plat}")

    if not is_linux_ua:
        print("  ⚠️ OS MISMATCH — Camoufox generated non-Linux fingerprint!")
    else:
        print("  ✅ OS matches host system")

    # Now navigate to Bing
    response = page.goto("https://www.bing.com", wait_until="domcontentloaded")
    print(f"\nBing homepage status: {response.status}")
    page.wait_for_timeout(random.randint(4000, 6000))

    # Interact
    page.mouse.move(random.randint(200, 600), random.randint(150, 400))
    page.wait_for_timeout(random.randint(1000, 2000))

    search_input = page.locator("#sb_form_q")
    _human_type(page, search_input, "python zlib documentation")
    page.wait_for_timeout(random.randint(1000, 2000))
    page.keyboard.press("Enter")
    page.wait_for_timeout(6000)

    content = page.content()
    title = page.title()
    url = page.url
    print(f"\nAfter search:")
    print(f"  Title: {title}")
    print(f"  URL: {url}")

    challenge_markers = ["one last step", "solve the challenge", "verifying"]
    is_challenged = any(m in content.lower() for m in challenge_markers)
    print(f"  Challenged: {is_challenged}")

    if is_challenged:
        print("\n  Challenge page analysis:")
        iframes = page.frames
        print(f"  Frames: {len(iframes)}")
        for f in iframes:
            print(f"    Frame: {f.url[:100]}")

        # Check cookies post-challenge
        cookies = page.context.cookies()
        akamai = [c for c in cookies if "ak_" in c.get("name", "") or "bm_" in c.get("name", "")]
        print(f"\n  Akamai cookies: {len(akamai)}")
        for c in akamai:
            print(f"    {c['name']}: {c['value'][:60]}")

        page.screenshot(path="tests/screenshots/bing_oslinux_challenge.png")
    else:
        results = page.locator("#b_results .b_algo")
        print(f"  Search results count: {results.count()}")
        page.screenshot(path="tests/screenshots/bing_oslinux_pass.png")
        print("  ✅ PASS!")
