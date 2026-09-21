from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.observability.metrics import RETRIES
from app.routing.router import select_worker
from app.workers.worker import WorkerInferenceError, WorkerNotHealthyError, WorkerQueueFullError, WorkerRuntime


class NoHealthyWorkerError(RuntimeError):
    pass


class CapacityError(RuntimeError):
    pass


class WorkerPool:
    def __init__(self) -> None:
        self.workers = [
            WorkerRuntime(worker_id="worker-1", model="qwen", max_concurrency=2, queue_limit=settings.queue_limit, base_latency_ms=130),
            WorkerRuntime(worker_id="worker-2", model="qwen", max_concurrency=2, queue_limit=settings.queue_limit, base_latency_ms=140),
            WorkerRuntime(worker_id="worker-3", model="llama", max_concurrency=1, queue_limit=settings.queue_limit, base_latency_ms=180),
        ]

    def list_workers(self) -> list[dict[str, Any]]:
        return [worker.snapshot() for worker in self.workers]

    def set_worker_health(self, worker_id: str, healthy: bool) -> None:
        worker = self._find(worker_id)
        worker.mark_healthy(healthy)

    def set_worker_failure_mode(self, worker_id: str, mode: str) -> None:
        worker = self._find(worker_id)
        if mode not in {"healthy", "slow", "error"}:
            raise ValueError("mode must be one of healthy, slow, error")
        worker.set_failure_mode(mode)

    def reset_default_states(self) -> None:
        for worker in self.workers:
            worker.mark_healthy(True)
            worker.set_failure_mode("healthy")
            worker.active_requests = 0
            worker.queue_depth = 0
            worker.utilization = 0.0

    def _find(self, worker_id: str) -> WorkerRuntime:
        for worker in self.workers:
            if worker.worker_id == worker_id:
                return worker
        raise KeyError(f"worker {worker_id} not found")

    async def process_request(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        request_id: str,
        customer: str,
    ) -> dict[str, Any]:
        prompt = "\n".join(f"{message['role']}: {message['content']}" for message in messages)
        last_error: Exception | None = None

        for attempt in range(1, settings.max_retries + 1):
            worker = select_worker(model, self.workers)
            if worker is None:
                if any(candidate.model == model and candidate.healthy for candidate in self.workers):
                    RETRIES.labels(model=model).inc()
                    raise CapacityError(f"capacity limit reached for model '{model}'")
                raise NoHealthyWorkerError(f"no healthy worker available to serve model '{model}'")
            try:
                result = await worker.execute(prompt, max_tokens, request_id)
                await worker.complete_success()
                return {
                    "request_id": request_id,
                    "customer": customer,
                    "model": model,
                    "worker_id": worker.worker_id,
                    "response": result["response"],
                    "output_tokens": int(result["output_tokens"]),
                    "latency_ms": int(result["latency_ms"]),
                }
            except (WorkerQueueFullError, WorkerInferenceError, WorkerNotHealthyError) as exc:
                last_error = exc
                RETRIES.labels(model=model).inc()
                if attempt < settings.max_retries:
                    await asyncio.sleep(0.05)
                    continue
                raise CapacityError(f"capacity limit reached for model '{model}'") from exc

        if last_error is not None:
            raise NoHealthyWorkerError(f"worker failure for model '{model}'") from last_error
        raise NoHealthyWorkerError(f"no healthy worker available to serve model '{model}'")
