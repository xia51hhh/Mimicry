"""Tests for the Mimicry CLI."""
import subprocess
import sys
import os
import json
import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "cli.py")
SIDECAR_DIR = os.path.join(os.path.dirname(__file__), "..")


def run_cli(*args, input_data=None):
    """Run CLI command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, CLI_PATH, *args],
        capture_output=True,
        text=True,
        cwd=SIDECAR_DIR,
        input=input_data,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIValidate:
    def test_validate_valid_workflow(self, tmp_path):
        wf = {"name": "test", "nodes": [{"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"}], "edges": []}
        f = tmp_path / "wf.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 0
        result = json.loads(stdout)
        assert result["valid"] is True

    def test_validate_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 1

    def test_validate_missing_nodes(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"name": "test"}))
        code, stdout, _ = run_cli("validate", str(f))
        result = json.loads(stdout)
        assert result["valid"] is False
        assert "nodes" in result["errors"][0].lower()


class TestCLIHelp:
    def test_help_flag(self):
        code, stdout, _ = run_cli("--help")
        assert code == 0
        assert "mimicry" in stdout.lower() or "usage" in stdout.lower()

    def test_validate_help(self):
        code, stdout, _ = run_cli("validate", "--help")
        assert code == 0
