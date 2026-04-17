"""Recording engine: inject JS into Camoufox pages to capture user actions."""
from __future__ import annotations
from loguru import logger

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

  // Scroll (debounced)
  let scrollTimer;
  document.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      emit('scroll', { x: window.scrollX, y: window.scrollY });
    }, 300);
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
        """Inject recording script into the current page."""
        page = self._controller._page
        if page:
            page.evaluate(RECORDER_JS)
            # Also inject on navigation
            page.on("load", lambda: page.evaluate(RECORDER_JS))
            logger.debug("Recorder JS injected")

    def _poll_events(self) -> None:
        """Pull events from the browser page."""
        page = self._controller._page
        if not page:
            return
        try:
            raw_events = page.evaluate("window.__mimicryEvents || []")
            if raw_events and len(raw_events) > len(self._events):
                self._events = raw_events
        except Exception as e:
            logger.warning(f"Failed to poll events: {e}")

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
                    nodes.append({
                        "type": "action",
                        "action": "scroll",
                        "selector": "window",
                        "direction": "down",
                        "amount": event.get("y", 300),
                    })

        return nodes
