"""
Camoufox browser fetcher with GitHub token support and progress reporting.

Wraps `camoufox fetch` to:
1. Inject GITHUB_TOKEN as Authorization header (avoids 403 rate limit)
2. Output JSON progress lines to stdout for real-time progress tracking
"""

import json
import os
import sys
from io import BytesIO
from typing import Optional

def emit(step: str, progress: int, detail: str = ""):
    """Output a JSON progress line to stdout."""
    print(json.dumps({"step": step, "progress": progress, "detail": detail}), flush=True)


def main():
    token = os.environ.get("GITHUB_TOKEN", "")

    if token:
        import requests
        _original_get = requests.get

        def patched_get(url, **kwargs):
            if "api.github.com" in str(url):
                headers = kwargs.setdefault("headers", {})
                headers["Authorization"] = f"token {token}"
            return _original_get(url, **kwargs)

        requests.get = patched_get

    # Monkey-patch webdl to report download progress
    import requests
    from camoufox import pkgman

    _original_webdl = pkgman.webdl

    def progress_webdl(url: str, desc: Optional[str] = None, buffer=None, bar: bool = True):
        """Download with JSON progress output."""
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        if buffer is None:
            buffer = BytesIO()

        downloaded = 0
        last_pct = -1
        total_mb = total_size / (1024 * 1024)

        for data in response.iter_content(block_size):
            size = buffer.write(data)
            downloaded += size
            if total_size > 0:
                pct = int(downloaded * 100 / total_size)
                if pct != last_pct:
                    last_pct = pct
                    dl_mb = downloaded / (1024 * 1024)
                    emit("browser", pct, f"{dl_mb:.0f}MB/{total_mb:.0f}MB")

        buffer.seek(0)
        return buffer

    pkgman.webdl = progress_webdl

    # Run the camoufox fetch
    from camoufox.__main__ import CamoufoxUpdate
    from camoufox.addons import DefaultAddons, maybe_download_addons
    from camoufox.locale import ALLOW_GEOIP, download_mmdb

    emit("browser", 0, "checking")
    CamoufoxUpdate().update()
    emit("browser", 90, "extras")
    if ALLOW_GEOIP:
        download_mmdb()
    maybe_download_addons(list(DefaultAddons))
    emit("browser", 100, "done")

if __name__ == "__main__":
    main()
