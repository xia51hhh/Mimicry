import pytest
from browser.env_check import CamoufoxEnv


def test_check_returns_dict():
    result = CamoufoxEnv.check()
    assert isinstance(result, dict)
    assert "installed" in result
    assert "version" in result
    assert isinstance(result["installed"], bool)


def test_version_string_or_none():
    result = CamoufoxEnv.check()
    if result["installed"]:
        assert isinstance(result["version"], str)
        assert len(result["version"]) > 0
    else:
        assert result["version"] is None
