from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter

import httpx


async def run_single(client: httpx.AsyncClient, model: str, max_tokens: int, request_id: str) -> tuple[float, int, str]:
    start = time.perf_counter()
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": f"Test request {request_id} for {model}."}],
            "max_tokens": max_tokens,
        },
        headers={"X-Request-ID": request_id},
    )
    elapsed = time.perf_counter() - start
    return elapsed, response.status_code, response.json().get("worker_id", "unknown")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Local concurrency benchmark for the inference platform")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model-mix", default="qwen:80,llama:20")
    args = parser.parse_args()

    model_mix = {}
    for item in args.model_mix.split(","):
        model, share = item.split(":")
        model_mix[model.strip()] = int(share)

    async def runner() -> None:
        semaphore = asyncio.Semaphore(args.concurrency)
        results: list[tuple[float, int, str]] = []

        async def run_one(index: int) -> None:
            model = "qwen" if index % 10 < model_mix.get("qwen", 0) / 10 else "llama"
            async with semaphore:
                async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
                    result = await run_single(client, model, args.max_tokens, f"bench-{index}")
                    results.append(result)

        tasks = [asyncio.create_task(run_one(i)) for i in range(args.requests)]
        await asyncio.gather(*tasks)
        return results

    results = await runner()
    latencies = [latency for latency, status_code, _ in results]
    errors = [status_code for _, status_code, _ in results if status_code != 200]
    status_distribution = Counter(errors)
    summary = {
        "request_count": len(results),
        "success_count": sum(1 for _, status_code, _ in results if status_code == 200),
        "failure_count": len(errors),
        "throughput_rps": round(len(results) / max(sum(latencies), 1e-9), 3),
        "average_latency_s": round(statistics.mean(latencies), 4) if latencies else 0,
        "p50_latency_s": round(statistics.median(latencies), 4) if latencies else 0,
        "p95_latency_s": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 4) if latencies else 0,
        "p99_latency_s": round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 4) if latencies else 0,
        "status_code_distribution": {str(key): value for key, value in sorted(status_distribution.items())},
        "concurrency": args.concurrency,
        "max_tokens": args.max_tokens,
        "model_mix": model_mix,
        "base_url": args.base_url,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
