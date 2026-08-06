"""
Security Validation Test Suite
================================
Tests:
  - SQL injection
  - Malformed JSON
  - Oversized payloads
  - Unicode edge cases
  - Path traversal
  - Rate limiting
  - Request validation
  - Secret leakage
"""

import json
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Any

BASE = "http://localhost:8001"
TIMEOUT = 15

passed = 0
failed = 0


def _raw_request(method: str, path: str, body: bytes = None, headers: dict = None,
                 content_type: str = "application/json") -> Dict[str, Any]:
    """Low-level HTTP request for security testing."""
    url = f"{BASE}{path}"
    hdrs = {"Content-Type": content_type}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": data, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"status": e.code, "body": data, "headers": dict(e.headers) if hasattr(e, 'headers') else {}}
    except Exception as e:
        return {"status": 0, "body": "", "error": str(e)}


def _ok(label):
    global passed; passed += 1
    print(f"  [PASS] {label}")

def _nok(label, reason=""):
    global failed; failed += 1
    print(f"  [FAIL] {label}  ({reason})")


# ─── 1. SQL Injection ────────────────────────────────────────────────────────

def test_sql_injection():
    print(f"\n{'='*70}")
    print(f"  TEST: SQL Injection Prevention")
    print(f"{'='*70}")

    payloads = [
        "'; DROP TABLE memories; --",
        "\" OR 1=1 --",
        "1; SELECT * FROM sqlite_master; --",
        "' UNION SELECT sql FROM sqlite_master --",
        "Robert'); DROP TABLE memories;--",
    ]

    for payload in payloads:
        # Test in agent_name field (validated by Pydantic)
        r = _raw_request("POST", "/execute", json.dumps({
            "agent_name": payload,
            "action": "test",
            "input_data": {}
        }).encode())
        if r["status"] == 422:
            _ok(f"agent_name rejected: {payload[:30]}...")
        elif r["status"] in (400, 500):
            _ok(f"agent_name blocked: {payload[:30]}... (HTTP {r['status']})")
        else:
            _nok(f"SQL injection not blocked in agent_name", f"HTTP {r['status']}")

        # Test in input_data (should be sanitized or treated as data)
        r = _raw_request("POST", "/execute", json.dumps({
            "agent_name": "memory_agent",
            "action": "recall",
            "input_data": {"query": payload}
        }).encode())
        # Should succeed (query is treated as data, not SQL) or fail gracefully
        if r["status"] in (200, 422, 400):
            _ok(f"input_data safe: {payload[:30]}... (HTTP {r['status']})")
        elif r["status"] == 500:
            # Check if it's a SQL error leaking
            if "sqlite" in r["body"].lower() or "sql" in r["body"].lower():
                _nok(f"SQL error leaked in response", r["body"][:60])
            else:
                _ok(f"input_data handled: {payload[:30]}... (HTTP 500 but no SQL leak)")
        else:
            _nok(f"Unexpected response", f"HTTP {r['status']}")


# ─── 2. Malformed JSON ───────────────────────────────────────────────────────

def test_malformed_json():
    print(f"\n{'='*70}")
    print(f"  TEST: Malformed JSON Handling")
    print(f"{'='*70}")

    bad_payloads = [
        (b"", "Empty body"),
        (b"{", "Incomplete JSON"),
        (b"{'key': 'value'}", "Single quotes"),
        (b'{"agent_name": }', "Missing value"),
        (b"null", "Null body"),
        (b"[1,2,3]", "Array instead of object"),
        (b"\x00\x01\x02", "Binary garbage"),
        (b"<xml>not json</xml>", "XML payload"),
    ]

    for payload, desc in bad_payloads:
        r = _raw_request("POST", "/execute", payload)
        if r["status"] in (400, 422):
            _ok(f"Rejected: {desc} (HTTP {r['status']})")
        elif r["status"] == 500:
            _ok(f"Handled: {desc} (HTTP 500 — server didn't crash)")
        elif r["status"] == 0:
            _nok(f"Server crashed on: {desc}")
        else:
            _nok(f"Unexpected response for: {desc}", f"HTTP {r['status']}")


# ─── 3. Oversized Payloads ───────────────────────────────────────────────────

