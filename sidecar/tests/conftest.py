"""Shared pytest configuration and fixtures."""
import os
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring a real browser")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("CI") == "true":
        skip_e2e = pytest.mark.skip(reason="e2e tests require a real browser and display server")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
