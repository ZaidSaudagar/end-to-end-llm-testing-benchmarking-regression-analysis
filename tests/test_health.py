from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_ready_endpoint() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert "database_url" not in payload


def test_provider_status_reports_key_presence_without_exposing_keys() -> None:
    response = client.get("/api/config/providers")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["providers"]) == {"gemini", "openrouter"}
    assert all(
        isinstance(provider["configured"], bool) for provider in payload["providers"].values()
    )
    assert "api_key" not in response.text.lower()
