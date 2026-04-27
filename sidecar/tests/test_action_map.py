import json
from pathlib import Path

from engine.action_map import FRONTEND_TO_BACKEND, BACKEND_TO_FRONTEND, to_backend, to_frontend


ROOT = Path(__file__).resolve().parents[2]
SHARED_ACTION_MAP = ROOT / "shared" / "action-map.json"


def test_python_map_matches_shared_source():
    with SHARED_ACTION_MAP.open(encoding="utf-8") as f:
        shared_map = json.load(f)

    assert FRONTEND_TO_BACKEND == shared_map


def test_maps_are_inverse():
    for fe, be in FRONTEND_TO_BACKEND.items():
        assert BACKEND_TO_FRONTEND[be] == fe, f"{be} should map back to {fe}"


def test_no_duplicate_backend_names():
    backends = list(FRONTEND_TO_BACKEND.values())
    assert len(backends) == len(set(backends)), "Duplicate backend names detected"


def test_to_backend_known():
    assert to_backend("Navigate") == "open"
    assert to_backend("GoBack") == "back"
    assert to_backend("Delay") == "sleep"


def test_to_frontend_known():
    assert to_frontend("open") == "Navigate"
    assert to_frontend("back") == "GoBack"
    assert to_frontend("sleep") == "Delay"


def test_passthrough_unknown():
    assert to_backend("unknown_action") == "unknown_action"
    assert to_frontend("unknown_action") == "unknown_action"
