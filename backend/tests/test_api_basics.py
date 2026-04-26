import uuid

from fastapi.testclient import TestClient

from backend.app.db import store
from backend.app.main import app


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
        assert disable.json()["enabled"] is False


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
        assert "mdns_base_url" in bootstrap.json()

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

        mdns = client.get("/api/integrations/mdns/status")
        assert mdns.status_code == 200
        mdns_payload = mdns.json()
        assert "enabled" in mdns_payload
        assert "published" in mdns_payload

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

        sensors = client.get("/api/sensors")
        assert sensors.status_code == 200
        sensors_payload = sensors.json()
        assert sensors_payload["ok"] is True
        assert isinstance(sensors_payload.get("sensors"), list)

        assistant = client.post(
            "/api/assistant/query",
            json={"question_id": "current_system_status"},
        )
        assert assistant.status_code == 200
        assistant_payload = assistant.json()
        assert assistant_payload["ok"] is True
        assert assistant_payload["question_id"] == "current_system_status"
        assert isinstance(assistant_payload.get("answer"), str)