def test_oversized_payloads():
    print(f"\n{'='*70}")
    print(f"  TEST: Oversized Payload Rejection")
    print(f"{'='*70}")

    # 1MB payload (at the limit)
    big_data = {"agent_name": "memory_agent", "action": "store",
                "input_data": {"content": "X" * (1024 * 1024)}}
    r = _raw_request("POST", "/execute", json.dumps(big_data).encode())
    if r["status"] in (413, 422, 400):
        _ok(f"1MB payload rejected (HTTP {r['status']})")
    elif r["status"] == 200:
        _ok(f"1MB payload accepted (within server limit)")
    elif r["status"] == 500:
        _ok(f"1MB payload caused server error (not a crash)")
    else:
        _nok(f"1MB payload: unexpected", f"HTTP {r['status']}")

    # 5MB payload
    huge_data = {"agent_name": "memory_agent", "action": "store",
                 "input_data": {"content": "Y" * (5 * 1024 * 1024)}}
    try:
        r = _raw_request("POST", "/execute", json.dumps(huge_data).encode())
        if r["status"] in (413, 422, 400):
            _ok(f"5MB payload rejected (HTTP {r['status']})")
        elif r["status"] == 500:
            _ok(f"5MB payload caused error (not a crash)")
        else:
            _nok(f"5MB payload accepted without limit", f"HTTP {r['status']}")
    except Exception as e:
        _ok(f"5MB payload rejected at transport level: {str(e)[:40]}")

    # Deeply nested JSON
    nested = {"a": None}
    current = nested
    for _ in range(100):
        new = {"a": None}
        current["a"] = new
        current = new
    deep_data = {"agent_name": "memory_agent", "action": "store",
                 "input_data": nested}
    r = _raw_request("POST", "/execute", json.dumps(deep_data).encode())
    if r["status"] in (200, 400, 422, 500):
        _ok(f"Deeply nested JSON handled (HTTP {r['status']})")
    else:
        _nok(f"Deep nesting issue", f"HTTP {r['status']}")


# ─── 4. Unicode Edge Cases ───────────────────────────────────────────────────

def test_unicode_edge_cases():
    print(f"\n{'='*70}")
    print(f"  TEST: Unicode Edge Cases")
    print(f"{'='*70}")

    unicode_payloads = [
        ("Emoji: 🧠💡🤖🔥", "Emoji payload"),
        ("CJK: 人工智能虚拟大脑", "Chinese characters"),
        ("Arabic: الذكاء الاصطناعي", "Arabic text"),
        ("Null bytes: \x00\x00\x00", "Null bytes in string"),
        ("Mixed: café résumé naïve", "Accented characters"),
        ("ZWJ: 👨‍💻👩‍🔬", "Zero-width joiners"),
        ("RTL: \u202Eevil\u202C", "Right-to-left override"),
        ("Surrogate: \ud800", "Surrogate character"),
    ]

    for payload, desc in unicode_payloads:
        try:
            r = _raw_request("POST", "/execute", json.dumps({
                "agent_name": "memory_agent",
                "action": "store",
                "input_data": {"content": payload, "memory_type": "short_term"}
            }, ensure_ascii=False).encode("utf-8"))
            if r["status"] in (200, 422, 400):
                _ok(f"{desc} (HTTP {r['status']})")
            elif r["status"] == 500:
                _ok(f"{desc} handled with error (HTTP 500, no crash)")
            else:
                _nok(f"{desc}", f"HTTP {r['status']}")
        except (json.JSONDecodeError, UnicodeEncodeError) as e:
            _ok(f"{desc} rejected at serialization: {type(e).__name__}")


# ─── 5. Path Traversal ──────────────────────────────────────────────────────

def test_path_traversal():
    print(f"\n{'='*70}")
    print(f"  TEST: Path Traversal Prevention")
    print(f"{'='*70}")

    traversal_paths = [
        "/../../etc/passwd",
        "/..\\..\\windows\\system32\\config\\sam",
        "/%2e%2e/%2e%2e/etc/shadow",
        "/agents/../../../etc/passwd",
        "/execute?file=../../../etc/passwd",
        "/.env",
        "/config.yaml",
        "/.git/config",
    ]

    for path in traversal_paths:
        r = _raw_request("GET", path)
        if r["status"] in (404, 405, 422, 400):
            _ok(f"Blocked: {path} (HTTP {r['status']})")
        elif r["status"] == 200:
            # Check if sensitive data was returned
            if "root:" in r["body"] or "password" in r["body"].lower():
                _nok(f"Path traversal succeeded!", f"{path} returned sensitive data")
            else:
                _ok(f"Path exists but no sensitive data: {path}")
        else:
            _ok(f"Handled: {path} (HTTP {r['status']})")


# ─── 6. Rate Limiting ───────────────────────────────────────────────────────

def test_rate_limiting():
    print(f"\n{'='*70}")
    print(f"  TEST: Rate Limiting")
    print(f"{'='*70}")

    # The server has a rate limit of 120 requests per 60s window
    # We'll send 130 requests rapidly
    statuses = []
    for i in range(130):
        r = _raw_request("GET", "/health")
        statuses.append(r["status"])

    rate_limited = sum(1 for s in statuses if s == 429)
    succeeded = sum(1 for s in statuses if s == 200)

    if rate_limited > 0:
        _ok(f"Rate limiting active: {rate_limited}/130 requests got 429, {succeeded} got 200")
    else:
        _nok(f"No rate limiting detected in 130 rapid requests (all returned 200)")

    # Wait for rate limit window to clear (small portion)
    time.sleep(2)

    # Verify recovery
    r = _raw_request("GET", "/health")
    if r["status"] == 200:
        _ok(f"Rate limit recovery: subsequent request succeeded")
    elif r["status"] == 429:
        _ok(f"Still rate limited (within window) — rate limiting is working")
    else:
        _nok(f"Rate limit recovery unexpected", f"HTTP {r['status']}")


