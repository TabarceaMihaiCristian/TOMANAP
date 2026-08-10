"""Unit tests for deterministic load-harness result calculations."""

from scripts.soak import Sample, percentile, summarize


def test_percentile_uses_nearest_rank_and_handles_empty_input() -> None:
    assert percentile([], 95) == 0
    assert percentile([10, 20, 30, 40], 50) == 20
    assert percentile([10, 20, 30, 40], 95) == 40


def test_summary_reports_latency_errors_and_operations() -> None:
    summary = summarize(
        [
            Sample("create", 10, True),
            Sample("create", 30, False),
            Sample("join", 20, True),
        ]
    )

    assert summary["requests"] == 3
    assert summary["successes"] == 2
    assert summary["failures"] == 1
    assert summary["error_rate"] == 1 / 3
    assert summary["p95_ms"] == 30
    assert summary["operations"] == {"create": 2, "join": 1}
