from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _ensure_project_root_on_path() -> None:
    """Allow running as `python backend/run_backend.py` from repo root."""
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


if __name__ == "__main__":
    _ensure_project_root_on_path()
    from backend.app.core.config import load_env_file

    load_env_file()
    uvicorn.run(
        "backend.app.main:app",
        host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "8765")),
        reload=False,
    )
