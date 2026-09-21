from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from app.observability.metrics import (
    ACTIVE_REQUESTS,
    WORKER_HEALTH,
    WORKER_QUEUE_DEPTH,
    WORKER_UTILIZATION,
)


class WorkerQueueFullError(RuntimeError):
    pass


class WorkerNotHealthyError(RuntimeError):
    pass


class WorkerInferenceError(RuntimeError):
    pass


@dataclass
class WorkerRuntime:
    """A logical worker representing a model served by a local inference backend.

    GPU utilization is simulated in this assessment. It is intentionally labeled as
    simulated so the local platform remains realistic without requiring NVIDIA GPUs.
    """

    worker_id: str
    model: str
    healthy: bool = True
    max_concurrency: int = 2
    queue_limit: int = 3
    base_latency_ms: int = 120
    failure_mode: Literal["healthy", "slow", "error"] = "healthy"
    active_requests: int = 0
    queue_depth: int = 0
    utilization: float = 0.0
    requests_completed: int = 0
    requests_failed: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def snapshot(self) -> dict[str, object]:
        return {
            "worker_id": self.worker_id,
            "model": self.model,
            "healthy": self.healthy,
            "active_requests": self.active_requests,
            "queue_depth": self.queue_depth,
            "utilization": round(self.utilization, 3),
            "requests_completed": self.requests_completed,
            "requests_failed": self.requests_failed,
        }

    async def execute(self, prompt: str, max_tokens: int, request_id: str) -> dict[str, object]:
        async with self._lock:
            if not self.healthy:
                self.requests_failed += 1
                WORKER_HEALTH.labels(worker_id=self.worker_id, model=self.model).set(0)
                raise WorkerNotHealthyError(f"worker {self.worker_id} is unhealthy")
            if self.active_requests >= self.max_concurrency:
                self.requests_failed += 1
                WORKER_HEALTH.labels(worker_id=self.worker_id, model=self.model).set(1)
                raise WorkerQueueFullError(f"worker {self.worker_id} is at capacity")
            self.active_requests += 1
            self.queue_depth = max(self.queue_depth, self.active_requests)
            self.utilization = min(1.0, self.active_requests / self.max_concurrency)
            ACTIVE_REQUESTS.labels(worker_id=self.worker_id, model=self.model).set(self.active_requests)
            WORKER_QUEUE_DEPTH.labels(worker_id=self.worker_id, model=self.model).set(self.queue_depth)
            WORKER_UTILIZATION.labels(worker_id=self.worker_id, model=self.model).set(self.utilization)

        try:
            if self.failure_mode == "error":
                self.healthy = False
                WORKER_HEALTH.labels(worker_id=self.worker_id, model=self.model).set(0)
                raise WorkerInferenceError(f"simulated inference error on {self.worker_id}")

            sleep_seconds = self._simulated_latency_seconds(max_tokens)
            if self.failure_mode == "slow":
                sleep_seconds *= 4
            await asyncio.sleep(sleep_seconds)

            text = self._build_response(prompt, max_tokens)
            output_tokens = min(max_tokens, max(5, len(text.split()) // 2))
            return {
                "request_id": request_id,
                "worker_id": self.worker_id,
                "model": self.model,
                "response": text,
                "output_tokens": output_tokens,
                "latency_ms": int(sleep_seconds * 1000),
            }
        finally:
            async with self._lock:
                self.active_requests -= 1
                self.utilization = max(0.0, min(1.0, self.active_requests / self.max_concurrency))
                ACTIVE_REQUESTS.labels(worker_id=self.worker_id, model=self.model).set(self.active_requests)
                WORKER_UTILIZATION.labels(worker_id=self.worker_id, model=self.model).set(self.utilization)
                if self.active_requests == 0:
                    self.queue_depth = 0
                    WORKER_QUEUE_DEPTH.labels(worker_id=self.worker_id, model=self.model).set(0)

    def _simulated_latency_seconds(self, max_tokens: int) -> float:
        base = self.base_latency_ms / 1000.0
        token_factor = max_tokens / 180.0
        return max(0.12, base * (0.75 + token_factor))

    def _build_response(self, prompt: str, max_tokens: int) -> str:
        suffix = " This is a simulated inference response for local benchmarking and failure testing."
        if self.model == "qwen":
            response = (
                f"Qwen says: {prompt[:110]} is being handled by {self.worker_id}. "
                f"The platform is balancing throughput, reliability, and queue pressure."
            )
        else:
            response = (
                f"Llama says: {prompt[:110]} is being processed on {self.worker_id}. "
                f"This simulated workload is tuned for local testing without real GPUs."
            )
        if max_tokens > 30:
            response += suffix
        return response

    def mark_healthy(self, healthy: bool) -> None:
        self.healthy = healthy
        WORKER_HEALTH.labels(worker_id=self.worker_id, model=self.model).set(1 if healthy else 0)

    def set_failure_mode(self, mode: Literal["healthy", "slow", "error"]) -> None:
        self.failure_mode = mode
        if mode == "healthy":
            self.healthy = True
            WORKER_HEALTH.labels(worker_id=self.worker_id, model=self.model).set(1)

    async def complete_success(self) -> None:
        async with self._lock:
            self.requests_completed += 1

    async def complete_failure(self) -> None:
        async with self._lock:
            self.requests_failed += 1
