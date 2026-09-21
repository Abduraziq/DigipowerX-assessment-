# What I would do next

## Before production

1. Replace simulation with a real inference runtime such as vLLM, TGI, or llama.cpp.
2. Move token metering from SQLite to PostgreSQL or a warehouse-friendly event pipeline.
3. Add per-tenant authentication, quotas, and rate limits.
4. Add OpenTelemetry distributed tracing and richer Grafana dashboards.
5. Add a real model registry and canary deployment workflow with rollback rules.
6. Harden the API with TLS, network policies, and secret management.

## Next scaling milestone

1. Introduce a multi-cluster Kubernetes deployment with regional ingress and failover.
2. Add Redis or a distributed coordination layer for queueing and scheduler state.
3. Add autoscaling on queue depth, request rate, and P95 latency.
4. Add a logging and metrics pipeline for longer retention and central analysis.
5. Add persistent model artifacts and image registries for warm-model pools.

## Longer term

1. Add multi-tenant isolation and admission control by customer and project.
2. Add Kafka-based usage event streaming and analytical storage.
3. Add model lifecycle management, versioning, and shadow traffic testing.
4. Add safety controls for prompt validation, rate limiting, and abuse detection.
5. Add disaster recovery playbooks and multi-cluster failover drills.

## Known limitations

- This service is intentionally a local simulation; it does not model real GPU scheduling or topology.
- SQLite is fine locally but not enough for large-scale usage ingestion.
- Worker health and queue pressure are basic models, not production-grade scheduler logic.
- The benchmark is local and synthetic rather than measured against a real serving runtime.

## Deliberate omissions

- No fake enterprise complexity or heavy abstraction layers.
- No pretend GPU claims.
- No large-scale distributed coordination beyond the design notes.
- No production-grade autoscaling config beyond the architecture discussion.

## Priority order

1. Replace the simulation with a real backend.
2. Add real tenancy and authentication controls.
3. Add distributed observability and tracing.
4. Add durable metering and event streaming.
5. Add multi-cluster scheduling and global load balancing.
