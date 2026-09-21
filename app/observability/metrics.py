from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

TOTAL_REQUESTS = Counter(
    "inference_total_requests",
    "Total requests received by the inference service",
    labelnames=("model",),
)
SUCCESSFUL_REQUESTS = Counter(
    "inference_successful_requests",
    "Successful inference requests",
    labelnames=("model",),
)
FAILED_REQUESTS = Counter(
    "inference_failed_requests",
    "Failed inference requests",
    labelnames=("model",),
)
LATENCY_SECONDS = Histogram(
    "inference_request_latency_seconds",
    "End-to-end request latency",
    labelnames=("model",),
)
ACTIVE_REQUESTS = Gauge(
    "inference_active_requests",
    "Active requests in flight",
    labelnames=("worker_id", "model"),
)
WORKER_HEALTH = Gauge(
    "worker_health",
    "Worker health status; 1 is healthy and 0 is unhealthy",
    labelnames=("worker_id", "model"),
)
WORKER_QUEUE_DEPTH = Gauge(
    "worker_queue_depth",
    "Current queue depth for a worker",
    labelnames=("worker_id", "model"),
)
WORKER_UTILIZATION = Gauge(
    "worker_utilization",
    "Simulated GPU utilization; clearly marked as simulated",
    labelnames=("worker_id", "model"),
)
GENERATED_TOKENS = Counter(
    "inference_generated_tokens_total",
    "Generated output tokens recorded for successful requests by model",
    labelnames=("model",),
)
ROUTING_FAILURES = Counter(
    "inference_routing_failures_total",
    "Count of routing failures due to no healthy worker or queue pressure",
    labelnames=("model",),
)
TIMEOUTS = Counter(
    "inference_timeouts_total",
    "Timed-out requests",
    labelnames=("model",),
)
RETRIES = Counter(
    "inference_retries_total",
    "Retry attempts on failed worker selection or execution",
    labelnames=("model",),
)
