from engine.action_map import FRONTEND_TO_BACKEND, BACKEND_TO_FRONTEND, to_backend, to_frontend


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
