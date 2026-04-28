"""Recording engine: inject JS into Camoufox pages to capture user actions."""
from __future__ import annotations
from loguru import logger

# JavaScript injected into pages to capture user interactions
RECORDER_JS = """
(() => {
  if (window.__mimicryRecorder) return;
  window.__mimicryRecorder = true;

  const events = [];

  // Generate the best single-segment selector for an element within its root
  const bestSegment = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute && el.getAttribute('name')) {
      return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.getAttribute('name')) + '"]';
    }
    if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim().split(/\\s+/).filter(c => c.length > 0);
      if (cls.length > 0) {
        const sel = el.tagName.toLowerCase() + '.' + cls.map(c => CSS.escape(c)).join('.');
        const root = el.getRootNode();
        const scope = root.querySelectorAll ? root : document;
        if (scope.querySelectorAll(sel).length === 1) return sel;
      }
    }
    return '';
  };

  // Build a path of tag:nth-of-type segments from el up to (but not including) stopAt
  const buildPath = (el, stopAt) => {
    const path = [];
    let current = el;
    while (current && current !== stopAt && current !== document.documentElement) {
      let seg = current.tagName.toLowerCase();
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
        if (siblings.length > 1) {
          const idx = siblings.indexOf(current) + 1;
          seg += ':nth-of-type(' + idx + ')';
        }
      }
      path.unshift(seg);
      current = parent;
    }
    return path.join(' > ');
  };

  const getSelector = (el) => {
    // Collect segments across shadow boundaries (deepest first)
    const segments = [];
    let current = el;

    while (current) {
      const root = current.getRootNode();
      const isShadow = root instanceof ShadowRoot;

      // Try short unique selector first, fallback to full path
      const short = bestSegment(current);
      if (short) {
        segments.unshift(short);
      } else {
        const boundary = isShadow ? root.host : document.body;
        segments.unshift(buildPath(current, boundary));
      }

      if (isShadow) {
        // Continue from the shadow host in its parent DOM
        current = root.host;
      } else {
        break;
      }
    }

    return segments.join(' >> ');
  };

  const emit = (type, detail) => {
    const event = { type, ...detail, timestamp: Date.now(), url: location.href };
    events.push(event);
    // Store for polling
    window.__mimicryEvents = events;
  };

  // Click
  document.addEventListener('click', (e) => {
    const sel = getSelector(e.target);
    emit('click', { selector: sel, x: e.clientX, y: e.clientY });
  }, true);

  // Double click
  document.addEventListener('dblclick', (e) => {
    const sel = getSelector(e.target);
    emit('dblclick', { selector: sel });
  }, true);

  // Input/change (debounced per element)
  const inputTimers = new WeakMap();
  document.addEventListener('input', (e) => {
    const el = e.target;
    if (!el.matches('input, textarea, [contenteditable]')) return;
    clearTimeout(inputTimers.get(el));
    inputTimers.set(el, setTimeout(() => {
      const sel = getSelector(el);
      const value = el.value || el.textContent || '';
      emit('type', { selector: sel, value });
    }, 500));
  }, true);

  // Select change
  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.tagName === 'SELECT') {
      emit('select', { selector: getSelector(el), value: el.value });
    }
  }, true);

  // Scroll (capture delta via wheel event)
  let scrollTimer;
  document.addEventListener('wheel', (e) => {
    const dy = e.deltaY;
    if (Math.abs(dy) < 10) return;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      emit('scroll', { deltaY: dy });
    }, 300);
  }, { capture: true, passive: true });

  // Hover (debounced, only on interactive elements)
  let hoverTimer;
  document.addEventListener('mouseover', (e) => {
    const el = e.target;
    if (!el || !el.matches('a, button, [role="button"], input, label, [data-hover]')) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      emit('hover', { selector: getSelector(el) });
    }, 800);
  }, true);
  document.addEventListener('mouseout', () => {
    clearTimeout(hoverTimer);
  }, true);

  // Keyboard shortcuts (non-input keys)
  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) || '';
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || (e.target && e.target.isContentEditable);
    // Only record special keys outside input fields, or Escape/Enter anywhere
    if (isInput && !['Escape', 'Enter', 'Tab'].includes(e.key)) return;
    if (['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) return;
    let key = '';
    if (e.ctrlKey) key += 'Control+';
    if (e.altKey) key += 'Alt+';
    if (e.shiftKey && e.key.length > 1) key += 'Shift+';
    if (e.metaKey) key += 'Meta+';
    key += e.key;
    const sel = isInput ? getSelector(e.target) : 'body';
    emit('press_key', { selector: sel, key });
  }, true);

  console.log('[Mimicry] Recorder injected');
})();
"""


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

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if not self._controller.connected:
            raise RuntimeError("Browser not connected")
        self._recording = True
        self._events.clear()
        self._last_poll_index = 0
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
                page.evaluate(RECORDER_JS)
                page.on("load", lambda p=page: self._safe_inject(p))
                # Inject into all existing frames
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        frame.evaluate(RECORDER_JS)
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
            page.wait_for_load_state("domcontentloaded")
            page.evaluate(RECORDER_JS)
            page.on("load", lambda p=page: self._safe_inject(p))
            logger.debug("Recorder JS injected into new tab")
        except Exception as e:
            logger.warning(f"Failed to inject into new tab: {e}")

    @staticmethod
    def _safe_inject(page) -> None:
        try:
            page.evaluate(RECORDER_JS)
        except Exception:
            pass

    @staticmethod
    def _safe_inject_frame(frame) -> None:
        """Inject recorder into a frame after it loads."""
        try:
            frame.wait_for_load_state("domcontentloaded", timeout=5000)
            frame.evaluate(RECORDER_JS)
        except Exception:
            pass

    def _poll_events(self) -> None:
        """Pull events from all browser pages and frames."""
        ctx = self._controller._context
        if not ctx:
            return
        all_events = []
        for page in ctx.pages:
            try:
                raw = page.evaluate("window.__mimicryEvents || []")
                if raw:
                    all_events.extend(raw)
            except Exception:
                pass
            # Collect from iframes
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    raw = frame.evaluate("window.__mimicryEvents || []")
                    if raw:
                        all_events.extend(raw)
                except Exception:
                    pass
        # Sort by timestamp and deduplicate
        all_events.sort(key=lambda e: e.get("timestamp", 0))
        if len(all_events) > len(self._events):
            self._events = all_events

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

            # Auto-insert OPEN for new URLs
            if url and url not in seen_navigations:
                seen_navigations.add(url)
                last_data = nodes[-1].get("data", {}) if nodes else {}
                if not nodes or nodes[-1].get("action") != "open" or last_data.get("url") != url:
                    nodes.append(_make_node("open", {"url": url}))

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

        # Attach selector quality score into data
        for node in nodes:
            sel = node.get("data", {}).get("selector")
            if sel:
                node["data"]["selectorScore"] = score_selector(sel)

        return nodes
