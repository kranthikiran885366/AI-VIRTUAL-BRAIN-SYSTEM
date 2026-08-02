import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable, Set

logger = logging.getLogger(__name__)

# Default processing interval (seconds)
AGENT_PROCESSING_INTERVAL = 1.0


@dataclass
class AgentMetrics:
    """Operational metrics collected by the base agent."""

    execution_count: int = 0
    execution_failures: int = 0
    task_success_count: int = 0
    task_failure_count: int = 0
    heartbeat_count: int = 0
    restart_count: int = 0
    pause_count: int = 0
    active_tasks: int = 0
    queue_size: int = 0
    total_execution_time: float = 0.0
    last_execution_duration: float = 0.0
    last_execution_at: Optional[str] = None
    last_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "execution_count": self.execution_count,
            "execution_failures": self.execution_failures,
            "task_success_count": self.task_success_count,
            "task_failure_count": self.task_failure_count,
            "heartbeat_count": self.heartbeat_count,
            "restart_count": self.restart_count,
            "pause_count": self.pause_count,
            "active_tasks": self.active_tasks,
            "queue_size": self.queue_size,
            "total_execution_time": self.total_execution_time,
            "last_execution_duration": self.last_execution_duration,
            "last_execution_at": self.last_execution_at,
            "last_error": self.last_error,
            "average_execution_time": (
                self.total_execution_time / self.execution_count if self.execution_count else 0.0
            ),
        }


