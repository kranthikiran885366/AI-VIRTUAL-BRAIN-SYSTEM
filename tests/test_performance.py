"""
Performance Benchmarks
======================
Measures:
  - Startup time (already started — measure via uptime)
  - Reasoning latency
  - Planning latency
  - Memory lookup latency
  - API throughput (health endpoint)
  - Scheduler throughput (agent exec)
  - CPU usage / RAM usage
"""

import json
import os
import statistics
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

BASE = "http://localhost:8001"
TIMEOUT = 30
ITERATIONS = 20  # per benchmark


def _exec(agent: str, action: str, data: dict) -> Dict[str, Any]:
    body = json.dumps({"agent_name": agent, "action": action, "input_data": data}).encode()
    req = urllib.request.Request(f"{BASE}/execute", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read()
            return {"ok": True, "latency_ms": (time.perf_counter() - start) * 1000, "status": resp.status}
    except Exception as e:
        return {"ok": False, "latency_ms": (time.perf_counter() - start) * 1000, "error": str(e)[:60]}


def _get(path: str) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
            return {"ok": True, "latency_ms": (time.perf_counter() - start) * 1000, "data": data}
    except Exception as e:
        return {"ok": False, "latency_ms": (time.perf_counter() - start) * 1000, "error": str(e)[:60]}


def _bench(label: str, fn, iterations: int = ITERATIONS) -> Dict[str, Any]:
    """Run a benchmark function N times and collect stats."""
    latencies = []
    successes = 0
    for i in range(iterations):
        result = fn()
        latencies.append(result["latency_ms"])
        if result.get("ok"):
            successes += 1

    sorted_lat = sorted(latencies)
    stats = {
        "label": label,
        "iterations": iterations,
        "successes": successes,
        "failures": iterations - successes,
        "mean_ms": statistics.mean(latencies),
        "median_ms": sorted_lat[len(sorted_lat) // 2],
        "p95_ms": sorted_lat[int(len(sorted_lat) * 0.95)],
        "p99_ms": sorted_lat[min(int(len(sorted_lat) * 0.99), len(sorted_lat) - 1)],
        "min_ms": sorted_lat[0],
        "max_ms": sorted_lat[-1],
        "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
    }
    return stats


def _print_bench(stats: Dict[str, Any]):
    status = "[PASS]" if stats["failures"] == 0 else "[WARN]"
    print(f"\n  {status} {stats['label']}")
    print(f"     Iterations: {stats['iterations']}  |  Success: {stats['successes']}  |  Failed: {stats['failures']}")
    print(f"     Mean:   {stats['mean_ms']:>8.1f}ms")
    print(f"     Median: {stats['median_ms']:>8.1f}ms")
    print(f"     p95:    {stats['p95_ms']:>8.1f}ms")
    print(f"     p99:    {stats['p99_ms']:>8.1f}ms")
    print(f"     Min:    {stats['min_ms']:>8.1f}ms  |  Max: {stats['max_ms']:>8.1f}ms")
    print(f"     StdDev: {stats['stdev_ms']:>8.1f}ms")


# ─── Benchmarks ──────────────────────────────────────────────────────────────

def bench_server_uptime():
    """Measure server uptime (proxy for startup time)."""
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: Server Startup / Uptime")
    print(f"{'='*70}")
    r = _get("/health")
    if r["ok"]:
        uptime = r["data"].get("uptime_seconds", 0)
        print(f"  Server uptime: {uptime:.1f}s")
        print(f"  Health check latency: {r['latency_ms']:.1f}ms")
    else:
        print(f"  ERROR: Server not reachable")


def bench_health_throughput():
    """Measure /health endpoint throughput."""
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: Health Endpoint Throughput")
    print(f"{'='*70}")

    count = 200
    start = time.perf_counter()
    successes = 0
    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(lambda: _get("/health")) for _ in range(count)]
        for f in as_completed(futures):
            if f.result().get("ok"):
                successes += 1
    elapsed = time.perf_counter() - start
    rps = count / elapsed
    print(f"  Requests: {count}")
    print(f"  Successes: {successes}")
    print(f"  Wall time: {elapsed:.2f}s")
    print(f"  Throughput: {rps:.1f} req/s")
    return rps


def bench_reasoning_latency():
    """Measure reasoning_agent:reason latency."""
    stats = _bench("Reasoning Agent Latency", lambda: _exec("reasoning_agent", "reason", {
        "query": "Analyze the implications of quantum computing on cryptography"
    }))
    _print_bench(stats)
    return stats


def bench_planning_latency():
    """Measure planning_agent:create_plan latency."""
    stats = _bench("Planning Agent Latency", lambda: _exec("planning_agent", "create_plan", {
        "goal": "Build a recommendation system",
        "context": {"domain": "e-commerce", "scale": "medium"},
    }))
    _print_bench(stats)
    return stats


def bench_memory_store_latency():
    """Measure memory_agent:store latency."""
    counter = [0]
    def fn():
        counter[0] += 1
        return _exec("memory_agent", "store", {
            "content": f"Benchmark memory entry #{counter[0]}",
            "memory_type": "short_term",
            "importance": 0.5,
        })
    stats = _bench("Memory Store Latency", fn)
    _print_bench(stats)
    return stats


def bench_memory_recall_latency():
    """Measure memory_agent:recall latency."""
    stats = _bench("Memory Recall Latency", lambda: _exec("memory_agent", "recall", {
        "query": "benchmark", "limit": 5,
    }))
    _print_bench(stats)
    return stats


def bench_emotion_latency():
    """Measure emotion_agent:process_emotion latency."""
    stats = _bench("Emotion Processing Latency", lambda: _exec("emotion_agent", "process_emotion", {
        "text": "I am feeling very excited about the progress we have made!"
    }))
    _print_bench(stats)
    return stats


def bench_decision_latency():
    """Measure decision_agent:make_decision latency."""
    stats = _bench("Decision Agent Latency", lambda: _exec("decision_agent", "make_decision", {
        "options": ["Option A", "Option B", "Option C"],
        "context": "Choose the best strategy",
    }))
    _print_bench(stats)
    return stats


def bench_scheduler_throughput():
    """Measure agent execution throughput via the scheduler pipeline."""
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: Scheduler Throughput (Agent Executions)")
    print(f"{'='*70}")

    count = 100
    agents = [
        ("emotion_agent", "get_state", {}),
        ("memory_agent", "get_stats", {}),
        ("task_agent", "get_status", {}),
        ("learning_agent", "get_status", {}),
    ]
    start = time.perf_counter()
    successes = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        def run(i):
            a, act, d = agents[i % len(agents)]
            return _exec(a, act, d)
        futures = [pool.submit(run, i) for i in range(count)]
        for f in as_completed(futures):
            if f.result().get("ok"):
                successes += 1
    elapsed = time.perf_counter() - start
    rps = count / elapsed
    print(f"  Executions: {count}")
    print(f"  Successes: {successes}")
    print(f"  Wall time: {elapsed:.2f}s")
    print(f"  Throughput: {rps:.1f} exec/s")
    return rps


def bench_system_resources():
    """Measure current CPU and RAM usage of the Python process."""
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: System Resource Usage")
    print(f"{'='*70}")

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        cpu = proc.cpu_percent(interval=1)
        mem = proc.memory_info()
        print(f"  Test runner CPU: {cpu:.1f}%")
        print(f"  Test runner RAM: {mem.rss / 1024 / 1024:.1f} MB")

        # Find the orchestrator process
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(p.info.get("cmdline") or [])
                if "orchestrator" in cmdline and "python" in cmdline.lower():
                    cpu = p.cpu_percent(interval=1)
                    mem = p.memory_info()
                    print(f"  Orchestrator PID {p.pid}:")
                    print(f"    CPU: {cpu:.1f}%")
                    print(f"    RAM: {mem.rss / 1024 / 1024:.1f} MB")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        else:
            print("  (Could not find orchestrator process via psutil)")
    except ImportError:
        print("  psutil not installed — skipping CPU/RAM measurement")
        print("  Install with: pip install psutil")

    # Fallback: check /status endpoint for internal metrics
    r = _get("/status")
    if r["ok"]:
        summary = r["data"].get("summary", {})
        print(f"  Server-reported agents: {summary.get('total_agents', 'N/A')}")
        print(f"  Running agents: {summary.get('running_agents', 'N/A')}")
        print(f"  Pending messages: {summary.get('pending_messages', 'N/A')}")
        print(f"  Pending tasks: {summary.get('pending_tasks', 'N/A')}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  PERFORMANCE BENCHMARK SUITE")
    print("=" * 70)

    bench_server_uptime()
    health_rps = bench_health_throughput()

    all_stats = []
    all_stats.append(bench_reasoning_latency())
    all_stats.append(bench_planning_latency())
    all_stats.append(bench_memory_store_latency())
    all_stats.append(bench_memory_recall_latency())
    all_stats.append(bench_emotion_latency())
    all_stats.append(bench_decision_latency())

    sched_rps = bench_scheduler_throughput()
    bench_system_resources()

    # Summary table
    print(f"\n{'='*70}")
    print(f"  PERFORMANCE SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Benchmark':<35s} {'Mean':>8s} {'p95':>8s} {'p99':>8s} {'Min':>8s} {'Max':>8s}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for s in all_stats:
        print(f"  {s['label']:<35s} {s['mean_ms']:>7.1f}ms {s['p95_ms']:>7.1f}ms {s['p99_ms']:>7.1f}ms {s['min_ms']:>7.1f}ms {s['max_ms']:>7.1f}ms")
    print(f"\n  Health Throughput:    {health_rps:.1f} req/s")
    print(f"  Scheduler Throughput: {sched_rps:.1f} exec/s")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
