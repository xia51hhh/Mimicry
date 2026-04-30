"""Quick test script: webDriverAdvanced analysis."""
from camoufox.sync_api import Camoufox
import json

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
    page.goto('about:blank')

    result = page.evaluate("""() => {
        const val = navigator.webdriver;
        const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
        // iframe cross-check
        const iframe = document.createElement('iframe');
        document.body.appendChild(iframe);
        const iframeVal = iframe.contentWindow.navigator.webdriver;
        const iframeDesc = Object.getOwnPropertyDescriptor(
            iframe.contentWindow.Navigator.prototype, 'webdriver'
        );
        // toString check
        let mainGetterStr = null;
        let iframeGetterStr = null;
        if (desc && desc.get) mainGetterStr = desc.get.toString();
        if (iframeDesc && iframeDesc.get) iframeGetterStr = iframeDesc.get.toString();
        document.body.removeChild(iframe);
        return {
            mainValue: val,
            mainDesc: desc ? {
                configurable: desc.configurable,
                enumerable: desc.enumerable,
                hasGetter: !!desc.get,
                writable: desc.writable,
                value: desc.value
            } : null,
            mainGetterStr: mainGetterStr,
            iframeValue: iframeVal,
            iframeDesc: iframeDesc ? {
                configurable: iframeDesc.configurable,
                hasGetter: !!iframeDesc.get,
                writable: iframeDesc.writable,
                value: iframeDesc.value
            } : null,
            iframeGetterStr: iframeGetterStr,
        };
    }""")
    print(json.dumps(result, indent=2))

    main_cfg = result['mainDesc']['configurable'] if result['mainDesc'] else None
    iframe_cfg = result['iframeDesc']['configurable'] if result['iframeDesc'] else None
    if main_cfg == iframe_cfg and result['mainValue'] == result['iframeValue']:
        print("\nCONSISTENT: iframe matches main window")
    else:
        print(f"\nMISMATCH: main configurable={main_cfg}, iframe configurable={iframe_cfg}")

