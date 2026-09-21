from __future__ import annotations

from app.workers.worker import WorkerRuntime


def select_worker(request_model: str, workers: list[WorkerRuntime]) -> WorkerRuntime | None:
    """Choose the least-loaded healthy worker for the requested model.

    The route selection is intentionally simple: it filters by model and health, then
    ranks candidates by queue depth, active requests, and utilization before breaking
    ties by worker_id. This is easy to explain in an interview and works well for
    heterogeneous local inference workloads without introducing scheduler complexity.
    """
    eligible = [
        worker
        for worker in workers
        if worker.model == request_model and worker.healthy and worker.active_requests < worker.max_concurrency
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda worker: (
            worker.queue_depth + worker.active_requests,
            worker.utilization,
            worker.worker_id,
        ),
    )[0]
