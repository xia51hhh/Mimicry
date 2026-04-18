from loguru import logger
import platform
import subprocess
import re

# Set DPI awareness once at process level (Windows only)
if platform.system() == "Windows":
    import ctypes
    try:
        # Per-Monitor DPI Aware V2 (Win10 1703+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            # Per-Monitor DPI Aware (Win8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            # Legacy fallback (Vista+)
            ctypes.windll.user32.SetProcessDPIAware()


class BrowserController:
    def __init__(self):
        self._camoufox = None
        self._browser = None
        self._page = None

    @staticmethod
    def _get_screen_size() -> tuple[int, int]:
        """Get logical screen size in CSS pixels (DPI-aware, cross-platform)."""
        system = platform.system()
        if system == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            dc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, dc)
            scale = dpi / 96.0
            return int(sw / scale), int(sh / scale)
        elif system == "Darwin":
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"], text=True
            )
            m = re.search(r"Resolution:\s+(\d+)\s*x\s*(\d+)", out)
            if m:
                return int(m.group(1)), int(m.group(2))
        else:  # Linux / X11
            out = subprocess.check_output(["xdpyinfo"], text=True)
            m = re.search(r"dimensions:\s+(\d+)x(\d+)", out)
            if m:
                return int(m.group(1)), int(m.group(2))
        return 1920, 1080  # fallback

    @property
    def connected(self) -> bool:
        return self._browser is not None

    def launch(self, headless: bool = False, proxy: dict | None = None):
        if self._browser:
            logger.warning("Browser already running")
            return

        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            raise RuntimeError("Camoufox is not installed. Run camoufox.install first.")

        kwargs = {"headless": headless, "geoip": True, "block_webrtc": True}
        if proxy:
            kwargs["proxy"] = proxy

        # Fit browser window to screen (cross-platform, DPI-aware)
        try:
            w, h = self._get_screen_size()
            kwargs["window"] = (max(w - 100, 800), max(h - 150, 600))
        except Exception:
            pass

        logger.info(f"Launching Camoufox (headless={headless})")
        self._camoufox = Camoufox(**kwargs)
        self._browser = self._camoufox.__enter__()
        self._page = self._browser.new_page()
        logger.info("Browser launched")

    def close(self):
        if self._camoufox:
            self._camoufox.__exit__(None, None, None)
            self._camoufox = None
            self._browser = None
            self._page = None
            logger.info("Browser closed")

    def navigate(self, url: str):
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL scheme not allowed: {url}")
        self._page.goto(url)

    def click(self, selector: str):
        self._page.click(selector)

    def type_text(self, selector: str, text: str):
        self._page.fill(selector, text)

    def wait_for(self, selector: str, timeout: int = 5000):
        self._page.wait_for_selector(selector, timeout=timeout)

    def screenshot(self, path: str = "screenshot.png") -> str:
        self._page.screenshot(path=path)
        return path

    def get_url(self) -> str:
        return self._page.url if self._page else ""

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "url": self.get_url() if self.connected else None,
            "pages": len(self._browser.contexts[0].pages) if self._browser and self._browser.contexts else 0,
        }

    def dblclick(self, selector: str):
        self._page.dblclick(selector)

    def hover(self, selector: str):
        self._page.hover(selector)

    def select_option(self, selector: str, value: str):
        self._page.select_option(selector, value)

    def clear(self, selector: str):
        self._page.fill(selector, "")

    def focus(self, selector: str):
        self._page.focus(selector)

    def go_back(self):
        self._page.go_back()

    def go_forward(self):
        self._page.go_forward()

    def reload(self):
        self._page.reload()

    def press_key(self, selector: str, key: str):
        if selector and selector != "body":
            self._page.locator(selector).press(key)
        else:
            self._page.keyboard.press(key)

    def scroll(self, selector: str = "window", direction: str = "down", amount: int = 300):
        dy = amount if direction == "down" else -amount
        if selector == "window":
            self._page.evaluate(f"window.scrollBy(0, {dy})")
        else:
            self._page.locator(selector).scroll_into_view_if_needed()

    def evaluate(self, expression: str):
        return self._page.evaluate(expression)

    def get_element_text(self, selector: str) -> str:
        return self._page.locator(selector).inner_text()

    def get_element_attribute(self, selector: str, attr: str) -> str | None:
        return self._page.locator(selector).get_attribute(attr)

    def get_element_count(self, selector: str) -> int:
        return self._page.locator(selector).count()

    def upload_file(self, selector: str, file_path: str):
        self._page.locator(selector).set_input_files(file_path)

    def new_tab(self, url: str = "") -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        page = self._browser.contexts[0].new_page()
        if url:
            page.goto(url)
        self._page = page

    def switch_tab(self, index: int) -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        pages = self._browser.contexts[0].pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            self._page.bring_to_front()
        else:
            raise ValueError(f"Tab index {index} out of range (0-{len(pages)-1})")

    def close_tab(self, index: int | None = None) -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        pages = self._browser.contexts[0].pages
        if index is not None:
            if 0 <= index < len(pages):
                pages[index].close()
            else:
                raise ValueError(f"Tab index {index} out of range")
        else:
            self._page.close()
        remaining = self._browser.contexts[0].pages
        self._page = remaining[-1] if remaining else None

    def extract_table(self, selector: str) -> list[list[str]]:
        """Extract table data as a 2D list of strings."""
        return self._page.evaluate("""(selector) => {
            const table = document.querySelector(selector);
            if (!table) return [];
            return Array.from(table.rows).map(row =>
                Array.from(row.cells).map(cell => cell.innerText.trim())
            );
        }""", selector)

    def handle_dialog(self, accept: bool = True, text: str = "") -> None:
        def handler(dialog):
            if accept:
                dialog.accept(text) if text else dialog.accept()
            else:
                dialog.dismiss()
        self._page.once("dialog", handler)
