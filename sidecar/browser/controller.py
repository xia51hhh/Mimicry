from loguru import logger
import platform
import random
import subprocess
import re
import time
import uuid
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

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


@dataclass
class TabInfo:
    """Tab identification metadata for recording/replay matching."""
    tab_id: str          # UUID, runtime-unique
    seq: int             # Creation order (1-based, never reused)
    url_origin: str      # e.g. "https://example.com"
    url_path: str        # e.g. "/login"
    title: str           # Page title at time of capture

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_page(page, tab_id: str, seq: int) -> "TabInfo":
        parsed = urlparse(page.url or "")
        return TabInfo(
            tab_id=tab_id,
            seq=seq,
            url_origin=f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else "",
            url_path=parsed.path or "/",
            title=page.title() if page.url else "",
        )


class BrowserController:
    def __init__(self):
        self._camoufox = None
        self._browser = None
        self._page = None
        self._persistent = False  # True when using persistent_context
        self._browser_pid = None
        self.launch_warnings: list[str] = []
        self._on_disconnected = None
        # Tab identification registry
        self._tab_registry: dict[str, TabInfo] = {}   # tabId → TabInfo
        self._page_to_tab: dict[int, str] = {}        # id(page) → tabId
        self._seq_counter: int = 0                      # monotonic, 1-based

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
        else:  # Linux
            import os
            # GNOME Wayland/X11: parse Mutter D-Bus for current monitors
            try:
                dbus_out = subprocess.check_output(
                    ["gdbus", "call", "--session",
                     "--dest", "org.gnome.Mutter.DisplayConfig",
                     "--object-path", "/org/gnome/Mutter/DisplayConfig",
                     "--method", "org.gnome.Mutter.DisplayConfig.GetCurrentState"],
                    text=True, stderr=subprocess.DEVNULL, timeout=3,
                )
                # Find all current modes: ('WxH@freq', W, H, freq, scale, [...], {'is-current': <true>...})
                # Parse each is-current block to extract resolution and scale
                monitors = []
                for m in re.finditer(r"'is-current': <true>", dbus_out):
                    chunk = dbus_out[max(0, m.start() - 400):m.start()]
                    # Find resolution: W, H, freq, scale pattern
                    mode = re.findall(r"(\d+),\s*(\d+),\s*[\d.]+,\s*([\d.]+),\s*\[", chunk)
                    if mode:
                        w, h, sc = mode[-1]
                        monitors.append((int(w), int(h), float(sc)))
                if monitors:
                    # Pick the monitor with highest resolution
                    w, h, sc = max(monitors, key=lambda m: m[0] * m[1])
                    scale = max(1, round(sc))
                    return w // scale, h // scale
            except Exception:
                pass

            # Fallback: xdpyinfo + GDK_SCALE
            scale = 1
            gdk = os.environ.get("GDK_SCALE")
            if gdk:
                try:
                    scale = int(gdk)
                except ValueError:
                    pass
            try:
                out = subprocess.check_output(["xdpyinfo"], text=True, stderr=subprocess.DEVNULL)
                m = re.search(r"dimensions:\s+(\d+)x(\d+)", out)
                if m:
                    pw, ph = int(m.group(1)), int(m.group(2))
                    return pw // scale, ph // scale
            except Exception:
                pass
        return 1920, 1080  # fallback

    @staticmethod
    def get_monitors() -> list[dict]:
        """Get all connected monitors with logical resolution (after scaling)."""
        system = platform.system()
        monitors = []

        if system == "Linux":
            try:
                dbus_out = subprocess.check_output(
                    ["gdbus", "call", "--session",
                     "--dest", "org.gnome.Mutter.DisplayConfig",
                     "--object-path", "/org/gnome/Mutter/DisplayConfig",
                     "--method", "org.gnome.Mutter.DisplayConfig.GetCurrentState"],
                    text=True, stderr=subprocess.DEVNULL, timeout=3,
                )
                # Parse connector names and current modes
                import re
                # Find connector names (e.g., 'eDP-1', 'DP-4')
                connectors = re.findall(r"\('([A-Za-z]+-\d+)',", dbus_out)
                connector_idx = 0
                for m in re.finditer(r"'is-current': <true>", dbus_out):
                    chunk = dbus_out[max(0, m.start() - 400):m.start()]
                    mode = re.findall(r"(\d+),\s*(\d+),\s*[\d.]+,\s*([\d.]+),\s*\[", chunk)
                    if mode:
                        w, h, sc = mode[-1]
                        w, h, sc = int(w), int(h), float(sc)
                        scale = max(1, round(sc))
                        name_match = re.findall(r"'display-name': <'([^']+)'>", dbus_out[m.start():m.start()+500])
                        name = name_match[0] if name_match else f"Monitor {connector_idx + 1}"
                        monitors.append({
                            "name": name,
                            "physical_width": w,
                            "physical_height": h,
                            "scale": sc,
                            "logical_width": w // scale,
                            "logical_height": h // scale,
                        })
                    connector_idx += 1
            except Exception as e:
                logger.debug(f"Monitor detection failed: {e}")

        if not monitors:
            # Fallback: single monitor from _get_screen_size
            w, h = BrowserController._get_screen_size()
            monitors.append({
                "name": "Primary",
                "physical_width": w,
                "physical_height": h,
                "scale": 1.0,
                "logical_width": w,
                "logical_height": h,
            })

        return monitors

    @property
    def connected(self) -> bool:
        if not self._browser:
            return False
        try:
            # Check if browser process is still alive
            if hasattr(self._browser, 'is_connected'):
                return self._browser.is_connected()
            # For persistent context, check pages
            if self._persistent:
                return len(self._browser.pages) > 0
            return len(self._browser.contexts) > 0
        except Exception:
            return False

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
        except ImportError as e:
            logger.error(f"Camoufox import failed: {e}")
            raise RuntimeError("Camoufox is not installed. Run camoufox.install first.")

        kwargs = {
            "headless": headless,
            "humanize": True,
            "os": {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
                platform.system(), "linux"
            ),
            "geoip": False,
            "block_webrtc": True,
            "enable_cache": True,
            "disable_coop": True,
            "i_know_what_im_doing": True,
        }
        if proxy:
            kwargs["proxy"] = proxy

        # Apply profile overrides
        if profile:
            logger.info(f"Applying profile overrides: {list(profile.keys())}")
            if profile.get("user_data_dir"):
                kwargs["persistent_context"] = True
                kwargs["user_data_dir"] = profile["user_data_dir"]
            if profile.get("fingerprint"):
                kwargs["config"] = profile["fingerprint"]
            if profile.get("proxy"):
                kwargs["proxy"] = profile["proxy"]
            if profile.get("os_target"):
                kwargs["os"] = profile["os_target"]

            # Apply browser_config overrides
            bc = profile.get("browser_config") or {}
            if isinstance(bc, dict):
                # Bool/value params: direct mapping to Camoufox kwargs
                bool_params = [
                    "headless", "geoip", "block_webrtc", "block_webgl",
                    "block_images", "enable_cache", "disable_coop",
                ]
                for key in bool_params:
                    if key in bc:
                        kwargs[key] = bc[key]

                if "humanize" in bc:
                    kwargs["humanize"] = bc["humanize"]
                if bc.get("locale"):
                    kwargs["locale"] = bc["locale"]
                if bc.get("timezone"):
                    # timezone goes into Camoufox config dict
                    kwargs.setdefault("config", {})
                    kwargs["config"]["timezone"] = bc["timezone"]
                if bc.get("os"):
                    kwargs["os"] = bc["os"]
                if bc.get("fonts"):
                    kwargs["fonts"] = bc["fonts"]
                if bc.get("addons"):
                    kwargs["addons"] = bc["addons"]
                if bc.get("executable_path"):
                    kwargs["executable_path"] = bc["executable_path"]
                if bc.get("args"):
                    kwargs["args"] = bc["args"]
                if bc.get("virtual_display"):
                    kwargs["virtual_display"] = bc["virtual_display"]

                # Window size from browser_config takes priority
                if bc.get("window_width") and bc.get("window_height"):
                    kwargs["window"] = (bc["window_width"], bc["window_height"])

        # Fit browser window to screen if not explicitly set
        if "window" not in kwargs:
            try:
                w, h = self._get_screen_size()
                kwargs["window"] = (w, h)
                logger.debug(f"Screen size: {w}x{h}, window: {kwargs['window']}")
            except Exception as e:
                logger.warning(f"Failed to detect screen size: {e}")

        self._persistent = kwargs.get("persistent_context", False)
        # Log kwargs without potentially large config values
        safe_log = {k: v for k, v in kwargs.items() if k != "config"}
        logger.info(f"Launching Camoufox: {safe_log}")

        self.launch_warnings = []

        try:
            self._camoufox = Camoufox(**kwargs)
            ctx_or_browser = self._camoufox.__enter__()
        except Exception as e:
            # Retry without geoip if IP lookup failed
            if "ip" in str(e).lower() and kwargs.get("geoip"):
                self.launch_warnings.append(f"GeoIP 定位失败 ({e})，已禁用 GeoIP 继续启动")
                logger.warning(f"geoip failed ({e}), retrying without geoip")
                kwargs["geoip"] = False
                try:
                    self._camoufox = Camoufox(**kwargs)
                    ctx_or_browser = self._camoufox.__enter__()
                except Exception as e2:
                    logger.error(f"Camoufox launch failed (retry): {type(e2).__name__}: {e2}")
                    self._camoufox = None
                    raise
            else:
                logger.error(f"Camoufox launch failed: {type(e).__name__}: {e}")
                self._camoufox = None
                raise

        if self._persistent:
            # persistent_context returns a BrowserContext directly
            self._browser = ctx_or_browser
            self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
        else:
            self._browser = ctx_or_browser
            self._page = self._browser.new_page()

        # Save browser process PID for force-kill fallback
        try:
            impl = getattr(self._browser, '_impl_obj', self._browser)
            if hasattr(impl, '_browser_type'):
                # For BrowserContext (persistent), try parent browser
                bt = impl._browser_type
                if hasattr(bt, '_connection') and hasattr(bt._connection, '_transport'):
                    proc = getattr(bt._connection._transport, '_proc', None)
                    if proc:
                        self._browser_pid = proc.pid
            elif hasattr(impl, '_connection'):
                proc = getattr(impl._connection._transport, '_proc', None)
                if proc:
                    self._browser_pid = proc.pid
        except Exception:
            pass
        if not self._browser_pid:
            # Fallback: find Firefox PID from process tree
            try:
                import psutil
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if 'firefox' in (p.info.get('name') or '').lower():
                        cmdline = p.info.get('cmdline') or []
                        if any('camoufox' in str(c).lower() for c in cmdline):
                            self._browser_pid = p.pid
                            break
            except Exception:
                pass
        logger.info(f"Browser PID: {self._browser_pid}")

        # Inject anti-detection patches before any navigation
        self._inject_stealth_scripts()

        # Navigate to startup URL if configured
        startup_url = (profile or {}).get("browser_config", {}).get("startup_url")
        if startup_url and startup_url.startswith(("http://", "https://")):
            try:
                self._page.goto(startup_url)
            except Exception as e:
                logger.warning(f"Failed to navigate to startup URL: {e}")

        # Initialize tab registry with the first page
        self._register_page(self._page)
        # Track externally opened tabs (window.open, target="_blank")
        ctx = self._context
        if ctx:
            ctx.on("page", self._on_external_page)

        logger.info("Browser launched")

        # Register disconnect listener
        try:
            if self._persistent:
                self._browser.on("close", lambda: self._fire_disconnected())
            else:
                self._browser.on("disconnected", lambda: self._fire_disconnected())
        except Exception as e:
            logger.warning(f"Failed to register disconnect listener: {e}")

    def _fire_disconnected(self):
        logger.info("Browser disconnected event fired")
        if self._on_disconnected:
            try:
                self._on_disconnected()
            except Exception as e:
                logger.warning(f"on_disconnected callback error: {e}")

    # -- Anti-detection stealth patches --
    _STEALTH_JS = """\
    (() => {
        // Ensure navigator.webdriver descriptor consistency across all frames.
        // Camoufox patches this at C++ level but dynamically-created iframes
        // may have a slightly different descriptor. This script normalizes them.
        const patchFrame = (win) => {
            try {
                const Nav = win.Navigator.prototype;
                const desc = Object.getOwnPropertyDescriptor(Nav, 'webdriver');
                if (!desc) return;
                // If it's already a getter returning false, ensure native appearance
                if (desc.get) {
                    const nativeGet = desc.get;
                    Object.defineProperty(Nav, 'webdriver', {
                        get: function webdriver() { return false; },
                        set: undefined,
                        enumerable: true,
                        configurable: true,
                    });
                    // Make toString look native
                    const getDesc = Object.getOwnPropertyDescriptor(Nav, 'webdriver');
                    if (getDesc && getDesc.get) {
                        getDesc.get.toString = () => 'function get webdriver() {\\n    [native code]\\n}';
                    }
                }
            } catch(e) {}
        };
        patchFrame(window);
        // Patch iframes as they are added to DOM
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
    })();
    """

    def _inject_stealth_scripts(self):
        """Inject anti-detection scripts into the browser context."""
        ctx = self._context
        if not ctx:
            return
        try:
            ctx.add_init_script(self._STEALTH_JS)
            logger.debug("Stealth scripts injected")
        except Exception as e:
            logger.warning(f"Failed to inject stealth scripts: {e}")

    def _register_page(self, page) -> TabInfo:
        """Register a page in the tab registry and return its TabInfo.
        Idempotent: if page is already registered, returns existing TabInfo."""
        existing_tab_id = self._page_to_tab.get(id(page))
        if existing_tab_id and existing_tab_id in self._tab_registry:
            return self._tab_registry[existing_tab_id]
        self._seq_counter += 1
        tab_id = str(uuid.uuid4())
        info = TabInfo.from_page(page, tab_id, self._seq_counter)
        self._tab_registry[tab_id] = info
        self._page_to_tab[id(page)] = tab_id
        # Auto-cleanup on close (handles manual close, crash, etc.)
        page.on("close", lambda p=page: self._unregister_page(p))
        logger.debug(f"Tab registered: seq={info.seq}, tabId={tab_id[:8]}..., url={info.url_origin}{info.url_path}")
        return info

    def _unregister_page(self, page) -> TabInfo | None:
        """Remove a page from the tab registry."""
        tab_id = self._page_to_tab.pop(id(page), None)
        if tab_id:
            info = self._tab_registry.pop(tab_id, None)
            if info:
                logger.debug(f"Tab unregistered: seq={info.seq}, tabId={tab_id[:8]}...")
            return info
        return None

    def _on_external_page(self, page) -> None:
        """Handle externally opened tab (window.open, target=_blank)."""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        try:
            self._register_page(page)
            self._page = page
            logger.info(f"External tab detected and registered (seq={self._seq_counter})")
        except Exception as e:
            logger.warning(f"Failed to register external page: {e}")

    def _update_tab_info(self, page) -> None:
        """Refresh URL/title in registry for a page."""
        tab_id = self._page_to_tab.get(id(page))
        if tab_id and tab_id in self._tab_registry:
            info = self._tab_registry[tab_id]
            parsed = urlparse(page.url or "")
            info.url_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else ""
            info.url_path = parsed.path or "/"
            try:
                info.title = page.title() if page.url else ""
            except Exception:
                pass

    def get_current_tab_info(self) -> dict | None:
        """Get TabInfo for the current active page."""
        if not self._page:
            return None
        self._update_tab_info(self._page)
        tab_id = self._page_to_tab.get(id(self._page))
        if tab_id and tab_id in self._tab_registry:
            return self._tab_registry[tab_id].to_dict()
        return None

    def get_all_tabs(self) -> list[dict]:
        """Get TabInfo for all open pages."""
        ctx = self._context
        if not ctx:
            return []
        result = []
        for page in ctx.pages:
            self._update_tab_info(page)
            tab_id = self._page_to_tab.get(id(page))
            if tab_id and tab_id in self._tab_registry:
                result.append(self._tab_registry[tab_id].to_dict())
        return result

    def close(self):
        camoufox = self._camoufox
        browser = self._browser
        pid = self._browser_pid
        self._camoufox = None
        self._browser = None
        self._page = None
        self._persistent = False
        self._browser_pid = None
        # Clear tab registry
        self._tab_registry.clear()
        self._page_to_tab.clear()
        self._seq_counter = 0

        if not camoufox and not browser and not pid:
            return

        import signal, os

        # Close on the current thread so Playwright's greenlet can switch
        # back to the dispatcher_fiber that was created on this same thread.
        try:
            if browser:
                browser.close()
        except Exception as e:
            logger.warning(f"Browser.close error: {e}")
        try:
            if camoufox:
                camoufox.__exit__(None, None, None)
        except Exception as e:
            logger.warning(f"Camoufox exit error: {e}")

        # Force kill if process is still alive
        if pid:
            try:
                os.kill(pid, 0)  # Check if alive
                os.kill(pid, signal.SIGKILL)
                logger.info(f"Force-killed browser process {pid}")
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.warning(f"Failed to kill browser process {pid}: {e}")

        logger.info("Browser closed")

    def navigate(self, url: str, wait_until: str = "networkidle"):
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL scheme not allowed: {url}")
        try:
            self._page.goto(url, wait_until=wait_until)
        except Exception:
            # networkidle may timeout on sites with persistent connections; fall back to load
            if wait_until != "load":
                self._page.goto(url, wait_until="load")

    def click(self, selector: str, force: bool = False):
        self._page.click(selector, force=force)

    def type_text(self, selector: str, text: str, humanize: bool = True):
        locator = self._page.locator(selector)
        if humanize:
            locator.click()
            locator.fill("")
            for char in text:
                locator.press(char, delay=random.randint(50, 180))
                if random.random() < 0.05:
                    time.sleep(random.uniform(0.3, 0.8))
        else:
            locator.fill(text)

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

    def select_option(self, selector: str, value: str, humanize: bool = True):
        locator = self._page.locator(selector)
        if humanize:
            locator.click()
            time.sleep(random.uniform(0.2, 0.5))
        locator.select_option(value)

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

    def scroll(self, selector: str = "window", direction: str = "down", amount: int = 300, humanize: bool = True):
        dy = amount if direction == "down" else -amount
        if humanize:
            if selector != "window":
                box = self._page.locator(selector).bounding_box()
                if box:
                    cx = box["x"] + box["width"] / 2 + random.randint(-10, 10)
                    cy = box["y"] + box["height"] / 2 + random.randint(-10, 10)
                    self._page.mouse.move(cx, cy)
                else:
                    self._page.locator(selector).evaluate(f"el => el.scrollBy(0, {dy})")
                    return
            remaining = abs(dy)
            while remaining > 0:
                step = min(remaining, random.randint(80, 150))
                actual_dy = step if dy > 0 else -step
                self._page.mouse.wheel(0, actual_dy)
                remaining -= step
                time.sleep(random.uniform(0.02, 0.08))
        else:
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

    def new_tab(self, url: str = "") -> dict:
        """Open a new tab, optionally navigate to url. Returns TabInfo dict."""
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        page = ctx.new_page()
        if url:
            page.goto(url)
        self._page = page
        info = self._register_page(page)
        return info.to_dict()

    def switch_tab(self, target: int | str | dict | None = None, **match_hints) -> dict:
        """Switch to a tab using gradient matching.

        Matching priority:
        1. tabId exact match (same session)
        2. seq creation order (cross-session replay)
        3. urlOrigin + urlPath (auxiliary + hand-written workflow)
        4. title fallback

        Args:
            target: int (legacy index), str (tabId), or dict with match hints
            **match_hints: seq, urlOrigin, urlPath, title
        Returns: TabInfo dict of switched-to tab
        """
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        pages = ctx.pages
        if not pages:
            raise RuntimeError("No tabs available")

        # Legacy: plain integer index
        if isinstance(target, int):
            if 0 <= target < len(pages):
                self._page = pages[target]
                self._page.bring_to_front()
                self._update_tab_info(self._page)
                tab_id = self._page_to_tab.get(id(self._page))
                return self._tab_registry[tab_id].to_dict() if tab_id else {}
            raise ValueError(f"Tab index {target} out of range (0-{len(pages)-1})")

        # Build match criteria from target dict or kwargs
        criteria = {}
        if isinstance(target, dict):
            criteria = target
        elif isinstance(target, str):
            criteria["tabId"] = target
        criteria.update(match_hints)

        # Priority 1: tabId exact match
        if tab_id := criteria.get("tabId"):
            for page in pages:
                if self._page_to_tab.get(id(page)) == tab_id:
                    self._page = page
                    page.bring_to_front()
                    self._update_tab_info(page)
                    return self._tab_registry[tab_id].to_dict()

        # Priority 2: seq match
        if (raw_seq := criteria.get("seq")) is not None:
            seq = int(raw_seq)
            for tid, info in self._tab_registry.items():
                if info.seq == seq:
                    for page in pages:
                        if self._page_to_tab.get(id(page)) == tid:
                            self._page = page
                            page.bring_to_front()
                            self._update_tab_info(page)
                            return info.to_dict()

        # Priority 3: urlOrigin + urlPath
        url_origin = criteria.get("urlOrigin", "")
        url_path = criteria.get("urlPath", "")
        if url_origin:
            for page in pages:
                self._update_tab_info(page)
                tid = self._page_to_tab.get(id(page))
                if tid and tid in self._tab_registry:
                    info = self._tab_registry[tid]
                    if info.url_origin == url_origin and (not url_path or info.url_path == url_path):
                        self._page = page
                        page.bring_to_front()
                        return info.to_dict()

        # Priority 4: title fallback
        if title := criteria.get("title"):
            for page in pages:
                self._update_tab_info(page)
                tid = self._page_to_tab.get(id(page))
                if tid and tid in self._tab_registry:
                    info = self._tab_registry[tid]
                    if title.lower() in info.title.lower():
                        self._page = page
                        page.bring_to_front()
                        return info.to_dict()

        raise ValueError(f"No tab matching criteria: {criteria}")

    def close_tab(self, target: int | str | None = None) -> None:
        """Close a tab by index, tabId, or current tab (None)."""
        ctx = self._context
        if not ctx:
            raise RuntimeError("No browser context")
        pages = ctx.pages

        page_to_close = None
        if target is None:
            page_to_close = self._page
        elif isinstance(target, int):
            if 0 <= target < len(pages):
                page_to_close = pages[target]
            else:
                raise ValueError(f"Tab index {target} out of range")
        elif isinstance(target, str):
            # tabId match
            for page in pages:
                if self._page_to_tab.get(id(page)) == target:
                    page_to_close = page
                    break
            if not page_to_close:
                raise ValueError(f"No tab with tabId: {target}")

        if page_to_close:
            page_to_close.close()
            # _unregister_page is called by the page.on("close") listener
            # registered in _register_page, but call explicitly as safety net
            self._unregister_page(page_to_close)

        remaining = ctx.pages
        if remaining:
            if self._page not in remaining:
                self._page = remaining[-1]
                self._page.bring_to_front()
        else:
            self._page = None

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

    def setup_download_listener(self, timeout: int = 30000):
        """Pre-register download listener. Call before the action that triggers download."""
        import threading
        self._download_holder = [None]
        self._download_event = threading.Event()
        self._download_timeout = timeout

        def on_download(download):
            self._download_holder[0] = download
            self._download_event.set()

        self._page.on("download", on_download)
        self._download_handler = on_download

    def wait_for_download(self, save_path: str) -> str:
        """Wait for the pre-registered download to complete and save it."""
        timeout = getattr(self, "_download_timeout", 30000)
        if not self._download_event.wait(timeout=timeout / 1000):
            raise TimeoutError(f"No download started within {timeout}ms")
        download = self._download_holder[0]
        download.save_as(save_path)
        self._page.remove_listener("download", self._download_handler)
        return save_path

    def handle_download(self, save_path: str, timeout: int = 30000) -> str:
        """Backward-compatible: setup + wait."""
        self.setup_download_listener(timeout)
        return self.wait_for_download(save_path)