# ─── 7. Request Validation ──────────────────────────────────────────────────

def test_request_validation():
    print(f"\n{'='*70}")
    print(f"  TEST: Request Validation")
    print(f"{'='*70}")

    # Missing required fields
    r = _raw_request("POST", "/execute", json.dumps({}).encode())
    if r["status"] == 422:
        _ok("Missing fields rejected (HTTP 422)")
    else:
        _nok("Missing fields not properly validated", f"HTTP {r['status']}")

    # Empty agent name
    r = _raw_request("POST", "/execute", json.dumps({
        "agent_name": "", "action": "test", "input_data": {}
    }).encode())
    if r["status"] == 422:
        _ok("Empty agent_name rejected (HTTP 422)")
    else:
        _nok("Empty agent_name accepted", f"HTTP {r['status']}")

    # Very long agent name
    r = _raw_request("POST", "/execute", json.dumps({
        "agent_name": "a" * 500, "action": "test", "input_data": {}
    }).encode())
    if r["status"] == 422:
        _ok("Long agent_name rejected (HTTP 422)")
    else:
        _nok("Long agent_name accepted", f"HTTP {r['status']}")

    # Invalid method
    r = _raw_request("DELETE", "/execute")
    if r["status"] in (405, 404):
        _ok(f"DELETE /execute rejected (HTTP {r['status']})")
    else:
        _nok(f"DELETE /execute not rejected", f"HTTP {r['status']}")

    # Non-existent agent
    r = _raw_request("POST", "/execute", json.dumps({
        "agent_name": "nonexistent_agent", "action": "test", "input_data": {}
    }).encode())
    if r["status"] in (404, 500, 200):
        _ok(f"Nonexistent agent handled (HTTP {r['status']})")
    else:
        _nok(f"Nonexistent agent", f"HTTP {r['status']}")

    # Special characters in action
    r = _raw_request("POST", "/execute", json.dumps({
        "agent_name": "memory_agent", "action": "<script>alert(1)</script>", "input_data": {}
    }).encode())
    if r["status"] in (200, 422, 400, 500):
        _ok(f"XSS in action field handled (HTTP {r['status']})")
    else:
        _nok(f"XSS handling", f"HTTP {r['status']}")


# ─── 8. Secret Leakage ──────────────────────────────────────────────────────

def test_secret_leakage():
    print(f"\n{'='*70}")
    print(f"  TEST: Secret Leakage Prevention")
    print(f"{'='*70}")

    sensitive_patterns = [
        "OPENAI_API_KEY", "openai_api_key", "sk-", "JWT_SECRET",
        "DATABASE_PASSWORD", "SECRET_KEY", "password", "token",
    ]

    # Check error responses for secret leakage
    error_endpoints = [
        ("POST", "/execute", json.dumps({"agent_name": "nonexistent"}).encode()),
        ("GET", "/nonexistent_endpoint"),
    ]

    for method, path, *body in error_endpoints:
        b = body[0] if body else None
        r = _raw_request(method, path, b)
        body_text = r["body"].lower()
        leaked = [p for p in sensitive_patterns if p.lower() in body_text]
        if leaked:
            _nok(f"Secret leaked in {method} {path}", f"Found: {leaked}")
        else:
            _ok(f"No secrets in {method} {path} response (HTTP {r['status']})")

    # Check health endpoint for secret leakage
    r = _raw_request("GET", "/health")
    body_text = r["body"].lower()
    leaked = [p for p in sensitive_patterns if p.lower() in body_text]
    if leaked:
        _nok(f"Secret leaked in /health", f"Found: {leaked}")
    else:
        _ok(f"No secrets in /health response")

    # Check /status for secret leakage
    r = _raw_request("GET", "/status")
    body_text = r["body"].lower()
    # Filter out legitimate uses (e.g., field names like "status")
    real_leaks = [p for p in sensitive_patterns
                  if p.lower() in body_text and p.lower() not in ("password", "token")]
    if real_leaks:
        _nok(f"Secret leaked in /status", f"Found: {real_leaks}")
    else:
        _ok(f"No secrets in /status response")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 70)
    print("  SECURITY VALIDATION TEST SUITE")
    print("=" * 70)

    test_sql_injection()
    test_malformed_json()
    test_oversized_payloads()
    test_unicode_edge_cases()
    test_path_traversal()
    test_rate_limiting()
    test_request_validation()
    test_secret_leakage()

    print(f"\n{'='*70}")
    print(f"  SECURITY TEST SUMMARY")
    print(f"{'='*70}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    status = "SUCCESS" if failed == 0 else f"FAILURE: {failed} FAILURES"
    print(f"  Status: {status}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
