#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_ACTIVATE="${VENV_ACTIVATE:-$HOME/venvs/thesis/bin/activate}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8765}"
BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "[preview] venv activate script not found: $VENV_ACTIVATE" >&2
  exit 1
fi

source "$VENV_ACTIVATE"
cd "$ROOT_DIR"

echo "[preview] Running backend tests"
python -m pytest backend/tests -q

echo "[preview] Building dashboard frontend"
(
  cd web_dashboard_ui
  npm run build
)

echo "[preview] Starting backend"
python -m backend.run_backend >/tmp/preview_full_system_backend.log 2>&1 &
BACKEND_PID=$!
cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

READY=0
for _ in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/tmp/preview_health.json 2>/dev/null; then
    READY=1
    break
  fi
  sleep 0.5
done

if [[ "$READY" -ne 1 ]]; then
  echo "[preview] Backend did not become ready. Check /tmp/preview_full_system_backend.log" >&2
  exit 1
fi

echo "[preview] Health: $(cat /tmp/preview_health.json)"

echo "[preview] Logging in"
curl -fsS -c /tmp/preview.cookies \
  -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' >/tmp/preview_login.json

echo "[preview] Login: $(cat /tmp/preview_login.json)"

curl -fsS -b /tmp/preview.cookies "$BASE_URL/api/auth/me" >/tmp/preview_me.json
echo "[preview] Auth check: $(cat /tmp/preview_me.json)"

echo "[preview] Triggering smoke + door events"
curl -fsS -X POST "$BASE_URL/api/sensors/event" \
  -H 'Content-Type: application/json' \
  -d '{"node_id":"smoke_node1","event":"SMOKE_HIGH","location":"Living Room","value":0.91}' >/tmp/preview_smoke.json

curl -fsS -X POST "$BASE_URL/api/sensors/event" \
  -H 'Content-Type: application/json' \
  -d '{"node_id":"door_force","event":"DOOR_FORCE","location":"Door Entrance Area","value":0.98}' >/tmp/preview_door.json

curl -fsS -b /tmp/preview.cookies "$BASE_URL/api/ui/events/live?limit=30" >/tmp/preview_events.json

ALERT_ID="$(python - <<'PY'
import json
payload = json.load(open('/tmp/preview_events.json'))
for alert in payload.get('alerts', []):
    if not alert.get('acknowledged'):
        print(alert.get('id'))
        break
PY
)"

if [[ -n "$ALERT_ID" ]]; then
  echo "[preview] Acknowledging alert $ALERT_ID"
  curl -fsS -b /tmp/preview.cookies -X POST "$BASE_URL/api/alerts/${ALERT_ID}/ack" >/tmp/preview_ack.json
  echo "[preview] Ack: $(cat /tmp/preview_ack.json)"
else
  echo "[preview] No active alert found to acknowledge"
fi

curl -fsS -b /tmp/preview.cookies "$BASE_URL/api/ui/events/live?limit=30" >/tmp/preview_events_after_ack.json

python - <<'PY'
import json
before = json.load(open('/tmp/preview_events.json'))
after = json.load(open('/tmp/preview_events_after_ack.json'))
active_before = [a for a in before.get('alerts', []) if not a.get('acknowledged')]
active_after = [a for a in after.get('alerts', []) if not a.get('acknowledged')]
print(f"[preview] Active alerts before ack: {len(active_before)}")
print(f"[preview] Active alerts after ack:  {len(active_after)}")
PY

echo "[preview] Dashboard URL: $BASE_URL/dashboard"

echo "[preview] Completed"
