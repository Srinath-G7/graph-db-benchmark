"""Shared timing + percentile helpers so every workload runner reports
numbers the same way. Keeping this in one place is what makes the
cross-platform comparison actually fair.
"""
import time
import json
import os
import statistics
from contextlib import contextmanager


@contextmanager
def timed():
    """Context manager yielding a dict that gets filled with elapsed_ms."""
    result = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed_ms"] = (time.perf_counter() - start) * 1000.0


def percentile(values, pct):
    """Nearest-rank percentile. values: list[float], pct: 0-100."""
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def summarize(latencies_ms):
    return {
        "n": len(latencies_ms),
        "p50_ms": round(percentile(latencies_ms, 50), 3) if latencies_ms else None,
        "p95_ms": round(percentile(latencies_ms, 95), 3) if latencies_ms else None,
        "min_ms": round(min(latencies_ms), 3) if latencies_ms else None,
        "max_ms": round(max(latencies_ms), 3) if latencies_ms else None,
        "mean_ms": round(statistics.mean(latencies_ms), 3) if latencies_ms else None,
    }


def save_result(platform, workload_name, payload, results_dir="results"):
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"{platform}__{workload_name}.json")
    payload = {"platform": platform, "workload": workload_name, **payload}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[saved] {path}")
    return path


def run_n_times(fn, n, warmup=10):
    """Run fn() warmup times (discarded), then n times, returning latencies_ms.
    fn should perform exactly one query/operation and take no args.
    """
    for _ in range(warmup):
        fn()
    latencies = []
    for _ in range(n):
        with timed() as t:
            fn()
        latencies.append(t["elapsed_ms"])
    return latencies
