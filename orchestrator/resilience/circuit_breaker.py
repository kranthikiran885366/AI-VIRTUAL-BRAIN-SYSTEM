"""
Phase 15 — Production Circuit Breaker & Bulkhead Isolation.

Implements the circuit-breaker pattern (CLOSED → OPEN → HALF_OPEN → CLOSED)
and bulkhead-isolation pattern for protecting downstream services
from cascading failures.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "CircuitBreakerState",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "BulkheadIsolator",
    "BulkheadFullError",
]


# ─── Custom Exceptions ──────────────────────────────────────────────────────


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is attempted while the circuit breaker is OPEN."""

    def __init__(self, name: str, recovery_remaining: float = 0.0) -> None:
        self.breaker_name = name
        self.recovery_remaining = recovery_remaining
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Recovery in {recovery_remaining:.1f}s."
        )


class BulkheadFullError(RuntimeError):
    """Raised when the bulkhead has no capacity for additional calls."""

    def __init__(self, name: str) -> None:
        self.bulkhead_name = name
        super().__init__(f"Bulkhead '{name}' is full — request rejected.")


# ─── Circuit Breaker State ───────────────────────────────────────────────────


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# ─── Circuit Breaker ────────────────────────────────────────────────────────


class CircuitBreaker:
    """Production circuit breaker with automatic state transitions.

    * CLOSED  → normal operation; failures counted.
    * OPEN    → all calls rejected until *recovery_timeout* elapses.
    * HALF_OPEN → limited probe calls; consecutive successes reset to CLOSED,
                  any failure immediately returns to OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._lock = Lock()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._total_calls = 0
        self._total_failures = 0

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through the circuit breaker."""
        with self._lock:
            self._maybe_transition_to_half_open()
            current_state = self._state
            self._total_calls += 1

            if current_state == CircuitBreakerState.OPEN:
                remaining = self._recovery_remaining()
                raise CircuitBreakerOpenError(self.name, remaining)

            if current_state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, 0.0)
                self._half_open_calls += 1

        # Execute outside the lock
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            self._maybe_transition_to_half_open()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "consecutive_successes": self._consecutive_successes,
                "last_failure_time": self._last_failure_time,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        with self._lock:
            self._transition(CircuitBreakerState.CLOSED)
            logger.info("circuit_breaker.reset name=%s", self.name)

    def force_open(self) -> None:
        with self._lock:
            self._transition(CircuitBreakerState.OPEN)
            self._opened_at = time.monotonic()
            logger.warning("circuit_breaker.force_open name=%s", self.name)

    def force_close(self) -> None:
        with self._lock:
            self._transition(CircuitBreakerState.CLOSED)
            logger.info("circuit_breaker.force_close name=%s", self.name)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_success(self) -> None:
        with self._lock:
            self._success_count += 1
            self._consecutive_successes += 1
            self._failure_count = 0

            if (
                self._state == CircuitBreakerState.HALF_OPEN
                and self._consecutive_successes >= self.success_threshold
            ):
                self._transition(CircuitBreakerState.CLOSED)
                logger.info(
                    "circuit_breaker.recovered name=%s after %d successes",
                    self.name,
                    self._consecutive_successes,
                )

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._consecutive_successes = 0
            self._last_failure_time = time.monotonic()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._transition(CircuitBreakerState.OPEN)
                self._opened_at = time.monotonic()
                logger.warning(
                    "circuit_breaker.half_open_failed name=%s → OPEN", self.name
                )
            elif (
                self._state == CircuitBreakerState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._transition(CircuitBreakerState.OPEN)
                self._opened_at = time.monotonic()
                logger.warning(
                    "circuit_breaker.opened name=%s failures=%d",
                    self.name,
                    self._failure_count,
                )

    def _maybe_transition_to_half_open(self) -> None:
        """Must be called under lock."""
        if self._state == CircuitBreakerState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.recovery_timeout:
                self._transition(CircuitBreakerState.HALF_OPEN)
                self._half_open_calls = 0
                self._consecutive_successes = 0
                logger.info(
                    "circuit_breaker.half_open name=%s after %.1fs",
                    self.name,
                    elapsed,
                )

    def _transition(self, new_state: CircuitBreakerState) -> None:
        """Must be called under lock."""
        old = self._state
        self._state = new_state
        if new_state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0
            self._consecutive_successes = 0
            self._opened_at = None

    def _recovery_remaining(self) -> float:
        """Must be called under lock."""
        if self._opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self.recovery_timeout - elapsed)


# ─── Bulkhead Isolator ──────────────────────────────────────────────────────


class BulkheadIsolator:
    """Limits concurrent access to a resource using a semaphore-based bulkhead.

    Prevents a single service from consuming all available threads/connections.
    """

    def __init__(
        self, name: str, max_concurrent: int = 10, max_queue: int = 50
    ) -> None:
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = Lock()
        self._active = 0
        self._queued = 0
        self._rejected = 0
        self._total_calls = 0

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with bulkhead concurrency limiting."""
        with self._lock:
            self._total_calls += 1
            # Check queue capacity
            pending = self._active + self._queued
            if pending >= self.max_concurrent + self.max_queue:
                self._rejected += 1
                raise BulkheadFullError(self.name)
            self._queued += 1

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            with self._lock:
                self._queued -= 1
                self._rejected += 1
            raise BulkheadFullError(self.name)

        with self._lock:
            self._queued -= 1
            self._active += 1

        try:
            return await func(*args, **kwargs)
        finally:
            self._semaphore.release()
            with self._lock:
                self._active -= 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "active_count": self._active,
                "queued_count": self._queued,
                "max_concurrent": self.max_concurrent,
                "max_queue": self.max_queue,
                "rejected_count": self._rejected,
                "total_calls": self._total_calls,
            }
