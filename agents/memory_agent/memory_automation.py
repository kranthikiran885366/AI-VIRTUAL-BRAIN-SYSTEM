"""Memory automation — rule-based post-processing that persists changes via MemoryStorage."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_HISTORY = 1000
_DEFAULT_RULES_PATH = "data/memory_automation_rules.json"


class MemoryAutomation:
    """
    Rule-based memory automation.
    Each rule defines conditions + actions.  Actions are executed against the
    live MemoryStorage instance so every change is durable.
    """

    def __init__(self, storage: Optional[Any] = None):
        self.storage = storage          # MemoryStorage — injected after construction
        self.automation_rules: Dict[str, Dict] = {}
        self.execution_history: List[Dict] = []
        self.max_history: int = _DEFAULT_MAX_HISTORY
        self._rules_path: str = _DEFAULT_RULES_PATH
        self._initialized = False
        self._running = False
        self._memory_queue: asyncio.Queue = asyncio.Queue()
        self._loop_task: Optional[asyncio.Task] = None

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        if self._initialized:
            return
        await self._load_rules()
        self._running = True
        self._loop_task = asyncio.create_task(self._automation_loop(), name="memory_automation.loop")
        self._initialized = True
        logger.info("memory_automation.initialized rules=%d", len(self.automation_rules))

    async def shutdown(self):
        if not self._initialized:
            return
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        await self._save_rules()
        self._initialized = False
        logger.info("memory_automation.shutdown")

    # ─── Queue entry point ────────────────────────────────────────────────────

    async def enqueue(self, memory: Dict[str, Any]):
        """Enqueue a memory dict for rule processing."""
        if self._initialized:
            await self._memory_queue.put(memory)

    # ─── Internal loop ────────────────────────────────────────────────────────

    async def _automation_loop(self):
        while self._running:
            try:
                memory = await asyncio.wait_for(self._memory_queue.get(), timeout=1.0)
                await self._process_memory(memory)
                self._memory_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("memory_automation.loop_error error=%s", exc)
                await asyncio.sleep(1.0)

    async def _process_memory(self, memory: Dict[str, Any]):
        for rule_id, rule in list(self.automation_rules.items()):
            if not await self._matches_rule(memory, rule):
                continue
            try:
                for action in rule.get("actions", []):
                    await self._dispatch_action(memory, action)
                self._record_execution(memory, rule_id, True)
            except Exception as exc:
                logger.error("memory_automation.rule_error rule=%s error=%s", rule_id, exc)
                self._record_execution(memory, rule_id, False, str(exc))

    # ─── Condition evaluation ─────────────────────────────────────────────────

    async def _matches_rule(self, memory: Dict, rule: Dict) -> bool:
        for condition in rule.get("conditions", []):
            if not self._evaluate_condition(memory, condition):
                return False
        return True

    def _evaluate_condition(self, memory: Dict, condition: Dict) -> bool:
        field = condition.get("field", "")
        operator = condition.get("operator", "equals")
        value = condition.get("value")
        memory_value = memory.get(field)
        if memory_value is None:
            return False
        ops = {
            "equals": lambda a, b: a == b,
            "contains": lambda a, b: b in str(a),
            "greater_than": lambda a, b: float(a) > float(b),
            "less_than": lambda a, b: float(a) < float(b),
            "in": lambda a, b: a in b,
            "not_in": lambda a, b: a not in b,
        }
        fn = ops.get(operator)
        return bool(fn(memory_value, value)) if fn else False

    # ─── Action dispatch ──────────────────────────────────────────────────────

    async def _dispatch_action(self, memory: Dict, action: Dict):
        action_type = action.get("type", "")
        handlers: Dict[str, Callable] = {
            "categorize": self._handle_categorize,
            "tag": self._handle_tag,
            "link": self._handle_link,
            "archive": self._handle_archive,
            "prioritize": self._handle_prioritize,
            "summarize": self._handle_summarize,
        }
        handler = handlers.get(action_type)
        if handler:
            await handler(memory, action)
        else:
            logger.warning("memory_automation.unknown_action type=%s", action_type)

    async def _handle_categorize(self, memory: Dict, action: Dict):
        """Persist category update to storage."""
        mem_id = memory.get("id")
        category = action.get("category")
        if not mem_id or not category or not self.storage:
            return
        self.storage._write_sql(
            "UPDATE memories SET category = ?, updated_at = ? WHERE id = ?",
            (category, datetime.utcnow().isoformat(), mem_id),
        )
        self.storage.lru_cache.remove(mem_id)
        logger.debug("memory_automation.categorized id=%s category=%s", mem_id, category)

    async def _handle_tag(self, memory: Dict, action: Dict):
        """Merge new tags into existing tags and persist."""
        mem_id = memory.get("id")
        new_tags: List[str] = action.get("tags", [])
        if not mem_id or not new_tags or not self.storage:
            return
        existing = self.storage.retrieve(mem_id)
        if not existing:
            return
        merged = list(set((existing.metadata.tags or []) + new_tags))
        self.storage.update(mem_id, {"tags": merged}, reason="automation_tag")
        logger.debug("memory_automation.tagged id=%s tags=%s", mem_id, merged)

    async def _handle_link(self, memory: Dict, action: Dict):
        """Create relationship edges between this memory and target IDs."""
        mem_id = memory.get("id")
        target_ids: List[str] = action.get("memory_ids", [])
        rel_type_str: str = action.get("relationship_type", "associated")
        if not mem_id or not target_ids or not self.storage:
            return
        from .memory_types import RelationshipType
        try:
            rel_type = RelationshipType(rel_type_str)
        except ValueError:
            rel_type = RelationshipType.ASSOCIATED
        for target_id in target_ids:
            self.storage.add_relationship(mem_id, target_id, rel_type)
        logger.debug("memory_automation.linked id=%s targets=%s", mem_id, target_ids)

    async def _handle_archive(self, memory: Dict, action: Dict):
        """Archive the memory via storage."""
        mem_id = memory.get("id")
        if not mem_id or not self.storage:
            return
        self.storage.archive(mem_id)
        logger.debug("memory_automation.archived id=%s", mem_id)

    async def _handle_prioritize(self, memory: Dict, action: Dict):
        """Update the priority column in storage."""
        mem_id = memory.get("id")
        priority = action.get("priority")
        if not mem_id or priority is None or not self.storage:
            return
        self.storage._write_sql(
            "UPDATE memories SET priority = ?, updated_at = ? WHERE id = ?",
            (int(priority), datetime.utcnow().isoformat(), mem_id),
        )
        self.storage.lru_cache.remove(mem_id)
        logger.debug("memory_automation.prioritized id=%s priority=%d", mem_id, priority)

    async def _handle_summarize(self, memory: Dict, action: Dict):
        """
        Store a summary annotation in the memory's metadata context.
        Full LLM summarization is a hook — currently stores a length-based stub
        that can be replaced by injecting a summarizer callable.
        """
        mem_id = memory.get("id")
        if not mem_id or not self.storage:
            return
        existing = self.storage.retrieve(mem_id)
        if not existing:
            return
        content_str = str(existing.content)
        summary = content_str[:200] + ("…" if len(content_str) > 200 else "")
        ctx = existing.metadata.context or {}
        ctx["auto_summary"] = summary
        ctx["summarized_at"] = datetime.utcnow().isoformat()
        existing.metadata.context = ctx
        self.storage.update(mem_id, {}, reason="automation_summarize")
        logger.debug("memory_automation.summarized id=%s", mem_id)

    # ─── Execution history ────────────────────────────────────────────────────

    def _record_execution(self, memory: Dict, rule_id: str, success: bool, error: Optional[str] = None):
        self.execution_history.append({
            "id": f"exec-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "memory_id": memory.get("id"),
            "rule_id": rule_id,
            "success": success,
            "error": error,
        })
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]

    # ─── Rule CRUD ────────────────────────────────────────────────────────────

    async def add_rule(self, rule: Dict) -> str:
        rule_id = f"rule-{uuid.uuid4().hex[:12]}"
        self.automation_rules[rule_id] = rule
        await self._save_rules()
        return rule_id

    async def update_rule(self, rule_id: str, rule: Dict):
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        self.automation_rules[rule_id] = rule
        await self._save_rules()

    async def delete_rule(self, rule_id: str):
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        del self.automation_rules[rule_id]
        await self._save_rules()

    async def get_rule(self, rule_id: str) -> Dict:
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        return self.automation_rules[rule_id]

    async def get_rules(self) -> Dict[str, Dict]:
        return dict(self.automation_rules)

    async def get_execution_history(self) -> List[Dict]:
        return list(self.execution_history)

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "rule_count": len(self.automation_rules),
            "execution_count": len(self.execution_history),
            "success_count": sum(1 for e in self.execution_history if e["success"]),
            "error_count": sum(1 for e in self.execution_history if not e["success"]),
            "queue_size": self._memory_queue.qsize(),
            "is_running": self._running,
        }

    async def clear_rules(self):
        self.automation_rules.clear()
        await self._save_rules()

    async def clear_history(self):
        self.execution_history.clear()

    # ─── Persistence ──────────────────────────────────────────────────────────

    async def _load_rules(self):
        try:
            if os.path.exists(self._rules_path):
                with open(self._rules_path, "r") as f:
                    self.automation_rules = json.load(f)
                logger.info("memory_automation.rules_loaded count=%d", len(self.automation_rules))
        except Exception as exc:
            logger.warning("memory_automation.rules_load_failed error=%s", exc)
            self.automation_rules = {}

    async def _save_rules(self):
        try:
            os.makedirs(os.path.dirname(self._rules_path) or ".", exist_ok=True)
            with open(self._rules_path, "w") as f:
                json.dump(self.automation_rules, f, indent=2)
        except Exception as exc:
            logger.error("memory_automation.rules_save_failed error=%s", exc)
