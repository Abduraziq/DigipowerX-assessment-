from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from app import api as api_module
from app.config import settings as app_settings
from app.main import create_app

app = create_app()


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_workers_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/workers")
    assert response.status_code == 200
    assert len(response.json()["workers"]) >= 3


def test_successful_qwen_routing() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "qwen", "messages": [{"role": "user", "content": "Explain Kubernetes in simple terms."}], "max_tokens": 50},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "qwen"
    assert payload["request_id"]
    assert response.headers.get("X-Request-ID") == payload["request_id"]


def test_successful_llama_routing() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "llama", "messages": [{"role": "user", "content": "Explain microservices."}], "max_tokens": 60},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "llama"
    assert payload["worker_id"] == "worker-3"


def test_model_filtering_errors() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gemini", "messages": [{"role": "user", "content": "bad model"}], "max_tokens": 20},
        )
    assert response.status_code == 400


def test_unhealthy_worker_exclusion() -> None:
    with TestClient(app) as client:
        client.post("/admin/workers/worker-1/health", json={"healthy": False})
        response = client.post(
            "/v1/chat/completions",
            json={"model": "qwen", "messages": [{"role": "user", "content": "Use healthy worker."}], "max_tokens": 40},
        )
        assert response.status_code == 200
        assert response.json()["worker_id"] == "worker-2"
        client.post("/admin/reset")


def test_all_qwen_workers_unhealthy_returns_503() -> None:
    with TestClient(app) as client:
        client.post("/admin/workers/worker-1/health", json={"healthy": False})
        client.post("/admin/workers/worker-2/health", json={"healthy": False})
        response = client.post(
            "/v1/chat/completions",
            json={"model": "qwen", "messages": [{"role": "user", "content": "No qwen workers left"}], "max_tokens": 40},
        )
        assert response.status_code == 503
        client.post("/admin/reset")


def test_queue_capacity_backpressure() -> None:
    from app.api import routes as route_module

    with TestClient(app) as client:
        worker_1 = route_module.pool.workers[0]
        worker_2 = route_module.pool.workers[1]
        worker_1.active_requests = 2
        worker_2.active_requests = 2
        response = client.post(
            "/v1/chat/completions",
            json={"model": "qwen", "messages": [{"role": "user", "content": "Queue pressure test."}], "max_tokens": 50},
        )
        assert response.status_code == 429
        worker_1.active_requests = 0
        worker_2.active_requests = 0
        client.post("/admin/reset")


def test_timeout_behavior() -> None:
    from app.api import routes as route_module

    original_settings = route_module.settings
    route_module.settings = replace(original_settings, request_timeout_seconds=0.05)
    client = None
    try:
        with TestClient(app) as client:
            client.post("/admin/workers/worker-3/mode", json={"mode": "slow"})
            response = client.post(
                "/v1/chat/completions",
                json={"model": "llama", "messages": [{"role": "user", "content": "Timeout path check."}], "max_tokens": 200},
            )
        assert response.status_code == 504
    finally:
        route_module.settings = original_settings
        if client is not None:
            client.post("/admin/reset")


def test_usage_records_written() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "qwen", "messages": [{"role": "user", "content": "Write usage meter."}], "max_tokens": 50},
        )
        usage = client.get("/usage").json()
    assert response.status_code == 200
    assert usage["records"]


def test_metrics_endpoint_available() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "inference_total_requests" in body
    assert "worker_health" in body


def test_request_id_is_propagated() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "llama", "messages": [{"role": "user", "content": "Check request ID."}], "max_tokens": 25},
            headers={"X-Request-ID": "req-123"},
        )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.json()["request_id"] == "req-123"


def test_worker_failure_mode_error() -> None:
    with TestClient(app) as client:
        client.post("/admin/workers/worker-3/mode", json={"mode": "error"})
        response = client.post(
            "/v1/chat/completions",
            json={"model": "llama", "messages": [{"role": "user", "content": "Trigger worker error."}], "max_tokens": 30},
        )
        assert response.status_code == 503
        client.post("/admin/reset")