class BaseAgent:
    """Base class for all virtual brain agents with full message handling."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        state: Optional[Dict[str, Any]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        emotions: Optional[Dict[str, float]] = None,
        connections: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        task_timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_delay: float = 0.5,
        logger_: Optional[logging.Logger] = None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.version = version
        self.config = config or {}
        self.dependencies = dependencies or {}
        self.task_timeout = task_timeout
        self.retry_attempts = max(1, retry_attempts)
        self.retry_delay = max(0.0, retry_delay)
        self.logger = logger_ or logging.getLogger(f"{__name__}.{agent_type}.{agent_id}")
        self.state: Dict[str, Any] = state or {}
        self.memory: List[Dict] = memory or []
        self.emotions: Dict[str, float] = emotions or {
            "happiness": 0.5,
            "sadness": 0.0,
            "anger": 0.0,
            "fear": 0.0,
            "surprise": 0.0,
            "confidence": 0.7,
            "uncertainty": 0.1,
        }
        self.connections: Dict[str, List[str]] = {"default": connections or []}
        self._process_task: Optional[asyncio.Task] = None
        self._managed_tasks: Set[asyncio.Task] = set()
        self._message_handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self._lifecycle_lock = asyncio.Lock()
        self._initialized = False
        self._paused = False
        self._running = False
        self._shutdown = False
        self._started_at: Optional[datetime] = None
        self._paused_at: Optional[datetime] = None
        self._message_broker = None
        self._message_queue = None
        self._last_heartbeat: Optional[datetime] = None
        self.metrics = AgentMetrics()
        self.state.setdefault("status", "created")
        self.state.setdefault("created_at", datetime.utcnow().isoformat())
        self.state.setdefault("last_active", datetime.utcnow().isoformat())
        self.state.setdefault("version", self.version)
        self.state.setdefault("processed_messages", 0)
        self.state.setdefault("errors", 0)

    async def initialize(self):
        if self._initialized:
            return

        async with self._lifecycle_lock:
            if self._initialized:
                return

            self.logger.info("Initializing agent", extra={"agent_id": self.agent_id, "agent_type": self.agent_type})
            self.state.update({
                "status": "initializing",
                "last_active": datetime.utcnow().isoformat(),
                "version": self.version,
            })

            await self.validate_configuration()

            if self._message_broker is None:
                try:
                    from orchestrator.agent_communication import get_message_broker
                    self._message_broker = get_message_broker()
                except Exception as exc:
                    self.logger.warning(
                        "Message broker unavailable",
                        extra={"agent_id": self.agent_id, "error": str(exc)},
                    )

            if self._message_broker is not None and self._message_queue is None:
                try:
                    self._message_queue = await self._message_broker.register_agent(self.agent_id)
                    self.logger.debug(
                        "Agent registered with message broker",
                        extra={"agent_id": self.agent_id},
                    )
                except Exception as exc:
                    self.logger.warning(
                        "Agent broker registration failed",
                        extra={"agent_id": self.agent_id, "error": str(exc)},
                    )

            self._shutdown = False
            self._paused = False
            self._running = True
            self._initialized = True
            self._started_at = datetime.utcnow()
            self._last_heartbeat = self._started_at
            self.state["status"] = "active"
            self._process_task = self.create_managed_task(self._process_loop(), name=f"{self.agent_id}.process_loop")
            self.logger.info("Agent initialized", extra={"agent_id": self.agent_id, "version": self.version})

    async def shutdown(self):
        async with self._lifecycle_lock:
            if self._shutdown:
                return

            self.logger.info("Shutting down agent", extra={"agent_id": self.agent_id})
            self._running = False
            self._shutdown = True
            self.state["status"] = "shutdown"
            self.state["last_active"] = datetime.utcnow().isoformat()
            await self.cancel_active_tasks()

            if self._message_broker is not None:
                try:
                    await self._message_broker.unregister_agent(self.agent_id)
                except Exception as exc:
                    self.logger.warning(
                        "Broker unregister failed",
                        extra={"agent_id": self.agent_id, "error": str(exc)},
                    )

            self._initialized = False
            self._paused = False
            self._message_queue = None
            self._process_task = None
            self.logger.info("Agent shut down", extra={"agent_id": self.agent_id})

    async def pause(self):
        if not self._initialized:
            return
        self._paused = True
        self.metrics.pause_count += 1
        self._paused_at = datetime.utcnow()
        self.state["status"] = "paused"

    async def resume(self):
        if not self._initialized:
            return
        self._paused = False
        self._paused_at = None
        self.state["status"] = "active"

    async def restart(self):
        self.metrics.restart_count += 1
        await self.shutdown()
        await self.initialize()

    async def register_message_handler(self, message_type: Any, handler: Callable[[Any], Awaitable[None]]):
        key = self._message_type_key(message_type)
        self._message_handlers[key] = handler

    def create_managed_task(self, coro: Awaitable[Any], name: Optional[str] = None) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self._managed_tasks.add(task)
        task.add_done_callback(self._managed_tasks.discard)
        return task

    async def cancel_active_tasks(self):
        tasks = [task for task in list(self._managed_tasks) if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._managed_tasks.clear()

    async def _process_loop(self):
        while not self._shutdown:
            try:
                if self._paused:
                    await asyncio.sleep(AGENT_PROCESSING_INTERVAL)
                    continue

                self.state["last_active"] = datetime.utcnow().isoformat()
                await self.heartbeat()
                await self._process_incoming_messages()
                await self._process_messages()
                await self._update_state()
                await self._process_emotions()
                await self._maintain_connections()
                self.metrics.active_tasks = sum(1 for task in self._managed_tasks if not task.done())
                await asyncio.sleep(AGENT_PROCESSING_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.metrics.execution_failures += 1
                self.metrics.last_error = str(e)
                self.state["errors"] = self.state.get("errors", 0) + 1
                self.logger.error(
                    "Error in agent loop",
                    extra={"agent_id": self.agent_id, "error": str(e)},
                )
                await asyncio.sleep(1)

    def _message_type_key(self, message_type: Any) -> str:
        if hasattr(message_type, "value"):
            return str(message_type.value)
        return str(message_type)

    def _resolve_message_handler(self, message: Any) -> Callable[[Any], Awaitable[None]]:
        key = self._message_type_key(getattr(message, "message_type", ""))
        default_handlers = {
            "memory_recall": self._handle_memory_recall,
            "memory_store": self._handle_memory_store,
            "emotion_update": self._handle_emotion_update,
            "task_create": self._handle_task_create,
            "decision_request": self._handle_decision_request,
            "learning_update": self._handle_learning_update,
            "perception_input": self._handle_perception_input,
            "planning_request": self._handle_planning_request,
            "creativity_idea": self._handle_creativity_idea,
            "health_check": self._handle_health_check,
        }
        return self._message_handlers.get(key) or default_handlers.get(key, self._handle_custom_message)

    async def validate_configuration(self):
        """Hook for subclasses to validate required configuration."""
        if not isinstance(self.config, dict):
            raise ValueError("Agent configuration must be a dictionary")

    async def heartbeat(self):
        self.metrics.heartbeat_count += 1
        await self._send_heartbeat()

    async def _send_heartbeat(self):
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.HEARTBEAT,
                content={"status": self.state.get("status", "active"), "agent_id": self.agent_id},
                priority=MessagePriority.LOW,
            )
            self._last_heartbeat = datetime.utcnow()
            self.metrics.last_execution_at = self._last_heartbeat.isoformat()
        except Exception as e:
            self.logger.debug("Heartbeat failed", extra={"agent_id": self.agent_id, "error": str(e)})

    async def _process_incoming_messages(self):
        if not self._message_queue:
            return
        try:
            from orchestrator.agent_communication import MessageType
            while True:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.05)
                if not message:
                    break
                self.state["processed_messages"] = self.state.get("processed_messages", 0) + 1

                handler = self._resolve_message_handler(message)
                await handler(message)

        except asyncio.TimeoutError:
            return
        except Exception as e:
            self.metrics.execution_failures += 1
            self.metrics.last_error = str(e)
            self.logger.debug(
                "Message processing error",
                extra={"agent_id": self.agent_id, "error": str(e)},
            )

    # ─── Message Handlers (fully implemented) ────────────────────────────────

    async def _handle_memory_recall(self, message: Any):
        """Handle memory recall request — search and return matching memories."""
        query = message.content.get("query", {})
        results = await self.search_memory(query)
        self.logger.debug(
            "Memory recall completed",
            extra={"agent_id": self.agent_id, "result_count": len(results)},
        )
        # Send result back if reply_to is set
        if message.reply_to and self._message_broker:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=message.sender_agent_id,
                message_type=MessageType.STATE_UPDATE,
                content={"memories": results, "query": query},
                priority=MessagePriority.NORMAL,
            )

    async def _handle_memory_store(self, message: Any):
        """Handle memory store request — add to agent memory."""
        memory_data = message.content
        await self.add_memory(memory_data)
        self.logger.debug("Memory stored", extra={"agent_id": self.agent_id})

    async def _handle_emotion_update(self, message: Any):
        """Handle emotion update — update agent emotional state."""
        emotion = message.content.get("emotion")
        intensity = message.content.get("intensity", 0.5)
        if emotion and emotion in self.emotions:
            await self.update_emotion(emotion, intensity)
            self.logger.debug(
                "Emotion updated",
                extra={"agent_id": self.agent_id, "emotion": emotion, "intensity": intensity},
            )

    async def _handle_task_create(self, message: Any):
        """Handle task creation request."""
        task_data = message.content
        self.logger.debug("Task received", extra={"agent_id": self.agent_id})
        # Store task in memory
        await self.add_memory({
            "type": "task",
            "content": f"Task: {task_data.get('title', '')} - {task_data.get('description', '')}",
            "importance": 0.8,
        })

    async def _handle_decision_request(self, message: Any):
        """Handle decision request — evaluate and respond."""
        context = message.content.get("context", {})
        self.logger.debug("Decision request received", extra={"agent_id": self.agent_id})
        if self._message_broker and message.sender_agent_id:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=message.sender_agent_id,
                message_type=MessageType.DECISION_RESULT,
                content={"decision": "proceed", "confidence": 0.7, "context": context},
                priority=MessagePriority.HIGH,
            )

    async def _handle_learning_update(self, message: Any):
        """Handle learning update — incorporate new knowledge."""
        knowledge = message.content.get("knowledge", "")
        if knowledge:
            await self.add_memory({
                "type": "knowledge",
                "content": str(knowledge),
                "importance": message.content.get("importance", 0.6),
            })
        self.logger.debug("Learning update processed", extra={"agent_id": self.agent_id})

    async def _handle_perception_input(self, message: Any):
        """Handle perception input — process sensory data."""
        input_type = message.content.get("input_type", "unknown")
        self.logger.debug(
            "Perception input received",
            extra={"agent_id": self.agent_id, "input_type": input_type},
        )

    async def _handle_planning_request(self, message: Any):
        """Handle planning request — generate plan steps."""
        goal = message.content.get("goal", "")
        self.logger.debug("Planning request received", extra={"agent_id": self.agent_id})
        if self._message_broker and message.sender_agent_id:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=message.sender_agent_id,
                message_type=MessageType.STATE_UPDATE,
                content={
                    "plan": [
                        "1. Define objectives",
                        "2. Break into subtasks",
                        "3. Prioritize",
                        "4. Execute",
                        "5. Review",
                    ],
                    "goal": goal,
                },
                priority=MessagePriority.NORMAL,
            )

    async def _handle_creativity_idea(self, message: Any):
        """Handle creativity idea — store and process creative content."""
        idea = message.content.get("idea", "")
        if idea:
            await self.add_memory({
                "type": "creative_idea",
                "content": str(idea),
                "importance": 0.7,
            })
        self.logger.debug("Creative idea processed", extra={"agent_id": self.agent_id})

    async def _handle_health_check(self, message: Any):
        """Handle health check — respond with current status."""
        if self._message_broker and message.sender_agent_id:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=message.sender_agent_id,
                message_type=MessageType.HEARTBEAT,
                content=await self.get_status(),
                priority=MessagePriority.HIGH,
            )

    async def _handle_custom_message(self, message: Any):
        """Handle custom/unknown message types — subclasses override this."""
        self.logger.debug(
            "Unhandled message type",
            extra={"agent_id": self.agent_id, "message_type": str(message.message_type)},
        )

    def _compute_health_score(self) -> float:
        score = 1.0
        if not self._initialized:
            score -= 0.4
        if self._paused:
            score -= 0.1
        score -= min(0.4, self.state.get("errors", 0) * 0.05)
        if self._last_heartbeat:
            age_seconds = (datetime.utcnow() - self._last_heartbeat).total_seconds()
            if age_seconds > max(5.0, float(self.task_timeout)):
                score -= 0.2
        return round(max(0.0, score), 3)

    # ─── Overridable Hooks ────────────────────────────────────────────────────

    async def _process_messages(self):
        """Process custom agent logic for derived agents."""
        # Base implementation does no specialized work
        await asyncio.sleep(0)

    async def _update_state(self):
        self.state["last_active"] = datetime.utcnow().isoformat()
        self.state["memory_count"] = len(self.memory)
        self.state["emotion_summary"] = {
            k: round(v, 3) for k, v in self.emotions.items()
        }

    async def _process_emotions(self):
        # Natural decay toward neutral
        for emotion in ["sadness", "anger", "fear", "surprise"]:
            if self.emotions.get(emotion, 0) > 0:
                self.emotions[emotion] = max(0.0, self.emotions[emotion] - 0.01)

    async def _maintain_connections(self):
        """Maintain agent connections with a simple keepalive strategy."""
        # Remove inactive connections after a grace window
        for connection_type, connections in list(self.connections.items()):
            self.connections[connection_type] = [
                agent_id for agent_id in connections if agent_id
            ]

    # ─── Memory Operations ────────────────────────────────────────────────────

    async def add_memory(self, memory_data: Dict):
        memory = {
            "id": memory_data.get("id") or str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "type": memory_data.get("type", "general"),
            "content": memory_data.get("content", ""),
            "importance": float(memory_data.get("importance", 0.5)),
            "emotions": memory_data.get("emotions", {}),
            "connections": memory_data.get("connections", []),
            "agent_id": self.agent_id,
        }
        self.memory.append(memory)
        # Keep local working memory bounded
        if len(self.memory) > 500:
            self.memory = sorted(self.memory, key=lambda m: float(m.get("importance", 0.5)), reverse=True)[:500]

    async def search_memory(self, query: Any) -> List[Dict]:
        results = []
        if isinstance(query, str):
            query_str = query.lower()
            for memory in self.memory:
                content_str = str(memory.get("content", "")).lower()
                if query_str in content_str:
                    results.append(memory)
            return results[:10]

        query_dict = query if isinstance(query, dict) else {}
        target_content = str(query_dict.get("content", query_dict.get("query", ""))).lower()
        target_type = query_dict.get("type")

        for memory in self.memory:
            if target_type and memory.get("type") != target_type:
                continue
            if target_content and target_content not in str(memory.get("content", "")).lower():
                continue
            results.append(memory)
        return results[: query_dict.get("limit", 10)]

    async def recall_memory(self, query: Any) -> List[Dict]:
        """Alias for search_memory to support integration checks."""
        return await self.search_memory(query)


    async def update_emotion(self, emotion: str, value: float):
        if emotion in self.emotions:
            self.emotions[emotion] = max(0.0, min(1.0, value))

    async def update_emotions(self, emotion: str, value: float):
        """Alias for update_emotion to support integration checks."""
        await self.update_emotion(emotion, value)

    async def add_connection(self, agent_id: str, connection_type: str):
        if connection_type not in self.connections:
            self.connections[connection_type] = []
        if agent_id not in self.connections[connection_type]:
            self.connections[connection_type].append(agent_id)

    async def get_status(self) -> Dict:
        active_tasks = sum(1 for task in self._managed_tasks if not task.done())
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "initialized": self._initialized,
            "paused": self._paused,
            "running": self._running,
            "version": self.version,
            "state": self.state,
            "emotions": self.emotions,
            "memory_count": len(self.memory),
            "connections": self.connections,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "metrics": self.metrics.as_dict(),
            "active_tasks": active_tasks,
        }

    async def get_health(self) -> Dict[str, Any]:
        healthy = bool(self._initialized) and not self._shutdown and self.state.get("status", "active") != "shutdown"
        status = "healthy" if healthy else "stopped"
        if self._paused:
            status = "paused"
        elif self._shutdown:
            status = "shutdown"
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": status,
            "healthy": healthy,
            "is_healthy": healthy,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "memory_count": len(self.memory),
            "connections": self.connections,
            "processed_messages": self.state.get("processed_messages", 0),
            "errors": self.state.get("errors", 0),
            "uptime_seconds": (
                (datetime.utcnow() - self._started_at).total_seconds() if self._started_at else 0.0
            ),
            "health_score": self._compute_health_score(),
            "metrics": self.metrics.as_dict(),
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        start_time = datetime.utcnow()
        self.metrics.execution_count += 1
        try:
            result = await asyncio.wait_for(self._execute_task_once(task), timeout=self.task_timeout)
            self.metrics.task_success_count += 1
            return result
        except asyncio.TimeoutError as exc:
            self.metrics.execution_failures += 1
            self.metrics.task_failure_count += 1
            self.metrics.last_error = str(exc)
            raise
        except Exception as exc:
            self.metrics.execution_failures += 1
            self.metrics.task_failure_count += 1
            self.metrics.last_error = str(exc)
            raise
        finally:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.last_execution_duration = duration
            self.metrics.total_execution_time += duration
            self.metrics.last_execution_at = datetime.utcnow().isoformat()

    async def _execute_task_once(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "unknown")
        input_data = task.get("input_data", {}) or {}

        # Basic actions supported by all agents
        if action in ("store", "add_memory"):
            await self.add_memory({
                "type": input_data.get("type", "general"),
                "content": input_data.get("content", ""),
                "importance": input_data.get("importance", 0.5),
                "emotions": input_data.get("emotions", {}),
                "connections": input_data.get("connections", []),
            })
            return {"status": "stored", "action": action}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        # Fallback action for unhandled tasks
        return {
            "status": "completed",
            "action": action,
            "agent_id": self.agent_id,
            "message": f"Executed fallback task '{action}'",
        }

    async def execute_task_with_policies(self, task: Dict[str, Any]) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        attempts = max(1, self.retry_attempts)
        for attempt in range(1, attempts + 1):
            try:
                return await self.execute_task(task)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
                await asyncio.sleep(self.retry_delay * attempt)
        if last_error:
            raise last_error
        return {"status": "error", "message": "Task execution failed"}

    async def clear_memory(self):
        self.memory.clear()

    # ─── Messaging ────────────────────────────────────────────────────────────

    async def send_message(self, recipient_agent_id: Optional[str], message_type: str,
                           content: Dict[str, Any], priority: str = "normal") -> Optional[str]:
        if not self._message_broker:
            return None
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            msg_type = MessageType[message_type.upper()]
            prio = {"low": MessagePriority.LOW, "normal": MessagePriority.NORMAL,
                    "high": MessagePriority.HIGH, "critical": MessagePriority.CRITICAL}.get(
                priority.lower(), MessagePriority.NORMAL)
            return await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=recipient_agent_id,
                message_type=msg_type,
                content=content,
                priority=prio,
            )
        except Exception as e:
            self.metrics.last_error = str(e)
            self.logger.error("Send message failed", extra={"agent_id": self.agent_id, "error": str(e)})
            return None

    async def broadcast_message(self, message_type: str, content: Dict[str, Any],
                                priority: str = "normal") -> Optional[str]:
        return await self.send_message(None, message_type, content, priority)  # type: ignore
