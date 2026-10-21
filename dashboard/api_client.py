"""Small synchronous client for the benchmark FastAPI service."""

from __future__ import annotations

import os
from typing import Any

import httpx


class DashboardAPIError(RuntimeError):
    """User-facing error returned by the backend or caused by a connection failure."""


class APIClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 8.0,
        api_key: str | None = None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("backend URL must not be blank")
        resolved_api_key = api_key if api_key is not None else os.getenv("DASHBOARD_API_KEY", "")
        headers = {"X-API-Key": resolved_api_key} if resolved_api_key else None
        self._client = httpx.Client(
            base_url=normalized_url,
            timeout=timeout,
            transport=transport,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> APIClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def overview(self) -> dict[str, Any]:
        return self._request("GET", "/api/overview")

    def provider_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/config/providers")

    def list_datasets(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/datasets")

    def list_runs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", "/api/runs", params={"limit": limit})

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/runs/{run_id}")

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Runs are sequential and can exceed the normal short UI request timeout.
        return self._request("POST", "/api/runs", json=payload, timeout=None)

    def list_analyses(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", "/api/analyses", params={"limit": limit})

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/analyses/{analysis_id}")

    def compare_runs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/analyses/compare", json=payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DashboardAPIError(
                "Could not reach the backend. Check that FastAPI is running and the backend URL is correct."
            ) from exc
        if response.is_error:
            try:
                payload = response.json()
                message = payload.get("detail", payload)
            except ValueError:
                message = response.text[:500] or response.reason_phrase
            raise DashboardAPIError(f"Backend returned HTTP {response.status_code}: {message}")
        try:
            return response.json()
        except ValueError as exc:
            raise DashboardAPIError("Backend returned a response that was not valid JSON.") from exc
