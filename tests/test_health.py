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
    assert set(payload["providers"]) == {"gemini", "groq", "minimax"}
    assert all(
        isinstance(provider["configured"], bool) for provider in payload["providers"].values()
    )
    assert "api_key" not in response.text.lower()


def test_dataset_cases_endpoint_returns_rich_case_payload() -> None:
    response = client.get("/api/datasets/benchmark_dataset.csv/cases")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_file"] == "benchmark_dataset.csv"
    assert payload["total_cases"] == 63
    assert len(payload["cases"]) == 63
    first_case = payload["cases"][0]
    assert "test_case_id" in first_case
    assert "input_prompt" in first_case
    assert "difficulty" in first_case


def test_custom_models_crud_flow() -> None:
    # 1. Create a custom model
    create_resp = client.post(
        "/api/custom-models",
        json={
            "name": "Local Ollama Test",
            "model_id": "llama3.2",
            "base_url": "http://localhost:11434/v1",
            "description": "Local test model",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    model_id = created["id"]
    assert created["name"] == "Local Ollama Test"
    assert created["has_api_key"] is False

    # 2. List custom models
    list_resp = client.get("/api/custom-models")
    assert list_resp.status_code == 200
    models = list_resp.json()
    assert any(m["id"] == model_id for m in models)

    # 3. Delete custom model
    del_resp = client.delete(f"/api/custom-models/{model_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"
