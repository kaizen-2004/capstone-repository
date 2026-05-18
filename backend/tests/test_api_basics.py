import json
import time
import uuid

import numpy as np
from fastapi.testclient import TestClient

from backend.app.db import store
from backend.app.main import app
from backend.app.services.supervisor import Supervisor


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True


def test_login_and_me() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200
        payload = login.json()
        assert isinstance(payload.get("token"), str)
        assert int(payload.get("expires_in_seconds") or 0) == 24 * 60 * 60

        me_by_bearer = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {payload['token']}"},
        )
        assert me_by_bearer.status_code == 200
        assert me_by_bearer.json()["authenticated"] is True

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["authenticated"] is True


def test_enroll_start_and_complete_contract() -> None:
    person_name = f"Enroll Test {uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        start = client.post(
            "/api/enroll/start",
            json={
                "name": person_name,
                "role": "Authorized",
                "capture_source": "mobile_app",
            },
        )
        assert start.status_code == 200
        start_payload = start.json()
        assert start_payload["ok"] is True
        assert str(start_payload["enroll_id"]).startswith("enroll-face-")
        assert int(start_payload["min_required"]) == 40
        assert int(start_payload["target"]) == 40

        complete = client.post(
            "/api/enroll/complete",
            json={"enroll_id": start_payload["enroll_id"], "trigger_train": False},
        )
        assert complete.status_code == 400
        assert "minimum samples not met" in str(complete.json().get("detail") or "")


def test_enroll_start_and_complete_user_code_alias_contract() -> None:
    full_name = f"Alias Enroll {uuid.uuid4().hex[:6]}"
    user_code = f"USR-{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        start = client.post(
            "/api/enroll/start",
            json={"full_name": full_name, "user_code": user_code},
        )
        assert start.status_code == 200
        start_payload = start.json()
        assert start_payload["ok"] is True
        assert str(start_payload["enroll_id"]).startswith("enroll-face-")
        assert start_payload["user_code"] == user_code

        complete = client.post(
            "/api/enroll/complete",
            json={"user_code": user_code, "trigger_train": False},
        )
        assert complete.status_code == 400
        assert "minimum samples not met" in str(complete.json().get("detail") or "")


def test_enroll_upload_user_code_alias_multipart_contract() -> None:
    full_name = f"Alias Upload {uuid.uuid4().hex[:6]}"
    user_code = f"USR-{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        start = client.post(
            "/api/enroll/start",
            json={"full_name": full_name, "user_code": user_code},
        )
        assert start.status_code == 200
        start_payload = start.json()

        face_service = app.state.face_service
        original_capture_sample = face_service.capture_sample

        def _fake_capture_sample(
            person_name: str, image_data_url: str, source: str = "phone_upload"
        ) -> dict:
            assert person_name == full_name
            assert image_data_url.startswith("data:image/jpeg;base64,")
            assert source.startswith("mobile_enroll:")
            return face_service.training_status(person_name, min_required=40, target=40)

        face_service.capture_sample = _fake_capture_sample
        try:
            upload = client.post(
                "/api/enroll/upload",
                data={
                    "user_code": user_code,
                    "capture_source": "mobile_app",
                    "sample_index": "1",
                },
                files={"image": ("sample.jpg", b"fake-jpeg-bytes", "image/jpeg")},
            )
        finally:
            face_service.capture_sample = original_capture_sample

        assert upload.status_code == 200
        upload_payload = upload.json()
        assert upload_payload["ok"] is True
        assert upload_payload["user_code"] == user_code
        assert upload_payload["sample_index"] == "1"
    assert upload_payload["capture_source"] == "mobile_app"
    assert upload_payload["enroll_id"] == start_payload["enroll_id"]


def test_enroll_upload_accepts_octet_stream_with_image_extension() -> None:
    full_name = f"Octet Upload {uuid.uuid4().hex[:6]}"
    user_code = f"USR-{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        start = client.post(
            "/api/enroll/start",
            json={"full_name": full_name, "user_code": user_code},
        )
        assert start.status_code == 200

        face_service = app.state.face_service
        original_capture_sample = face_service.capture_sample

        def _fake_capture_sample(
            person_name: str, image_data_url: str, source: str = "phone_upload"
        ) -> dict:
            assert person_name == full_name
            assert image_data_url.startswith("data:image/jpeg;base64,")
            assert source.startswith("mobile_enroll:")
            return face_service.training_status(person_name, min_required=40, target=40)

        face_service.capture_sample = _fake_capture_sample
        try:
            upload = client.post(
                "/api/enroll/upload",
                data={
                    "user_code": user_code,
                    "capture_source": "mobile_app",
                    "sample_index": "2",
                },
                files={
                    "image": (
                        "sample.jpg",
                        b"fake-jpeg-bytes",
                        "application/octet-stream",
                    )
                },
            )
        finally:
            face_service.capture_sample = original_capture_sample

        assert upload.status_code == 200
        upload_payload = upload.json()
        assert upload_payload["ok"] is True
        assert upload_payload["user_code"] == user_code


