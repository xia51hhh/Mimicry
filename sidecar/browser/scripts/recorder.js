(() => {
  const _k = Symbol.for('_mr');
  if (window[_k]) return;
  window[_k] = true;

  const events = [];

  // Expose drain function via a non-enumerable Symbol property
  const _ek = Symbol.for('_me');
  Object.defineProperty(window, _ek, {
    value: () => events.splice(0),
    writable: false,
    enumerable: false,
    configurable: false,
  });

  // Generate the best single-segment selector for an element within its root
  const bestSegment = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute && el.getAttribute('name')) {
      return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.getAttribute('name')) + '"]';
    }
    if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim().split(/\s+/).filter(c => c.length > 0);
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

})();
