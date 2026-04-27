import subprocess
import sys
import json
from loguru import logger

# Server reference for thread-safe stdout writes
_server = None


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
