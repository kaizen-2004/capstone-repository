import uuid

from fastapi.testclient import TestClient

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
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["authenticated"] is True


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
            json={"push_enabled": False, "telegram_fallback_enabled": True},
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
        assert int(second_payload["cooldown_seconds"]) == 20
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
        assert telegram_status.status_code == 200
        assert telegram_status.json()["ok"] is True
        assert "configured" in telegram_status.json()

        send_access_link = client.post("/api/integrations/telegram/send-access-link")
        assert send_access_link.status_code == 200
        send_payload = send_access_link.json()
        assert send_payload["ok"] is True
        assert "sent" in send_payload
        assert "status" in send_payload


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
            json={"key": "TELEGRAM_BOT_TOKEN", "value": "token_for_test_only"},
        )
        assert update_secret.status_code == 200
        secret_payload = update_secret.json()
        assert secret_payload["ok"] is True
        assert secret_payload["key"] == "TELEGRAM_BOT_TOKEN"
        assert secret_payload["secret"] is True
        assert secret_payload["configured"] is True
        assert secret_payload["value"] == ""

        settings_live = client.get("/api/ui/settings/live")
        assert settings_live.status_code == 200
        runtime_settings = settings_live.json()["runtime_settings"]

        threshold_row = next(
            row for row in runtime_settings if row.get("key") == "FACE_COSINE_THRESHOLD"
        )
        assert threshold_row["value"] == "0.61"

        secret_row = next(
            row for row in runtime_settings if row.get("key") == "TELEGRAM_BOT_TOKEN"
        )
        assert secret_row["secret"] is True
        assert secret_row["configured"] is True
        assert secret_row["value"] == ""
