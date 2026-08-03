import pytest

from agents.reasoning_agent import ReasoningAgent


@pytest.mark.asyncio
async def test_reasoning_agent_produces_structured_production_result():
    agent = ReasoningAgent(agent_id="reasoning_agent")
    await agent.initialize()

    result = await agent.reason(
        "If the system loses network access, then the reasoning engine cannot fetch fresh evidence. "
        "The engine must continue with cached evidence and explain what remains uncertain.",
        context={
            "problem_statement": "Reasoning under partial evidence",
            "request_id": "req-123",
            "correlation_id": "corr-123",
            "trace_id": "trace-123",
            "objective": "derive a safe conclusion",
            "constraints": ["no fresh network lookups"],
            "decision_context": {"goal": "maintain service availability"},
        },
        evidence=[
            {"id": "ev-1", "content": "network access is unavailable", "confidence": 0.9, "source": "system"},
            {"id": "ev-2", "content": "cached evidence is available", "confidence": 0.75, "source": "memory"},
        ],
    )

    assert result["reasoning_id"]
    assert result["reasoning_type"] in {"deductive", "causal", "abductive", "analogical", "counterfactual", "constraint", "goal_oriented"}
    assert result["context"]["request_id"] == "req-123"
    assert result["context"]["correlation_id"] == "corr-123"
    assert result["context"]["trace_id"] == "trace-123"
    assert isinstance(result["reasoning_chain"], list) and result["reasoning_chain"]
    assert isinstance(result["evidence"], list) and result["evidence"]
    assert result["confidence"]["overall"] >= 0.0
    assert result["explanation"]["high_level"]
    assert result["reasoning_state"] in {"initialized", "processing", "completed", "failed"}


@pytest.mark.asyncio
async def test_reasoning_agent_detects_conflicts_and_reports_them():
    agent = ReasoningAgent(agent_id="reasoning_agent")
    await agent.initialize()

    result = await agent.reason(
        "The model claims the service is healthy. The same evidence also states the service is failing.",
        evidence=[
            {"id": "ev-a", "content": "service is healthy", "confidence": 0.8, "source": "system"},
            {"id": "ev-b", "content": "service is failing", "confidence": 0.8, "source": "system"},
        ],
    )

    assert result["contradictions"]
    assert result["reasoning_state"] == "completed"
    assert result["explanation"]["limitations"]
