# Benchmark results

## Methodology

- Test date: 2026-09-20
- Environment: local Windows workstation running the FastAPI service in-process via uvicorn
- Request count: 40
- Concurrency: 8
- Model mix: qwen 80%, llama 20%
- Max tokens: 200
- Worker configuration: worker-1 qwen, worker-2 qwen, worker-3 llama
- Simulated latency configuration: qwen base latency 130-140 ms, llama base latency 180 ms
- GPU utilization: simulated and intentionally labeled as simulated

## Required concurrency 8 benchmark

Measured actual values from a local run:

```json
{
  "request_count": 40,
  "success_count": 28,
  "failure_count": 12,
  "throughput_rps": 1.91,
  "average_latency_s": 0.5236,
  "p50_latency_s": 0.559,
  "p95_latency_s": 0.6776,
  "p99_latency_s": 0.6935,
  "status_code_distribution": {"429": 12}
}
```

## Observation

- The 12 rejected requests are HTTP 429 responses caused by worker concurrency saturation, not by a configured waiting queue. The two qwen workers have two active slots each, so a burst of eight qwen requests can admit four and reject the rest before later requests are scheduled.
- The 80/20 deterministic model mix creates an initial qwen-heavy burst, which makes this effect visible at concurrency 8. The exact rejection count can vary by a request or two with event-loop timing; the behavior is intentional bounded backpressure, but the local capacity is restrictive and should not be read as production throughput.
- HTTP 503 is reserved for the requested model having no healthy worker; it is not the normal response for capacity rejection.
- Latency is strongly influenced by the small local worker pool and the deterministic sleep-based inference simulation.

## Production estimate

This is a local simulation only. Any estimate for production throughput or latency would be hypothetical and not measured here. The project separates these values intentionally.

## What to optimize next

1. Increase per-model worker concurrency and queue ceilings.
2. Introduce continuous batching or a real serving runtime such as vLLM.
3. Add model-aware routing based on request length and token budget.
4. Add rate limiting and per-tenant quotas.
5. Move on to a real GPU-backed deployment for throughput validation.
