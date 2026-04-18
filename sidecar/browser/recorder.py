"""Recording engine: inject JS into Camoufox pages to capture user actions."""
from __future__ import annotations
from loguru import logger
from engine.action_map import to_frontend

# JavaScript injected into pages to capture user interactions
RECORDER_JS = """
(() => {
  if (window.__mimicryRecorder) return;
  window.__mimicryRecorder = true;

  const events = [];
  const getSelector = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim().split(/\\s+/).filter(c => c.length > 0);
      if (cls.length > 0) {
        const sel = el.tagName.toLowerCase() + '.' + cls.map(c => CSS.escape(c)).join('.');
        if (document.querySelectorAll(sel).length === 1) return sel;
      }
    }
    // Fallback: nth-child path
    const path = [];
    let current = el;
    while (current && current !== document.body && current !== document.documentElement) {
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


class RecordingEngine:
    def __init__(self, controller):
        self._controller = controller
        self._recording = False
        self._events: list[dict] = []
        self._last_poll_index = 0

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
        return new

    def _inject_recorder(self) -> None:
        """Inject recording script into all pages and listen for new tabs."""
        browser = self._controller._browser
        if not browser or not browser.contexts:
            return
        ctx = browser.contexts[0]
        # Inject into all existing pages
        for page in ctx.pages:
            try:
                page.evaluate(RECORDER_JS)
                page.on("load", lambda p=page: self._safe_inject(p))
            except Exception as e:
                logger.warning(f"Failed to inject into page: {e}")
        # Listen for new tabs
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

    def _poll_events(self) -> None:
        """Pull events from all browser pages."""
        browser = self._controller._browser
        if not browser or not browser.contexts:
            return
        ctx = browser.contexts[0]
        all_events = []
        for page in ctx.pages:
            try:
                raw = page.evaluate("window.__mimicryEvents || []")
                if raw:
                    all_events.extend(raw)
            except Exception:
                pass
        # Sort by timestamp and deduplicate
        all_events.sort(key=lambda e: e.get("ts", 0))
        if len(all_events) > len(self._events):
            self._events = all_events

    @staticmethod
    def events_to_workflow_nodes(events: list[dict]) -> list[dict]:
        """Convert recorded events to workflow JSON nodes."""
        nodes = []
        seen_navigations = set()

        for event in events:
            etype = event.get("type")
            url = event.get("url", "")

            # Auto-insert OPEN for new URLs
            if url and url not in seen_navigations:
                seen_navigations.add(url)
                if not nodes or nodes[-1].get("action") != "open" or nodes[-1].get("url") != url:
                    nodes.append({
                        "type": "action",
                        "action": "open",
                        "url": url,
                    })

            match etype:
                case "click":
                    nodes.append({
                        "type": "action",
                        "action": "click",
                        "selector": event["selector"],
                    })
                case "dblclick":
                    nodes.append({
                        "type": "action",
                        "action": "dblclick",
                        "selector": event["selector"],
                    })
                case "type":
                    # Merge consecutive types on same selector
                    if nodes and nodes[-1].get("action") == "type" and nodes[-1].get("selector") == event["selector"]:
                        nodes[-1]["value"] = event["value"]
                    else:
                        nodes.append({
                            "type": "action",
                            "action": "type",
                            "selector": event["selector"],
                            "value": event.get("value", ""),
                        })
                case "select":
                    nodes.append({
                        "type": "action",
                        "action": "select",
                        "selector": event["selector"],
                        "value": event.get("value", ""),
                    })
                case "scroll":
                    dy = event.get("deltaY", 300)
                    nodes.append({
                        "type": "action",
                        "action": "scroll",
                        "selector": "window",
                        "direction": "down" if dy > 0 else "up",
                        "amount": abs(dy),
                    })
                case "hover":
                    nodes.append({
                        "type": "action",
                        "action": "hover",
                        "selector": event["selector"],
                    })
                case "press_key":
                    nodes.append({
                        "type": "action",
                        "action": "press_key",
                        "selector": event.get("selector", "body"),
                        "key": event.get("key", ""),
                    })

        # Convert backend action names to frontend PascalCase
        for node in nodes:
            if "action" in node:
                node["action"] = to_frontend(node["action"])

        return nodes
