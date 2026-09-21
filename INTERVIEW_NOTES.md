# Production design for ~1,000 NVIDIA B200/B300 GPUs

This section is intentionally architecture-focused. The local project is not meant to simulate a 1,000-GPU platform directly.

## Core architecture

- Global API gateway with region-aware routing
- Authentication and tenant quotas at the edge
- Regional ingress with multi-cluster deployment
- Model-aware routing and scheduler
- GPU worker pools with per-model warm pools
- Distributed queueing and coordination layer
- Event-driven usage pipeline
- Centralized observability and alerting

## Why a single Kubernetes cluster is not enough

At 1,000 GPUs, a single cluster is often too operationally fragile for global traffic, region failover, and capacity management. A single scheduler can become a bottleneck under mixed model demand, capacity fragmentation, and maintenance windows. Operational isolation across clusters also helps with rollouts, incident response, and fault domains.

## Recommended production layout

- Global ingress with TLS and identity-aware routing
- Region-level API gateways
- Regional Kubernetes clusters with separate GPU pools per model family
- Model artifact storage in object storage or a private registry
- NVIDIA GPU Operator and Node Feature Discovery for GPU topology visibility
- vLLM or similar continuous-batching inference runtime
- Warm model pools for common models
- Redis or another coordination layer for queue and scheduling state
- Kafka or a similar event stream for usage records and logs
- PostgreSQL for relational storage and operational reporting
- Prometheus + Grafana + OpenTelemetry for the control plane

## Failure scenarios

### One unhealthy worker
A single unhealthy worker should be removed from the healthy pool without impacting the rest of the fleet. This is the same principle demonstrated in the local worker pool.

### One customer consuming most capacity
The system should use per-customer quotas, strict concurrency controls, and fair scheduling. Priority should be enforced with explicit policy, not obscure hidden behavior.

### Adding another model
The scheduler should route based on model compatibility, queue depth, and GPU topology. The model-specific warm pool should be pre-warmed or loaded on demand according to demand estimation.

### 10% canary rollout
A 10% canary lets the team validate latency, throughput, error rates, and cost before full promotion. The rollout should include automatic rollback thresholds on latency and failure rates.

### Cluster outage
Regional traffic should fail over to the next healthy cluster. Requests should be queued or rerouted according to the defined SLOs and quotas.

### Sudden doubling of P95 latency
The system should automatically surface saturation, queue growth, and GPU contention. If latency doubles, autoscaling or model fallback should engage as part of the incident response plan.

## GPU and topology concerns

The physical scheduling problem is more complex than the local simulation. Real scheduling considers:

- GPU topology and interconnect
- memory availability
- model size and KV cache footprint
- request batching efficiency
- node-level and rack-level failures
- preemption rules for jobs with mixed priorities

## SLO examples

- P95 latency for a given model family
- request error rate below a threshold
- queue saturation below a threshold
- healthy capacity across clusters
- usage ingestion lag for metering and cost accounting

## Why the local project matters

The local simulation demonstrates the operational mindset: health checks, queue pressure, least-loaded routing, metrics, tracing, and clean failure behavior. These are the same building blocks used in large GPU inference systems, even though the real platform must scale far beyond a simple service.
