import os
import threading
import time
import webbrowser

import uvicorn

from backend.app.main import app

HOST = os.getenv("CONDO_GUARDIAN_HOST", "127.0.0.1")
PORT = int(os.getenv("CONDO_GUARDIAN_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}/dashboard"


def open_browser() -> None:
    if os.getenv("CONDO_GUARDIAN_NO_BROWSER") == "1":
        return
    time.sleep(2)
    webbrowser.open(URL)


if __name__ == "__main__":
    os.environ.setdefault("APP_MODE", "desktop")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
