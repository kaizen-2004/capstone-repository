from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.security import expiry_iso, hash_password, now_iso, parse_iso, verify_password

_LOCK = threading.RLock()
_DB_PATH: Path | None = None


@dataclass
class DbConfig:
    path: Path
    session_ttl_seconds: int


_DB_CONFIG: DbConfig | None = None


def configure(path: Path, session_ttl_seconds: int) -> None:
    global _DB_PATH, _DB_CONFIG
    _DB_PATH = path
    _DB_CONFIG = DbConfig(path=path, session_ttl_seconds=session_ttl_seconds)


def _conn() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("database not configured")
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA foreign_keys=ON;")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_ts TEXT NOT NULL,
                updated_ts TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_ts TEXT NOT NULL,
                expires_ts TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS authorized_faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                note TEXT,
                created_ts TEXT NOT NULL,
                updated_ts TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS face_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                face_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                source TEXT NOT NULL,
                quality REAL NOT NULL DEFAULT 0,
                created_ts TEXT NOT NULL,
                FOREIGN KEY(face_id) REFERENCES authorized_faces(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                device_type TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                status TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                note TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                location TEXT,
                rtsp_url TEXT,
                status TEXT NOT NULL,
                fps_target INTEGER NOT NULL DEFAULT 12,
                last_seen_ts TEXT,
                last_error TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                event_code TEXT NOT NULL,
                source_node TEXT NOT NULL,
                location TEXT,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                details_json TEXT,
                ts TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                requires_ack INTEGER NOT NULL DEFAULT 1,
                ack_ts TEXT,
                ack_by TEXT,
                snapshot_path TEXT,
                details_json TEXT,
                ts TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_ts TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_code_ts ON events(event_code, ts DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status_ts ON alerts(status, ts DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_seen ON devices(last_seen_ts)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_faces_name ON authorized_faces(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_face_samples_face ON face_samples(face_id)")

        conn.commit()
        conn.close()


def ensure_admin_user(username: str, password: str) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        now = now_iso()
        cur.execute("SELECT id, password_hash FROM admin_users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO admin_users(username, password_hash, created_ts, updated_ts) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), now, now),
            )
        conn.commit()
        conn.close()


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash FROM admin_users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"id": int(row["id"]), "username": str(row["username"])}


def create_session(user_id: int, token: str) -> None:
    if _DB_CONFIG is None:
        raise RuntimeError("database not configured")
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            "INSERT OR REPLACE INTO sessions(token, user_id, created_ts, expires_ts) VALUES (?, ?, ?, ?)",
            (token, int(user_id), now, expiry_iso(_DB_CONFIG.session_ttl_seconds)),
        )
        conn.commit()
        conn.close()


def get_session_user(token: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.token, s.expires_ts, u.id as user_id, u.username
            FROM sessions s
            JOIN admin_users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        )
        row = cur.fetchone()
        conn.close()
    if row is None:
        return None
    expires = parse_iso(row["expires_ts"])
    if expires is None:
        delete_session(token)
        return None
    if expires <= parse_iso(now_iso()):
        delete_session(token)
        return None
    return {"id": int(row["user_id"]), "username": str(row["username"])}


def delete_session(token: str) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()


def prune_expired_sessions() -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE expires_ts <= ?", (now_iso(),))
        conn.commit()
        conn.close()


def upsert_device(
    node_id: str,
    label: str,
    device_type: str,
    location: str,
    ip_address: str,
    note: str = "",
    *,
    status: str = "online",
) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        ts = now_iso()
        cur.execute(
            """
            INSERT INTO devices(node_id, label, device_type, location, ip_address, status, last_seen_ts, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
              label=excluded.label,
              device_type=excluded.device_type,
              location=excluded.location,
              ip_address=excluded.ip_address,
              status=excluded.status,
              last_seen_ts=excluded.last_seen_ts,
              note=excluded.note
            """,
            (node_id, label, device_type, location, ip_address, status, ts, note),
        )
        conn.commit()
        conn.close()


def heartbeat_device(node_id: str, ip_address: str = "", note: str = "") -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        ts = now_iso()
        cur.execute(
            "UPDATE devices SET last_seen_ts=?, status='online', ip_address=COALESCE(NULLIF(?, ''), ip_address), note=? WHERE node_id=?",
            (ts, ip_address, note, node_id),
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO devices(node_id, label, device_type, location, ip_address, status, last_seen_ts, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (node_id, node_id, "sensor", "", ip_address, "online", ts, note),
            )
        conn.commit()
        conn.close()


def set_device_status(node_id: str, status: str, note: str = "") -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE devices SET status=?, note=? WHERE node_id=?", (status, note, node_id))
        conn.commit()
        conn.close()


def list_devices() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices ORDER BY location, label")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def list_offline_devices(node_offline_seconds: int) -> list[dict[str, Any]]:
    rows = list_devices()
    cutoff = parse_iso(now_iso())
    if cutoff is None:
        return []
    offline: list[dict[str, Any]] = []
    for row in rows:
        seen = parse_iso(str(row.get("last_seen_ts") or ""))
        if seen is None:
            continue
        seconds = (cutoff - seen).total_seconds()
        if seconds > node_offline_seconds and str(row.get("status")) != "offline":
            offline.append(row)
    return offline


def upsert_camera(node_id: str, label: str, location: str, rtsp_url: str, fps_target: int) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO cameras(node_id, label, location, rtsp_url, status, fps_target, last_seen_ts, last_error)
            VALUES (?, ?, ?, ?, 'offline', ?, NULL, '')
            ON CONFLICT(node_id) DO UPDATE SET
              label=excluded.label,
              location=excluded.location,
              rtsp_url=excluded.rtsp_url,
              fps_target=excluded.fps_target
            """,
            (node_id, label, location, rtsp_url, int(fps_target)),
        )
        conn.commit()
        conn.close()


def set_camera_runtime(node_id: str, status: str, last_error: str = "") -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        ts = now_iso() if status == "online" else None
        cur.execute(
            "UPDATE cameras SET status=?, last_seen_ts=COALESCE(?, last_seen_ts), last_error=? WHERE node_id=?",
            (status, ts, last_error[:500], node_id),
        )
        conn.commit()
        conn.close()


def list_cameras() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM cameras ORDER BY location, node_id")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def create_event(
    event_type: str,
    event_code: str,
    source_node: str,
    location: str,
    severity: str,
    title: str,
    description: str,
    details: dict[str, Any] | None = None,
    ts: str | None = None,
) -> int:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO events(type, event_code, source_node, location, severity, title, description, details_json, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                event_code,
                source_node,
                location,
                severity,
                title,
                description,
                json.dumps(details or {}, separators=(",", ":")),
                ts or now_iso(),
            ),
        )
        conn.commit()
        event_id = int(cur.lastrowid)
        conn.close()
    return event_id


def create_alert(
    alert_type: str,
    severity: str,
    status: str,
    requires_ack: bool,
    title: str,
    description: str,
    source_node: str,
    location: str,
    event_id: int | None = None,
    snapshot_path: str = "",
    details: dict[str, Any] | None = None,
    ts: str | None = None,
) -> int:
    payload = {
        "title": title,
        "description": description,
        "source_node": source_node,
        "location": location,
    }
    if details:
        payload.update(details)
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alerts(event_id, type, severity, status, requires_ack, ack_ts, ack_by, snapshot_path, details_json, ts)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                event_id,
                alert_type,
                severity,
                status,
                1 if requires_ack else 0,
                snapshot_path,
                json.dumps(payload, separators=(",", ":")),
                ts or now_iso(),
            ),
        )
        conn.commit()
        alert_id = int(cur.lastrowid)
        conn.close()
    return alert_id


def ack_alert(alert_id: int, ack_by: str, status: str = "ACK") -> bool:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE alerts SET status=?, ack_ts=?, ack_by=? WHERE id=? AND status='ACTIVE'",
            (status, now_iso(), ack_by, int(alert_id)),
        )
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
    return updated


def list_events(limit: int) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (max(1, min(1000, int(limit))),))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def list_alerts(limit: int) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (max(1, min(1000, int(limit))),))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def list_active_alerts() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM alerts WHERE status='ACTIVE' ORDER BY ts DESC")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def upsert_setting(key: str, value: str) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO settings(key, value, updated_ts) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
            (key, value, now_iso()),
        )
        conn.commit()
        conn.close()


def list_settings() -> list[dict[str, str]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings ORDER BY key")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def create_face(name: str, note: str = "") -> dict[str, Any]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        ts = now_iso()
        cur.execute(
            "INSERT INTO authorized_faces(name, note, created_ts, updated_ts, is_active) VALUES (?, ?, ?, ?, 1)",
            (name, note, ts, ts),
        )
        face_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
    return {"id": face_id, "name": name, "note": note, "created_ts": ts}


def delete_face(face_id: int) -> bool:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM authorized_faces WHERE id = ?", (int(face_id),))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
    return deleted


def list_faces() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT f.*, COUNT(s.id) AS sample_count
            FROM authorized_faces f
            LEFT JOIN face_samples s ON s.face_id = f.id
            WHERE f.is_active = 1
            GROUP BY f.id
            ORDER BY f.name
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def get_face_by_name(name: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM authorized_faces WHERE lower(name) = lower(?) LIMIT 1", (name,))
        row = cur.fetchone()
        conn.close()
    return dict(row) if row else None


def add_face_sample(face_id: int, image_path: str, source: str, quality: float) -> int:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO face_samples(face_id, image_path, source, quality, created_ts) VALUES (?, ?, ?, ?, ?)",
            (int(face_id), image_path, source, float(quality), now_iso()),
        )
        sample_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
    return sample_id


def count_face_samples(face_id: int) -> int:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) AS c FROM face_samples WHERE face_id = ?", (int(face_id),))
        row = cur.fetchone()
        conn.close()
    return int((row or {"c": 0})["c"])


def list_face_samples(face_id: int) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM face_samples WHERE face_id = ? ORDER BY created_ts DESC", (int(face_id),))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def daily_stats(days: int) -> list[dict[str, Any]]:
    limit = max(1, min(31, int(days)))
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            WITH RECURSIVE d(day, n) AS (
                SELECT date('now', 'localtime'), 1
                UNION ALL
                SELECT date(day, '-1 day'), n + 1 FROM d WHERE n < ?
            )
            SELECT
                d.day as date,
                COALESCE(SUM(CASE WHEN e.event_code='AUTHORIZED' THEN 1 ELSE 0 END), 0) AS authorized_faces,
                COALESCE(SUM(CASE WHEN e.event_code='UNKNOWN' THEN 1 ELSE 0 END), 0) AS unknown_detections,
                COALESCE(SUM(CASE WHEN e.event_code='FLAME_SIGNAL' THEN 1 ELSE 0 END), 0) AS flame_signals,
                COALESCE(SUM(CASE WHEN e.event_code='SMOKE_HIGH' THEN 1 ELSE 0 END), 0) AS smoke_high_events,
                COALESCE(SUM(CASE WHEN a.type='FIRE' THEN 1 ELSE 0 END), 0) AS fire_alerts,
                COALESCE(SUM(CASE WHEN a.type IN ('INTRUDER','DOOR_TAMPER') THEN 1 ELSE 0 END), 0) AS intruder_alerts,
                1.4 AS avg_response_seconds
            FROM d
            LEFT JOIN events e ON date(e.ts, 'localtime') = d.day
            LEFT JOIN alerts a ON date(a.ts, 'localtime') = d.day
            GROUP BY d.day
            ORDER BY d.day ASC
            """,
            (limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    return rows


def log(level: str, message: str) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO system_logs(level, message, ts) VALUES (?, ?, ?)",
            (level.upper()[:16], message[:1000], now_iso()),
        )
        conn.commit()
        conn.close()


def cleanup_old_records(event_days: int, log_days: int) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE ts < datetime('now', ?)", (f"-{int(event_days)} day",))
        cur.execute("DELETE FROM system_logs WHERE ts < datetime('now', ?)", (f"-{int(log_days)} day",))
        conn.commit()
        conn.close()


def event_exists_recent(event_code: str, source_node: str, window_seconds: int = 120) -> bool:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM events
            WHERE event_code=? AND source_node=?
              AND ts >= datetime('now', ?)
            LIMIT 1
            """,
            (event_code, source_node, f"-{int(window_seconds)} seconds"),
        )
        row = cur.fetchone()
        conn.close()
    return row is not None


def set_face_updated(face_id: int) -> None:
    with _LOCK:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE authorized_faces SET updated_ts=? WHERE id=?", (now_iso(), int(face_id)))
        conn.commit()
        conn.close()


def get_runtime_snapshot() -> dict[str, Any]:
    return {
        "devices": list_devices(),
        "cameras": list_cameras(),
        "active_alerts": list_active_alerts(),
        "settings": list_settings(),
    }
