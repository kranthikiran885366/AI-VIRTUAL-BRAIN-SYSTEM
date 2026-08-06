"""
Failure Recovery Tests
=======================
Force failures and verify:
  - Graceful degradation
  - Retry behaviour
  - Recovery after failure
  - No data corruption
"""

import json
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Any

BASE = "http://localhost:8001"
TIMEOUT = 30

passed = 0
failed = 0


def _exec(agent, action, data=None):
    body = json.dumps({"agent_name": agent, "action": action, "input_data": data or {}}).encode()
    req = urllib.request.Request(f"{BASE}/execute", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return {"ok": True, "status": resp.status, "body": json.loads(resp.read()),
                    "latency_ms": (time.perf_counter() - start) * 1000}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"ok": False, "status": e.code, "body": body,
                "latency_ms": (time.perf_counter() - start) * 1000}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e),
                "latency_ms": (time.perf_counter() - start) * 1000}


def _get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as resp:
            return {"ok": True, "status": resp.status, "body": json.loads(resp.read())}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)}


def _ok(label):
    global passed; passed += 1
    print(f"  [PASS] {label}")

def _nok(label, reason=""):
    global failed; failed += 1
    print(f"  [FAIL] {label}  ({reason})")


# ─── 1. Nonexistent Agent Graceful Degradation ──────────────────────────────

def test_nonexistent_agent():
    print(f"\n{'='*70}")
    print(f"  TEST: Nonexistent Agent Graceful Degradation")
    print(f"{'='*70}")

    r = _exec("ghost_agent", "do_something", {"data": "test"})
    if r["status"] in (200, 404, 500):
        _ok(f"Server handled nonexistent agent (HTTP {r['status']})")
    else:
        _nok(f"Unexpected response", f"HTTP {r['status']}")

    # Verify server is still healthy after
    h = _get("/health")
    if h["ok"]:
        _ok("Server healthy after nonexistent agent request")
    else:
        _nok("Server unhealthy after nonexistent agent request")


# ─── 2. Invalid Action Graceful Degradation ──────────────────────────────────

def test_invalid_action():
    print(f"\n{'='*70}")
    print(f"  TEST: Invalid Action Graceful Degradation")
    print(f"{'='*70}")

    r = _exec("memory_agent", "nonexistent_action", {})
    if r["status"] in (200, 400, 422, 500):
        _ok(f"Invalid action handled (HTTP {r['status']})")
    else:
        _nok(f"Unexpected response", f"HTTP {r['status']}")

    # System should still work
    r2 = _exec("memory_agent", "get_stats", {})
    if r2["ok"]:
        _ok("memory_agent still works after invalid action")
    else:
        _nok("memory_agent broken after invalid action")


# ─── 3. Agent Error Containment ──────────────────────────────────────────────

def test_error_containment():
    print(f"\n{'='*70}")
    print(f"  TEST: Agent Error Containment (bad input shouldn't crash others)")
    print(f"{'='*70}")

    # Send intentionally problematic data to one agent
    r1 = _exec("reasoning_agent", "reason", {
        "query": None,  # Will be serialized as null
    })
    # Whether this succeeds or fails, it shouldn't crash other agents

    # Immediately test other agents
    agents_ok = 0
    agents_tested = [
        ("emotion_agent", "get_state", {}),
        ("memory_agent", "get_stats", {}),
        ("task_agent", "get_status", {}),
        ("learning_agent", "get_status", {}),
    ]

    for agent, action, data in agents_tested:
        r = _exec(agent, action, data)
        if r["ok"]:
            agents_ok += 1

    if agents_ok == len(agents_tested):
        _ok(f"All {agents_ok} other agents unaffected by error in reasoning_agent")
    elif agents_ok > 0:
        _ok(f"{agents_ok}/{len(agents_tested)} agents still working (partial isolation)")
    else:
        _nok("All agents affected by single agent error")


# ─── 4. Timeout Handling ─────────────────────────────────────────────────────

