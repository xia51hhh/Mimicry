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


class TestCLIValidateFormats:
    """Test CLI validate with different workflow formats."""

    def test_validate_canonical_format(self, tmp_path):
        """Canonical format: kind + position + data structure."""
        wf = {
            "name": "Canonical",
            "nodes": [
                {
                    "id": "n1",
                    "kind": "action",
                    "action": "Navigate",
                    "position": {"x": 300, "y": 100},
                    "data": {"url": "https://example.com"},
                }
            ],
            "edges": [],
        }
        f = tmp_path / "canonical.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 0
        result = json.loads(stdout)
        assert result["valid"] is True
        assert result["node_count"] == 1

    def test_validate_compact_format_fails(self, tmp_path):
        """Compact format has no edges — CLI validate currently rejects it."""
        wf = {
            "name": "Compact",
            "nodes": [
                {"action": "Navigate", "data": {"url": "https://example.com"}},
                {"action": "Click", "data": {"selector": "#btn"}},
            ],
        }
        f = tmp_path / "compact.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        # Compact format doesn't have edges, so CLI validate fails
        assert code == 1
        result = json.loads(stdout)
        assert result["valid"] is False

    def test_validate_legacy_format(self, tmp_path):
        """Legacy format: type + flat fields — CLI accepts if has nodes+edges."""
        wf = {
            "name": "Legacy",
            "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
            ],
            "edges": [],
        }
        f = tmp_path / "legacy.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 0
        result = json.loads(stdout)
        assert result["valid"] is True

    def test_validate_recording_no_edges(self, tmp_path):
        """Recording format: kind + action + no position — no edges fails."""
        wf = {
            "nodes": [
                {"kind": "action", "action": "click", "data": {"selector": "#btn"}},
            ]
        }
        f = tmp_path / "recording.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 1
        result = json.loads(stdout)
        assert result["valid"] is False

    def test_validate_empty_workflow(self, tmp_path):
        """Empty nodes + edges is valid."""
        wf = {"name": "Empty", "nodes": [], "edges": []}
        f = tmp_path / "empty.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 0
        result = json.loads(stdout)
        assert result["valid"] is True
        assert result["node_count"] == 0

    def test_validate_unknown_action(self, tmp_path):
        """Node with unknown action should report error."""
        wf = {
            "name": "Bad",
            "nodes": [{"id": "1", "type": "action", "action": "NonExistent"}],
            "edges": [],
        }
        f = tmp_path / "bad_action.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 1
        result = json.loads(stdout)
        assert result["valid"] is False
        assert any("NonExistent" in e for e in result["errors"])

    def test_validate_file_not_found(self):
        """Non-existent file should exit with error."""
        code, stdout, _ = run_cli("validate", "/nonexistent/path.json")
        assert code == 1
        result = json.loads(stdout)
        assert result["valid"] is False
