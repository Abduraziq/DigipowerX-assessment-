from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.models.schemas import ChatCompletionRequest, FailureConfig
from app.observability.logging import setup_logging
from app.observability.metrics import (
    FAILED_REQUESTS,
    GENERATED_TOKENS,
    LATENCY_SECONDS,
    ROUTING_FAILURES,
    SUCCESSFUL_REQUESTS,
    TIMEOUTS,
    TOTAL_REQUESTS,
)
from app.workers.pool import CapacityError, NoHealthyWorkerError, WorkerPool

router = APIRouter()
logger = setup_logging()
pool = WorkerPool()


def _count_prompt_tokens(text: str) -> int:
    return max(1, len(text.split()) // 2)


def _record_failed_usage(
    request_id: str,
    customer: str,
    model: str,
    input_tokens: int,
    start: float,
    status: str,
) -> None:
    from app.metering.repository import UsageMeteringRepository

    UsageMeteringRepository(settings.sqlite_path).record_usage(
        request_id=request_id,
        customer=customer,
        model=model,
        input_tokens=input_tokens,
        output_tokens=0,
        total_tokens=input_tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
        worker_id=None,
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
async def ready() -> dict[str, Any]:
    healthy = sum(1 for worker in pool.workers if worker.healthy)
    return {"ready": healthy > 0, "healthy_workers": healthy, "total_workers": len(pool.workers)}


@router.get("/workers")
async def workers() -> dict[str, Any]:
    return {"workers": pool.list_workers()}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/usage")
async def usage(limit: int = 20) -> dict[str, Any]:
    from app.metering.repository import UsageMeteringRepository

    repo = UsageMeteringRepository(settings.sqlite_path)
    records = repo.list_recent(limit=limit)
    return {"records": records}


@router.post("/admin/workers/{worker_id}/health")
async def set_worker_health(worker_id: str, payload: FailureConfig) -> dict[str, Any]:
    if payload.healthy is None:
        raise HTTPException(status_code=400, detail="healthy must be set")
    pool.set_worker_health(worker_id, payload.healthy)
    return {"worker_id": worker_id, "healthy": payload.healthy}


@router.post("/admin/workers/{worker_id}/mode")
async def set_worker_mode(worker_id: str, payload: FailureConfig) -> dict[str, Any]:
    if payload.mode is None:
        raise HTTPException(status_code=400, detail="mode must be set")
    pool.set_worker_failure_mode(worker_id, payload.mode)
    return {"worker_id": worker_id, "mode": payload.mode}


@router.post("/admin/reset")
async def reset_pool() -> dict[str, Any]:
    pool.reset_default_states()
    return {"status": "ok", "workers": pool.list_workers()}


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, payload: ChatCompletionRequest) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    customer = request.headers.get("X-Customer", settings.default_customer)
    model = payload.model.lower()
    if model not in {"qwen", "llama"}:
        raise HTTPException(status_code=400, detail="unsupported model; only qwen and llama are served")

    start = time.perf_counter()
    input_tokens = _count_prompt_tokens(" ".join(message.content for message in payload.messages))
    TOTAL_REQUESTS.labels(model=model).inc()
    try:
        result = await asyncio.wait_for(
            pool.process_request(
                model=model,
                messages=[message.model_dump() for message in payload.messages],
                max_tokens=payload.max_tokens,
                request_id=request_id,
                customer=customer,
            ),
            timeout=settings.request_timeout_seconds,
        )
        output_tokens = int(result["output_tokens"])
        total_tokens = input_tokens + output_tokens
        latency_ms = int((time.perf_counter() - start) * 1000)

        response_body = {
            "request_id": request_id,
            "model": model,
            "worker_id": result["worker_id"],
            "response": result["response"],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
        }

        SUCCESSFUL_REQUESTS.labels(model=model).inc()
        GENERATED_TOKENS.labels(model=model).inc(output_tokens)
        LATENCY_SECONDS.labels(model=model).observe(latency_ms / 1000.0)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "customer": customer,
                "model": model,
                "worker_id": result["worker_id"],
                "latency_ms": latency_ms,
                "status": "success",
            },
        )

        from app.metering.repository import UsageMeteringRepository

        usage_repo = UsageMeteringRepository(settings.sqlite_path)
        usage_repo.record_usage(
            request_id=request_id,
            customer=customer,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            worker_id=result["worker_id"],
            status="success",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        response = JSONResponse(content=response_body)
        response.headers["X-Request-ID"] = request_id
        return response
    except asyncio.TimeoutError:
        elapsed_seconds = time.perf_counter() - start
        LATENCY_SECONDS.labels(model=model).observe(elapsed_seconds)
        TIMEOUTS.labels(model=model).inc()
        FAILED_REQUESTS.labels(model=model).inc()
        _record_failed_usage(request_id, customer, model, input_tokens, start, "timeout")
        logger.warning("request_timed_out", extra={"request_id": request_id, "customer": customer, "model": model, "status": "timeout"})
        raise HTTPException(status_code=504, detail="inference timed out", headers={"X-Request-ID": request_id})
    except CapacityError as exc:
        ROUTING_FAILURES.labels(model=model).inc()
        FAILED_REQUESTS.labels(model=model).inc()
        LATENCY_SECONDS.labels(model=model).observe(time.perf_counter() - start)
        _record_failed_usage(request_id, customer, model, input_tokens, start, "capacity")
        logger.warning("capacity_limit_reached", extra={"request_id": request_id, "customer": customer, "model": model, "status": "capacity"})
        raise HTTPException(status_code=429, detail=str(exc), headers={"X-Request-ID": request_id}) from exc
    except NoHealthyWorkerError as exc:
        ROUTING_FAILURES.labels(model=model).inc()
        FAILED_REQUESTS.labels(model=model).inc()
        LATENCY_SECONDS.labels(model=model).observe(time.perf_counter() - start)
        _record_failed_usage(request_id, customer, model, input_tokens, start, "unavailable")
        logger.error("no_healthy_worker", extra={"request_id": request_id, "customer": customer, "model": model, "status": "failed"})
        raise HTTPException(status_code=503, detail=str(exc), headers={"X-Request-ID": request_id}) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        FAILED_REQUESTS.labels(model=model).inc()
        LATENCY_SECONDS.labels(model=model).observe(time.perf_counter() - start)
        _record_failed_usage(request_id, customer, model, input_tokens, start, "error")
        logger.exception("internal_failure", extra={"request_id": request_id, "customer": customer, "model": model, "status": "failed"})
        raise HTTPException(
            status_code=500,
            detail=f"internal inference failure: {exc}",
            headers={"X-Request-ID": request_id},
        ) from exc
