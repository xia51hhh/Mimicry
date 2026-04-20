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
        self._persistent = False  # True when using persistent_context

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

    @property
    def _context(self):
        """Get the active BrowserContext regardless of launch mode."""
        if not self._browser:
            return None
        if self._persistent:
            return self._browser  # _browser IS the context
        return self._browser.contexts[0] if self._browser.contexts else None

    def launch(self, headless: bool = False, proxy: dict | None = None, profile: dict | None = None):
        if self._browser:
            logger.warning("Browser already running")
            return

        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            raise RuntimeError("Camoufox is not installed. Run camoufox.install first.")

        kwargs = {
            "headless": headless,
            "humanize": True,
            "os": "windows",
            "geoip": True,
            "block_webrtc": True,
            "enable_cache": True,
            "disable_coop": True,
            "i_know_what_im_doing": True,
        }
        if proxy:
            kwargs["proxy"] = proxy

        # Apply profile overrides
        if profile:
            if profile.get("user_data_dir"):
                kwargs["persistent_context"] = True
                kwargs["user_data_dir"] = profile["user_data_dir"]
            if profile.get("fingerprint"):
                kwargs["config"] = profile["fingerprint"]
            if profile.get("proxy"):
                kwargs["proxy"] = profile["proxy"]
            if profile.get("os_target"):
                kwargs["os"] = profile["os_target"]

        # Fit browser window to screen (cross-platform, DPI-aware)
        try:
            w, h = self._get_screen_size()
            kwargs["window"] = (max(w - 100, 800), max(h - 150, 600))
        except Exception:
            pass

        self._persistent = kwargs.get("persistent_context", False)
        logger.info(f"Launching Camoufox (headless={headless}, persistent={self._persistent})")
        self._camoufox = Camoufox(**kwargs)
        ctx_or_browser = self._camoufox.__enter__()

        if self._persistent:
            # persistent_context returns a BrowserContext directly
            self._browser = ctx_or_browser
            self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
        else:
            self._browser = ctx_or_browser
            self._page = self._browser.new_page()

        logger.info("Browser launched")

    def close(self):
        if self._camoufox:
            self._camoufox.__exit__(None, None, None)
            self._camoufox = None
            self._browser = None
            self._page = None
            self._persistent = False
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
        ctx = self._context
        return {
            "connected": self.connected,
            "url": self.get_url() if self.connected else None,
            "pages": len(ctx.pages) if ctx else 0,
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
            self._page.locator(selector).evaluate(f"el => el.scrollBy(0, {dy})")

    def evaluate(self, expression: str):
        return self._page.evaluate(expression)

    def get_element_text(self, selector: str) -> str:
        return self._page.locator(selector).inner_text()

    def get_element_attribute(self, selector: str, attr: str) -> str | None:
        return self._page.locator(selector).get_attribute(attr)

    def get_element_count(self, selector: str) -> int:
        return self._page.locator(selector).count()

    def is_visible(self, selector: str) -> bool:
        """Check if an element matching the selector is visible."""
        return self._page.locator(selector).is_visible()

    def upload_file(self, selector: str, file_path: str):
        self._page.locator(selector).set_input_files(file_path)

    def new_tab(self, url: str = "") -> None:
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        page = ctx.new_page()
        if url:
            page.goto(url)
        self._page = page

    def switch_tab(self, index: int) -> None:
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        pages = ctx.pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            self._page.bring_to_front()
        else:
            raise ValueError(f"Tab index {index} out of range (0-{len(pages)-1})")

    def close_tab(self, index: int | None = None) -> None:
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        pages = ctx.pages
        if index is not None:
            if 0 <= index < len(pages):
                pages[index].close()
            else:
                raise ValueError(f"Tab index {index} out of range")
        else:
            self._page.close()
        remaining = ctx.pages
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

    def switch_frame(self, selector: str | None = None) -> None:
        """Switch to an iframe by selector, or back to main frame if None."""
        if selector is None:
            self._page = self._page.main_frame.page
        else:
            frame = self._page.frame_locator(selector)
            # Store frame locator for subsequent operations
            self._frame_locator = frame

    def wait_for_page(self, state: str = "load", timeout: int = 30000) -> None:
        """Wait for page to reach a load state: 'load', 'domcontentloaded', 'networkidle'."""
        self._page.wait_for_load_state(state, timeout=timeout)

    def get_cookie(self, name: str | None = None) -> list[dict] | dict | None:
        """Get cookies. If name is provided, return that cookie; otherwise all."""
        ctx = self._context
        if not ctx:
            return []
        cookies = ctx.cookies()
        if name:
            for c in cookies:
                if c["name"] == name:
                    return c
            return None
        return cookies

    def set_cookie(self, cookies: list[dict]) -> None:
        """Add cookies to the browser context."""
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        ctx.add_cookies(cookies)

    def delete_cookie(self, name: str | None = None) -> None:
        """Clear cookies. If name given, clear only matching; otherwise all."""
        ctx = self._context
        if not ctx:
            return
        if name:
            ctx.clear_cookies(name=name)
        else:
            ctx.clear_cookies()

    def handle_download(self, save_path: str, timeout: int = 30000) -> str:
        """Wait for a download event and save the file."""
        import threading
        download_holder = [None]
        event = threading.Event()

        def on_download(download):
            download_holder[0] = download
            event.set()

        self._page.on("download", on_download)
        try:
            if not event.wait(timeout=timeout / 1000):
                raise TimeoutError(f"No download started within {timeout}ms")
            download = download_holder[0]
            download.save_as(save_path)
            return save_path
        finally:
            self._page.remove_listener("download", on_download)
