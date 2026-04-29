import os
import socket
import threading
import time
import webbrowser

import uvicorn

from backend.app.main import app

HOST = os.getenv("CONDO_GUARDIAN_HOST", "0.0.0.0")
PORT = int(os.getenv("CONDO_GUARDIAN_PORT", "8765"))


def detect_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0] or "").strip()
    except Exception:
        return ""
    finally:
        sock.close()


def build_open_url() -> str:
    explicit_url = os.getenv("CONDO_GUARDIAN_OPEN_URL", "").strip()
    if explicit_url:
        return explicit_url

    host_override = os.getenv("CONDO_GUARDIAN_OPEN_URL_HOST", "").strip()
    if host_override:
        return f"http://{host_override}:{PORT}/dashboard"

    lan_ip = detect_lan_ip()
    if lan_ip and lan_ip != "127.0.0.1":
        return f"http://{lan_ip}:{PORT}/dashboard"
    return f"http://127.0.0.1:{PORT}/dashboard"


OPEN_URL = build_open_url()


def open_browser() -> None:
    if os.getenv("CONDO_GUARDIAN_NO_BROWSER") == "1":
        return
    time.sleep(2)
    webbrowser.open(OPEN_URL)


if __name__ == "__main__":
    os.environ.setdefault("APP_MODE", "desktop")
    lan_ip = detect_lan_ip() or "unavailable"
    print(f"[CondoGuardian] bind=http://{HOST}:{PORT}")
    print(f"[CondoGuardian] local=http://127.0.0.1:{PORT}/dashboard")
    print(f"[CondoGuardian] lan=http://{lan_ip}:{PORT}/dashboard")
    print(f"[CondoGuardian] open={OPEN_URL}")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