class SessionManager:
    """Manages multiple BrowserController instances keyed by session_id."""

    def __init__(self):
        self._sessions: dict[str, BrowserController] = {}
        import threading
        self._lock = threading.Lock()
        self._on_session_disconnected = None  # callback(session_id)

    def create(self, session_id: str, **kwargs) -> BrowserController:
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing and existing.connected:
                logger.info(f"Session reused: {session_id}")
                return existing
            if existing:
                try:
                    existing.close()
                except Exception:
                    pass
                del self._sessions[session_id]

        # Launch on the current thread — Playwright's greenlet-based sync API
        # binds dispatcher_fiber to the calling thread.  Launching in a
        # separate thread would cause all subsequent Playwright calls to fail
        # with "cannot switch to a different thread (which happens to have
        # exited)" once that thread exits.
        ctrl = BrowserController()
        ctrl.launch(**kwargs)

        with self._lock:
            self._sessions[session_id] = ctrl

        # Register disconnect callback
        def _on_disconnect():
            with self._lock:
                self._sessions.pop(session_id, None)
            logger.info(f"Session auto-removed on disconnect: {session_id}")
            if self._on_session_disconnected:
                self._on_session_disconnected(session_id)

        ctrl._on_disconnected = _on_disconnect
        logger.info(f"Session created: {session_id}")
        return ctrl

    def get(self, session_id: str) -> BrowserController:
        with self._lock:
            ctrl = self._sessions.get(session_id)
        if not ctrl:
            raise RuntimeError(f"Session '{session_id}' not found")
        return ctrl

    def destroy(self, session_id: str) -> None:
        with self._lock:
            ctrl = self._sessions.pop(session_id, None)
        if ctrl:
            ctrl.close()
            logger.info(f"Session destroyed: {session_id}")

    def list_sessions(self) -> list[dict]:
        with self._lock:
            dead = [sid for sid, ctrl in self._sessions.items() if not ctrl.connected]
            for sid in dead:
                ctrl = self._sessions.pop(sid)
                try:
                    ctrl.close()
                except Exception:
                    pass
                logger.info(f"Session auto-cleaned: {sid}")
            return [
                {"session_id": sid, **ctrl.status()}
                for sid, ctrl in self._sessions.items()
            ]

    def destroy_all(self) -> None:
        with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            self.destroy(sid)
