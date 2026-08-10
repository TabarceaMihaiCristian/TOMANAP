"""Stateful bounded load/soak runner for a separately started TOMANAP API."""

import argparse
import asyncio
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx2 as httpx

SESSION_HEADER = "X-TOMANAP-Session"


@dataclass(frozen=True, slots=True)
class Sample:
    """One sanitized request outcome."""

    operation: str
    duration_ms: float
    success: bool
    failure: str | None = None


def percentile(values: list[float], rank: int) -> float:
    """Return a deterministic nearest-rank percentile."""
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil((rank / 100) * len(ordered)) - 1)
    return round(ordered[index], 3)


def summarize(samples: list[Sample]) -> dict[str, Any]:
    """Aggregate bounded non-sensitive scenario measurements."""
    durations = [sample.duration_ms for sample in samples]
    failures = sum(not sample.success for sample in samples)
    total = len(samples)
    return {
        "requests": total,
        "successes": total - failures,
        "failures": failures,
        "error_rate": failures / total if total else 0,
        "p50_ms": percentile(durations, 50),
        "p95_ms": percentile(durations, 95),
        "p99_ms": percentile(durations, 99),
        "operations": dict(Counter(sample.operation for sample in samples)),
    }


async def request(
    client: httpx.AsyncClient,
    samples: list[Sample],
    operation: str,
    method: str,
    path: str,
    *,
    expected_status: int,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Measure one request without retaining response bodies or credentials."""
    started_at = time.perf_counter()
    failure: str | None = None
    payload: dict[str, Any] | None = None
    try:
        response = await client.request(method, path, **kwargs)
        if response.status_code != expected_status:
            failure = f"unexpected_status:{response.status_code}"
        else:
            parsed = response.json()
            if isinstance(parsed, dict):
                payload = parsed
            else:
                failure = "unexpected_response_shape"
    except (httpx.HTTPError, ValueError) as error:
        failure = type(error).__name__
    samples.append(
        Sample(
            operation=operation,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            success=failure is None,
            failure=failure,
        )
    )
    return payload if failure is None else None


async def play_one_round(
    client: httpx.AsyncClient,
    samples: list[Sample],
    worker: int,
    iteration: int,
) -> None:
    """Create a two-player room and reach an authoritative active round."""
    suffix = uuid4().hex[:6]
    host = await request(
        client,
        samples,
        "game.create",
        "POST",
        "/games",
        expected_status=201,
        json={
            "display_name": f"Host-{worker}-{iteration}-{suffix}",
            "round_count": 1,
            "round_duration_seconds": 60,
        },
    )
    if host is None:
        return
    room_code = host["game"]["room_code"]
    guest = await request(
        client,
        samples,
        "game.join",
        "POST",
        f"/games/{room_code}/join",
        expected_status=201,
        json={"display_name": f"Guest-{worker}-{iteration}-{suffix}"},
    )
    if guest is None:
        return
    ready = await request(
        client,
        samples,
        "lobby.ready",
        "POST",
        f"/games/{room_code}/ready",
        expected_status=200,
        headers={SESSION_HEADER: guest["session_token"]},
        json={"is_ready": True},
    )
    if ready is None:
        return
    started = await request(
        client,
        samples,
        "game.start",
        "POST",
        f"/games/{room_code}/start",
        expected_status=200,
        headers={
            SESSION_HEADER: host["session_token"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    if started is None:
        return
    await request(
        client,
        samples,
        "round.current",
        "GET",
        f"/games/{room_code}/rounds/current",
        expected_status=200,
        headers={SESSION_HEADER: host["session_token"]},
    )


async def run(args: argparse.Namespace) -> tuple[dict[str, Any], list[Sample]]:
    """Run bounded concurrent stateful scenarios."""
    samples: list[Sample] = []
    limits = httpx.Limits(
        max_connections=max(10, args.virtual_users * 2),
        max_keepalive_connections=max(5, args.virtual_users),
    )
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=args.timeout_seconds,
        limits=limits,
    ) as client:
        ready = await request(
            client,
            samples,
            "health.ready",
            "GET",
            "/health/ready",
            expected_status=200,
        )
        if ready is None:
            return summarize(samples), samples

        async def worker(worker_id: int) -> None:
            for iteration in range(args.iterations):
                await play_one_round(client, samples, worker_id, iteration)

        await asyncio.gather(
            *(worker(worker_id) for worker_id in range(args.virtual_users))
        )
    return summarize(samples), samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--virtual-users", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.virtual_users < 1 or args.iterations < 1:
        raise ValueError("virtual-users and iterations must be positive")
    summary, samples = asyncio.run(run(args))
    result = {
        "configuration": {
            "base_url": args.base_url,
            "virtual_users": args.virtual_users,
            "iterations": args.iterations,
        },
        "summary": summary,
        "failure_types": dict(
            Counter(sample.failure for sample in samples if sample.failure is not None)
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    failed = (
        summary["error_rate"] > args.max_error_rate
        or summary["p95_ms"] > args.max_p95_ms
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