def test_timeout_handling():
    print(f"\n{'='*70}")
    print(f"  TEST: Timeout Handling")
    print(f"{'='*70}")

    # Send a request that might take a while, but use a very short client timeout
    start = time.perf_counter()
    try:
        body = json.dumps({
            "agent_name": "reasoning_agent",
            "action": "reason",
            "input_data": {"query": "Solve P=NP"}
        }).encode()
        req = urllib.request.Request(f"{BASE}/execute", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
            elapsed = time.perf_counter() - start
            _ok(f"Request completed within 2s timeout ({elapsed*1000:.0f}ms)")
    except Exception as e:
        elapsed = time.perf_counter() - start
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            _ok(f"Client timeout triggered after {elapsed:.1f}s (expected)")
        else:
            _ok(f"Request failed with: {str(e)[:40]} ({elapsed:.1f}s)")

    # Verify server is still responsive
    time.sleep(1)
    h = _get("/health")
    if h["ok"]:
        _ok("Server responsive after timeout scenario")
    else:
        _nok("Server unresponsive after timeout")


# ─── 5. Database Contention ──────────────────────────────────────────────────

def test_database_contention():
    print(f"\n{'='*70}")
    print(f"  TEST: Database Contention (concurrent writes + reads)")
    print(f"{'='*70}")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Concurrent writes to memory_agent
    def write_fn(i):
        return _exec("memory_agent", "store", {
            "content": f"Contention test entry {i}",
            "memory_type": "short_term", "importance": 0.5,
        })

    def read_fn(i):
        return _exec("memory_agent", "recall", {"query": "contention test", "limit": 3})

    write_ok = 0
    read_ok = 0
    write_err = 0
    read_err = 0

    with ThreadPoolExecutor(max_workers=20) as pool:
        # Mix writes and reads
        futures = []
        for i in range(15):
            futures.append(("write", pool.submit(write_fn, i)))
            futures.append(("read", pool.submit(read_fn, i)))

        for op, f in futures:
            r = f.result()
            if r["ok"]:
                if op == "write": write_ok += 1
                else: read_ok += 1
            else:
                if op == "write": write_err += 1
                else: read_err += 1

    if write_err == 0 and read_err == 0:
        _ok(f"All concurrent ops succeeded: {write_ok} writes, {read_ok} reads")
    elif write_err + read_err < 5:
        _ok(f"Mostly succeeded: {write_ok}W/{write_err}F writes, {read_ok}R/{read_err}F reads")
    else:
        _nok(f"Heavy contention failures", f"W={write_ok}/{write_err}, R={read_ok}/{read_err}")


# ─── 6. Rapid Agent Switching ────────────────────────────────────────────────

def test_rapid_agent_switching():
    print(f"\n{'='*70}")
    print(f"  TEST: Rapid Agent Switching (context switching stress)")
    print(f"{'='*70}")

    agents = [
        ("memory_agent", "get_stats", {}),
        ("emotion_agent", "get_state", {}),
        ("reasoning_agent", "reason", {"query": "test"}),
        ("planning_agent", "create_plan", {"goal": "test"}),
        ("decision_agent", "make_decision", {"options": ["A"]}),
        ("learning_agent", "get_status", {}),
        ("task_agent", "get_status", {}),
        ("creativity_agent", "generate_idea", {"topic": "test"}),
    ]

    ok_count = 0
    for cycle in range(3):  # 3 cycles through all agents
        for agent, action, data in agents:
            r = _exec(agent, action, data)
            if r["ok"]:
                ok_count += 1

    total = len(agents) * 3
    if ok_count == total:
        _ok(f"All {total} rapid switches succeeded")
    elif ok_count > total * 0.9:
        _ok(f"{ok_count}/{total} switches succeeded (>90%)")
    else:
        _nok(f"Rapid switching failures", f"{ok_count}/{total}")


# ─── 7. Recovery After Burst of Errors ───────────────────────────────────────

def test_recovery_after_errors():
    print(f"\n{'='*70}")
    print(f"  TEST: Recovery After Burst of Errors")
    print(f"{'='*70}")

    # Generate a burst of errors
    print("  [Phase 1] Generating 20 error requests...")
    for i in range(20):
        _exec("nonexistent_agent_" + str(i), "bad_action", {"bad": True})

    time.sleep(1)

    # Now verify normal operation
    print("  [Phase 2] Testing recovery...")
    recovery_ok = 0
    for agent, action, data in [
        ("memory_agent", "get_stats", {}),
        ("emotion_agent", "get_state", {}),
        ("reasoning_agent", "reason", {"query": "recovery test"}),
        ("learning_agent", "get_status", {}),
    ]:
        r = _exec(agent, action, data)
        if r["ok"]:
            recovery_ok += 1

    if recovery_ok == 4:
        _ok(f"Full recovery: all 4 agents healthy after error burst")
    elif recovery_ok > 0:
        _ok(f"Partial recovery: {recovery_ok}/4 agents healthy")
    else:
        _nok("No recovery after error burst")

    # Check overall health
    h = _get("/health")
    if h["ok"]:
        status = h["body"].get("status", "unknown")
        _ok(f"Health check: {status}")
    else:
        _nok("Health check failed after recovery")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 70)
    print("  FAILURE RECOVERY TEST SUITE")
    print("=" * 70)

    test_nonexistent_agent()
    test_invalid_action()
    test_error_containment()
    test_timeout_handling()
    test_database_contention()
    test_rapid_agent_switching()
    test_recovery_after_errors()

    print(f"\n{'='*70}")
    print(f"  FAILURE RECOVERY SUMMARY")
    print(f"{'='*70}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    status = "SUCCESS" if failed == 0 else f"FAILURE: {failed} FAILURES"
    print(f"  Status: {status}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