def test_enroll_upload_accepts_octet_stream_without_extension() -> None:
    full_name = f"Octet No Ext {uuid.uuid4().hex[:6]}"
    user_code = f"USR-{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        start = client.post(
            "/api/enroll/start",
            json={"full_name": full_name, "user_code": user_code},
        )
        assert start.status_code == 200

        face_service = app.state.face_service
        original_capture_sample = face_service.capture_sample

        def _fake_capture_sample(
            person_name: str, image_data_url: str, source: str = "phone_upload"
        ) -> dict:
            assert person_name == full_name
            assert image_data_url.startswith("data:image/jpeg;base64,")
            assert source.startswith("mobile_enroll:")
            return face_service.training_status(person_name, min_required=40, target=40)

        face_service.capture_sample = _fake_capture_sample
        try:
            upload = client.post(
                "/api/enroll/upload",
                data={
                    "user_code": user_code,
                    "capture_source": "mobile_app",
                    "sample_index": "3",
                },
                files={
                    "image": (
                        "capture",
                        b"\xff\xd8\xff\xdb\x00\x43fake-jpeg-bytes",
                        "application/octet-stream",
                    )
                },
            )
        finally:
            face_service.capture_sample = original_capture_sample

        assert upload.status_code == 200
        upload_payload = upload.json()
        assert upload_payload["ok"] is True
        assert upload_payload["user_code"] == user_code


def test_mobile_remote_status_and_config() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        status_before = client.get("/api/remote/mobile/status")
        assert status_before.status_code == 200
        assert "enabled" in status_before.json()

        enable = client.post("/api/remote/mobile/config", json={"enabled": True})
        assert enable.status_code == 200
        assert enable.json()["enabled"] is True

        status_after_enable = client.get("/api/remote/mobile/status")
        assert status_after_enable.status_code == 200
        assert status_after_enable.json()["enabled"] is True

        disable = client.post("/api/remote/mobile/config", json={"enabled": False})
        assert disable.status_code == 200
        assert disable.json()["enabled"] is True


def test_mobile_auth_timeout_clears_session_cookie() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        token = client.cookies.get("session_token")
        assert token
        store.delete_session(token)

        response = client.get("/api/remote/mobile/status")
        assert response.status_code == 401
        assert response.json()["detail"] == "Session expired"
        set_cookie = response.headers.get("set-cookie", "")
        assert "session_token=" in set_cookie
        assert "Max-Age=0" in set_cookie


def test_mobile_bootstrap_device_and_preferences() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        bootstrap = client.get("/api/mobile/bootstrap")
        assert bootstrap.status_code == 200
        assert bootstrap.json()["ok"] is True
        assert "network_modes" in bootstrap.json()
        assert "preferred_base_url" in bootstrap.json()
        assert "mdns_base_url" not in bootstrap.json()

        register = client.post(
            "/api/mobile/device/register",
            json={
                "device_id": "mobile-test-device-001",
                "platform": "web_pwa",
                "network_mode": "lan",
                "push_subscription": {
                    "endpoint": "https://example.push.test/sub/abc123",
                    "keys": {"p256dh": "test_p256dh", "auth": "test_auth"},
                },
            },
        )
        assert register.status_code == 200
        assert register.json()["ok"] is True
        assert register.json()["device_id"] == "mobile-test-device-001"

        prefs_before = client.get("/api/mobile/notifications/preferences")
        assert prefs_before.status_code == 200
        assert prefs_before.json()["ok"] is True
        assert "push_enabled" in prefs_before.json()

        prefs_update = client.post(
            "/api/mobile/notifications/preferences",
            json={"push_enabled": False},
        )
        assert prefs_update.status_code == 200
        assert prefs_update.json()["push_enabled"] is False

        unregister = client.post(
            "/api/mobile/device/unregister",
            json={"device_id": "mobile-test-device-001"},
        )
        assert unregister.status_code == 200
        assert unregister.json()["ok"] is True


