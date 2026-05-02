"""Multi-strategy element selector generator and analyzer.

Generates multiple candidate selectors for a given element, scores them
for stability and uniqueness, and returns ranked recommendations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from loguru import logger


@dataclass
class SelectorCandidate:
    selector: str
    strategy: str
    score: int
    is_unique: bool
    match_count: int

    def to_dict(self) -> dict:
        return asdict(self)


# Stability base scores per strategy type (higher = more stable)
_STRATEGY_SCORES: dict[str, int] = {
    "id": 95,
    "data-testid": 95,
    "data-attr": 90,
    "text": 88,
    "name": 85,
    "role": 80,
    "class": 55,
    "css-path": 35,
    "xpath": 25,
}

# JS code to analyze a single element and return raw data for selector generation
ANALYZE_ELEMENT_JS = """
(element) => {
    const result = {
        tagName: element.tagName.toLowerCase(),
        id: element.id || '',
        className: (typeof element.className === 'string') ? element.className.trim() : '',
        name: element.getAttribute('name') || '',
        type: element.getAttribute('type') || '',
        role: element.getAttribute('role') || '',
        ariaLabel: element.getAttribute('aria-label') || '',
        dataTestId: element.getAttribute('data-testid') || element.getAttribute('data-test-id') || '',
        dataAttrs: {},
        textContent: (element.textContent || '').trim().substring(0, 100),
        innerText: (element.innerText || '').trim().substring(0, 100),
        placeholder: element.getAttribute('placeholder') || '',
        href: element.getAttribute('href') || '',
        src: element.getAttribute('src') || '',
        depth: 0,
        childIndex: 0,
        siblingCount: 0,
    };

    // Collect data-* attributes
    for (const attr of element.attributes) {
        if (attr.name.startsWith('data-') && attr.name !== 'data-testid' && attr.name !== 'data-test-id') {
            result.dataAttrs[attr.name] = attr.value;
        }
    }

    // DOM depth
    let d = 0;
    let p = element;
    while (p.parentElement) { d++; p = p.parentElement; }
    result.depth = d;

    // Sibling info
    if (element.parentElement) {
        const siblings = Array.from(element.parentElement.children);
        result.siblingCount = siblings.length;
        result.childIndex = siblings.indexOf(element);
    }

    return result;
}
"""

# JS code to check how many elements a selector matches on the page
CHECK_SELECTOR_JS = """
(selector) => {
    try {
        return document.querySelectorAll(selector).length;
    } catch(e) {
        return -1;
    }
}
"""

# JS code to generate the full CSS path for an element
CSS_PATH_JS = """
(element) => {
    const path = [];
    let current = element;
    while (current && current !== document.documentElement) {
        let seg = current.tagName.toLowerCase();
        if (current.parentElement) {
            const siblings = Array.from(current.parentElement.children).filter(c => c.tagName === current.tagName);
            if (siblings.length > 1) {
                const idx = siblings.indexOf(current) + 1;
                seg += ':nth-of-type(' + idx + ')';
            }
        }
        path.unshift(seg);
        current = current.parentElement;
    }
    return path.join(' > ');
}
"""


def _looks_dynamic(value: str) -> bool:
    """Check if a string looks like a dynamically generated identifier."""
    if not value:
        return False
    # Long hex strings, UUIDs, or strings with many digits
    if re.search(r'[0-9a-f]{8,}', value, re.I):
        return True
    if re.search(r'\d{4,}', value):
        return True
    # Hashed class names (e.g., css-modules: _1a2b3c)
    if re.match(r'^_[a-z0-9]{5,}$', value, re.I):
        return True
    return False


def generate_candidates(element_info: dict) -> list[dict]:
    """Generate candidate selectors from analyzed element info.

    Args:
        element_info: Dict from ANALYZE_ELEMENT_JS evaluation.

    Returns:
        List of {selector, strategy, base_score} dicts.
    """
    candidates: list[dict] = []
    tag = element_info.get("tagName", "div")

    # 1. ID selector
    el_id = element_info.get("id", "")
    if el_id and not _looks_dynamic(el_id):
        candidates.append({
            "selector": f"#{el_id}",
            "strategy": "id",
            "base_score": _STRATEGY_SCORES["id"],
        })

    # 2. data-testid
    test_id = element_info.get("dataTestId", "")
    if test_id:
        candidates.append({
            "selector": f'[data-testid="{test_id}"]',
            "strategy": "data-testid",
            "base_score": _STRATEGY_SCORES["data-testid"],
        })

    # 3. data-* attributes (non-dynamic)
    for attr_name, attr_val in element_info.get("dataAttrs", {}).items():
        if attr_val and not _looks_dynamic(attr_val):
            candidates.append({
                "selector": f'{tag}[{attr_name}="{attr_val}"]',
                "strategy": "data-attr",
                "base_score": _STRATEGY_SCORES["data-attr"],
            })
            break  # Only use first good data-attr

    # 4. text= selector (Playwright native)
    text = element_info.get("innerText", "") or element_info.get("textContent", "")
    if text and len(text) <= 50 and not _looks_dynamic(text):
        # Use exact match for short text
        safe_text = text.replace('"', '\\"')
        candidates.append({
            "selector": f'text="{safe_text}"',
            "strategy": "text",
            "base_score": _STRATEGY_SCORES["text"],
        })

    # 5. name attribute
    name = element_info.get("name", "")
    if name and not _looks_dynamic(name):
        candidates.append({
            "selector": f'{tag}[name="{name}"]',
            "strategy": "name",
            "base_score": _STRATEGY_SCORES["name"],
        })

    # 6. role + aria-label
    role = element_info.get("role", "")
    aria_label = element_info.get("ariaLabel", "")
    if role:
        if aria_label:
            candidates.append({
                "selector": f'role={role}[name="{aria_label}"]',
                "strategy": "role",
                "base_score": _STRATEGY_SCORES["role"],
            })
        else:
            candidates.append({
                "selector": f'role={role}',
                "strategy": "role",
                "base_score": _STRATEGY_SCORES["role"] - 15,  # Less specific without name
            })

    # 7. placeholder (for inputs)
    placeholder = element_info.get("placeholder", "")
    if placeholder and tag in ("input", "textarea"):
        candidates.append({
            "selector": f'{tag}[placeholder="{placeholder}"]',
            "strategy": "name",
            "base_score": _STRATEGY_SCORES["name"] - 5,
        })

    # 8. Class-based selector (filter out dynamic classes)
    class_str = element_info.get("className", "")
    if class_str:
        classes = [c for c in class_str.split() if c and not _looks_dynamic(c)]
        if classes:
            cls_selector = tag + "." + ".".join(classes[:3])  # Max 3 classes
            candidates.append({
                "selector": cls_selector,
                "strategy": "class",
                "base_score": _STRATEGY_SCORES["class"],
            })

    return candidates


def score_candidate(candidate: dict, match_count: int, depth: int) -> SelectorCandidate:
    """Score a candidate selector based on match count and DOM depth.

    Scoring formula:
    - Base score from strategy type (40% weight)
    - Uniqueness bonus/penalty (30% weight)
    - DOM depth penalty (15% weight)
    - Dynamic attribute penalty (15% weight)
    """
    base = candidate["base_score"]
    is_unique = match_count == 1

    # Uniqueness component (0-100 scale, 30% weight)
    if match_count == 1:
        uniqueness_score = 100
    elif match_count <= 3:
        uniqueness_score = 50
    elif match_count > 0:
        uniqueness_score = 20
    else:
        uniqueness_score = 0  # No match at all

    # Depth penalty (0-100 scale, 15% weight)
    depth_score = max(0, 100 - depth * 8)

    # Dynamic content penalty (15% weight)
    dynamic_score = 100
    if _looks_dynamic(candidate["selector"]):
        dynamic_score = 30

    final = int(
        base * 0.40
        + uniqueness_score * 0.30
        + depth_score * 0.15
        + dynamic_score * 0.15
    )
    final = max(0, min(100, final))

    return SelectorCandidate(
        selector=candidate["selector"],
        strategy=candidate["strategy"],
        score=final,
        is_unique=is_unique,
        match_count=match_count,
    )


def analyze_element(page: Any, element_handle: Any) -> list[SelectorCandidate]:
    """Analyze an element and return ranked selector candidates.

    Args:
        page: Playwright Page object.
        element_handle: Playwright ElementHandle of the target element.

    Returns:
        List of SelectorCandidate sorted by score (highest first).
    """
    # 1. Gather element info
    element_info = element_handle.evaluate(ANALYZE_ELEMENT_JS)
    depth = element_info.get("depth", 5)

    # 2. Generate candidates
    raw_candidates = generate_candidates(element_info)

    # 3. Add CSS path fallback
    css_path = element_handle.evaluate(CSS_PATH_JS)
    if css_path:
        raw_candidates.append({
            "selector": css_path,
            "strategy": "css-path",
            "base_score": _STRATEGY_SCORES["css-path"],
        })

    # 4. Check uniqueness for each candidate
    results: list[SelectorCandidate] = []
    for cand in raw_candidates:
        sel = cand["selector"]
        # text= and role= selectors are Playwright-only, can't use querySelectorAll
        if sel.startswith("text=") or sel.startswith("role="):
            try:
                match_count = page.locator(sel).count()
            except Exception:
                match_count = -1
        else:
            try:
                match_count = page.evaluate(CHECK_SELECTOR_JS, sel)
            except Exception:
                match_count = -1

        if match_count < 0:
            continue  # Invalid selector, skip

        scored = score_candidate(cand, match_count, depth)
        results.append(scored)

    # 5. Sort by score descending
    results.sort(key=lambda c: c.score, reverse=True)
    return results


def quick_enhance_selector(page: Any, selector: str) -> dict:
    """Quickly analyze a recorded selector and return the best alternative.

    This is a lightweight version of analyze_element designed for use
    during recording. It finds the element by selector, gathers info,
    generates candidates with uniqueness checks, and returns the best one.

    Returns:
        Dict with keys: best_selector, best_score, candidates (list of dicts),
        or empty dict on failure.
    """
    try:
        handle = page.query_selector(selector)
        if not handle:
            return {}

        element_info = handle.evaluate(ANALYZE_ELEMENT_JS)
        depth = element_info.get("depth", 5)
        raw = generate_candidates(element_info)

        if not raw:
            return {}

        # Check uniqueness for each candidate
        scored: list[SelectorCandidate] = []
        for cand in raw:
            sel = cand["selector"]
            if sel.startswith("text=") or sel.startswith("role="):
                try:
                    mc = page.locator(sel).count()
                except Exception:
                    mc = -1
            else:
                try:
                    mc = page.evaluate(CHECK_SELECTOR_JS, sel)
                except Exception:
                    mc = -1
            if mc < 0:
                continue
            scored.append(score_candidate(cand, mc, depth))

        if not scored:
            return {}

        scored.sort(key=lambda c: c.score, reverse=True)
        best = scored[0]

        return {
            "best_selector": best.selector,
            "best_score": best.score,
            "best_strategy": best.strategy,
            "candidates": [c.to_dict() for c in scored[:5]],
        }
    except Exception as e:
        logger.debug(f"quick_enhance_selector failed for '{selector}': {e}")
        return {}
