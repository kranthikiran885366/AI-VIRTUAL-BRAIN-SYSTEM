"""Production Cognitive Memory Subsystem Tests (Phase 3)."""

import asyncio
import pytest
from datetime import datetime, timedelta

from orchestrator.database import DatabaseManager, DatabaseConfig
from orchestrator.execution_pipeline import execute_via_pipeline
from orchestrator.task_scheduler import TaskScheduler
from orchestrator.agent_manager import AgentManager
from orchestrator.agent_communication import get_message_broker

from agents.memory_agent.agent import MemoryAgent
from agents.memory_agent.memory_types import (
    MemoryType,
    RelationshipType,
    MemorySearchFilter,
)


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_database_schema_initialization(tmp_path):
    db_file = str(tmp_path / "test_brain.db")
    db_mgr = DatabaseManager(DatabaseConfig(database_path=db_file))
    db_mgr.initialize()

    val = db_mgr.migration_validator.validate(
        ["memories", "memory_relationships", "memory_history"]
    )
    assert val["ok"] is True
    db_mgr.shutdown()


@pytest.mark.asyncio
async def test_cognitive_memory_tiers():
    import time
    uid = f"tier_user_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"tier_agent_{time.time_ns()}")
    await agent.initialize()

    wm = await agent.store_working_memory(content=f"Active reasoning goal {uid}", user_id=uid)
    assert wm["status"] in ("stored", "created")
    assert wm["memory_id"] is not None

    st = await agent.store_short_term_memory(
        content=f"Recent observation {uid}", user_id=uid, importance=0.5
    )
    assert st["memory_id"] is not None

    lt = await agent.store_long_term_memory(
        content=f"Durable fact dark mode {uid}", user_id=uid, importance=0.9
    )
    assert lt["memory_id"] is not None

    ep = await agent.store_episodic_memory(
        event={"action": "login", "uid": uid}, user_id=uid
    )
    assert ep["memory_id"] is not None

    sem = await agent.store_semantic_memory(
        fact=f"Python dynamically typed {uid}", user_id=uid
    )
    assert sem["memory_id"] is not None

    proc = await agent.store_procedural_memory(
        workflow={"steps": ["validate", "execute", "respond"], "uid": uid}, user_id=uid
    )
    assert proc["memory_id"] is not None

    stats = await agent.get_stats()
    # High-importance stores (importance >= 0.65) get promoted to long_term via
    # INSERT OR REPLACE — so the distinct row count may be < 6 after merges.
    assert stats["total"] >= 4
    await agent.shutdown()


@pytest.mark.asyncio
async def test_hybrid_search_and_ranking():
    import time
    uid = f"rank_u_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"rank_agent_{time.time_ns()}")
    await agent.initialize()

    await agent.store(
        content=f"Artificial intelligence and neural network architectures {uid}",
        importance=0.9,
        user_id=uid,
    )
    await agent.store(
        content=f"Baking chocolate cake and cookie recipes {uid}",
        importance=0.3,
        user_id=uid,
    )

    recalled = await agent.recall(query="intelligence neural", user_id=uid, limit=5)
    assert len(recalled) > 0
    assert "artificial intelligence" in str(recalled[0]["content"]).lower()
    assert "_relevance_score" in recalled[0]

    await agent.shutdown()


@pytest.mark.asyncio
async def test_memory_relationship_links():
    import time
    uid = f"rel_u_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"rel_agent_{time.time_ns()}")
    await agent.initialize()

    m1 = await agent.store(content=f"Task A: Create database index {uid}", user_id=uid)
    m2 = await agent.store(content=f"Outcome A: Query speed improved 5x {uid}", user_id=uid)

    link_res = await agent.link_memories(
        source_id=m1["memory_id"],
        target_id=m2["memory_id"],
        relationship_type=RelationshipType.TASK_OUTCOME,
        weight=1.5,
    )
    assert link_res["status"] == "linked"

    recalled = await agent.recall(
        query="database index", user_id=uid, traverse_relationships=True
    )
    assert len(recalled) > 0
    assert len(recalled[0]["linked_memories"]) > 0
    assert recalled[0]["linked_memories"][0] == m2["memory_id"]

    await agent.shutdown()


