"""
High-Concurrency Stress Tests
==============================
Validates scalability under concurrent load:
  - 50 concurrent users
  - 100 concurrent users
  - 500 concurrent requests
  - 1000 queued tasks

Measures: latency (p50/p95/p99), throughput (req/s), failure rate, timeout recovery.
"""

import json
import statistics
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Any

BASE = "http://localhost:8001"
TIMEOUT = 30


@dataclass
class RequestResult:
    status: int = 0
    latency_ms: float = 0.0
    error: str = ""
    success: bool = False


@dataclass
class ConcurrencyReport:
    label: str = ""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    failure_rate_pct: float = 0.0
    latencies_ms: List[float] = field(default_factory=list)
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    throughput_rps: float = 0.0
    wall_time_s: float = 0.0
    errors: Dict[str, int] = field(default_factory=dict)


def _make_request(method: str, path: str, body: dict = None) -> RequestResult:
    """Make a single HTTP request and return timing + status."""
    start = time.perf_counter()
    try:
        url = f"{BASE}{path}"
        if body is not None:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
            latency = (time.perf_counter() - start) * 1000
            return RequestResult(status=resp.status, latency_ms=latency, success=True)
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - start) * 1000
        return RequestResult(status=e.code, latency_ms=latency, error=f"HTTP {e.code}", success=False)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return RequestResult(status=0, latency_ms=latency, error=str(e)[:80], success=False)


