from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_TARGETS = {
    "fire_smoke": 10,
    "fire_normal": 5,
    "intruder_door_force": 10,
    "face_unknown": 10,
    "face_authorized": 10,
    "fire_flame": 5,
}

FIELDNAMES = [
    "trial_no",
    "module",
    "scenario",
    "expected_label",
    "predicted_label",
    "event_id",
    "alert_id",
    "event_timestamp",
    "alert_timestamp",
    "event_code",
    "alert_type",
    "source_node",
    "location",
    "event_severity",
    "alert_severity",
    "event_title",
    "alert_title",
    "snapshot_path",
    "acknowledged",
    "review_status",
    "correct",
    "remarks",
]


def load_payload(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    rows = payload.get(key, [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain a valid {key!r} list")
    return [row for row in rows if isinstance(row, dict)]


def normalize_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_alert_lookup(alerts: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_alert_id: dict[str, dict[str, Any]] = {}
    by_event_id: dict[str, dict[str, Any]] = {}
    for alert in alerts:
        alert_id = normalize_id(alert.get("id"))
        event_id = normalize_id(alert.get("event_id"))
        if alert_id:
            by_alert_id[alert_id] = alert
        if event_id and event_id not in by_event_id:
            by_event_id[event_id] = alert
    return by_alert_id, by_event_id


def find_related_alert(
    event: dict[str, Any],
    by_alert_id: dict[str, dict[str, Any]],
    by_event_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    related_alert_id = normalize_id(event.get("related_alert_id"))
    if related_alert_id and related_alert_id in by_alert_id:
        return by_alert_id[related_alert_id]

    event_id = normalize_id(event.get("id"))
    if event_id and event_id in by_event_id:
        return by_event_id[event_id]

    return {}


def classify_event(event: dict[str, Any], alert: dict[str, Any]) -> tuple[str, str, str]:
    event_code = str(event.get("event_code") or "").strip().upper()
    alert_type = str(alert.get("event_code") or "").strip().upper()
    source_node = str(event.get("source_node") or "").strip().lower()

    if event_code in {"SMOKE_HIGH", "SMOKE_WARNING"} or alert_type == "SMOKE_WARNING":
        return "fire", "Smoke warning / high smoke", "SMOKE"
    if event_code == "SMOKE_NORMAL":
        return "fire", "Smoke returned to normal", "NORMAL"
    if event_code == "FLAME_SIGNAL" or alert_type == "FIRE":
        return "fire", "Visual flame / fire fusion alert", "FIRE"
    if event_code == "DOOR_FORCE":
        if alert_type == "AUTHORIZED_ENTRY":
            return "intruder", "Door-force trigger with authorized face", "AUTHORIZED"
        if alert_type == "INTRUDER":
            return "intruder", "Forced door opening attempt", "INTRUDER"
        return "intruder", "Door-force trigger", "INTRUDER"
    if event_code in {"UNKNOWN", "PERSON_DETECTED"} or alert_type == "INTRUDER":
        return "face", "Unknown / non-authorized person", "NON_AUTHORIZED"
    if event_code == "AUTHORIZED" or alert_type == "AUTHORIZED_ENTRY":
        return "face", "Authorized person detected", "AUTHORIZED"
    if source_node.startswith("cam_"):
        return "face", "Camera detection", event_code or alert_type or "UNKNOWN"
    return "system", "System event", event_code or alert_type or "UNKNOWN"


def category_key(event: dict[str, Any], alert: dict[str, Any]) -> str:
    event_code = str(event.get("event_code") or "").strip().upper()
    alert_type = str(alert.get("event_code") or "").strip().upper()

    if event_code in {"SMOKE_HIGH", "SMOKE_WARNING"} or alert_type == "SMOKE_WARNING":
        return "fire_smoke"
    if event_code == "SMOKE_NORMAL":
        return "fire_normal"
    if event_code == "DOOR_FORCE":
        return "intruder_door_force"
    if event_code == "UNKNOWN" or (alert_type == "INTRUDER" and str(event.get("source_node") or "").startswith("cam_")):
        return "face_unknown"
    if event_code == "AUTHORIZED" or alert_type == "AUTHORIZED_ENTRY":
        return "face_authorized"
    if event_code == "FLAME_SIGNAL" or alert_type == "FIRE":
        return "fire_flame"
    return "other"


def make_row(event: dict[str, Any], alert: dict[str, Any]) -> dict[str, str]:
    module, scenario, predicted_label = classify_event(event, alert)
    snapshot_path = str(alert.get("snapshot_path") or event.get("snapshot_path") or "")
    return {
        "trial_no": "",
        "module": module,
        "scenario": scenario,
        "expected_label": "",
        "predicted_label": predicted_label,
        "event_id": normalize_id(event.get("id")),
        "alert_id": normalize_id(alert.get("id") or event.get("related_alert_id")),
        "event_timestamp": str(event.get("timestamp") or ""),
        "alert_timestamp": str(alert.get("timestamp") or ""),
        "event_code": str(event.get("event_code") or ""),
        "alert_type": str(alert.get("event_code") or ""),
        "source_node": str(event.get("source_node") or alert.get("source_node") or ""),
        "location": str(event.get("location") or alert.get("location") or ""),
        "event_severity": str(event.get("severity") or ""),
        "alert_severity": str(alert.get("severity") or ""),
        "event_title": str(event.get("title") or ""),
        "alert_title": str(alert.get("title") or ""),
        "snapshot_path": snapshot_path,
        "acknowledged": str(alert.get("acknowledged") if alert else ""),
        "review_status": str(alert.get("review_status") or ""),
        "correct": "",
        "remarks": "",
    }


def choose_rows(events: list[dict[str, Any]], alerts: list[dict[str, Any]], limit: int) -> list[dict[str, str]]:
    by_alert_id, by_event_id = build_alert_lookup(alerts)
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)

    for event in events:
        alert = find_related_alert(event, by_alert_id, by_event_id)
        key = category_key(event, alert)
        if key == "other":
            continue
        buckets[key].append(make_row(event, alert))

    selected: list[dict[str, str]] = []
    for key, target in DEFAULT_TARGETS.items():
        selected.extend(buckets.get(key, [])[:target])

    if len(selected) < limit:
        seen = {(row["event_id"], row["alert_id"]) for row in selected}
        for key in DEFAULT_TARGETS:
            for row in buckets.get(key, [])[DEFAULT_TARGETS[key] :]:
                row_key = (row["event_id"], row["alert_id"])
                if row_key in seen:
                    continue
                selected.append(row)
                seen.add(row_key)
                if len(selected) >= limit:
                    break
            if len(selected) >= limit:
                break

    selected = selected[:limit]
    for index, row in enumerate(selected, start=1):
        row["trial_no"] = str(index)
    return selected


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Chapter 4 trial review sheet from exported event and alert logs."
    )
    parser.add_argument("--events", default="chapter4_events_log.json", type=Path)
    parser.add_argument("--alerts", default="chapter4_alerts_log.json", type=Path)
    parser.add_argument("--output", default="chapter4_trial_review_sheet.csv", type=Path)
    parser.add_argument("--limit", default=50, type=int)
    args = parser.parse_args()

    events = load_payload(args.events, "events")
    alerts = load_payload(args.alerts, "alerts")
    rows = choose_rows(events, alerts, max(1, args.limit))
    write_csv(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
