import subprocess
import sys
import json
import os
from pathlib import Path
from loguru import logger

# Server reference for thread-safe stdout writes
_server = None

# CoryKing fork is the community-maintained Camoufox with latest anti-detection fixes
CAMOUFOX_UPSTREAM_REPO = "CoryKing/camoufox"  # CoryKing fork
CAMOUFOX_RELEASES_API = f"https://api.github.com/repos/{CAMOUFOX_UPSTREAM_REPO}/releases/latest"


def set_server(server):
    global _server
    _server = server


def _send_notification(method: str, params: dict):
    """Send a JSON-RPC notification via server (thread-safe) or direct stdout (fallback)."""
    if _server:
        _server.send_notification(method, params)
    else:
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()


class CamoufoxEnv:
    @staticmethod
    def check() -> dict:
        """检测 Camoufox 是否已安装及版本信息"""
        try:
            import camoufox  # noqa: F401
            version = CamoufoxEnv._get_pip_version()
            return {"installed": True, "version": version}
        except ImportError:
            return {"installed": False, "version": None}

    @staticmethod
    def _get_pip_version() -> str | None:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "camoufox"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    @staticmethod
    def install() -> dict:
        """安装 camoufox 包并下载浏览器，发送实时进度通知"""
        try:
            # Step 1: pip install
            _send_notification("camoufox.progress", {"stage": "pip_install", "progress": 0, "message": "Installing camoufox package..."})
            logger.info("Installing camoufox...")

            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "--no-input", "camoufox[geoip]"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            try:
                lines = []
                for line in proc.stdout:
                    line = line.strip()
                    if line:
                        lines.append(line)
                        progress = min(40, len(lines) * 2)
                        _send_notification("camoufox.progress", {"stage": "pip_install", "progress": progress, "message": line})

                proc.wait(timeout=300)
            except Exception:
                proc.kill()
                proc.wait()
                raise
            if proc.returncode != 0:
                error_msg = (lines[-1] if lines else "pip install failed")[:200]
                _send_notification("camoufox.progress", {"stage": "error", "progress": 0, "message": error_msg})
                return {"success": False, "error": f"pip install failed: {error_msg}"}

            _send_notification("camoufox.progress", {"stage": "pip_install", "progress": 45, "message": "Package installed, fetching browser..."})

            # Step 2: camoufox fetch
            logger.info("Fetching Camoufox browser binary...")
            proc = subprocess.Popen(
                [sys.executable, "-m", "camoufox", "fetch"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            try:
                fetch_lines = []
                for line in proc.stdout:
                    line = line.strip()
                    if line:
                        fetch_lines.append(line)
                        progress = min(95, 45 + len(fetch_lines) * 3)
                        _send_notification("camoufox.progress", {"stage": "fetch_browser", "progress": progress, "message": line})

                proc.wait(timeout=600)
            except Exception:
                proc.kill()
                proc.wait()
                raise
            if proc.returncode != 0:
                error_msg = fetch_lines[-1] if fetch_lines else "camoufox fetch failed"
                _send_notification("camoufox.progress", {"stage": "error", "progress": 0, "message": error_msg})
                return {"success": False, "error": f"camoufox fetch failed: {error_msg}"}

            _send_notification("camoufox.progress", {"stage": "done", "progress": 100, "message": "Installation complete"})

            check = CamoufoxEnv.check()
            return {"success": True, "version": check["version"]}

        except subprocess.TimeoutExpired:
            _send_notification("camoufox.progress", {"stage": "error", "progress": 0, "message": "Installation timed out"})
            return {"success": False, "error": "Installation timed out"}
        except Exception as e:
            _send_notification("camoufox.progress", {"stage": "error", "progress": 0, "message": str(e)})
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_browser_version() -> dict | None:
        """Read local browser version from version.json."""
        version_file = Path.home() / ".cache" / "camoufox" / "version.json"
        if not version_file.exists():
            return None
        try:
            data = json.loads(version_file.read_text())
            return {
                "version": data.get("version"),
                "release": data.get("release"),
            }
        except Exception:
            return None

    @staticmethod
    def check_update() -> dict:
        """Check if a newer CoryKing Camoufox release is available.

        Returns:
            {
                "current_version": "142.0.1" | None,
                "current_release": "fork.26" | None,
                "latest_version": "143.0" | None,
                "latest_tag": "v143.0-fork.1" | None,
                "update_available": bool,
                "error": str | None,
            }
        """
        import urllib.request
        import urllib.error

        # Get current local version
        local = CamoufoxEnv.get_browser_version()
        current_version = local["version"] if local else None
        current_release = local["release"] if local else None

        result = {
            "current_version": current_version,
            "current_release": current_release,
            "latest_version": None,
            "latest_tag": None,
            "update_available": False,
            "error": None,
        }

        # Query GitHub releases API for CoryKing fork
        try:
            req = urllib.request.Request(
                CAMOUFOX_RELEASES_API,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Mimicry-Sidecar"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            result["latest_tag"] = tag
            # Parse version from tag (e.g. "v142.0.1-fork.26" → "142.0.1")
            tag_stripped = tag.lstrip("v") if tag else ""
            version_part = tag_stripped.split("-")[0] if tag_stripped else None
            result["latest_version"] = version_part

            # Compare full tag: version first, then release suffix
            if current_version and version_part:
                if _version_gt(version_part, current_version):
                    result["update_available"] = True
                elif version_part == current_version:
                    # Same base version, compare release suffix (fork.26 vs fork.27)
                    latest_release = tag_stripped.split("-", 1)[1] if "-" in tag_stripped else ""
                    result["update_available"] = _release_gt(latest_release, current_release or "")
            elif not current_version and version_part:
                result["update_available"] = True

        except urllib.error.URLError as e:
            result["error"] = f"Network error: {e.reason}"
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def update_browser() -> dict:
        """Update Camoufox browser binary to the latest CoryKing release."""
        _send_notification("camoufox.progress", {"stage": "update", "progress": 0, "message": "Fetching latest browser..."})
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "camoufox", "fetch", "--force"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            lines = []
            for line in proc.stdout:
                line = line.strip()
                if line:
                    lines.append(line)
                    progress = min(95, len(lines) * 3)
                    _send_notification("camoufox.progress", {"stage": "update", "progress": progress, "message": line})
            proc.wait(timeout=600)

            if proc.returncode != 0:
                error_msg = lines[-1] if lines else "camoufox fetch failed"
                return {"success": False, "error": error_msg}

            _send_notification("camoufox.progress", {"stage": "done", "progress": 100, "message": "Update complete"})
            new_version = CamoufoxEnv.get_browser_version()
            return {
                "success": True,
                "version": new_version["version"] if new_version else None,
                "release": new_version["release"] if new_version else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Update timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _version_gt(a: str, b: str) -> bool:
    """Compare two version strings (e.g. '143.0.1' > '142.0.1')."""
    def parts(v: str) -> list[int]:
        return [int(x) for x in v.split(".") if x.isdigit()]
    pa, pb = parts(a), parts(b)
    # Pad to same length
    while len(pa) < len(pb):
        pa.append(0)
    while len(pb) < len(pa):
        pb.append(0)
    return pa > pb


def _release_gt(a: str, b: str) -> bool:
    """Compare release suffixes (e.g. 'fork.27' > 'fork.26')."""
    import re
    def extract_num(s: str) -> int:
        m = re.search(r"(\d+)$", s)
        return int(m.group(1)) if m else 0
    return extract_num(a) > extract_num(b)
