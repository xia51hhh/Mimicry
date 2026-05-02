"""Recording engine: inject JS into Camoufox pages to capture user actions."""
from __future__ import annotations
import time as _time
from pathlib import Path
from loguru import logger

_RECORDER_JS: str | None = None


def _load_recorder_js() -> str:
    global _RECORDER_JS
    if _RECORDER_JS is None:
        js_path = Path(__file__).parent / "scripts" / "recorder.js"
        _RECORDER_JS = js_path.read_text(encoding="utf-8")
    return _RECORDER_JS


def _try_enhance_selector(page, selector: str) -> dict:
    """Try to enhance a selector using multi-strategy analysis. Returns enhancement dict or {}."""
    try:
        from browser.selector import quick_enhance_selector
        return quick_enhance_selector(page, selector)
    except Exception:
        return {}





def score_selector(selector: str) -> int:
    """Score a CSS selector for quality/stability (0-100).
    Higher = more stable and readable.
    """
    score = 50  # baseline

    # Bonus for ID
    if selector.startswith("#") and " " not in selector:
        score += 40

    # Bonus for name attribute
    if '[name="' in selector:
        score += 25

    # Bonus for data-testid
    if "[data-testid" in selector or "[data-test" in selector:
        score += 35

    # Penalty for nth-of-type (fragile)
    nth_count = selector.count(":nth-of-type")
    score -= nth_count * 15

    # Penalty for deep nesting
    depth = selector.count(" > ") + selector.count(" ")
    score -= depth * 5

    # Shadow DOM combinator — neutral to slightly positive
    if " >> " in selector:
        score += 20

    return max(0, min(100, score))


