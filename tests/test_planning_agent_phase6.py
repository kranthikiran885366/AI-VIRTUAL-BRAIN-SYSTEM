import asyncio

from agents.planning_agent import PlanningAgent


class TestPlanningAgentPhase6:
    def test_create_plan_builds_structured_production_context(self):
        agent = PlanningAgent()

        plan = asyncio.run(agent.create_plan(
            goal="Ship a secure release for a customer-facing dashboard",
            timeframe="2 weeks",
            constraints=["must preserve SLA", "must not increase risk"],
            context={
                "request_id": "req-123",
                "correlation_id": "corr-123",
                "trace_id": "trace-123",
                "priority": 3,
            },
        ))

        assert plan["plan_id"]
        assert plan["goal_id"]
        assert plan["status"] == "active"
        assert plan["plan_context"]["request_id"] == "req-123"
        assert plan["plan_context"]["correlation_id"] == "corr-123"
        assert plan["plan_context"]["trace_id"] == "trace-123"
        assert plan["validation"]["status"] in {"passed", "warning"}
        assert plan["explanation"]["confidence"] >= 0.0
        assert plan["htn"]["root_task"]
        assert plan["history"]

    def test_execute_task_supports_plan_fetch_and_replanning(self):
        agent = PlanningAgent()
        created = asyncio.run(agent.create_plan("Reduce outage risk for payments"))

        fetched = asyncio.run(agent.execute_task({
            "action": "get_plan",
            "input_data": {"plan_id": created["plan_id"]},
        }))
        assert fetched["plan_id"] == created["plan_id"]

        replanned = asyncio.run(agent.execute_task({
            "action": "replan",
            "input_data": {
                "plan_id": created["plan_id"],
                "goal": "Reduce outage risk for payments and restore degraded volume",
                "constraints": ["must stay within budget"],
            },
        }))
        assert replanned["plan_id"] == created["plan_id"]
        assert replanned["version"] >= 2