def _run_concurrent(label: str, concurrency: int, requests_fn, total: int = None) -> ConcurrencyReport:
    """Execute requests_fn concurrently and collect metrics."""
    total = total or concurrency
    report = ConcurrencyReport(label=label, total_requests=total)

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(concurrency, 200)) as pool:
        futures = [pool.submit(requests_fn, i) for i in range(total)]
        for f in as_completed(futures):
            try:
                result: RequestResult = f.result()
                report.latencies_ms.append(result.latency_ms)
                if result.success:
                    report.successful += 1
                else:
                    report.failed += 1
                    key = result.error or f"HTTP_{result.status}"
                    report.errors[key] = report.errors.get(key, 0) + 1
            except Exception as e:
                report.failed += 1
                key = str(e)[:40]
                report.errors[key] = report.errors.get(key, 0) + 1

    report.wall_time_s = time.perf_counter() - wall_start
    if report.latencies_ms:
        sorted_lat = sorted(report.latencies_ms)
        report.p50_ms = sorted_lat[len(sorted_lat) // 2]
        report.p95_ms = sorted_lat[int(len(sorted_lat) * 0.95)]
        report.p99_ms = sorted_lat[int(len(sorted_lat) * 0.99)]
        report.mean_ms = statistics.mean(sorted_lat)
        report.min_ms = sorted_lat[0]
        report.max_ms = sorted_lat[-1]
    report.failure_rate_pct = (report.failed / report.total_requests * 100) if report.total_requests else 0
    report.throughput_rps = report.total_requests / report.wall_time_s if report.wall_time_s > 0 else 0
    return report


def _print_report(r: ConcurrencyReport):
    status = "PASS" if r.failure_rate_pct < 5 else "WARN" if r.failure_rate_pct < 20 else "FAIL"
    print(f"\n{'='*70}")
    print(f"  [{status}] {r.label}")
    print(f"{'='*70}")
    print(f"  Total Requests:    {r.total_requests}")
    print(f"  Successful:        {r.successful}")
    print(f"  Failed:            {r.failed}  ({r.failure_rate_pct:.1f}%)")
    print(f"  Wall Time:         {r.wall_time_s:.2f}s")
    print(f"  Throughput:        {r.throughput_rps:.1f} req/s")
    print(f"  Latency p50:       {r.p50_ms:.1f}ms")
    print(f"  Latency p95:       {r.p95_ms:.1f}ms")
    print(f"  Latency p99:       {r.p99_ms:.1f}ms")
    print(f"  Latency mean:      {r.mean_ms:.1f}ms")
    print(f"  Latency min/max:   {r.min_ms:.1f}ms / {r.max_ms:.1f}ms")
    if r.errors:
        print(f"  Error breakdown:")
        for err, cnt in sorted(r.errors.items(), key=lambda x: -x[1]):
            print(f"    {err}: {cnt}")
    return status


# ─── Test Functions ───────────────────────────────────────────────────────────

def test_health_50_concurrent():
    """50 concurrent GET /health requests."""
    def fn(_): return _make_request("GET", "/health")
    return _run_concurrent("50 Concurrent Health Checks", 50, fn)


def test_health_100_concurrent():
    """100 concurrent GET /health requests."""
    def fn(_): return _make_request("GET", "/health")
    return _run_concurrent("100 Concurrent Health Checks", 100, fn)


def test_agent_exec_50_concurrent():
    """50 concurrent agent executions (mixed agents)."""
    agents = [
        ("emotion_agent", "get_state", {}),
        ("memory_agent", "get_stats", {}),
        ("learning_agent", "get_status", {}),
        ("task_agent", "get_status", {}),
        ("reasoning_agent", "reason", {"query": "What is 2+2?"}),
    ]
    def fn(i):
        agent, action, data = agents[i % len(agents)]
        return _make_request("POST", "/execute", {
            "agent_name": agent, "action": action, "input_data": data
        })
    return _run_concurrent("50 Concurrent Agent Executions", 50, fn)


def test_agent_exec_100_concurrent():
    """100 concurrent agent executions."""
    agents = [
        ("emotion_agent", "get_state", {}),
        ("memory_agent", "get_stats", {}),
        ("decision_agent", "make_decision", {"options": ["A", "B"], "context": "test"}),
        ("creativity_agent", "generate_idea", {"topic": "AI"}),
        ("language_agent", "analyze", {"text": "Hello world"}),
    ]
    def fn(i):
        agent, action, data = agents[i % len(agents)]
        return _make_request("POST", "/execute", {
            "agent_name": agent, "action": action, "input_data": data
        })
    return _run_concurrent("100 Concurrent Agent Executions", 100, fn)


def test_mixed_500_requests():
    """500 mixed read/write requests."""
    def fn(i):
        if i % 3 == 0:
            return _make_request("GET", "/health")
        elif i % 3 == 1:
            return _make_request("GET", "/agents")
        else:
            return _make_request("POST", "/execute", {
                "agent_name": "emotion_agent", "action": "get_state", "input_data": {}
            })
    return _run_concurrent("500 Mixed Requests", 200, fn, total=500)


def test_memory_store_burst():
    """100 concurrent memory store operations (write contention)."""
    def fn(i):
        return _make_request("POST", "/execute", {
            "agent_name": "memory_agent",
            "action": "store",
            "input_data": {
                "content": f"Concurrency test memory #{i}",
                "memory_type": "short_term",
                "importance": 0.3,
                "tags": ["stress_test"],
            }
        })
    return _run_concurrent("100 Concurrent Memory Writes", 100, fn)


def test_queued_tasks_1000():
    """1000 queued lightweight tasks (health checks) to measure queue throughput."""
    def fn(i):
        return _make_request("GET", "/health")
    return _run_concurrent("1000 Queued Tasks", 100, fn, total=1000)


def test_timeout_recovery():
    """Fire 50 concurrent requests after a burst of 200 — verify the server recovers."""
    print("\n  [Phase 1] Burst of 200 requests...")
    def fn(_): return _make_request("GET", "/health")
    burst = _run_concurrent("Burst Phase (200 requests)", 200, fn)
    _print_report(burst)

    time.sleep(2)  # Let server settle

    print("  [Phase 2] Recovery: 50 requests post-burst...")
    recovery = _run_concurrent("Recovery Phase (50 requests)", 50, fn)
    return recovery


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  HIGH-CONCURRENCY STRESS TEST SUITE")
    print("=" * 70)

    # Verify server is up
    try:
        r = _make_request("GET", "/health")
        if not r.success:
            print(f"  ERROR: Server not reachable at {BASE} (HTTP {r.status})")
            sys.exit(1)
        print(f"  Server healthy at {BASE}")
    except Exception as e:
        print(f"  ERROR: Cannot connect to server: {e}")
        sys.exit(1)

    tests = [
        test_health_50_concurrent,
        test_health_100_concurrent,
        test_agent_exec_50_concurrent,
        test_agent_exec_100_concurrent,
        test_mixed_500_requests,
        test_memory_store_burst,
        test_queued_tasks_1000,
        test_timeout_recovery,
    ]

    results = []
    for test_fn in tests:
        print(f"\n{'─'*70}")
        print(f"  Running: {test_fn.__doc__}")
        report = test_fn()
        status = _print_report(report)
        results.append((report.label, status, report))

    # Summary
    print(f"\n{'='*70}")
    print(f"  CONCURRENCY TEST SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    warned = sum(1 for _, s, _ in results if s == "WARN")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    for label, status, r in results:
        print(f"  [{status}] {label:40s}  {r.throughput_rps:>7.1f} req/s  p95={r.p95_ms:>8.1f}ms  fail={r.failure_rate_pct:.1f}%")
    print(f"\n  Total: {passed} PASS, {warned} WARN, {failed} FAIL")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
