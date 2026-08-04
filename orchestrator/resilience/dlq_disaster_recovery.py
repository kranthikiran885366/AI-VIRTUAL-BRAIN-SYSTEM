"""
Phase 15 — Dead-Letter Queue & Disaster Recovery.

DLQ captures failed messages for later retry or manual inspection.
DisasterRecoveryManager manages backup manifests, integrity verification,
and failover simulation for enterprise resilience.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "DLQEntry",
    "DeadLetterQueue",
    "BackupManifest",
    "DisasterRecoveryManager",
]


# ─── DLQ Entry ───────────────────────────────────────────────────────────────


@dataclass
class DLQEntry:
    """A single dead-letter queue entry representing a failed message."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_message: Dict[str, Any] = field(default_factory=dict)
    error_reason: str = ""
    source_queue: str = ""
    failed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | retried | discarded | recovered

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DLQEntry":
        data = dict(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Dead-Letter Queue ──────────────────────────────────────────────────────


class DeadLetterQueue:
    """Thread-safe in-memory dead-letter queue with retry and purge support."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._lock = Lock()
        self._entries: Dict[str, DLQEntry] = {}
        self._order: List[str] = []  # insertion order
        self._max_size = max_size

    def enqueue(
        self,
        message: Dict[str, Any],
        error_reason: str,
        source_queue: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DLQEntry:
        entry = DLQEntry(
            original_message=message,
            error_reason=error_reason,
            source_queue=source_queue,
            metadata=metadata or {},
        )
        with self._lock:
            if len(self._entries) >= self._max_size:
                # Evict oldest discarded/recovered entries first
                self._evict_old()
            self._entries[entry.entry_id] = entry
            self._order.append(entry.entry_id)
        logger.info(
            "dlq.enqueued entry_id=%s source=%s reason=%s",
            entry.entry_id, source_queue, error_reason[:80],
        )
        return entry

    def dequeue(self, count: int = 1) -> List[DLQEntry]:
        with self._lock:
            result = []
            for eid in self._order:
                if len(result) >= count:
                    break
                entry = self._entries.get(eid)
                if entry and entry.status == "pending":
                    result.append(entry)
            return result

    def retry_entry(self, entry_id: str) -> Optional[DLQEntry]:
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return None
            entry.retry_count += 1
            if entry.retry_count > entry.max_retries:
                entry.status = "discarded"
                logger.warning("dlq.max_retries_exceeded entry_id=%s", entry_id)
            else:
                entry.status = "retried"
            return entry

    def discard_entry(self, entry_id: str) -> bool:
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return False
            entry.status = "discarded"
            return True

    def recover_entry(self, entry_id: str) -> bool:
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return False
            entry.status = "recovered"
            return True

    def get_entry(self, entry_id: str) -> Optional[DLQEntry]:
        with self._lock:
            return self._entries.get(entry_id)

    def list_entries(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[DLQEntry]:
        with self._lock:
            entries = list(self._entries.values())
        if status:
            entries = [e for e in entries if e.status == status]
        return entries[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._entries.values())
        by_status: Dict[str, int] = defaultdict(int)
        for e in entries:
            by_status[e.status] += 1
        oldest = min((e.failed_at for e in entries), default=None) if entries else None
        return {
            "total_size": len(entries),
            "by_status": dict(by_status),
            "oldest_entry": oldest,
            "max_size": self._max_size,
        }

    def purge(self, older_than_hours: int = 72) -> int:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        ).isoformat()
        removed = 0
        with self._lock:
            to_remove = []
            for eid, entry in self._entries.items():
                if entry.status in ("discarded", "recovered") and entry.failed_at < cutoff:
                    to_remove.append(eid)
            for eid in to_remove:
                del self._entries[eid]
                removed += 1
            self._order = [eid for eid in self._order if eid in self._entries]
        if removed:
            logger.info("dlq.purged count=%d older_than_hours=%d", removed, older_than_hours)
        return removed

    def _evict_old(self) -> None:
        """Evict oldest terminal entries when at capacity. Must be called under lock."""
        for eid in list(self._order):
            if len(self._entries) < self._max_size:
                break
            entry = self._entries.get(eid)
            if entry and entry.status in ("discarded", "recovered"):
                del self._entries[eid]
                self._order.remove(eid)


# ─── Backup Manifest ────────────────────────────────────────────────────────


@dataclass
class BackupManifest:
    """Represents a logical backup of system components."""
    backup_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    components: List[str] = field(default_factory=list)
    size_bytes: int = 0
    checksum: str = ""
    status: str = "pending"  # pending | completed | failed | verified
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupManifest":
        data = dict(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Disaster Recovery Manager ──────────────────────────────────────────────


class DisasterRecoveryManager:
    """Enterprise disaster recovery manager with backup manifests and failover simulation."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._backups: Dict[str, BackupManifest] = {}
        self._failover_history: List[Dict[str, Any]] = []

    def create_backup(
        self,
        components: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackupManifest:
        manifest = BackupManifest(
            components=components,
            metadata=metadata or {},
        )
        # Simulate checksum computation
        raw = f"{manifest.backup_id}|{'|'.join(components)}|{manifest.created_at}"
        manifest.checksum = hashlib.sha256(raw.encode()).hexdigest()[:32]
        manifest.status = "completed"
        manifest.size_bytes = len(raw.encode()) * 100  # simulated size

        with self._lock:
            self._backups[manifest.backup_id] = manifest
        logger.info(
            "dr.backup_created id=%s components=%s",
            manifest.backup_id, components,
        )
        return manifest

    def verify_backup(self, backup_id: str) -> bool:
        with self._lock:
            manifest = self._backups.get(backup_id)
        if not manifest:
            return False
        raw = f"{manifest.backup_id}|{'|'.join(manifest.components)}|{manifest.created_at}"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:32]
        valid = manifest.checksum == expected
        if valid:
            manifest.status = "verified"
        else:
            manifest.status = "failed"
        logger.info("dr.backup_verified id=%s valid=%s", backup_id, valid)
        return valid

    def list_backups(self, limit: int = 50) -> List[BackupManifest]:
        with self._lock:
            backups = sorted(
                self._backups.values(),
                key=lambda b: b.created_at,
                reverse=True,
            )
        return backups[:limit]

    def get_recovery_status(self) -> Dict[str, Any]:
        with self._lock:
            backups = list(self._backups.values())
        total = len(backups)
        verified = sum(1 for b in backups if b.status == "verified")
        completed = sum(1 for b in backups if b.status in ("completed", "verified"))
        latest = max((b.created_at for b in backups), default=None) if backups else None
        return {
            "total_backups": total,
            "verified_backups": verified,
            "completed_backups": completed,
            "latest_backup": latest,
            "dr_ready": verified > 0,
            "failover_tests": len(self._failover_history),
        }

    def simulate_failover(self) -> Dict[str, Any]:
        start = time.monotonic()
        # Simulate failover steps
        steps = [
            {"step": "detect_failure", "duration_ms": 5.0, "status": "ok"},
            {"step": "elect_new_leader", "duration_ms": 12.0, "status": "ok"},
            {"step": "restore_state", "duration_ms": 25.0, "status": "ok"},
            {"step": "verify_consistency", "duration_ms": 8.0, "status": "ok"},
            {"step": "redirect_traffic", "duration_ms": 3.0, "status": "ok"},
        ]
        total_ms = sum(s["duration_ms"] for s in steps)
        result = {
            "simulation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_failover_time_ms": total_ms,
            "steps": steps,
            "success": True,
            "wall_clock_ms": (time.monotonic() - start) * 1000,
        }
        with self._lock:
            self._failover_history.append(result)
        logger.info("dr.failover_simulated total_ms=%.1f", total_ms)
        return result
