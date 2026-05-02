/**
 * Element picker overlay — injected into browser pages for visual element selection.
 *
 * When active, highlights elements on hover with a blue border + info tooltip,
 * and emits the selected element on click. Press Escape to cancel.
 *
 * Communication protocol:
 *   window[Symbol.for('_mp')] = { picked: null, active: false }
 *   - Set .active = true to start picking
 *   - Read .picked to get the selected element info
 *   - Set .active = false to stop and clean up
 */
(() => {
  const KEY = Symbol.for('_mp');
  if (window[KEY]) return;

  const state = { picked: null, active: false, pendingResolve: null };
  window[KEY] = state;

  // Overlay elements
  let overlay = null;
  let tooltip = null;
  let currentTarget = null;

  function createOverlay() {
    overlay = document.createElement('div');
    overlay.id = '__mimicry_picker_overlay';
    Object.assign(overlay.style, {
      position: 'fixed',
      pointerEvents: 'none',
      zIndex: '2147483646',
      border: '2px solid #3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.08)',
      borderRadius: '2px',
      transition: 'all 0.1s ease',
      display: 'none',
    });

    tooltip = document.createElement('div');
    tooltip.id = '__mimicry_picker_tooltip';
    Object.assign(tooltip.style, {
      position: 'fixed',
      zIndex: '2147483647',
      backgroundColor: '#1e293b',
      color: '#e2e8f0',
      fontSize: '12px',
      fontFamily: 'monospace',
      padding: '4px 8px',
      borderRadius: '4px',
      pointerEvents: 'none',
      whiteSpace: 'nowrap',
      maxWidth: '400px',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      display: 'none',
      boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
    });

    document.documentElement.appendChild(overlay);
    document.documentElement.appendChild(tooltip);
  }

  function removeOverlay() {
    if (overlay) { overlay.remove(); overlay = null; }
    if (tooltip) { tooltip.remove(); tooltip = null; }
  }

  function getElementInfo(el) {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : '';
    const cls = el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.')
      : '';
    const rect = el.getBoundingClientRect();
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);
    return { tag, id, cls, w, h, rect };
  }

  function updateOverlay(el) {
    if (!overlay || !tooltip) return;
    const info = getElementInfo(el);
    const r = info.rect;

    // Position overlay
    Object.assign(overlay.style, {
      left: r.left + 'px',
      top: r.top + 'px',
      width: r.width + 'px',
      height: r.height + 'px',
      display: 'block',
    });

    // Tooltip content
    let label = info.tag;
    if (info.id) label += info.id;
    else if (info.cls) label += info.cls;
    label += ` (${info.w}×${info.h})`;
    tooltip.textContent = label;

    // Position tooltip above element, or below if no room
    const tooltipHeight = 24;
    let tooltipTop = r.top - tooltipHeight - 4;
    if (tooltipTop < 0) tooltipTop = r.bottom + 4;
    Object.assign(tooltip.style, {
      left: Math.max(0, r.left) + 'px',
      top: tooltipTop + 'px',
      display: 'block',
    });
  }

  function hideOverlay() {
    if (overlay) overlay.style.display = 'none';
    if (tooltip) tooltip.style.display = 'none';
    currentTarget = null;
  }

  // --- Event handlers ---
  function onMouseMove(e) {
    if (!state.active) return;
    const el = e.target;
    if (el === overlay || el === tooltip) return;
    if (el === currentTarget) return;
    currentTarget = el;
    updateOverlay(el);
  }

  function onClick(e) {
    if (!state.active) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const el = currentTarget || e.target;
    if (el === overlay || el === tooltip) return;

    const info = getElementInfo(el);

    // Build a quick selector
    let quickSelector = '';
    if (el.id) {
      quickSelector = '#' + CSS.escape(el.id);
    } else if (el.getAttribute('name')) {
      quickSelector = el.tagName.toLowerCase() + '[name="' + CSS.escape(el.getAttribute('name')) + '"]';
    } else if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim().split(/\s+/).filter(c => c.length > 0);
      if (cls.length > 0) {
        quickSelector = el.tagName.toLowerCase() + '.' + cls.map(c => CSS.escape(c)).join('.');
      }
    }
    if (!quickSelector) {
      quickSelector = info.tag;
    }

    state.picked = {
      selector: quickSelector,
      tagName: info.tag,
      id: el.id || '',
      className: el.className || '',
      width: info.w,
      height: info.h,
      x: Math.round(info.rect.x),
      y: Math.round(info.rect.y),
    };

    deactivate();
  }

  function onKeyDown(e) {
    if (!state.active) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      state.picked = null;
      deactivate();
    }
  }

  function activate() {
    state.active = true;
    state.picked = null;
    createOverlay();
    document.addEventListener('mousemove', onMouseMove, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('keydown', onKeyDown, true);
    document.body.style.cursor = 'crosshair';
  }

  function deactivate() {
    state.active = false;
    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
    document.body.style.cursor = '';
    hideOverlay();
    removeOverlay();
  }

  // Expose control API
  Object.defineProperty(window, Symbol.for('_mp_start'), {
    value: () => { activate(); return true; },
    writable: false, enumerable: false, configurable: false,
  });

  Object.defineProperty(window, Symbol.for('_mp_stop'), {
    value: () => { deactivate(); return true; },
    writable: false, enumerable: false, configurable: false,
  });

  Object.defineProperty(window, Symbol.for('_mp_result'), {
    value: () => state.picked,
    writable: false, enumerable: false, configurable: false,
  });
})();
