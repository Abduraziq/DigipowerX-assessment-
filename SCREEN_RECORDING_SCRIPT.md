# Screen recording script

Target length: 4-5 minutes. Keep the terminal and editor visible, and run the commands exactly as shown.

## 0:00-0:30 — Problem and architecture

**Show:** `README.md`, then the repository tree.

**Say:**

> "This is a local inference platform for the DigiPower X MLOps assessment. A request enters through FastAPI, the router selects a healthy worker for the requested model, and the worker returns a simulated inference response. The service also exposes Prometheus metrics, structured logs, and SQLite usage metering. I kept the implementation deliberately small so every reliability decision is visible and explainable."

**Point out:**

- `app/api/routes.py` — HTTP API and status handling
- `app/routing/router.py` — least-loaded routing
- `app/workers/pool.py` and `app/workers/worker.py` — worker execution and failure behavior
- `app/observability/` — metrics and JSON logging
- `app/metering/repository.py` — usage records

## 0:30-1:05 — Run the service and show readiness

**Run in a second terminal:**

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Run:**

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/ready
Invoke-WebRequest http://127.0.0.1:8000/workers
```

**Say:**

> "`/health` confirms that the process is alive. `/ready` reports whether there is healthy serving capacity. `/workers` exposes the logical worker state, including health, active requests, queue-depth reporting, utilization, and completed or failed request counts."

## 1:05-1:45 — Successful qwen and llama requests

**Run:**

```powershell
$body = @{
  model = "qwen"
  messages = @(@{role = "user"; content = "Explain Kubernetes simply."})
  max_tokens = 50
} | ConvertTo-Json -Depth 5
Invoke-WebRequest http://127.0.0.1:8000/v1/chat/completions `
  -Method Post -ContentType "application/json" -Body $body
```

Run the same command with `model = "llama"`.

**Say:**

> "The response contains a request ID, model, selected worker, response text, token usage, and latency. The token counts are intentionally approximate word-based estimates because this demonstration does not use a real model tokenizer. The qwen request is routed to one of the two qwen workers; the llama request is routed to the llama worker."

## 1:45-2:35 — Explain routing and failure behavior

**Show:** `app/routing/router.py`, then `app/workers/pool.py`.

**Say:**

> "Routing is deterministic. It filters workers by requested model and health, excludes workers at active concurrency capacity, then ranks candidates by queue depth plus active requests, utilization, and worker ID. This is easy to debug and avoids pretending that a simple round-robin policy understands worker load."

**Run:**

```powershell
$falseBody = '{"healthy":false}'
Invoke-WebRequest http://127.0.0.1:8000/admin/workers/worker-1/health `
  -Method Post -ContentType "application/json" -Body $falseBody
```

Send the qwen request again.

**Say:**

> "With worker 1 unhealthy, the request is routed to worker 2. The failure is isolated to that worker."

Then disable worker 2:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/admin/workers/worker-2/health `
  -Method Post -ContentType "application/json" -Body $falseBody
```

Send qwen again and show HTTP 503.

**Say:**

> "When no healthy worker serves the requested model, the API returns 503. That is different from 429: 503 means unavailable capacity because there is no healthy worker; 429 means healthy workers exist but their active capacity is saturated."

Reset the demo:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/admin/reset `
  -Method Post -ContentType "application/json" -Body "{}"
```

## 2:35-3:15 — Metrics, request IDs, and usage

**Run:**

```powershell
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-WebRequest http://127.0.0.1:8000/usage
```

**Say:**

> "`/metrics` exposes total, successful, and failed requests, latency histograms, active requests, worker health, queue-depth gauges, utilization, retries, timeouts, routing failures, and generated tokens. Request IDs and customer IDs are not metric labels, so arbitrary request traffic cannot create unbounded label cardinality."

> "Successful and failed requests are recorded in SQLite with request ID, customer, model, approximate input and output tokens, total tokens, latency, worker ID when available, status, and timestamp. In production, I would replace this local SQLite path with durable usage events and a scalable analytical store."

## 3:15-3:55 — Tests and benchmark

**Run:**

```powershell
python -m pytest -q
python scripts/load_test.py --requests 40 --concurrency 8 --max-tokens 200 --model-mix "qwen:80,llama:20"
```

**Say:**

> "The test suite covers health, readiness, routing, unhealthy-worker exclusion, all-worker failure, capacity rejection, timeout behavior, usage metering, metrics, request IDs, and worker errors."

> "The concurrency-8 benchmark is measured locally, not estimated. The documented run produced 40 requests, 28 successes, 12 HTTP 429 responses, 1.91 requests per second, 0.559 seconds P50, 0.6776 seconds P95, and 0.6935 seconds P99."

> "The 429s are intentional backpressure. The two qwen workers expose four active slots total, and this implementation rejects excess work instead of maintaining a waiting queue. The exact rejection count can vary slightly with event-loop timing. I would increase capacity or add a bounded queue only after defining the desired latency and admission-control policy."

## 3:55-4:35 — Production evolution

**Show:** `INTERVIEW_NOTES.md` and `k8s/deployment.yaml`.

**Say:**

> "The local service is not claiming to be a production GPU scheduler. For roughly 1,000 B200 or B300 GPUs, I would preserve the same control-plane ideas but replace the simulation with a real serving runtime such as vLLM, use GPU-aware Kubernetes scheduling and warm model pools, add regional clusters and global routing, use continuous batching, enforce tenant quotas and admission control, and stream usage events into durable storage."

> "The Kubernetes manifests demonstrate the deployment shape: replicas, rolling updates, CPU and memory requests and limits, readiness, liveness, and a ClusterIP service. They are intentionally CPU-only because this repository is a local simulation rather than a real GPU deployment."

## 4:35-4:55 — Close with tradeoffs

**Say:**

> "The main tradeoff is simplicity versus production completeness. This implementation demonstrates the request path, deterministic routing, bounded retries, explicit 429 versus 503 semantics, timeout cleanup, observability, and metering without hiding the fact that inference, utilization, and tokenization are simulated. That makes the behavior reproducible and gives a clear path to production hardening."

## Questions to be ready for

- **Why not round robin?**
  Because worker load and health matter more than equal assignment, especially with heterogeneous latency.

- **Why 429 instead of waiting?**
  The local implementation uses bounded active concurrency and fail-fast backpressure. Waiting would require a real queue, admission policy, and queue-time SLO.

- **Why 503 when all workers are unhealthy?**
  The service has no healthy serving capacity for the requested model. Retrying locally would not improve that condition.

- **Are the token counts real?**
  No. They are approximate local estimates. A production meter must use the serving runtime's tokenizer or authoritative usage event.

- **What is the most important production change?**
  Replace process-local worker state and SQLite with a real serving runtime, distributed admission control, durable usage events, authentication, and tenant isolation.

- **What should not be exposed in production?**
  The unauthenticated `/admin/*` failure-simulation endpoints. They exist only for the local demonstration.
