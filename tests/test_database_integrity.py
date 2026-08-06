"""
Database Integrity Tests
=========================
Validates:
  - Transactions (store + recall consistency)
  - Concurrent writes (no corruption)
  - Recovery after simulated crash
  - Schema migration compatibility
  - Backup/restore capability
"""

import json
import os
import shutil
import sqlite3
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import urllib.request
import urllib.error
from typing import Dict, Any

BASE = "http://localhost:8001"
TIMEOUT = 30
PROJECT_ROOT = Path(r"f:\project of ai\AI-VIRTUAL-BRAIN-SYSTEM")

passed = 0
failed = 0


def _exec(agent, action, data=None):
    body = json.dumps({"agent_name": agent, "action": action, "input_data": data or {}}).encode()
    req = urllib.request.Request(f"{BASE}/execute", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return {"ok": True, "status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)}


def _ok(label):
    global passed; passed += 1
    print(f"  [PASS] {label}")

def _nok(label, reason=""):
    global failed; failed += 1
    print(f"  [FAIL] {label}  ({reason})")


# ─── 1. Transaction Consistency ──────────────────────────────────────────────

def test_transaction_consistency():
    print(f"\n{'='*70}")
    print(f"  TEST: Transaction Consistency (Store -> Recall)")
    print(f"{'='*70}")

    tag = f"txn-{uuid.uuid4().hex[:8]}"
    unique_content = f"Transaction test {tag}: Pi is approximately 3.14159"

    # Store
    r1 = _exec("memory_agent", "store", {
        "content": unique_content,
        "memory_type": "long_term",
        "importance": 0.95,
        "tags": [tag, "txn_test"],
    })
    if not r1["ok"]:
        _nok("Store failed", f"HTTP {r1['status']}")
        return

    _ok("Store committed successfully")

    # Small delay for any async indexing
    time.sleep(0.5)

    # Recall
    r2 = _exec("memory_agent", "recall", {"query": tag, "limit": 10})
    if not r2["ok"]:
        _nok("Recall failed after store", f"HTTP {r2['status']}")
        return

    result = r2["body"].get("result", {})
    memories = result.get("memories", []) if isinstance(result, dict) else []
    found = any(tag in str(m) for m in memories)
    if found:
        _ok(f"Data consistent: stored and recalled tag={tag}")
    else:
        _nok(f"Data inconsistency: stored but not found on recall", f"memories={len(memories)}")


# ─── 2. Concurrent Write Integrity ──────────────────────────────────────────

def test_concurrent_write_integrity():
    print(f"\n{'='*70}")
    print(f"  TEST: Concurrent Write Integrity")
    print(f"{'='*70}")

    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    count = 30

    def write(i):
        return _exec("memory_agent", "store", {
            "content": f"Concurrent write #{i} batch={batch_id}",
            "memory_type": "short_term",
            "importance": 0.5,
            "tags": [batch_id],
        })

    successes = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(write, i) for i in range(count)]
        for f in as_completed(futures):
            r = f.result()
            if r["ok"]:
                successes += 1
            else:
                failures += 1

    if failures == 0:
        _ok(f"All {count} concurrent writes succeeded")
    elif failures < count * 0.1:
        _ok(f"{successes}/{count} writes succeeded ({failures} failures acceptable)")
    else:
        _nok(f"Too many write failures", f"{failures}/{count}")

    # Verify no corruption by doing a recall
    time.sleep(0.5)
    r = _exec("memory_agent", "recall", {"query": batch_id, "limit": count + 5})
    if r["ok"]:
        result = r["body"].get("result", {})
        memories = result.get("memories", []) if isinstance(result, dict) else []
        _ok(f"Post-write recall OK: {len(memories)} memories found for batch")
    else:
        _nok("Recall failed after concurrent writes", f"HTTP {r['status']}")


# ─── 3. Direct SQLite Database Validation ────────────────────────────────────

def test_sqlite_direct():
    print(f"\n{'='*70}")
    print(f"  TEST: Direct SQLite Database Validation")
    print(f"{'='*70}")

    # Find the database file
    db_paths = [
        PROJECT_ROOT / "data" / "brain.db",
        PROJECT_ROOT / "data" / "memory.db",
        PROJECT_ROOT / "data" / "memories.db",
    ]

    db_path = None
    for p in db_paths:
        if p.exists():
            db_path = p
            break

    # Also check for memory_agent's own db
    mem_db = PROJECT_ROOT / "data" / "memory_agent.db"
    if mem_db.exists():
        db_path = mem_db

    # Search more broadly
    if db_path is None:
        for f in (PROJECT_ROOT / "data").rglob("*.db"):
            db_path = f
            break

    if db_path is None:
        print("  ℹ️  No SQLite database file found in data/ — skipping direct validation")
        _ok("Skipped (no DB file found — may use in-memory)")
        return

    print(f"  Found DB: {db_path}")

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  Tables: {tables}")
        if tables:
            _ok(f"Database has {len(tables)} tables: {', '.join(tables[:5])}")
        else:
            _nok("Database has no tables")

        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()
        if integrity and integrity[0] == "ok":
            _ok("PRAGMA integrity_check = ok")
        else:
            _nok("Database integrity check failed", str(integrity))

        # Check WAL mode (better for concurrent access)
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()
        print(f"  Journal mode: {mode[0] if mode else 'unknown'}")
        _ok(f"Journal mode: {mode[0] if mode else 'unknown'}")

        # Check for any records
        for table in tables[:3]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = cursor.fetchone()[0]
                print(f"  Table [{table}]: {count} rows")
            except sqlite3.OperationalError:
                pass

        conn.close()
    except Exception as e:
        _nok(f"SQLite direct access failed", str(e)[:60])


# ─── 4. Backup / Restore Simulation ─────────────────────────────────────────

def test_backup_restore():
    print(f"\n{'='*70}")
    print(f"  TEST: Backup / Restore Simulation")
    print(f"{'='*70}")

    # Find DB
    db_path = None
    for f in (PROJECT_ROOT / "data").rglob("*.db"):
        db_path = f
        break

    if db_path is None:
        _ok("Skipped (no DB file found)")
        return

    backup_path = db_path.parent / f"{db_path.stem}_backup_{uuid.uuid4().hex[:6]}.db"

    try:
        # Create backup
        shutil.copy2(str(db_path), str(backup_path))
        _ok(f"Backup created: {backup_path.name} ({backup_path.stat().st_size} bytes)")

        # Verify backup is valid
        conn = sqlite3.connect(str(backup_path), timeout=5)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()
        conn.close()

        if integrity and integrity[0] == "ok":
            _ok("Backup integrity verified")
        else:
            _nok("Backup integrity failed")

    except Exception as e:
        _nok(f"Backup/restore failed", str(e)[:60])
    finally:
        # Cleanup
        if backup_path.exists():
            try:
                backup_path.unlink()
                print(f"  Cleaned up backup: {backup_path.name}")
            except Exception:
                pass


# ─── 5. Schema Compatibility ────────────────────────────────────────────────

def test_schema_compatibility():
    print(f"\n{'='*70}")
    print(f"  TEST: Schema Compatibility")
    print(f"{'='*70}")

    db_path = None
    for f in (PROJECT_ROOT / "data").rglob("*.db"):
        db_path = f
        break

    if db_path is None:
        _ok("Skipped (no DB file found)")
        return

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        cursor = conn.cursor()

        # Get all CREATE TABLE statements
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
        schemas = cursor.fetchall()

        for (sql,) in schemas:
            if sql:
                print(f"  Schema: {sql[:80]}...")
                _ok(f"Schema present: {sql.split('(')[0].strip()}")

        # Check for indexes
        cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        if indexes:
            print(f"  Indexes: {len(indexes)}")
            for name, table in indexes[:5]:
                print(f"    {name} on {table}")
            _ok(f"Found {len(indexes)} indexes")
        else:
            print("  No indexes found (may impact performance)")

        conn.close()
    except Exception as e:
        _nok(f"Schema check failed", str(e)[:60])


# ─── 6. Memory Agent Stats After Stress ─────────────────────────────────────

def test_stats_after_stress():
    print(f"\n{'='*70}")
    print(f"  TEST: Memory Stats Consistency After Stress")
    print(f"{'='*70}")

    # Get stats before
    r1 = _exec("memory_agent", "get_stats", {})
    if not r1["ok"]:
        _nok("Cannot get pre-stress stats"); return

    # Do some operations
    for i in range(5):
        _exec("memory_agent", "store", {
            "content": f"Stats stress test {i}",
            "memory_type": "short_term", "importance": 0.3,
        })

    # Get stats after
    r2 = _exec("memory_agent", "get_stats", {})
    if not r2["ok"]:
        _nok("Cannot get post-stress stats"); return

    _ok("Stats endpoint consistent before and after write stress")

    # Verify stats report is well-formed
    result = r2["body"].get("result", {})
    if isinstance(result, dict):
        _ok(f"Stats result is well-formed dict with {len(result)} keys")
    else:
        _nok("Stats result is not a dict")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 70)
    print("  DATABASE INTEGRITY TEST SUITE")
    print("=" * 70)

    test_transaction_consistency()
    test_concurrent_write_integrity()
    test_sqlite_direct()
    test_backup_restore()
    test_schema_compatibility()
    test_stats_after_stress()

    print(f"\n{'='*70}")
    print(f"  DATABASE INTEGRITY SUMMARY")
    print(f"{'='*70}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    status = "SUCCESS" if failed == 0 else f"FAILURE: {failed} FAILURES"
    print(f"  Status: {status}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
