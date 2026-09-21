# Screen recording script (under 5 minutes)

## 0:00 to 0:30 — Problem and architecture

"This is a local AI inference platform designed for the DigiPower X / NeoCloudz assessment. The flow is client to API to router to worker pool to metrics and usage metering. I kept the design intentionally simple and explainable, because in an interview the engineering logic matters more than fancy abstractions."

## 0:30 to 1:15 — Repository and core implementation

"The repository is organized around FastAPI, a simple router, and a worker pool. There are qwen workers and a llama worker. The router chooses the least-loaded healthy worker for the model, then the worker simulates inference and emits latency and token data."

## 1:15 to 2:00 — Successful inference and worker routing

"I’ll run a qwen request, then a llama request, and show the response structure. The response includes the request ID, worker ID, token usage, and latency. The router is explicit and easy to point to in the code."

## 2:00 to 2:45 — Failure simulation

"Now I’ll mark a qwen worker unhealthy and show that traffic automatically moves to the remaining healthy qwen worker. Then I’ll mark both qwen workers unhealthy and show a clean 503 response instead of a system-wide outage."

## 2:45 to 3:30 — Prometheus metrics and usage metering

"The service exposes Prometheus metrics on /metrics, including request counts, worker health, queue depth, and generated tokens. I also record usage in SQLite with request_id, model, latency, tokens, and worker_id. This is a good local model for a production metering pipeline."

## 3:30 to 4:15 — Load test and measured findings

"I run a concurrency-8 test to generate actual benchmark data. The results show throughput, p50, p95, p99, and failure counts. It is important to distinguish measured numbers from production estimates."

## 4:15 to 4:50 — Production evolution and tradeoffs

"For real deployment, the same pattern extends to a GPU-backed serving runtime with Kubernetes, warm pools, queueing, multi-cluster routing, GPUs, telemetry, and durable metering. The local simulation is intentionally simple and honest about its boundaries."
