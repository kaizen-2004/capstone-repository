from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 200
        payload = response.json()
        assert payload['ok'] is True


def test_login_and_me() -> None:
    with TestClient(app) as client:
        login = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        assert login.status_code == 200
        me = client.get('/api/auth/me')
        assert me.status_code == 200
        assert me.json()['authenticated'] is True
