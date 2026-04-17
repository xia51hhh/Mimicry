from camoufox.sync_api import Camoufox
from loguru import logger


class BrowserController:
    def __init__(self):
        self._camoufox = None
        self._browser = None
        self._page = None

    @property
    def connected(self) -> bool:
        return self._browser is not None

    def launch(self, headless: bool = False, proxy: dict | None = None):
        if self._browser:
            logger.warning("Browser already running")
            return

        kwargs = {"headless": headless, "geoip": True, "block_webrtc": True}
        if proxy:
            kwargs["proxy"] = proxy

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
            "pages": len(self._browser.contexts[0].pages) if self._browser else 0,
        }
