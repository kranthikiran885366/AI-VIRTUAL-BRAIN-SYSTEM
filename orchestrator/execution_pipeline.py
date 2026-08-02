"""Shared execution pipeline for orchestrator requests and tasks."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from .execution_context import build_execution_context
from .task_scheduler import TaskPriority

try:
    from structlog import get_logger
    logger = get_logger()
except ImportError:
    logger = logging.getLogger(__name__)


async def execute_via_pipeline(
    *,
    agent_name: str,
    action: str,
    input_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    priority: str = "normal",
    task_scheduler: Optional[Any] = None,
    agent_manager: Optional[Any] = None,
    communication_controller: Optional[Any] = None,
    message_broker: Optional[Any] = None,
    timeout: Optional[float] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Route an execution request through the single authoritative pipeline path."""
    task_id = str(uuid.uuid4())
    request_id = request_id or f"req-{task_id}"
    correlation_id = correlation_id or f"corr-{task_id}"
    trace_id = trace_id or f"trace-{task_id}"

    priority_value = TaskPriority.MEDIUM
    if isinstance(priority, TaskPriority):
        priority_value = priority
    else:
        try:
            priority_value = TaskPriority[str(priority).upper()]
        except Exception:
            try:
                priority_value = TaskPriority(int(priority))
            except Exception:
                priority_value = TaskPriority.MEDIUM

    task_definition = {
        "id": task_id,
        "name": f"agent:{agent_name}:{action}",
        "description": f"Execution request for {agent_name}:{action}",
        "priority": priority_value,
        "status": "pending",
        "timeout": timeout or 60,
        "dependencies": [],
        "parameters": {
            "agent_name": agent_name,
            "action": action,
            "input_data": input_data or {},
            "user_id": user_id,
            "conversation_id": conversation_id,
        },
        "correlation_id": correlation_id,
        "trace_id": trace_id,
        "created_at": datetime.utcnow().isoformat(),
        "agent_manager": agent_manager,
    }

    execution_context = build_execution_context(
        request_id=request_id,
        correlation_id=correlation_id,
        trace_id=trace_id,
        task_id=task_id,
        agent_id=agent_name,
        conversation_id=conversation_id,
        timeout=task_definition["timeout"],
        priority=priority_value.value,
        metadata={"priority": priority_value.value, "action": action},
    )
    token = execution_context.bind() if execution_context else None

    # Step 1: Notify broker of pipeline initiation if broker is available
    if message_broker is not None:
        try:
            if hasattr(message_broker, "send_message"):
                await message_broker.send_message(
                    sender_agent_id="pipeline",
                    recipient_agent_id=agent_name,
                    message_type="TASK_CREATE" if hasattr(message_broker, "MessageType") else "task_create",
                    content={"action": action, "task_id": task_id},
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                )
        except Exception as exc:
            logger.warning(f"execution_pipeline.broker_notify_failed error={exc}")

    try:
        if task_scheduler is None:
            raise RuntimeError("Task scheduler is required for the execution pipeline")

        # Step 2: Schedule task
        if hasattr(task_scheduler, "schedule_task"):
            await task_scheduler.schedule_task(task_definition)
        else:
            raise RuntimeError("Task scheduler does not support scheduling")

        # Step 3: Wait for task execution via TaskScheduler -> AgentManager -> Agent
        if hasattr(task_scheduler, "wait_for_task"):
            task_result = await task_scheduler.wait_for_task(task_id, timeout=task_definition["timeout"])
        else:
            task_result = {"id": task_id, "status": "completed", "result": {"status": "completed"}}

        if not task_result:
            task_result = {"status": "error", "error": "Task execution timed out or failed to return a result"}

        raw_result = task_result.get("result") if isinstance(task_result, dict) else task_result
        if raw_result is None:
            raw_result = task_result

        # Step 4: Notify communication_controller of completion if available
        if communication_controller is not None and hasattr(communication_controller, "broadcast_event"):
            try:
                await communication_controller.broadcast_event(
                    "pipeline_completed",
                    {
                        "task_id": task_id,
                        "agent_name": agent_name,
                        "action": action,
                        "correlation_id": correlation_id,
                        "trace_id": trace_id,
                    },
                )
            except Exception as exc:
                logger.warning(f"execution_pipeline.controller_broadcast_failed error={exc}")

        # Explicit parentheses — avoids operator precedence bug where
        # `"error" in raw_result and ...` bound tighter than `or`.
        # Memory-agent domain statuses (created, stored, merged, etc.) are
        # all successful outcomes and must NOT be treated as errors.
        _PIPELINE_FAILURE_STATUSES = {"error", "failed", "timeout"}
        is_error = isinstance(raw_result, dict) and (
            raw_result.get("status") in _PIPELINE_FAILURE_STATUSES
            or (
                "error" in raw_result
                and raw_result.get("status") not in (
                    "completed", "ok", "created", "stored", "merged",
                    "linked", "consolidated", "cleared", "archived",
                    "restored", "deleted",
                )
            )
        )

        return {
            "status": "completed" if not is_error else "error",
            "task_id": task_id,
            "agent": agent_name,
            "action": action,
            "result": raw_result,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        if token is not None:
            execution_context.unbind(token)