class RecordingEngine:
    def __init__(self, controller):
        self._controller = controller
        self._recording = False
        self._events: list[dict] = []
        self._last_poll_index = 0
        self.event_callback: callable | None = None
        self._active_page_id: int | None = None  # id(page) of last active page for switch detection
        self._page_tab_cache: dict[int, dict] = {}  # id(page) → TabInfo dict snapshot (survives unregister)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if not self._controller.connected:
            raise RuntimeError("Browser not connected")
        self._recording = True
        self._events.clear()
        self._last_poll_index = 0
        self._page_tab_cache.clear()
        self._active_page_id = id(self._controller._page) if self._controller._page else None
        self._inject_recorder()
        logger.info("Recording started")

    def stop(self) -> list[dict]:
        self._recording = False
        # Final poll
        self._poll_events()
        events = list(self._events)
        logger.info(f"Recording stopped, {len(events)} events captured")
        return events

    def poll_new_events(self) -> list[dict]:
        """Poll for new events since last check."""
        if not self._recording:
            return []
        self._poll_events()
        new = self._events[self._last_poll_index:]
        self._last_poll_index = len(self._events)
        if new and self.event_callback:
            for event in new:
                self.event_callback(event)
        return new

    def _inject_recorder(self) -> None:
        """Inject recording script into all pages and frames."""
        ctx = self._controller._context
        if not ctx:
            return
        for page in ctx.pages:
            try:
                page.evaluate(_load_recorder_js())
                page.on("load", lambda p=page: self._safe_inject(p))
                page.on("close", lambda p=page: self._on_page_close(p))
                # Cache tabInfo for close event
                pid = id(page)
                tab_id = self._controller._page_to_tab.get(pid)
                if tab_id and tab_id in self._controller._tab_registry:
                    self._page_tab_cache[pid] = self._controller._tab_registry[tab_id].to_dict()
                # Inject into all existing frames
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        frame.evaluate(_load_recorder_js())
                    except Exception:
                        pass
                # Listen for new frames
                page.on("frameattached", lambda frame: self._safe_inject_frame(frame))
            except Exception as e:
                logger.warning(f"Failed to inject into page: {e}")
        ctx.on("page", self._on_new_page)
        logger.debug("Recorder JS injected into %d pages", len(ctx.pages))

    def _on_new_page(self, page) -> None:
        """Handle new tab opened during recording."""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            # Get TabInfo from controller if available
            tab_info = {}
            if self._controller:
                pid = id(page)
                tab_id = self._controller._page_to_tab.get(pid)
                if tab_id and tab_id in self._controller._tab_registry:
                    tab_info = self._controller._tab_registry[tab_id].to_dict()
            # Record new tab event with TabInfo
            tab_event = {
                "type": "new_tab",
                "url": page.url,
                "timestamp": int(page.evaluate("Date.now()")),
                "tabInfo": tab_info,
            }
            self._events.append(tab_event)
            if self.event_callback:
                self.event_callback(tab_event)
            # Cache tabInfo for close event (survives controller unregister)
            if tab_info:
                self._page_tab_cache[id(page)] = tab_info
            # Track new tab as active for switch detection
            self._active_page_id = id(page)
            # Inject recorder into new tab
            page.evaluate(_load_recorder_js())
            page.on("load", lambda p=page: self._safe_inject(p))
            # Listen for tab close
            page.on("close", lambda p=page: self._on_page_close(p))
            logger.debug("Recorder JS injected into new tab, event recorded")
        except Exception as e:
            logger.warning(f"Failed to inject into new tab: {e}")

    def _on_page_close(self, page) -> None:
        """Handle tab closed during recording."""
        pid = id(page)
        # Use cached tabInfo (survives controller unregister race)
        tab_info = self._page_tab_cache.pop(pid, {})
        if not tab_info and self._controller:
            tab_id = self._controller._page_to_tab.get(pid)
            if tab_id and tab_id in self._controller._tab_registry:
                tab_info = self._controller._tab_registry[tab_id].to_dict()
        close_event = {
            "type": "close_tab",
            "url": getattr(page, "url", ""),
            "timestamp": int(_time.time() * 1000),
            "tabInfo": tab_info,
        }
        self._events.append(close_event)
        if self.event_callback:
            self.event_callback(close_event)
        logger.debug("Tab close event recorded")

    @staticmethod
    def _safe_inject(page) -> None:
        try:
            page.evaluate(_load_recorder_js())
        except Exception:
            pass

    @staticmethod
    def _safe_inject_frame(frame) -> None:
        """Inject recorder into a frame after it loads."""
        try:
            frame.wait_for_load_state("domcontentloaded", timeout=5000)
            frame.evaluate(_load_recorder_js())
        except Exception:
            pass

    def _poll_events(self) -> None:
        """Pull NEW events from all browser pages and frames (incremental).
        Auto-inserts switch_tab events when active page changes."""
        ctx = self._controller._context
        if not ctx:
            return
        new_events = []
        for page in ctx.pages:
            page_id = id(page)
            try:
                # Atomically drain events via Symbol-keyed function (not enumerable)
                raw = page.evaluate("""() => {
                    const fn = window[Symbol.for('_me')];
                    return fn ? fn() : [];
                }""")
                if raw:
                    for evt in raw:
                        evt["_page_id"] = page_id
                    new_events.extend(raw)
            except Exception:
                pass
            # Collect from iframes
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    raw = frame.evaluate("""() => {
                        const fn = window[Symbol.for('_me')];
                        return fn ? fn() : [];
                    }""")
                    if raw:
                        for evt in raw:
                            evt["_page_id"] = page_id
                        new_events.extend(raw)
                except Exception:
                    pass
        if not new_events:
            return
        # Sort new batch by timestamp
        new_events.sort(key=lambda e: e.get("timestamp", 0))
        # Detect page switches and insert switch_tab events
        for evt in new_events:
            page_id = evt.pop("_page_id", None)
            if page_id and page_id != self._active_page_id:
                # Page changed — auto-insert switch_tab
                tab_info = {}
                tab_id = self._controller._page_to_tab.get(page_id)
                if tab_id and tab_id in self._controller._tab_registry:
                    tab_info = self._controller._tab_registry[tab_id].to_dict()
                switch_event = {
                    "type": "switch_tab",
                    "timestamp": evt.get("timestamp", int(_time.time() * 1000)),
                    "tabInfo": tab_info,
                }
                self._events.append(switch_event)
                self._active_page_id = page_id

            # Auto-enhance selectors using multi-strategy analysis
            sel = evt.get("selector")
            if sel and self._controller._page:
                enhanced = _try_enhance_selector(self._controller._page, sel)
                if enhanced:
                    evt["_selectorAnalysis"] = enhanced

            self._events.append(evt)

    @staticmethod
    def events_to_workflow_nodes(events: list[dict]) -> list[dict]:
        """Convert recorded events to canonical workflow nodes.

        Output format (canonical):
            {kind: "action", action: "click", data: {selector: "#btn"}}
        Action names are snake_case (backend authority format).
        Position is omitted — layout is a frontend concern.
        """
        nodes = []
        seen_navigations = set()

        def _make_node(action: str, data: dict) -> dict:
            return {
                "kind": "action",
                "action": action,
                "data": data,
            }

        for event in events:
            etype = event.get("type")
            url = event.get("url", "")
            analysis = event.get("_selectorAnalysis")

            # Auto-insert OPEN for new URLs
            if url and url not in seen_navigations:
                seen_navigations.add(url)
                last_data = nodes[-1].get("data", {}) if nodes else {}
                if not nodes or nodes[-1].get("action") != "open" or last_data.get("url") != url:
                    nodes.append(_make_node("open", {"url": url}))
                    # Auto-insert wait after navigation
                    nodes.append(_make_node("wait", {
                        "selector": None,
                        "url_contains": None,
                        "time": "2s",
                    }))

            match etype:
                case "click":
                    nodes.append(_make_node("click", {"selector": event["selector"]}))
                case "dblclick":
                    nodes.append(_make_node("dblclick", {"selector": event["selector"]}))
                case "type":
                    # Merge consecutive types on same selector
                    if nodes and nodes[-1].get("action") == "type" and nodes[-1].get("data", {}).get("selector") == event["selector"]:
                        nodes[-1]["data"]["value"] = event["value"]
                    else:
                        nodes.append(_make_node("type", {
                            "selector": event["selector"],
                            "value": event.get("value", ""),
                        }))
                case "select":
                    nodes.append(_make_node("select", {
                        "selector": event["selector"],
                        "value": event.get("value", ""),
                    }))
                case "scroll":
                    dy = event.get("deltaY", 300)
                    nodes.append(_make_node("scroll", {
                        "selector": "window",
                        "direction": "down" if dy > 0 else "up",
                        "amount": abs(dy),
                    }))
                case "hover":
                    nodes.append(_make_node("hover", {"selector": event["selector"]}))
                case "press_key":
                    nodes.append(_make_node("press_key", {
                        "selector": event.get("selector", "body"),
                        "key": event.get("key", ""),
                    }))
                case "new_tab":
                    node_data = {"url": event.get("url", "")}
                    if ti := event.get("tabInfo"):
                        node_data["tabId"] = ti.get("tab_id", "")
                        node_data["seq"] = ti.get("seq")
                        node_data["urlOrigin"] = ti.get("url_origin", "")
                        node_data["urlPath"] = ti.get("url_path", "")
                    nodes.append(_make_node("new_tab", node_data))
                case "close_tab":
                    node_data = {}
                    if ti := event.get("tabInfo"):
                        node_data["tabId"] = ti.get("tab_id", "")
                        node_data["seq"] = ti.get("seq")
                    nodes.append(_make_node("close_tab", node_data))
                case "switch_tab":
                    node_data = {}
                    if ti := event.get("tabInfo"):
                        node_data["tabId"] = ti.get("tab_id", "")
                        node_data["seq"] = ti.get("seq")
                        node_data["urlOrigin"] = ti.get("url_origin", "")
                        node_data["urlPath"] = ti.get("url_path", "")
                        node_data["title"] = ti.get("title", "")
                    nodes.append(_make_node("switch_tab", node_data))

            # Attach selector analysis to the last generated node (if applicable)
            if analysis and nodes:
                last_data = nodes[-1].get("data", {})
                if last_data.get("selector"):
                    last_data["_selectorAnalysis"] = analysis

        # Attach selector quality score and candidates into data
        for node in nodes:
            sel = node.get("data", {}).get("selector")
            if sel:
                node["data"]["selectorScore"] = score_selector(sel)

        # Apply best enhanced selectors from multi-strategy analysis
        for node in nodes:
            analysis = node.get("data", {}).pop("_selectorAnalysis", None)
            if analysis and analysis.get("best_selector"):
                old_sel = node["data"].get("selector", "")
                best = analysis["best_selector"]
                best_score = analysis.get("best_score", 0)
                old_score = node["data"].get("selectorScore", 0)
                # Use enhanced selector if it scores better
                if best_score > old_score and best != old_sel:
                    node["data"]["selector"] = best
                    node["data"]["selectorScore"] = best_score
                    node["data"]["selectorOriginal"] = old_sel
                    node["data"]["selectorStrategy"] = analysis.get("best_strategy", "")
                if analysis.get("candidates"):
                    node["data"]["selectorCandidates"] = analysis["candidates"]

        return nodes