def test_intruder_event_cooldown_suppresses_repeats() -> None:
    node_id = f"door_force_cooldown_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        first = client.post(
            "/api/sensors/event",
            json={
                "node_id": node_id,
                "event": "DOOR_FORCE",
                "location": "Door Entrance Area",
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["ok"] is True
        assert first_payload["suppressed"] is False
        assert isinstance(first_payload["event_id"], int)
        assert isinstance(first_payload["alert_id"], int)

        second = client.post(
            "/api/sensors/event",
            json={
                "node_id": node_id,
                "event": "DOOR_FORCE",
                "location": "Door Entrance Area",
            },
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["ok"] is True
        assert second_payload["suppressed"] is True
        assert second_payload["suppression_reason"] == "intruder_cooldown"
        assert int(second_payload["cooldown_seconds"]) >= 0
        assert second_payload["event_id"] is None
        assert second_payload["alert_id"] is None


def test_door_state_events_do_not_create_alerts() -> None:
    node_id = f"door_force_state_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        dispatched_events: list[dict] = []
        original_dispatcher = app.state.event_engine.notification_dispatcher

        class FakeDispatcher:
            def dispatch_event(self, event: dict) -> None:
                dispatched_events.append(event)

        app.state.event_engine.notification_dispatcher = FakeDispatcher()
        try:
            opened = client.post(
                "/api/sensors/event",
                json={
                    "node_id": node_id,
                    "event": "DOOR_OPEN",
                    "location": "Door Entrance Area",
                    "value": 1.0,
                    "details": {
                        "sensor": "magnetic_reed_switch",
                        "door_state": "open",
                    },
                },
            )
            assert opened.status_code == 200
            opened_payload = opened.json()
            assert opened_payload["ok"] is True
            assert opened_payload["event_code"] == "DOOR_OPEN"
            assert opened_payload["classification"] == "sensor"
            assert isinstance(opened_payload["event_id"], int)
            assert opened_payload["alert_id"] is None
            assert opened_payload["suppressed"] is False

            closed = client.post(
                "/api/sensors/event",
                json={
                    "node_id": node_id,
                    "event": "DOOR_CLOSED",
                    "location": "Door Entrance Area",
                    "value": 0.0,
                    "details": {
                        "sensor": "magnetic_reed_switch",
                        "door_state": "closed",
                    },
                },
            )
            assert closed.status_code == 200
            closed_payload = closed.json()
            assert closed_payload["ok"] is True
            assert closed_payload["event_code"] == "DOOR_CLOSED"
            assert closed_payload["classification"] == "sensor"
            assert isinstance(closed_payload["event_id"], int)
            assert closed_payload["alert_id"] is None
            assert closed_payload["suppressed"] is False
        finally:
            app.state.event_engine.notification_dispatcher = original_dispatcher

    assert [event["event_code"] for event in dispatched_events] == [
        "DOOR_OPEN",
        "DOOR_CLOSED",
    ]


def test_smoke_warning_event_creates_fire_alert() -> None:
    node_id = f"smoke_warning_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        response = client.post(
            "/api/sensors/event",
            json={
                "node_id": node_id,
                "event": "SMOKE_WARNING",
                "location": "Living Room",
                "value": 0.12,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["event_code"] == "SMOKE_WARNING"
        assert payload["classification"] == "fire"
        assert isinstance(payload["event_id"], int)
        assert isinstance(payload["alert_id"], int)


def test_fire_bbox_detection_creates_immediate_alert_snapshot() -> None:
    node_id = f"cam_fire_bbox_{uuid.uuid4().hex[:8]}"
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCameraManager:
        def __init__(self) -> None:
            self.saved_snapshots: list[tuple[str, str]] = []

        def live_status(self) -> list[dict[str, str]]:
            return [{"node_id": node_id, "status": "online"}]

        def snapshot_frame(self, requested_node: str):
            assert requested_node == node_id
            return frame.copy()

        def save_snapshot(self, requested_node: str, snapshot_frame, prefix: str) -> str:
            assert requested_node == node_id
            assert prefix == "fire_confirmed_continuous"
            assert snapshot_frame is not None
            self.saved_snapshots.append((requested_node, prefix))
            return f"snapshots/test/{prefix}_{requested_node}.jpg"

    class FakeFireService:
        def detect_flame(self, snapshot_frame) -> dict:
            assert snapshot_frame is not None
            return {
                "flame": True,
                "smoke_detected": False,
                "confidence": 91.2,
                "score": 0.912,
                "threshold": 0.6,
                "detector": "test",
                "detected_class": "fire",
                "detected_class_index": 0,
                "bbox": [10, 12, 40, 36],
            }

    with TestClient(app):
        fake_camera_manager = FakeCameraManager()
        supervisor = Supervisor(
            node_offline_seconds=120,
            camera_offline_seconds=45,
            event_retention_days=90,
            log_retention_days=30,
            snapshot_root=app.state.settings.snapshot_root,
            regular_snapshot_retention_days=30,
            critical_snapshot_retention_days=90,
            camera_manager=fake_camera_manager,
            fire_service=FakeFireService(),
            fire_continuous_detection_enabled=True,
            fire_scan_seconds=2,
            fire_alert_cooldown_seconds=15,
        )

        supervisor.fire_confirmation_hits_required = 2
        supervisor._scan_fire_presence(time.time())

        events = [
            row
            for row in store.list_events(limit=100)
            if row.get("source_node") == node_id and row.get("event_code") == "FLAME_SIGNAL"
        ]
        assert len(events) == 1

        alerts = [
            row
            for row in store.list_alerts(limit=100)
            if row.get("event_id") == events[0]["id"] and row.get("type") == "FIRE"
        ]
        assert len(alerts) == 1
        assert str(alerts[0].get("snapshot_path") or "").endswith(
            f"fire_confirmed_continuous_{node_id}.jpg"
        )
        details = json.loads(str(alerts[0].get("details_json") or "{}"))
        assert details["flame_confirmation"]["bbox"] == [10, 12, 40, 36]
        assert fake_camera_manager.saved_snapshots == [
            (node_id, "fire_confirmed_continuous")
        ]


def test_remote_access_and_integration_status_routes() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        links = client.get("/api/remote/access/links")
        assert links.status_code == 200
        links_payload = links.json()
        assert links_payload["ok"] is True
        assert "preferred_url" in links_payload
        assert "lan_url" in links_payload
        assert "mdns_url" not in links_payload

        telegram_status = client.get("/api/integrations/telegram/status")
        assert telegram_status.status_code == 404

        telegram_send_link = client.post("/api/integrations/telegram/send-access-link")
        assert telegram_send_link.status_code == 404


def test_runtime_settings_update_and_secret_replace_flow() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        update_threshold = client.post(
            "/api/ui/settings/runtime",
            json={"key": "FACE_COSINE_THRESHOLD", "value": "0.61"},
        )
        assert update_threshold.status_code == 200
        update_payload = update_threshold.json()
        assert update_payload["ok"] is True
        assert update_payload["key"] == "FACE_COSINE_THRESHOLD"
        assert update_payload["value"] == "0.61"

        update_camera_timeout = client.post(
            "/api/ui/settings/runtime",
            json={"key": "CAMERA_OFFLINE_SECONDS", "value": "55"},
        )
        assert update_camera_timeout.status_code == 200
        timeout_payload = update_camera_timeout.json()
        assert timeout_payload["ok"] is True
        assert timeout_payload["key"] == "CAMERA_OFFLINE_SECONDS"
        assert timeout_payload["value"] == "55"

        update_secret = client.post(
            "/api/ui/settings/runtime",
            json={"key": "WEBPUSH_VAPID_PUBLIC_KEY", "value": "vapid_public_test_key"},
        )
        assert update_secret.status_code == 200
        secret_payload = update_secret.json()
        assert secret_payload["ok"] is True
        assert secret_payload["key"] == "WEBPUSH_VAPID_PUBLIC_KEY"
        assert secret_payload["secret"] is True
        assert secret_payload["configured"] is True
        assert secret_payload["value"] == ""

        settings_live = client.get("/api/ui/settings/live")
        assert settings_live.status_code == 200
        runtime_settings = settings_live.json()["runtime_settings"]
        runtime_keys = {str(row.get("key") or "") for row in runtime_settings}

        threshold_row = next(
            row for row in runtime_settings if row.get("key") == "FACE_COSINE_THRESHOLD"
        )
        assert threshold_row["value"] == "0.61"

        secret_row = next(
            row
            for row in runtime_settings
            if row.get("key") == "WEBPUSH_VAPID_PUBLIC_KEY"
        )
        assert secret_row["secret"] is True
        assert secret_row["configured"] is True
        assert secret_row["value"] == ""
        assert "TELEGRAM_BOT_TOKEN" not in runtime_keys


def test_guest_mode_suppresses_intruder_alerts_temporarily() -> None:
    node_id = f"door_force_guest_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        try:
            enable = client.post(
                "/api/ui/settings/guest-mode", json={"duration_hours": 2}
            )
            assert enable.status_code == 200
            enable_payload = enable.json()
            assert enable_payload["active"] is True
            assert int(enable_payload["remaining_seconds"]) > 0

            event_post = client.post(
                "/api/sensors/event",
                json={
                    "node_id": node_id,
                    "event": "DOOR_FORCE",
                    "location": "Door Entrance Area",
                },
            )
            assert event_post.status_code == 200
            event_payload = event_post.json()
            assert event_payload["ok"] is True
            assert event_payload["suppressed"] is False
            assert event_payload["classification"] == "guest"
            assert event_payload["event_code"] == "GUEST_ACTIVITY"
            assert isinstance(event_payload["event_id"], int)
            assert event_payload["alert_id"] is None

            events = [
                row
                for row in store.list_events(limit=100)
                if int(row.get("id") or 0) == int(event_payload["event_id"])
            ]
            assert len(events) == 1
            assert events[0]["event_code"] == "GUEST_ACTIVITY"
            assert events[0]["severity"] == "info"

            disable = client.post(
                "/api/ui/settings/guest-mode", json={"duration_hours": 0}
            )
            assert disable.status_code == 200
            assert disable.json()["active"] is False

            normal_event = client.post(
                "/api/sensors/event",
                json={
                    "node_id": node_id,
                    "event": "DOOR_FORCE",
                    "location": "Door Entrance Area",
                },
            )
            assert normal_event.status_code == 200
            normal_payload = normal_event.json()
            assert normal_payload["classification"] == "intruder"
            assert normal_payload["event_code"] == "DOOR_FORCE"
            assert isinstance(normal_payload["alert_id"], int)
        finally:
            store.set_guest_mode_until("")


def test_unknown_presence_alerting_ignores_legacy_disabled_flag() -> None:
    with TestClient(app):
        original = store.get_setting("UNKNOWN_PRESENCE_LOGGING_ENABLED")
        store.upsert_setting("UNKNOWN_PRESENCE_LOGGING_ENABLED", "false")
        try:
            supervisor = Supervisor(
                node_offline_seconds=120,
                camera_offline_seconds=45,
                event_retention_days=90,
                log_retention_days=30,
                snapshot_root=app.state.settings.snapshot_root,
                regular_snapshot_retention_days=30,
                critical_snapshot_retention_days=90,
                camera_manager=object(),
                face_service=object(),
                unknown_presence_logging_enabled=False,
            )

            assert supervisor._presence_logging_enabled_runtime() is True
            assert supervisor.unknown_presence_logging_enabled is True
        finally:
            if original is None:
                store.upsert_setting("UNKNOWN_PRESENCE_LOGGING_ENABLED", "true")
            else:
                store.upsert_setting("UNKNOWN_PRESENCE_LOGGING_ENABLED", original)


def test_alerts_and_events_api_contract_routes() -> None:
    node_id = f"door_force_contract_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        event_post = client.post(
            "/api/sensors/event",
            json={
                "node_id": node_id,
                "event": "DOOR_FORCE",
                "location": "Door Entrance Area",
            },
        )
        assert event_post.status_code == 200

        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        alerts = client.get("/api/alerts?limit=20")
        assert alerts.status_code == 200
        alerts_payload = alerts.json()
        assert alerts_payload["ok"] is True
        assert isinstance(alerts_payload.get("alerts"), list)

        events = client.get("/api/events?limit=20")
        assert events.status_code == 200
        events_payload = events.json()
        assert events_payload["ok"] is True
        assert isinstance(events_payload.get("events"), list)

        if alerts_payload["alerts"]:
            alert_id = int(alerts_payload["alerts"][0]["id"])
            ack = client.post(f"/api/alerts/{alert_id}/acknowledge")
            assert ack.status_code == 200
            assert ack.json()["ok"] is True


def test_alerts_and_events_support_date_range_filters() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        day_one_ts = "2026-01-01T08:30:00+00:00"
        day_two_ts = "2026-01-02T08:30:00+00:00"

        event_day_one = store.create_event(
            event_type="system",
            event_code="FILTER_TEST_DAY_ONE",
            source_node="filter_test_node",
            location="Test Lab",
            severity="warning",
            title="Date filter test day one",
            description="first day event",
            ts=day_one_ts,
        )
        alert_day_one = store.create_alert(
            alert_type="SYSTEM",
            severity="warning",
            status="ACTIVE",
            requires_ack=True,
            title="Date filter alert day one",
            description="first day alert",
            source_node="filter_test_node",
            location="Test Lab",
            event_id=event_day_one,
            ts=day_one_ts,
        )

        event_day_two = store.create_event(
            event_type="system",
            event_code="FILTER_TEST_DAY_TWO",
            source_node="filter_test_node",
            location="Test Lab",
            severity="warning",
            title="Date filter test day two",
            description="second day event",
            ts=day_two_ts,
        )
        alert_day_two = store.create_alert(
            alert_type="SYSTEM",
            severity="warning",
            status="ACTIVE",
            requires_ack=True,
            title="Date filter alert day two",
            description="second day alert",
            source_node="filter_test_node",
            location="Test Lab",
            event_id=event_day_two,
            ts=day_two_ts,
        )

        alerts = client.get(
            "/api/alerts?limit=500&from_ts=2026-01-01T00:00:00%2B00:00&to_ts=2026-01-02T00:00:00%2B00:00"
        )
        assert alerts.status_code == 200
        alert_ids = {int(row["id"]) for row in alerts.json().get("alerts", [])}
        assert alert_day_one in alert_ids
        assert alert_day_two not in alert_ids

        events = client.get(
            "/api/events?limit=500&from_ts=2026-01-01T00:00:00%2B00:00&to_ts=2026-01-02T00:00:00%2B00:00"
        )
        assert events.status_code == 200
        event_ids = {int(row["id"]) for row in events.json().get("events", [])}
        assert event_day_one in event_ids
        assert event_day_two not in event_ids


def test_events_expose_direct_and_linked_snapshot_paths() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        direct_snapshot_path = f"snapshots/2099-12-31/direct_{uuid.uuid4().hex[:8]}.jpg"
        direct_event_id = store.create_event(
            event_type="intruder",
            event_code="SNAPSHOT_DIRECT_TEST",
            source_node="cam_door",
            location="Door Entrance Area",
            severity="critical",
            title="Direct snapshot test",
            description="event has its own snapshot path",
            details={"snapshot_path": direct_snapshot_path},
        )

        linked_snapshot_path = f"snapshots/2099-12-31/linked_{uuid.uuid4().hex[:8]}.jpg"
        linked_event_id = store.create_event(
            event_type="fire",
            event_code="SNAPSHOT_LINKED_TEST",
            source_node="cam_indoor",
            location="Living Room",
            severity="warning",
            title="Linked snapshot test",
            description="event uses its alert snapshot path",
        )
        linked_alert_id = store.create_alert(
            alert_type="FIRE",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Linked snapshot alert",
            description="alert stores the snapshot path",
            source_node="cam_indoor",
            location="Living Room",
            event_id=linked_event_id,
            snapshot_path=linked_snapshot_path,
        )

        events_response = client.get("/api/events?limit=500")
        assert events_response.status_code == 200
        events_by_id = {
            int(row["id"]): row for row in events_response.json().get("events", [])
        }
        assert events_by_id[direct_event_id]["snapshot_path"] == f"/{direct_snapshot_path}"
        assert events_by_id[linked_event_id]["snapshot_path"] == f"/{linked_snapshot_path}"
        assert events_by_id[linked_event_id]["related_alert_id"] == linked_alert_id

        live_response = client.get("/api/ui/events/live?limit=500")
        assert live_response.status_code == 200
        live_events_by_id = {
            int(row["id"]): row for row in live_response.json().get("events", [])
        }
        live_alerts_by_id = {
            int(row["id"]): row for row in live_response.json().get("alerts", [])
        }
        assert live_events_by_id[linked_event_id]["snapshot_path"] == f"/{linked_snapshot_path}"
        assert live_events_by_id[linked_event_id]["related_alert_id"] == linked_alert_id
        assert live_alerts_by_id[linked_alert_id]["event_id"] == linked_event_id
        assert live_alerts_by_id[linked_alert_id]["snapshot_path"] == f"/{linked_snapshot_path}"


def test_resolved_alert_review_clears_active_alert_state() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        alert_id = store.create_alert(
            alert_type="INTRUDER",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Resolve Review Test",
            description="terminal review status should clear active state",
            source_node="cam_door",
            location="Door Entrance Area",
        )
        active_before = {int(row["id"]) for row in store.list_active_alerts()}
        assert alert_id in active_before

        response = client.post(
            f"/api/alerts/{alert_id}/review",
            json={"review_status": "resolved", "review_note": "handled"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["alert"]["review_status"] == "resolved"
        assert payload["alert"]["acknowledged"] is True

        updated = store.get_alert(alert_id)
        assert updated is not None
        assert str(updated.get("status") or "") == "RESOLVED"
        active_after = {int(row["id"]) for row in store.list_active_alerts()}
        assert alert_id not in active_after

        live_response = client.get("/api/ui/events/live?limit=500")
        assert live_response.status_code == 200
        live_alert = next(
            row
            for row in live_response.json().get("alerts", [])
            if int(row["id"]) == alert_id
        )
        assert live_alert["acknowledged"] is True


def test_face_profile_update_contract() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        seed_name = f"Face Update {uuid.uuid4().hex[:6]}"
        create = client.post(
            "/api/faces",
            json={"name": seed_name, "note": "Owner"},
        )
        assert create.status_code == 200
        created_face = create.json()["face"]
        db_id = int(created_face["db_id"])

        updated_name = f"{seed_name} Renamed"
        patch = client.patch(
            f"/api/faces/{db_id}",
            json={"name": updated_name, "note": "Family"},
        )
        assert patch.status_code == 200
        payload = patch.json()
        assert payload["ok"] is True
        assert payload["face"]["label"] == updated_name
        assert payload["face"]["role"] == "Family"


def test_face_profile_delete_contract() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        seed_name = f"Face Delete {uuid.uuid4().hex[:6]}"
        create = client.post(
            "/api/faces",
            json={"name": seed_name, "note": "Owner"},
        )
        assert create.status_code == 200
        db_id = int(create.json()["face"]["db_id"])

        delete = client.delete(f"/api/faces/{db_id}")
        assert delete.status_code == 200
        assert delete.json()["ok"] is True

        faces = client.get("/api/faces")
        assert faces.status_code == 200
        rows = faces.json().get("faces", [])
        assert all(int(row.get("db_id") or 0) != db_id for row in rows)


def test_alert_snapshot_delete_clears_file_and_path() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        settings = app.state.settings
        day = "2099-12-31"
        snap_dir = settings.snapshot_root / day
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_file = snap_dir / f"pytest_snapshot_{uuid.uuid4().hex[:8]}.jpg"
        snap_file.write_bytes(b"pytest-snapshot")

        snapshot_path = f"snapshots/{day}/{snap_file.name}"
        alert_id = store.create_alert(
            alert_type="INTRUDER",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Snapshot Delete Test",
            description="delete endpoint contract",
            source_node="cam_door",
            location="Door Entrance Area",
            snapshot_path=snapshot_path,
        )

        delete_response = client.post(f"/api/alerts/{alert_id}/snapshot/delete")
        assert delete_response.status_code == 200
        payload = delete_response.json()
        assert payload["ok"] is True
        assert payload["alert_id"] == alert_id

        updated = store.get_alert(alert_id)
        assert updated is not None
        assert str(updated.get("snapshot_path") or "") == ""
        assert not snap_file.exists()


def test_snapshot_feedback_confirm_marks_alert_confirmed() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        alert_id = store.create_alert(
            alert_type="INTRUDER",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Snapshot Confirm Test",
            description="confirm endpoint contract",
            source_node="cam_door",
            location="Door Entrance Area",
        )

        response = client.post(
            f"/api/alerts/{alert_id}/snapshot/feedback",
            json={"verdict": "confirmed"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["verdict"] == "confirmed"

        updated = store.get_alert(alert_id)
        assert updated is not None
        assert str(updated.get("review_status") or "") == "confirmed"


def test_snapshot_feedback_intruder_false_positive_imports_and_retrains() -> None:
    class FakeFaceService:
        def __init__(self) -> None:
            self.captured: list[tuple[str, str]] = []

        def capture_sample(self, person_name: str, image_data_url: str, source: str) -> dict:
            self.captured.append((person_name, source))
            assert image_data_url.startswith("data:image/jpeg;base64,")
            return {"ok": True, "name": person_name, "count": 1}

        def train(self) -> tuple[bool, str]:
            return True, "trained"

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        settings = app.state.settings
        day = "2099-12-30"
        snap_dir = settings.snapshot_root / day
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_file = snap_dir / f"pytest_intruder_{uuid.uuid4().hex[:8]}.jpg"
        snap_file.write_bytes(b"pytest-intruder-snapshot")

        face_name = f"Feedback Face {uuid.uuid4().hex[:6]}"
        store.create_face(face_name, "Owner")
        alert_id = store.create_alert(
            alert_type="INTRUDER",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Intruder Feedback Test",
            description="false positive endpoint contract",
            source_node="cam_door",
            location="Door Entrance Area",
            snapshot_path=f"snapshots/{day}/{snap_file.name}",
        )

        original_face_service = app.state.face_service
        fake_face_service = FakeFaceService()
        app.state.face_service = fake_face_service
        try:
            response = client.post(
                f"/api/alerts/{alert_id}/snapshot/feedback",
                json={"verdict": "false_positive", "face_name": face_name},
            )
        finally:
            app.state.face_service = original_face_service

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["train_ok"] is None
        assert (
            payload["train_message"]
            == "False-positive sample saved. Run group face retraining when ready."
        )
        assert fake_face_service.captured == [
            (face_name, f"snapshot_false_positive:alert_{alert_id}")
        ]

        updated = store.get_alert(alert_id)
        assert updated is not None
        assert str(updated.get("review_status") or "") == "false_positive"


def test_snapshot_feedback_fire_false_positive_copies_hard_negative() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        settings = app.state.settings
        day = "2099-12-29"
        snap_dir = settings.snapshot_root / day
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_file = snap_dir / f"pytest_fire_{uuid.uuid4().hex[:8]}.jpg"
        snap_file.write_bytes(b"pytest-fire-snapshot")
        alert_id = store.create_alert(
            alert_type="FIRE",
            severity="critical",
            status="ACTIVE",
            requires_ack=True,
            title="Fire Feedback Test",
            description="false positive endpoint contract",
            source_node="cam_indoor",
            location="Living Room",
            snapshot_path=f"snapshots/{day}/{snap_file.name}",
        )

        response = client.post(
            f"/api/alerts/{alert_id}/snapshot/feedback",
            json={"verdict": "false_positive"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        copied_path = str(payload["copied_path"])
        assert copied_path.startswith("training/fire/negative_false_alarms/")
        assert (settings.storage_root / copied_path).read_bytes() == b"pytest-fire-snapshot"

        updated = store.get_alert(alert_id)
        assert updated is not None
        assert str(updated.get("review_status") or "") == "false_positive"


def test_mobile_status_nodes_sensors_and_assistant_routes() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        status = client.get("/api/status")
        assert status.status_code == 200
        status_payload = status.json()
        assert status_payload["ok"] is True
        assert status_payload["backend"] == "online"

        health = client.get("/api/health")
        assert health.status_code == 200
        health_payload = health.json()
        assert health_payload["ok"] is True
        assert health_payload["backend"] == "online"

        nodes = client.get("/api/nodes")
        assert nodes.status_code == 200
        nodes_payload = nodes.json()
        assert nodes_payload["ok"] is True
        assert isinstance(nodes_payload.get("nodes"), list)
        assert [row.get("id") for row in nodes_payload["nodes"]] == [
            "smoke_node1",
            "smoke_node2",
            "door_force",
            "cam_indoor",
            "cam_door",
        ]

        sensors = client.get("/api/sensors")
        assert sensors.status_code == 200
        sensors_payload = sensors.json()
        assert sensors_payload["ok"] is True
        assert isinstance(sensors_payload.get("sensors"), list)
        assert [row.get("id") for row in sensors_payload["sensors"]] == [
            "smoke_node1",
            "smoke_node2",
            "door_force",
        ]

        assistant = client.post(
            "/api/assistant/query",
            json={"question_id": "current_system_status"},
        )
        assert assistant.status_code == 200
        assistant_payload = assistant.json()
        assert assistant_payload["ok"] is True
        assert assistant_payload["question_id"] == "current_system_status"
        answer = assistant_payload.get("answer")
        assert isinstance(answer, str)
        assert "Suggested action:" in answer
        assert len(answer) > 120


def test_daily_summary_report_pdf_contract() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        response = client.get("/api/reports/daily-summary?date=2026-05-11")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
        assert (
            'filename="intruflare_daily_report_2026-05-11.pdf"'
            in response.headers.get("content-disposition", "")
        )


def test_ui_live_events_route_returns_alerts_and_events() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert login.status_code == 200

        response = client.get("/api/ui/events/live?limit=500")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload.get("alerts"), list)
        assert isinstance(payload.get("events"), list)