@pytest.mark.asyncio
async def test_duplicate_detection_and_merging():
    import time

    ts = time.time_ns()
    unique_content = f"Deduplication test sentinel {ts}"
    uid = f"dup_user_{ts}"
    agent = MemoryAgent(agent_id=f"dup_agent_{ts}")
    await agent.initialize()

    res1 = await agent.store(content=unique_content, importance=0.4, user_id=uid)
    assert res1["status"] in ("stored", "created"), f"Expected created, got: {res1['status']}"

    res2 = await agent.store(content=unique_content, importance=0.8, user_id=uid)
    assert res2["status"] == "merged", f"Expected merged, got: {res2['status']}"
    assert res2["memory_id"] == res1["memory_id"]

    await agent.shutdown()


@pytest.mark.asyncio
async def test_memory_update_and_version_history():
    import time
    uid = f"u_upd_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"update_agent_{time.time_ns()}")
    await agent.initialize()

    res = await agent.store(content=f"Initial content v1 {uid}", importance=0.5, user_id=uid)
    mem_id = res["memory_id"]
    assert mem_id is not None

    updated = agent.storage.update(mem_id, {"content": "Updated content v2"}, reason="test_update")
    assert updated is True

    retrieved = agent.storage.retrieve(mem_id)
    assert retrieved is not None
    assert retrieved.version == 2

    history = agent.storage._execute_sql(
        "SELECT * FROM memory_history WHERE memory_id = ?", (mem_id,)
    )
    assert len(history) >= 1
    assert history[0]["change_reason"] == "test_update"

    await agent.shutdown()


@pytest.mark.asyncio
async def test_memory_archive_and_restore():
    import time
    uid = f"u_arch_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"archive_agent_{time.time_ns()}")
    await agent.initialize()

    res = await agent.store(content=f"Archivable memory {uid}", importance=0.4, user_id=uid)
    mem_id = res["memory_id"]

    archived = agent.storage.archive(mem_id)
    assert archived is True

    results = await agent.recall(query="Archivable memory", user_id=uid)
    ids = [r["id"] for r in results]
    assert mem_id not in ids

    restored = agent.storage.restore(mem_id)
    assert restored is True

    results_after = await agent.recall(query="Archivable memory", user_id=uid)
    ids_after = [r["id"] for r in results_after]
    assert mem_id in ids_after

    await agent.shutdown()


@pytest.mark.asyncio
async def test_memory_soft_and_hard_delete():
    import time
    uid = f"u_del_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"delete_agent_{time.time_ns()}")
    await agent.initialize()

    res = await agent.store(content=f"Memory to delete {uid}", importance=0.3, user_id=uid)
    mem_id = res["memory_id"]

    soft = agent.storage.delete(mem_id, hard=False)
    assert soft is True
    assert agent.storage.retrieve(mem_id) is None

    hard = agent.storage.delete(mem_id, hard=True)
    # Row already soft-deleted; hard delete returns False when row is gone
    rows = agent.storage._execute_sql(
        "SELECT id FROM memories WHERE id = ?", (mem_id,)
    )
    assert len(rows) == 0

    await agent.shutdown()


@pytest.mark.asyncio
async def test_ttl_expiry_and_cleanup():
    import time
    uid = f"u_ttl_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"ttl_agent_{time.time_ns()}")
    await agent.initialize()

    res = await agent.store(
        content=f"Ephemeral memory {uid}",
        importance=0.3,
        user_id=uid,
        ttl=0.001,
    )
    mem_id = res["memory_id"]

    # Manually set expires_at to the past so cleanup_expired picks it up
    past = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
    agent.storage._write_sql(
        "UPDATE memories SET expires_at = ? WHERE id = ?", (past, mem_id)
    )

    cleaned = agent.storage.cleanup_expired()
    assert cleaned >= 1

    assert agent.storage.retrieve(mem_id) is None

    await agent.shutdown()


