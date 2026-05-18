from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def _ensure_project_root_on_path() -> None:
    """Allow running as `python backend/run_backend.py` from repo root."""
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _configure_windows_event_loop() -> None:
    if sys.platform != "win32":
        return
    try:
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass


def _open_dashboard_later(port: int) -> None:
    if os.environ.get("CONDO_GUARDIAN_NO_BROWSER") == "1":
        return
    if os.environ.get("BACKEND_NO_BROWSER") == "1":
        return

    explicit_url = os.environ.get("BACKEND_OPEN_URL", "").strip()
    url = explicit_url or f"http://127.0.0.1:{port}/dashboard"

    def _open() -> None:
        time.sleep(2)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    _configure_windows_event_loop()
    _ensure_project_root_on_path()
    from backend.app.core.config import load_env_file

    load_env_file()
    port = int(os.environ.get("BACKEND_PORT", "8765"))
    _open_dashboard_later(port)
    uvicorn.run(
        "backend.app.main:app",
        host=os.environ.get("BACKEND_HOST", "0.0.0.0"),
        port=port,
        reload=False,
        access_log=_env_bool("BACKEND_ACCESS_LOG", False),
    )
