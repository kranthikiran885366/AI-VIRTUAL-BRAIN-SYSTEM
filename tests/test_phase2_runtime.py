import asyncio

import pytest

from communication_bus.message_broker import MessageBroker
from orchestrator.execution_context import build_execution_context, get_execution_context
from orchestrator.execution_pipeline import execute_via_pipeline
from orchestrator.task_scheduler import TaskScheduler, TaskPriority, TaskStatus


@pytest.mark.asyncio
async def test_message_broker_deduplicates_messages():
    broker = MessageBroker(config={"queue_maxsize": 10})
    await broker.start()
    try:
        first_id = await broker.publish_message(
            "test-topic",
            {"payload": "alpha"},
            sender="sender-a",
            recipient="recipient-a",
            priority=1,
            dedup_key="same-key",
        )
        second_id = await broker.publish_message(
            "test-topic",
            {"payload": "beta"},
            sender="sender-a",
            recipient="recipient-a",
            priority=1,
            dedup_key="same-key",
        )
        assert first_id == second_id
    finally:
        await broker.stop()


@pytest.mark.asyncio
async def test_message_broker_dead_letters_expired_messages():
    broker = MessageBroker(config={"queue_maxsize": 10, "message_ttl_seconds": 0})
    await broker.start()
    try:
        message_id = await broker.publish_message(
            "test-topic",
            {"payload": "gamma"},
            sender="sender-a",
            recipient="recipient-a",
            priority=1,
            ttl_seconds=0,
        )
        await asyncio.sleep(0.05)
        assert message_id
        status = await broker.get_status()
        assert status["recovery"]["dead_letter_size"] >= 1
    finally:
        await broker.stop()


def test_execution_context_builds_and_binds():
    ctx = build_execution_context(
        request_id="req-1",
        correlation_id="corr-1",
        trace_id="trace-1",
        task_id="task-1",
        agent_id="agent-1",
        conversation_id="conv-1",
        timeout=12.5,
        metadata={"source": "unit-test"},
    )
    assert ctx.request_id == "req-1"
    assert ctx.task_id == "task-1"
    assert ctx.timeout == 12.5
    assert get_execution_context() is None
    token = ctx.bind()
    try:
        current = get_execution_context()
        assert current is not None
        assert current.correlation_id == "corr-1"
    finally:
        ctx.unbind(token)


@pytest.mark.asyncio
async def test_scheduler_emits_runtime_events():
    class DummyBroker:
        def __init__(self):
            self.events = []

        async def publish(self, message):
            self.events.append(message)
            return True

        async def start(self):
            return None

        async def stop(self):
            return None

    class DummyWorker:
        async def execute_task(self, task):
            return {"status": "ok", "task_id": task["id"]}

    broker = DummyBroker()
    scheduler = TaskScheduler(
        {
            "task_timeout": 1.0,
            "message_broker": broker,
            "communication_controller": None,
        }
    )
    await scheduler.start()
    try:
        await scheduler.register_worker("worker-1", DummyWorker(), pool="agents")
        task_id = await scheduler.schedule_task(
            {
                "name": "unit-task",
                "priority": TaskPriority.CRITICAL,
                "worker_id": "worker-1",
                "parameters": {"agent_name": "worker-1", "action": "process", "input_data": {}},
            }
        )
        await asyncio.sleep(0.2)
        assert broker.events, "expected scheduler to emit runtime lifecycle events"
        assert any(event.get("task_id") == task_id for event in broker.events)
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_tracks_queued_and_assigned_state():
    class DummyAgentManager:
        async def execute_agent_task(self, agent_name, task, timeout_seconds=None, execution_context=None):
            return {"status": "completed", "agent": agent_name, "action": task.get("action"), "result": "ok"}

    class DummyWorker:
        async def execute_task(self, task):
            return {"status": "ok", "task_id": task["id"]}

    scheduler = TaskScheduler(
        {
            "task_timeout": 1.0,
            "message_broker": None,
            "communication_controller": None,
            "agent_manager": DummyAgentManager(),
        }
    )
    await scheduler.start()
    try:
        await scheduler.register_worker("worker-1", DummyWorker(), pool="agents")
        task_id = await scheduler.schedule_task(
            {
                "name": "lifecycle-task",
                "priority": TaskPriority.HIGH,
                "worker_id": "worker-1",
                "parameters": {"agent_name": "worker-1", "action": "process", "input_data": {}},
            }
        )
        task = scheduler.tasks[task_id]
        assert task["status"] == TaskStatus.QUEUED
        await asyncio.sleep(0.1)
        assert scheduler.tasks[task_id]["status"] in {TaskStatus.RUNNING, TaskStatus.COMPLETED}
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_execution_pipeline_routes_via_scheduler():
    class DummyAgentManager:
        async def execute_agent_task(self, agent_name, task, timeout_seconds=None, execution_context=None):
            return {"status": "completed", "agent": agent_name, "action": task.get("action"), "result": "ok"}

    class DummyScheduler:
        def __init__(self):
            self.task = None

        async def schedule_task(self, task):
            self.task = task
            return task["id"]

        async def wait_for_task(self, task_id, timeout=None):
            return {"id": task_id, "status": "completed", "result": {"status": "completed", "agent": self.task["parameters"]["agent_name"], "action": self.task["parameters"]["action"], "result": "ok"}}

    result = await execute_via_pipeline(
        agent_name="memory_agent",
        action="store",
        input_data={"content": "hello"},
        user_id="u1",
        conversation_id="c1",
        priority="high",
        task_scheduler=DummyScheduler(),
        agent_manager=DummyAgentManager(),
        communication_controller=None,
        message_broker=None,
    )

    assert result["status"] == "completed"
    assert result["agent"] == "memory_agent"
    assert result["result"]["result"] == "ok"


@pytest.mark.asyncio
async def test_pipeline_does_not_dispatch_agent_manager_directly():
    class DummyAgentManager:
        def __init__(self):
            self.calls = []

        async def execute_agent_task(self, agent_name, task, timeout_seconds=None, execution_context=None):
            self.calls.append((agent_name, task))
            return {"status": "completed", "agent": agent_name, "action": task.get("action"), "result": "ok"}

    class DummyScheduler:
        def __init__(self):
            self.task = None

        async def schedule_task(self, task):
            self.task = task
            return task["id"]

        async def wait_for_task(self, task_id, timeout=None):
            return {"id": task_id, "status": "completed", "result": {"status": "completed", "agent": self.task["parameters"]["agent_name"], "action": self.task["parameters"]["action"], "result": "ok"}}

    agent_manager = DummyAgentManager()
    result = await execute_via_pipeline(
        agent_name="memory_agent",
        action="store",
        input_data={"content": "hello"},
        user_id="u1",
        conversation_id="c1",
        priority="high",
        task_scheduler=DummyScheduler(),
        agent_manager=agent_manager,
        communication_controller=None,
        message_broker=None,
    )

    assert result["status"] == "completed"
    assert agent_manager.calls == []
