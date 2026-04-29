"""Full anti-detection test runner with inter-test cooldown."""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.makedirs(os.path.join(os.path.dirname(__file__), 'screenshots'), exist_ok=True)

import pytest
pytest.mark.skipif = lambda *a, **kw: lambda fn: fn

from tests.test_google_search import (
    test_google_search_via_typing,
    test_bing_search,
    test_duckduckgo_search,
    test_cloudflare_turnstile,
    test_browserscan_fingerprint,
    test_incolumitas_bot_detect,
    test_creepjs_fingerprint,
)

tests = [
    ('Google', test_google_search_via_typing),
    ('Bing', test_bing_search),
    ('DuckDuckGo', test_duckduckgo_search),
    ('Cloudflare Turnstile', test_cloudflare_turnstile),
    ('BrowserScan', test_browserscan_fingerprint),
    ('Incolumitas Bot Detect', test_incolumitas_bot_detect),
    ('CreepJS', test_creepjs_fingerprint),
]

results = []
for i, (name, fn) in enumerate(tests):
    if i > 0:
        print(f"\n⏳ Cooldown 5s before {name}...")
        time.sleep(5)
    try:
        fn()
        results.append((name, 'PASS'))
    except BaseException as e:
        results.append((name, f'FAIL: {e}'))

print()
print('=' * 50)
print('Anti-Detection Test Results')
print('=' * 50)
for name, status in results:
    icon = '✅' if status == 'PASS' else '❌'
    print(f'{icon} {name}: {status}')
print(f'\nTotal: {sum(1 for _, s in results if s == "PASS")}/{len(results)} passed')

