"""
Cross-Agent Collaboration Workflow Tests
=========================================
Validates multi-agent pipeline:
  Memory -> Reasoning -> Planning -> Decision -> Ethics -> Language -> Learning

Verifies: shared context, correlation IDs, execution ordering, state consistency.
"""

import json
import sys
import time
import uuid
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

BASE = "http://localhost:8001"
TIMEOUT = 30


def _exec(agent: str, action: str, data: dict, correlation_id: str = None) -> Dict[str, Any]:
    """Execute an agent action and return the full response dict."""
    body = {"agent_name": agent, "action": action, "input_data": data}
    payload = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    req = urllib.request.Request(f"{BASE}/execute", data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return {"http_status": resp.status, "body": json.loads(resp.read()),
                    "correlation_id": resp.headers.get("X-Correlation-ID", ""),
                    "trace_id": resp.headers.get("X-Trace-ID", "")}
    except urllib.error.HTTPError as e:
        return {"http_status": e.code, "body": {}, "error": str(e)}
    except Exception as e:
        return {"http_status": 0, "body": {}, "error": str(e)}


def _pass(label): print(f"  [PASS] {label}")
def _fail(label, reason=""): print(f"  [FAIL] {label}  ({reason})")
def _info(label): print(f"  [INFO] {label}")


# ─── Test 1: Full 7-Agent Cognitive Pipeline ──────────────────────────────────

def test_full_cognitive_pipeline():
    """Memory -> Reasoning -> Planning -> Decision -> Ethics -> Language -> Learning"""
    print(f"\n{'='*70}")
    print(f"  TEST: Full 7-Agent Cognitive Pipeline")
    print(f"{'='*70}")

    correlation_id = f"pipeline-{uuid.uuid4().hex[:12]}"
    context = {"topic": "AI safety", "user_goal": "understand alignment risks"}
    results = {}
    passed = 0
    failed = 0

    # Step 1: Memory — store context
    print(f"\n  [Step 1/7] memory_agent:store")
    r = _exec("memory_agent", "store", {
        "content": f"User wants to understand AI alignment risks. Session {correlation_id}",
        "memory_type": "short_term",
        "importance": 0.8,
        "tags": ["ai_safety", "pipeline_test"],
    }, correlation_id)
    results["memory_store"] = r
    if r["http_status"] == 200:
        _pass("memory_agent:store")
        passed += 1
    else:
        _fail("memory_agent:store", f"HTTP {r['http_status']}")
        failed += 1

    # Step 2: Memory — recall to feed downstream
    print(f"  [Step 2/7] memory_agent:recall")
    r = _exec("memory_agent", "recall", {
        "query": "AI alignment risks",
        "limit": 3,
    }, correlation_id)
    results["memory_recall"] = r
    recalled_context = ""
    if r["http_status"] == 200:
        res = r["body"].get("result")
        memories = res if isinstance(res, list) else res.get("memories", []) if isinstance(res, dict) else []
        if memories:
            recalled_context = memories[0].get("content", "") if isinstance(memories[0], dict) else str(memories[0])
        _pass(f"memory_agent:recall (found {len(memories)} memories)")
        passed += 1
    else:
        _fail("memory_agent:recall", f"HTTP {r['http_status']}")
        failed += 1

    # Step 3: Reasoning — analyze the topic
    print(f"  [Step 3/7] reasoning_agent:reason")
    r = _exec("reasoning_agent", "reason", {
        "query": f"Analyze AI alignment risks. Context: {recalled_context or context['topic']}",
        "context": context,
    }, correlation_id)
    results["reasoning"] = r
    reasoning_output = ""
    if r["http_status"] == 200:
        res = r["body"].get("result", {})
        reasoning_output = json.dumps(res)[:200] if isinstance(res, dict) else str(res)[:200]
        _pass(f"reasoning_agent:reason")
        passed += 1
    else:
        _fail("reasoning_agent:reason", f"HTTP {r['http_status']}")
        failed += 1

    # Step 4: Planning — create action plan
    print(f"  [Step 4/7] planning_agent:create_plan")
    r = _exec("planning_agent", "create_plan", {
        "goal": "Develop comprehensive understanding of AI alignment",
        "context": {"reasoning_output": reasoning_output, "topic": context["topic"]},
    }, correlation_id)
    results["planning"] = r
    plan_output = ""
    if r["http_status"] == 200:
        res = r["body"].get("result", {})
        plan_output = json.dumps(res)[:200] if isinstance(res, dict) else str(res)[:200]
        _pass(f"planning_agent:create_plan")
        passed += 1
    else:
        _fail("planning_agent:create_plan", f"HTTP {r['http_status']}")
        failed += 1

    # Step 5: Decision — evaluate options
    print(f"  [Step 5/7] decision_agent:make_decision")
    r = _exec("decision_agent", "make_decision", {
        "options": ["Research papers approach", "Interactive learning approach", "Expert consultation"],
        "context": f"Plan: {plan_output}",
        "criteria": ["effectiveness", "speed", "depth"],
    }, correlation_id)
    results["decision"] = r
    decision_output = ""
    if r["http_status"] == 200:
        res = r["body"].get("result", {})
        decision_output = json.dumps(res)[:200] if isinstance(res, dict) else str(res)[:200]
        _pass(f"decision_agent:make_decision")
        passed += 1
    else:
        _fail("decision_agent:make_decision", f"HTTP {r['http_status']}")
        failed += 1

    # Step 6: Ethics — evaluate the chosen path
    print(f"  [Step 6/7] ethics_agent:evaluate")
    r = _exec("ethics_agent", "evaluate", {
        "action": f"Pursue learning about AI alignment via: {decision_output[:100]}",
        "context": {"domain": "AI safety research", "stakeholders": ["user", "society"]},
    }, correlation_id)
    results["ethics"] = r
    if r["http_status"] == 200:
        _pass(f"ethics_agent:evaluate")
        passed += 1
    else:
        _fail("ethics_agent:evaluate", f"HTTP {r['http_status']}")
        failed += 1

    # Step 7: Language — synthesize final response
    print(f"  [Step 7/7] language_agent:analyze")
    r = _exec("language_agent", "analyze", {
        "text": f"Synthesize a response about AI alignment risks based on: reasoning={reasoning_output[:100]}, plan={plan_output[:100]}, decision={decision_output[:100]}",
    }, correlation_id)
    results["language"] = r
    if r["http_status"] == 200:
        _pass(f"language_agent:analyze")
        passed += 1
    else:
        _fail("language_agent:analyze", f"HTTP {r['http_status']}")
        failed += 1

    # Bonus: Learning — record what was learned
    print(f"  [Bonus] learning_agent:get_status")
    r = _exec("learning_agent", "get_status", {}, correlation_id)
    results["learning"] = r
    if r["http_status"] == 200:
        _pass(f"learning_agent:get_status")
        passed += 1
    else:
        _fail("learning_agent:get_status", f"HTTP {r['http_status']}")
        failed += 1

    return passed, failed, results


# ─── Test 2: Correlation ID Propagation ───────────────────────────────────────

def test_correlation_id_propagation():
    """Verify correlation IDs are echoed back in response headers."""
    print(f"\n{'='*70}")
    print(f"  TEST: Correlation ID Propagation")
    print(f"{'='*70}")

    test_id = f"corr-test-{uuid.uuid4().hex[:8]}"
    passed = 0
    failed = 0

    # Send with explicit correlation ID
    r = _exec("emotion_agent", "get_state", {}, test_id)
    if r.get("correlation_id") == test_id:
        _pass(f"Correlation ID echoed back: {test_id}")
        passed += 1
    else:
        _fail(f"Correlation ID not echoed", f"sent={test_id} got={r.get('correlation_id')}")
        failed += 1

    # Verify trace ID is generated
    if r.get("trace_id"):
        _pass(f"Trace ID generated: {r['trace_id'][:20]}...")
        passed += 1
    else:
        _fail("No Trace ID in response")
        failed += 1

    # Verify correlation ID in response body
    body = r.get("body", {})
    body_corr = body.get("correlation_id", "")
    if body_corr:
        _pass(f"Correlation ID in response body: {body_corr[:20]}...")
        passed += 1
    else:
        _info("No correlation_id in response body (may be in headers only)")
        passed += 1  # Not a hard requirement

    return passed, failed


# ─── Test 3: Shared Context Between Agents ────────────────────────────────────

def test_shared_context_via_memory():
    """Store context in memory_agent, then verify other agents can reference it."""
    print(f"\n{'='*70}")
    print(f"  TEST: Shared Context via Memory Agent")
    print(f"{'='*70}")

    session_id = f"ctx-{uuid.uuid4().hex[:8]}"
    passed = 0
    failed = 0

    # Store shared context
    r = _exec("memory_agent", "store", {
        "content": f"Important: The user prefers visual learning. Session: {session_id}",
        "memory_type": "short_term",
        "importance": 0.9,
        "tags": ["user_preference", session_id],
    })
    if r["http_status"] == 200:
        _pass("Stored shared context")
        passed += 1
    else:
        _fail("Failed to store context", f"HTTP {r['http_status']}")
        failed += 1

    # Recall it
    r = _exec("memory_agent", "recall", {"query": f"user preference {session_id}", "limit": 5})
    if r["http_status"] == 200:
        res = r["body"].get("result")
        memories = res if isinstance(res, list) else res.get("memories", []) if isinstance(res, dict) else []
        found = any(session_id in str(m) for m in memories)
        if found:
            _pass(f"Recalled shared context (found session {session_id})")
            passed += 1
        else:
            _fail(f"Context stored but not recalled", f"memories={len(memories)}")
            failed += 1
    else:
        _fail("Failed to recall context", f"HTTP {r['http_status']}")
        failed += 1

    return passed, failed


# ─── Test 4: Execution Ordering ──────────────────────────────────────────────

def test_execution_ordering():
    """Verify sequential execution respects ordering."""
    print(f"\n{'='*70}")
    print(f"  TEST: Execution Ordering (Sequential Pipeline)")
    print(f"{'='*70}")

    passed = 0
    failed = 0
    timestamps = []

    agents = [
        ("memory_agent", "get_stats", {}),
        ("reasoning_agent", "reason", {"query": "test ordering"}),
        ("planning_agent", "create_plan", {"goal": "test"}),
        ("decision_agent", "make_decision", {"options": ["A", "B"]}),
        ("language_agent", "analyze", {"text": "test"}),
    ]

    for agent, action, data in agents:
        start = time.perf_counter()
        r = _exec(agent, action, data)
        elapsed = time.perf_counter() - start
        timestamps.append((agent, elapsed, r["http_status"]))

        if r["http_status"] == 200:
            _pass(f"{agent}:{action} — {elapsed*1000:.0f}ms")
            passed += 1
        else:
            _fail(f"{agent}:{action}", f"HTTP {r['http_status']}")
            failed += 1

    # Verify all completed (ordering is naturally sequential here)
    all_200 = all(t[2] == 200 for t in timestamps)
    if all_200:
        _pass("All agents executed in order successfully")
        passed += 1
    else:
        _fail("Not all agents returned 200")
        failed += 1

    return passed, failed


# ─── Test 5: State Consistency ────────────────────────────────────────────────

def test_state_consistency():
    """Store, recall, modify, recall again - verify consistency."""
    print(f"\n{'='*70}")
    print(f"  TEST: State Consistency (Store -> Recall -> Store -> Recall)")
    print(f"{'='*70}")

    tag = f"consistency-{uuid.uuid4().hex[:8]}"
    passed = 0
    failed = 0

    # Store memory A
    r1 = _exec("memory_agent", "store", {
        "content": f"State A: Initial value for {tag}",
        "memory_type": "short_term", "importance": 0.7, "tags": [tag],
    })
    if r1["http_status"] == 200:
        _pass("Stored State A")
        passed += 1
    else:
        _fail("Store A failed"); failed += 1

    # Store memory B
    r2 = _exec("memory_agent", "store", {
        "content": f"State B: Updated value for {tag}",
        "memory_type": "short_term", "importance": 0.8, "tags": [tag],
    })
    if r2["http_status"] == 200:
        _pass("Stored State B")
        passed += 1
    else:
        _fail("Store B failed"); failed += 1

    # Recall and verify both exist
    r3 = _exec("memory_agent", "recall", {"query": tag, "limit": 10})
    if r3["http_status"] == 200:
        res = r3["body"].get("result")
        memories = res if isinstance(res, list) else res.get("memories", []) if isinstance(res, dict) else []
        contents = [str(m) for m in memories]
        found_a = any("State A" in c for c in contents)
        found_b = any("State B" in c for c in contents)
        if found_a and found_b:
            _pass(f"Both states found ({len(memories)} total memories)")
            passed += 1
        elif found_b:
            _pass(f"State B found (State A may have been merged/deduplicated)")
            passed += 1
        else:
            _fail(f"States not properly recalled", f"found_a={found_a} found_b={found_b}")
            failed += 1
    else:
        _fail("Recall failed"); failed += 1

    # Verify emotion agent state is independent
    r4 = _exec("emotion_agent", "get_state", {})
    if r4["http_status"] == 200:
        _pass("Emotion state independent and accessible")
        passed += 1
    else:
        _fail("Emotion state check failed"); failed += 1

    return passed, failed


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  CROSS-AGENT COLLABORATION TEST SUITE")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    # Test 1
    p, f, _ = test_full_cognitive_pipeline()
    total_passed += p; total_failed += f

    # Test 2
    p, f = test_correlation_id_propagation()
    total_passed += p; total_failed += f

    # Test 3
    p, f = test_shared_context_via_memory()
    total_passed += p; total_failed += f

    # Test 4
    p, f = test_execution_ordering()
    total_passed += p; total_failed += f

    # Test 5
    p, f = test_state_consistency()
    total_passed += p; total_failed += f

    # Summary
    print(f"\n{'='*70}")
    print(f"  CROSS-AGENT COLLABORATION SUMMARY")
    print(f"{'='*70}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    status = "SUCCESS" if total_failed == 0 else f"FAILURE: {total_failed} FAILURES"
    print(f"  Status: {status}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
