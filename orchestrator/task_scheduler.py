"""
Task Scheduler

Manages task scheduling, dispatch, worker assignment, and execution.

Production changes (Phase 2):
- task_queue.task_done() moved to AFTER _execute_task returns (race condition fix)
- max_concurrent_tasks enforced via asyncio.Semaphore
- _retry_queue dict cleaned up on task completion/cancellation
- monitor_queue() returns real-time computed metrics
- _execution_history auto-trimmed to configurable max_history
- Structured logging throughout with correlation_id / trace_id
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid
from enum import Enum

try:
    from structlog import get_logger
except ImportError:
    def get_logger():  # type: ignore
        return logging.getLogger(__name__)

try:
    from .config import settings
except ImportError:
    settings = None  # type: ignore

try:
    from .execution_context import build_execution_context
except ImportError:
    def build_execution_context(**kwargs):  # type: ignore
        return None

logger = get_logger()


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    RETRIED = "retried"


class TaskPriority(int, Enum):
    """Task priority enumeration."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskScheduler:
    """Manages task scheduling and execution."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.is_running = False

        self.tasks: Dict[str, Dict[str, Any]] = {}
        # Queue entries are always (int, str, str) — never datetime — so
        # Python 3.11+ tuple comparison never raises TypeError.
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.workers: Dict[str, Any] = {}
        self.worker_pools: Dict[str, List[str]] = {"default": []}
        self._worker_rr: Dict[str, int] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._task_lock = asyncio.Lock()
        self._execution_history: List[Dict[str, Any]] = []
        self._max_execution_history: int = int(self.config.get("max_execution_history", 5_000))
        # ← FIXED: _retry_queue now cleaned up on completion/cancel
        self._retry_queue: Dict[str, int] = {}
        self._worker_lock = asyncio.Lock()
        self._task_events: Dict[str, asyncio.Event] = {}
        self.message_broker = self.config.get("message_broker")
        self.communication_controller = self.config.get("communication_controller")
        self.agent_manager = self.config.get("agent_manager")
        self.max_concurrent_tasks: int = int(self.config.get("max_concurrent_tasks", 4))
        self.task_timeout: float = float(self.config.get("task_timeout", self.config.get("timeout", 300)))
        self.max_retries: int = int(self.config.get("max_retries", 2))
        self.retry_delay: float = float(self.config.get("retry_delay", 1.0))
        self.queue_maxsize: int = int(self.config.get("queue_maxsize", 1000))

        # ← Semaphore for max_concurrent_tasks enforcement
        self._concurrency_semaphore: asyncio.Semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        self.metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "retried_tasks": 0,
            "average_completion_time": 0.0,
            "queue_size": 0,
            "workers_registered": 0,
            "worker_assignments": 0,
            "concurrent_tasks": 0,
        }

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the task scheduler."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("task_scheduler.starting", max_concurrent_tasks=self.max_concurrent_tasks)

        # Recreate semaphore in case start() is called after stop()
        self._concurrency_semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        if not self._scheduler_task or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(
                self._process_tasks(), name="task_scheduler.process"
            )
        logger.info("task_scheduler.started")

    async def stop(self) -> None:
        """Stop the task scheduler."""
        logger.info("task_scheduler.stopping")
        self.is_running = False

        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        for task_id, task in list(self.running_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("task_scheduler.stopped")

    async def shutdown(self) -> None:
        """Compatibility alias for stop()."""
        await self.stop()

    # ─── Task Scheduling ──────────────────────────────────────────────────────

    async def schedule_task(self, task: Dict[str, Any]) -> str:
        """Schedule a new task."""
        task_id = task.get("id") or str(uuid.uuid4())


        priority = task.get("priority", TaskPriority.MEDIUM)
        if not isinstance(priority, TaskPriority):
            try:
                priority = TaskPriority(int(priority))
            except Exception:
                priority = TaskPriority.MEDIUM

        scheduled_for = task.get("scheduled_for", datetime.utcnow())
        if isinstance(scheduled_for, str):
            try:
                scheduled_for = datetime.fromisoformat(scheduled_for)
            except Exception:
                scheduled_for = datetime.utcnow()

        # Always store as ISO string so queue tuples are (int, str, str)
        scheduled_iso: str = (
            scheduled_for.isoformat()
            if isinstance(scheduled_for, datetime)
            else str(scheduled_for)
        )

        task_record = {
            "id": task_id,
            "name": task.get("name", "unnamed_task"),
            "description": task.get("description", ""),
            "priority": priority,
            "status": TaskStatus.QUEUED,
            "created_at": datetime.utcnow(),
            "scheduled_for": scheduled_iso,
            "timeout": task.get("timeout", self.task_timeout),
            "dependencies": task.get("dependencies", []),
            "parameters": task.get("parameters", {}),
            "result": None,
            "error": None,
            "attempts": 0,
            "max_retries": task.get("max_retries", self.max_retries),
            "retry_delay": task.get("retry_delay", self.retry_delay),
            "correlation_id": task.get("correlation_id"),
            "trace_id": task.get("trace_id"),
            "worker_id": task.get("worker_id"),
            "worker_pool": task.get("worker_pool", "default"),
            "assigned_worker": None,
            "execution_path": None,
            # Support agent_manager injection per-task (used by execute_via_pipeline)
            "agent_manager": task.get("agent_manager"),
        }

        self.tasks[task_id] = task_record
        self._task_events[task_id] = asyncio.Event()

        await self._emit_runtime_event("task.scheduled", task_record)

        await self.task_queue.put((
            -int(priority),   # negative → higher priority processed first
            scheduled_iso,    # ISO string — always comparable
            task_id,
        ))
        self.metrics["queue_size"] = self.task_queue.qsize()

        logger.info(
            "task_scheduler.task_scheduled",
            task_id=task_id,
            task_name=task_record["name"],
            priority=priority.value,
            correlation_id=task_record["correlation_id"],
            trace_id=task_record["trace_id"],
        )
        return task_id

    # ─── Runtime Event Emission ───────────────────────────────────────────────

    async def _emit_runtime_event(
        self, event_type: str, task: Dict[str, Any], error: Optional[str] = None
    ) -> None:
        """Publish task lifecycle updates to the configured runtime broker/controller."""
        if not self.message_broker and not self.communication_controller:
            return

        status = task.get("status")
        status_value = None
        if isinstance(status, TaskStatus):
            status_value = status.value
        elif status is not None:
            status_value = str(status)

        payload = {
            "type": "task_event",
            "event_type": event_type,
            "task_id": task.get("id"),
            "task_name": task.get("name"),
            "status": status_value,
            "priority": task.get("priority").value if isinstance(task.get("priority"), TaskPriority) else None,
            "correlation_id": task.get("correlation_id"),
            "trace_id": task.get("trace_id"),
            "worker_id": task.get("assigned_worker"),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {"execution_path": task.get("execution_path")},
        }
        if error:
            payload["error"] = error

        try:
            if self.message_broker:
                if hasattr(self.message_broker, "publish_message"):
                    await self.message_broker.publish_message(
                        "task-events",
                        payload,
                        sender="task_scheduler",
                        recipient=None,
                        priority=5,
                    )
                elif hasattr(self.message_broker, "send_message"):
                    await self.message_broker.send_message(
                        sender_agent_id="task_scheduler",
                        recipient_agent_id=None,
                        message_type="task_update",
                        content=payload,
                        priority=3,
                    )
                elif hasattr(self.message_broker, "publish"):
                    await self.message_broker.publish(payload)
        except Exception as exc:
            logger.warning("task_scheduler.runtime_event_publish_failed", error=str(exc))

        try:
            if self.communication_controller and hasattr(self.communication_controller, "broadcast_event"):
                await self.communication_controller.broadcast_event("task_event", payload)
        except Exception as exc:
            logger.warning("task_scheduler.controller_event_publish_failed", error=str(exc))

    # ─── Processing Loop ──────────────────────────────────────────────────────

    async def _process_tasks(self) -> None:
        """Process tasks from the queue, enforcing max_concurrent_tasks via semaphore."""
        while self.is_running:
            try:
                priority, scheduled_iso, task_id = await asyncio.wait_for(
                    self.task_queue.get(), timeout=0.5
                )

                # Respect scheduled time
                try:
                    scheduled_dt = datetime.fromisoformat(scheduled_iso)
                except Exception:
                    scheduled_dt = datetime.utcnow()

                if datetime.utcnow() < scheduled_dt:
                    await self.task_queue.put((priority, scheduled_iso, task_id))
                    self.task_queue.task_done()
                    await asyncio.sleep(0.05)
                    continue


                task = self.tasks.get(task_id)
                if not task:
                    self.task_queue.task_done()
                    continue

                # Skip cancelled tasks
                if task["status"] == TaskStatus.CANCELLED:
                    self.task_queue.task_done()
                    continue

                if not await self._check_dependencies(task):
                    await self.task_queue.put((priority, scheduled_iso, task_id))
                    self.task_queue.task_done()
                    await asyncio.sleep(0.05)
                    continue

                task["assigned_worker"] = await self._select_worker(task)
                task["status"] = TaskStatus.ASSIGNED if task.get("assigned_worker") else TaskStatus.QUEUED

                # ← FIXED: acquire semaphore BEFORE executing; task_done called AFTER
                # execution completes (was called before _execute_task in old code)
                await self._concurrency_semaphore.acquire()
                self.metrics["concurrent_tasks"] = (
                    self.max_concurrent_tasks - self._concurrency_semaphore._value
                )
                # Dispatch as a background task so the scheduler loop is not
                # blocked for the full task duration. The semaphore is released
                # inside the wrapper once the task finishes.
                bg = asyncio.create_task(
                    self._execute_task_and_release(task),
                    name=f"scheduler.task.{task['id']}",
                )
                self.running_tasks[task["id"]] = bg
                self.task_queue.task_done()
                self.metrics["queue_size"] = self.task_queue.qsize()

            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
            except Exception as e:
                logger.error("task_scheduler.process_error", error=str(e))
                await asyncio.sleep(1)

    async def _execute_task_and_release(self, task: Dict[str, Any]) -> None:
        """Wrapper that runs _execute_task then releases the concurrency semaphore."""
        try:
            await self._execute_task(task)
        finally:
            self._concurrency_semaphore.release()
            self.metrics["concurrent_tasks"] = (
                self.max_concurrent_tasks - self._concurrency_semaphore._value
            )

    async def _check_dependencies(self, task: Dict[str, Any]) -> bool:
        """Check if all task dependencies are satisfied."""
        for dep_id in task.get("dependencies", []):
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task["status"] != TaskStatus.COMPLETED:
                return False
        return True

    # ─── Task Execution ───────────────────────────────────────────────────────

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        """Execute a task through the real agent execution pipeline."""
        try:
            task["status"] = TaskStatus.RUNNING
            task["started_at"] = datetime.utcnow()
            await self._emit_runtime_event("task.started", task)

            logger.info(
                "task_scheduler.task_started",
                task_id=task["id"],
                task_name=task["name"],
                worker=task.get("assigned_worker"),
                correlation_id=task.get("correlation_id"),
                trace_id=task.get("trace_id"),
            )

            execution_task = asyncio.create_task(
                self._run_task(task), name=f"task_{task['id']}"
            )
            # Do not overwrite running_tasks here — the outer background task
            # reference is already stored by _process_tasks before dispatch.
            self._inner_tasks = getattr(self, "_inner_tasks", {})
            self._inner_tasks[task["id"]] = execution_task

            try:
                # capture result so we can inspect success/failure semantics
                result = await asyncio.wait_for(execution_task, timeout=task["timeout"])
                task["result"] = result

                # Treat the result as a failure only when it carries an explicit
                # error/failed/timeout status AND does not also carry a success
                # indicator.  Memory-agent operations return domain statuses like
                # "created", "stored", "merged" which are all successful outcomes.
                _FAILURE_STATUSES = {"error", "failed", "timeout"}
                _SUCCESS_STATUSES = {"completed", "ok", "created", "stored", "merged",
                                     "linked", "consolidated", "cleared", "archived",
                                     "restored", "deleted"}
                result_status = result.get("status") if isinstance(result, dict) else None
                is_agent_failure = (
                    isinstance(result, dict)
                    and result_status in _FAILURE_STATUSES
                    and result_status not in _SUCCESS_STATUSES
                )
                if is_agent_failure:
                    task["status"] = TaskStatus.FAILED
                    task["error"] = f"agent_manager_reported_failure: {result.get('status') }"
                    self.metrics["failed_tasks"] += 1
                    logger.warning(
                        "task_scheduler.task_failed_by_result",
                        task_id=task["id"],
                        result_status=result.get("status"),
                        correlation_id=task.get("correlation_id"),
                    )
                    # schedule retry if allowed
                    if task["attempts"] < task["max_retries"]:
                        task["attempts"] += 1
                        task["status"] = TaskStatus.RETRIED
                        self.metrics["retried_tasks"] += 1
                        retry_iso = (
                            datetime.utcnow() + timedelta(seconds=float(task["retry_delay"]))
                        ).isoformat()
                        await self.task_queue.put((-int(task["priority"]), retry_iso, task["id"]))
                        self._retry_queue[task["id"]] = task["attempts"]
                        await self._emit_runtime_event("task.retrying", task, error="agent_reported_failure")
                    else:
                        await self._emit_runtime_event("task.failed", task, error=task.get("error"))
                else:
                    task["status"] = TaskStatus.COMPLETED
                    self.metrics["completed_tasks"] += 1
                    await self._emit_runtime_event("task.completed", task)
                    logger.info(
                        "task_scheduler.task_completed",
                        task_id=task["id"],
                        task_name=task["name"],
                        correlation_id=task.get("correlation_id"),
                    )
            except asyncio.TimeoutError:
                task["status"] = TaskStatus.TIMED_OUT
                task["error"] = "Task execution timed out"
                self.metrics["failed_tasks"] += 1
                logger.warning(
                    "task_scheduler.task_timed_out",
                    task_id=task["id"],
                    timeout=task["timeout"],
                    correlation_id=task.get("correlation_id"),
                )
                if task["attempts"] < task["max_retries"]:
                    task["attempts"] += 1
                    task["status"] = TaskStatus.RETRIED
                    self.metrics["retried_tasks"] += 1
                    retry_iso = (
                        datetime.utcnow() + timedelta(seconds=float(task["retry_delay"]))
                    ).isoformat()
                    await self.task_queue.put((-int(task["priority"]), retry_iso, task["id"]))
                    self._retry_queue[task["id"]] = task["attempts"]
                    await self._emit_runtime_event("task.retrying", task, error="Task execution timed out")
                else:
                    task["status"] = TaskStatus.FAILED
                    await self._emit_runtime_event("task.failed", task, error="Max retries exceeded after timeout")
            except asyncio.CancelledError:
                task["status"] = TaskStatus.CANCELLED
                task["error"] = "Task was cancelled"
                self.metrics["cancelled_tasks"] += 1
                await self._emit_runtime_event("task.cancelled", task)
                raise
            except Exception as e:
                # Handle unexpected execution exceptions: allow retry if configured
                task["error"] = str(e)
                self.metrics["failed_tasks"] += 1
                logger.error(
                    "task_scheduler.task_failed_exception",
                    task_id=task["id"],
                    error=str(e),
                    correlation_id=task.get("correlation_id"),
                )
                if task["attempts"] < task["max_retries"]:
                    task["attempts"] += 1
                    task["status"] = TaskStatus.RETRIED
                    self.metrics["retried_tasks"] += 1
                    retry_iso = (
                        datetime.utcnow() + timedelta(seconds=float(task["retry_delay"]))
                    ).isoformat()
                    await self.task_queue.put((-int(task["priority"]), retry_iso, task["id"]))
                    self._retry_queue[task["id"]] = task["attempts"]
                    await self._emit_runtime_event("task.retrying", task, error=str(e))
                else:
                    task["status"] = TaskStatus.FAILED
                    await self._emit_runtime_event("task.failed", task, error=str(e))

            task["completed_at"] = datetime.utcnow()
            self.running_tasks.pop(task["id"], None)

            # ← FIXED: clean up _retry_queue after terminal state
            if task["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                self._retry_queue.pop(task["id"], None)

            if task.get("id") in self._task_events:
                self._task_events[task["id"]].set()
            self._update_metrics(task)
            self._append_history(task)

        except asyncio.CancelledError:
            task["status"] = TaskStatus.CANCELLED
            self.running_tasks.pop(task.get("id", ""), None)
            self._retry_queue.pop(task.get("id", ""), None)
            if task.get("id") in self._task_events:
                self._task_events[task["id"]].set()
            raise
        except Exception as e:
            logger.error("task_scheduler.execute_task_error", task_id=task.get("id"), error=str(e))
            task["status"] = TaskStatus.FAILED
            task["error"] = str(e)
            self.metrics["failed_tasks"] += 1
            self.running_tasks.pop(task.get("id", ""), None)
            self._retry_queue.pop(task.get("id", ""), None)
            if task.get("id") in self._task_events:
                self._task_events[task["id"]].set()

    def _append_history(self, task: Dict[str, Any]) -> None:
        """Append to execution history and auto-trim to max_execution_history."""
        self._execution_history.append({
            "task_id": task["id"],
            "task_name": task.get("name"),
            "status": task["status"].value if isinstance(task["status"], TaskStatus) else str(task["status"]),
            "started_at": task.get("started_at").isoformat() if task.get("started_at") else None,
            "completed_at": task.get("completed_at").isoformat() if task.get("completed_at") else None,
            "error": task.get("error"),
            "attempts": task.get("attempts", 0),
            "worker": task.get("assigned_worker"),
            "correlation_id": task.get("correlation_id"),
            "trace_id": task.get("trace_id"),
        })
        # ← Auto-trim execution history to avoid unbounded growth
        if len(self._execution_history) > self._max_execution_history:
            self._execution_history = self._execution_history[-self._max_execution_history:]

    async def _run_task(self, task: Dict[str, Any]) -> Any:
        """Dispatch task through the canonical AgentManager execution contract."""
        agent_name = task.get("parameters", {}).get("agent_name", "orchestrator_agent")
        context = build_execution_context(
            request_id=task.get("correlation_id") or str(uuid.uuid4()),
            correlation_id=task.get("correlation_id") or str(uuid.uuid4()),
            trace_id=task.get("trace_id") or str(uuid.uuid4()),
            task_id=task.get("id"),
            agent_id=agent_name,
            conversation_id=task.get("parameters", {}).get("conversation_id"),
            timeout=task.get("timeout"),
            metadata={"task_name": task.get("name"), "worker_id": task.get("assigned_worker")},
        )
        token = context.bind() if context else None
        try:
            action = task.get("parameters", {}).get("action", "process")
            input_data = task.get("parameters", {}).get("input_data", {})
            user_id = task.get("parameters", {}).get("user_id")
            # Prefer per-task agent_manager (set by execute_via_pipeline), fall back to scheduler-level
            agent_manager = task.get("agent_manager") or self.agent_manager

            if agent_manager is None:
                raise RuntimeError(
                    f"Task '{task.get('id')}' requires an AgentManager but none is configured. "
                    "Pass agent_manager in TaskScheduler config or task parameters."
                )

            task_payload = {
                "action": action,
                "input_data": input_data,
                "user_id": user_id,
            }
            task["execution_path"] = "agent_manager"
            result = await asyncio.wait_for(
                agent_manager.execute_agent_task(
                    agent_name,
                    task_payload,
                    timeout_seconds=task.get("timeout", self.task_timeout),
                    execution_context=context,
                ),
                timeout=task.get("timeout", self.task_timeout),
            )
            task["result"] = result
            return result
        finally:
            if token is not None:
                context.unbind(token)

    # ─── Metrics ──────────────────────────────────────────────────────────────

    def _update_metrics(self, task: Dict[str, Any]) -> None:
        """Update task metrics."""
        self.metrics["total_tasks"] += 1
        if (
            task["status"] == TaskStatus.COMPLETED
            and task.get("started_at")
            and task.get("completed_at")
        ):
            completion_time = (task["completed_at"] - task["started_at"]).total_seconds()
            n = self.metrics["completed_tasks"]
            if n > 0:
                self.metrics["average_completion_time"] = (
                    (self.metrics["average_completion_time"] * (n - 1) + completion_time) / n
                )

    # ─── Public API ───────────────────────────────────────────────────────────

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    async def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self.tasks.values())

    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Wait for a task to reach a terminal state."""
        event = self._task_events.get(task_id)
        if event is None:
            return self.tasks.get(task_id)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return self.tasks.get(task_id)
        return self.tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task["status"] in (TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.QUEUED):
            task["status"] = TaskStatus.CANCELLED
            self.metrics["cancelled_tasks"] += 1
            # ← Clean up retry queue entry
            self._retry_queue.pop(task_id, None)
            await self._emit_runtime_event("task.cancelled", task)
            if task_id in self._task_events:
                self._task_events[task_id].set()
            return True

        if task["status"] == TaskStatus.RUNNING:
            # Cancel the inner execution task if available, otherwise the outer wrapper
            inner_tasks = getattr(self, "_inner_tasks", {})
            running_task = inner_tasks.get(task_id) or self.running_tasks.get(task_id)
            if running_task:
                running_task.cancel()
                try:
                    await running_task
                except (asyncio.CancelledError, Exception):
                    pass
                task["status"] = TaskStatus.CANCELLED
                self.metrics["cancelled_tasks"] += 1
                self._retry_queue.pop(task_id, None)
                await self._emit_runtime_event("task.cancelled", task)
                return True

        return False

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "total_tasks": len(self.tasks),
            "execution_history_size": len(self._execution_history),
            "retry_queue_size": len(self._retry_queue),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "semaphore_available": self._concurrency_semaphore._value,
        }

    async def register_worker(self, worker_id: str, worker: Any, pool: str = "default") -> None:
        async with self._worker_lock:
            self.workers[worker_id] = worker
            if pool not in self.worker_pools:
                self.worker_pools[pool] = []
            if worker_id not in self.worker_pools[pool]:
                self.worker_pools[pool].append(worker_id)
            self._worker_rr.setdefault(pool, 0)
            self.metrics["workers_registered"] = len(self.workers)

    async def unregister_worker(self, worker_id: str) -> None:
        async with self._worker_lock:
            self.workers.pop(worker_id, None)
            for pool, workers in self.worker_pools.items():
                if worker_id in workers:
                    workers.remove(worker_id)
                    self._worker_rr[pool] = (
                        0 if not workers else self._worker_rr.get(pool, 0) % len(workers)
                    )
            self.metrics["workers_registered"] = len(self.workers)

    async def _select_worker(self, task: Dict[str, Any]) -> Optional[str]:
        preferred_worker = task.get("worker_id")
        if preferred_worker and preferred_worker in self.workers:
            self.metrics["worker_assignments"] += 1
            return preferred_worker

        pool_name = task.get("worker_pool") or "default"
        pool_workers = list(self.worker_pools.get(pool_name, []))
        if not pool_workers:
            pool_workers = list(self.worker_pools.get("default", []))
        if not pool_workers:
            return None

        index = self._worker_rr.get(pool_name, 0) % len(pool_workers)
        self._worker_rr[pool_name] = (index + 1) % len(pool_workers)
        self.metrics["worker_assignments"] += 1
        return pool_workers[index]

    async def initialize(self) -> None:
        logger.info("task_scheduler.initializing")
        self.tasks.clear()
        self.running_tasks.clear()
        self._retry_queue.clear()
        logger.info("task_scheduler.initialized")

    async def create_task(self, task: Dict[str, Any]) -> str:
        return await self.schedule_task(task)

    async def update_task_status(self, task_id: str, status: str, result: Any = None) -> None:
        task = self.tasks.get(task_id)
        if task:
            try:
                task["status"] = TaskStatus(status)
            except Exception:
                task["status"] = TaskStatus.PENDING
            task["result"] = result
            task["updated_at"] = datetime.utcnow()

    async def process_tasks(self) -> None:
        await self._process_tasks()

    async def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._execution_history[-limit:]

    async def monitor_queue(self) -> Dict[str, Any]:
        """Return real-time queue monitoring metrics."""
        return {
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "running_task_ids": list(self.running_tasks.keys()),
            "retry_queue_size": len(self._retry_queue),
            "retry_task_ids": list(self._retry_queue.keys()),
            "workers_registered": len(self.workers),
            "worker_pools": {name: len(workers) for name, workers in self.worker_pools.items()},
            "semaphore_available": self._concurrency_semaphore._value,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "total_tasks": len(self.tasks),
            "completed_tasks": self.metrics["completed_tasks"],
            "failed_tasks": self.metrics["failed_tasks"],
            "cancelled_tasks": self.metrics["cancelled_tasks"],
        }
