"""Test stealth patch on Incolumitas."""
from camoufox.sync_api import Camoufox
import json, time

STEALTH_JS = """(() => {
    const patchFrame = (win) => {
        try {
            const Nav = win.Navigator.prototype;
            const desc = Object.getOwnPropertyDescriptor(Nav, 'webdriver');
            if (!desc) return;
            if (desc.get) {
                Object.defineProperty(Nav, 'webdriver', {
                    get: function webdriver() { return false; },
                    set: undefined,
                    enumerable: true,
                    configurable: true,
                });
                const getDesc = Object.getOwnPropertyDescriptor(Nav, 'webdriver');
                if (getDesc && getDesc.get) {
                    getDesc.get.toString = () => 'function get webdriver() {\\n    [native code]\\n}';
                }
            }
        } catch(e) {}
    };
    patchFrame(window);
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node.tagName === 'IFRAME' && node.contentWindow) {
                    patchFrame(node.contentWindow);
                }
            }
        }
    });
    if (document.documentElement) {
        observer.observe(document.documentElement, {childList: true, subtree: true});
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.documentElement, {childList: true, subtree: true});
        });
    }
})();"""

with Camoufox(headless=True, os='linux', humanize=True, block_webrtc=True, i_know_what_im_doing=True) as browser:
    page = browser.new_page()
    page.context.add_init_script(STEALTH_JS)
    page.goto('https://bot.incolumitas.com/', timeout=30000)
    page.wait_for_load_state('networkidle', timeout=15000)
    time.sleep(8)

    old_tests = page.evaluate("""() => {
        const pres = document.querySelectorAll('pre');
        for (const p of pres) {
            if (p.textContent.includes('webDriverAdvanced')) return p.textContent;
        }
        return null;
    }""")
    if old_tests:
        data = json.loads(old_tests)
        intoli = data.get('intoli', {})
        print(f"webDriver: {intoli.get('webDriver')}")
        print(f"webDriverAdvanced: {intoli.get('webDriverAdvanced')}")
        if intoli.get('webDriverAdvanced') == 'OK':
            print('SUCCESS!')
        else:
            print('Still failing - detection is deeper than descriptor checks')
    else:
        print('Could not find test results')