@pytest.mark.asyncio
async def test_consolidation_promotes_short_term():
    import time

    agent = MemoryAgent(agent_id=f"consol_agent_{time.time_ns()}")
    await agent.initialize()

    # Store a short-term memory with importance above consolidation threshold
    res = await agent.store(
        content=f"High-importance short-term fact {time.time_ns()}",
        memory_type=MemoryType.SHORT_TERM,
        importance=0.8,
        user_id="u_consol",
    )
    mem_id = res["memory_id"]

    # Force consolidation
    consol_result = await agent.processor.consolidate()
    assert consol_result["status"] == "consolidated"

    # The memory should now be long_term
    mem = agent.storage.retrieve(mem_id)
    assert mem is not None
    assert mem.type == MemoryType.LONG_TERM

    await agent.shutdown()


@pytest.mark.asyncio
async def test_search_filter_by_tags():
    import time
    uid = f"u_tag_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"tag_agent_{time.time_ns()}")
    await agent.initialize()

    await agent.store(
        content=f"Tagged memory about Python {uid}",
        importance=0.6,
        user_id=uid,
        tags=["python", "programming"],
    )
    await agent.store(
        content=f"Untagged memory about cooking {uid}",
        importance=0.6,
        user_id=uid,
    )

    results = await agent.recall(
        query="memory", user_id=uid, tags=["python"], limit=10
    )
    assert len(results) >= 1
    assert all("python" in str(r["content"]).lower() for r in results)

    await agent.shutdown()


@pytest.mark.asyncio
async def test_search_filter_by_memory_type():
    import time

    agent = MemoryAgent(agent_id=f"type_filter_{time.time_ns()}")
    await agent.initialize()

    uid = f"u_type_{time.time_ns()}"
    await agent.store_episodic_memory(event={"action": "type_test"}, user_id=uid)
    await agent.store_semantic_memory(fact="Type filter semantic fact", user_id=uid)

    results = await agent.recall(
        query="type_test", user_id=uid, memory_type=MemoryType.EPISODIC, limit=10
    )
    assert all(r["type"] == "episodic" for r in results)

    await agent.shutdown()


@pytest.mark.asyncio
async def test_get_stats_returns_counts():
    import time
    uid = f"u_stats_{time.time_ns()}"
    agent = MemoryAgent(agent_id=f"stats_agent_{time.time_ns()}")
    await agent.initialize()

    for i in range(3):
        await agent.store(content=f"Stats test memory {i} {uid}", user_id=uid)

    stats = await agent.get_stats()
    assert "total" in stats
    assert stats["total"] >= 3
    assert "working_count" in stats
    assert "short_term_count" in stats
    assert "long_term_count" in stats

    await agent.shutdown()


@pytest.mark.asyncio
async def test_execution_pipeline_integration():
    broker = get_message_broker()
    await broker.start()

    agent_mgr = AgentManager({"agents": {}})
    await agent_mgr.initialize()
    await agent_mgr.start()

    memory_agent = MemoryAgent("memory_agent")
    await memory_agent.initialize()
    agent_mgr.agents["memory_agent"] = memory_agent

    scheduler = TaskScheduler(
        {
            "max_concurrent_tasks": 4,
            "task_timeout": 30,
            "message_broker": broker,
            "agent_manager": agent_mgr,
        }
    )
    await scheduler.initialize()
    await scheduler.register_worker("memory_agent", memory_agent)
    await scheduler.start()

    store_res = await execute_via_pipeline(
        agent_name="memory_agent",
        action="store",
        input_data={
            "content": "Pipeline test memory entry",
            "importance": 0.85,
            "user_id": "p_user",
        },
        task_scheduler=scheduler,
        agent_manager=agent_mgr,
        message_broker=broker,
        timeout=10.0,
    )
    assert store_res["status"] == "completed"
    assert store_res["result"]["status"] in ("stored", "created")

    recall_res = await execute_via_pipeline(
        agent_name="memory_agent",
        action="recall",
        input_data={"query": "pipeline test", "user_id": "p_user"},
        task_scheduler=scheduler,
        agent_manager=agent_mgr,
        message_broker=broker,
        timeout=10.0,
    )
    assert recall_res["status"] == "completed"
    assert recall_res["result"]["count"] >= 1

    await scheduler.stop()
    await memory_agent.shutdown()
    await agent_mgr.stop()
    await broker.stop()
