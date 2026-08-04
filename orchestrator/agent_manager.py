import asyncio
import inspect
import importlib
import importlib.util
import logging
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

try:
    from .exceptions import (
        AgentNotFoundError,
        AgentInitializationError,
        AgentExecutionError,
        AgentTimeoutError,
    )
except ImportError:
    # Fallback: use built-in exceptions if exceptions module not yet available
    AgentNotFoundError = RuntimeError  # type: ignore
    AgentInitializationError = RuntimeError  # type: ignore
    AgentExecutionError = RuntimeError  # type: ignore
    AgentTimeoutError = asyncio.TimeoutError  # type: ignore

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages the lifecycle and execution of all agents in the system."""

    def __init__(self, config: Dict[str, Any], dependency_container: Optional[Dict[str, Any]] = None):
        self.config = config if isinstance(config, dict) else {}
        self.dependency_container = dependency_container or {}
        self.agents: Dict[str, Any] = {}
        self.agent_status: Dict[str, str] = {}
        self.agent_metadata: Dict[str, Dict[str, Any]] = {}
        self.capability_registry: Dict[str, Set[str]] = {}
        self.version_registry: Dict[str, str] = {}
        self.execution_stats: Dict[str, Dict[str, Any]] = {}
        self.failure_history: Dict[str, List[Dict[str, Any]]] = {}
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._registry_lock = asyncio.Lock()
        self._loaded_modules: Dict[str, Any] = {}
        # Event-driven capability registry subscribers
        # Callback signature: (event: str, agent_name: str, snapshot: dict) -> None
        self._registry_subscribers: List[Any] = []

    async def execute_agent_task(
        self,
        agent_name: str,
        task: Dict[str, Any],
        timeout_seconds: float = 30.0,
        execution_context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute an agent task through the canonical AgentManager contract."""
        task_payload = dict(task or {})
        if execution_context is not None:
            task_payload.setdefault("execution_context", {})
            task_payload["execution_context"] = {
                **task_payload.get("execution_context", {}),
                "request_id": getattr(execution_context, "request_id", None),
                "correlation_id": getattr(execution_context, "correlation_id", None),
                "trace_id": getattr(execution_context, "trace_id", None),
                "task_id": getattr(execution_context, "task_id", None),
                "agent_id": getattr(execution_context, "agent_id", None),
                "conversation_id": getattr(execution_context, "conversation_id", None),
                "timeout": getattr(execution_context, "timeout", None),
                "retry_count": getattr(execution_context, "retry_count", 0),
                "priority": getattr(execution_context, "priority", 2),
                "deadline": getattr(execution_context, "deadline", None),
                "span_id": getattr(execution_context, "span_id", None),
            }
        return await self.execute_agent_with_timeout(
            agent_name,
            task_payload,
            timeout_seconds=timeout_seconds,
            execution_context=execution_context,
        )

    
    async def start(self):
        """Start the agent manager."""
        logger.info("Starting agent manager...")
        self.is_running = True
        
        # Load and initialize all agents
        for agent_name, agent_config in self.config.get("agents", {}).items():
            try:
                await self.load_agent(agent_name, agent_config)
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")
        
        # Start health monitoring loop
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self.monitor_agents(), name="agent_manager.monitor")
        
        logger.info("Agent manager started successfully")
    
    async def stop(self):
        """Stop the agent manager and all agents."""
        logger.info("Stopping agent manager...")
        self.is_running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all agents
        for agent_name, agent in list(self.agents.items()):
            try:
                await self.stop_agent(agent_name)
            except Exception as e:
                logger.error(f"Error stopping agent {agent_name}: {e}")
        
        logger.info("Agent manager stopped successfully")
    
    def _normalize_agent_class_name(self, agent_name: str) -> str:
        """Convert a snake_case agent name into a PascalCase class name."""
        parts = agent_name.replace("_agent", "").split("_")
        return "".join(part.capitalize() for part in parts) + "Agent"

    async def load_agent(self, agent_name: str, agent_config: Dict[str, Any], reload: bool = False) -> None:
        """Load and initialize an agent."""
        async with self._registry_lock:
            if agent_name in self.agents and not reload:
                self.agent_status[agent_name] = "running" if self.agent_status.get(agent_name) == "running" else self.agent_status.get(agent_name, "initialized")
                return

        try:
            module_candidates = [
                f"agents.{agent_name}.main",
                f"agents.{agent_name}",
                agent_name,
            ]
            agent_module = None
            last_error = None

            for module_path in module_candidates:
                try:
                    agent_module = importlib.import_module(module_path)
                    break
                except ModuleNotFoundError as e:
                    last_error = e
                except ImportError as e:
                    last_error = e
                    # Keep trying other candidates when dependencies are missing or relative import issues occur.
                    logger.debug("agent_manager.candidate_import_failed module=%s error=%s", module_path, e)
                    continue

            if not agent_module:
                agents_root = Path(__file__).resolve().parents[1] / "agents"
                fallback_paths = [
                    agents_root / f"{agent_name}.py",
                    agents_root / agent_name / "main.py",
                    agents_root / agent_name / "__init__.py",
                ]
                for path in fallback_paths:
                    if path.exists():
                        try:
                            spec_name = f"agents._loaded_{agent_name}_{path.stem}"
                            spec = importlib.util.spec_from_file_location(spec_name, path)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                sys.modules[spec_name] = module
                                spec.loader.exec_module(module)
                                agent_module = module
                                self._loaded_modules[agent_name] = module
                                break
                        except Exception as e:
                            last_error = e

            if not agent_module:
                raise last_error or ModuleNotFoundError(f"Agent module for {agent_name} not found")

            class_name = self._normalize_agent_class_name(agent_name)
            agent_class = getattr(agent_module, class_name, None)
            if not agent_class:
                agent_class = next(
                    (getattr(agent_module, attr) for attr in dir(agent_module) if attr.lower().endswith("agent") and isinstance(getattr(agent_module, attr), type)),
                    None,
                )

            if not agent_class:
                raise AttributeError(f"Agent class not found for {agent_name}")

            agent = None
            signature = inspect.signature(agent_class)
            params = [
                p for p in signature.parameters.values()
                if p.name != "self" and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]

            if len(params) == 1 and params[0].name in ("agent_id", "agent_name", "id"):
                agent = agent_class(agent_name)
            elif len(params) == 1 and params[0].name in ("config", "config_path", "settings", "options"):
                agent = agent_class(agent_config)
            else:
                try:
                    agent = agent_class(agent_name)
                except TypeError:
                    try:
                        agent = agent_class(agent_config)
                    except TypeError:
                        agent = agent_class()

            if hasattr(agent, "agent_id"):
                try:
                    agent.agent_id = agent_name
                except Exception:
                    pass
            if hasattr(agent, "agent_type"):
                try:
                    agent.agent_type = agent_name.replace("_agent", "")
                except Exception:
                    pass

            if hasattr(agent, "config"):
                try:
                    agent.config = agent_config or {}
                except Exception:
                    pass

            if hasattr(agent, "dependencies") and self.dependency_container:
                try:
                    agent.dependencies = self.dependency_container
                except Exception:
                    pass

            if hasattr(agent, "set_dependencies"):
                try:
                    await agent.set_dependencies(self.dependency_container)
                except TypeError:
                    agent.set_dependencies(self.dependency_container)
                except Exception:
                    pass

            await agent.initialize()

            async with self._registry_lock:
                self.agents[agent_name] = agent
                self.agent_status[agent_name] = "initialized"
                self.agent_metadata[agent_name] = {
                    "agent_name": agent_name,
                    "module": getattr(agent_module, "__name__", None),
                    "class_name": agent_class.__name__,
                    "loaded_at": datetime.utcnow().isoformat(),
                    "config": agent_config or {},
                }
                self.version_registry[agent_name] = getattr(agent, "version", "unknown")
                self.capability_registry[agent_name] = set(getattr(agent, "capabilities", []) or [])
                self.execution_stats.setdefault(agent_name, {
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "timeouts": 0,
                    "last_execution_at": None,
                    "last_duration": 0.0,
                })
                self.failure_history.setdefault(agent_name, [])

            logger.info(f"Agent {agent_name} loaded successfully")
            await self._emit_registry_event("agent_loaded", agent_name)

        except Exception as e:
            self.agent_status[agent_name] = "error"
            self.failure_history.setdefault(agent_name, []).append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "phase": "load_agent",
            })
            logger.error(f"Failed to load agent {agent_name}: {e}")
            raise
    
    async def get_agent(self, agent_name: str) -> Optional[Any]:
        """Get an agent by name."""
        return self.agents.get(agent_name)

    async def unload_agent(self, agent_name: str) -> bool:
        """Safely stop and remove an agent from the registry."""
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        try:
            await self.stop_agent(agent_name)
        finally:
            async with self._registry_lock:
                self.agents.pop(agent_name, None)
                self.agent_status.pop(agent_name, None)
                self.agent_metadata.pop(agent_name, None)
                self.capability_registry.pop(agent_name, None)
                self.version_registry.pop(agent_name, None)
        await self._emit_registry_event("agent_unloaded", agent_name)
        return True

    async def reload_agent(self, agent_name: str) -> bool:
        """Reload an agent from its original configuration."""
        metadata = self.agent_metadata.get(agent_name, {})
        config = metadata.get("config", self.config.get("agents", {}).get(agent_name, {}))
        await self.unload_agent(agent_name)
        await self.load_agent(agent_name, config, reload=True)
        return True

    async def execute_agent_with_timeout(
        self,
        agent_name: str,
        task: Dict[str, Any],
        timeout_seconds: float = 30.0,
        execution_context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute an agent task with a hard timeout.
        Returns a structured error dict on timeout or exception instead of raising.
        """
        agent = self.agents.get(agent_name)
        if not agent:
            return {
                "status": "error",
                "error": f"Agent '{agent_name}' not found",
                "error_type": "AgentNotFoundError",
                "agent": agent_name,
            }
        if not hasattr(agent, "execute_task"):
            return {
                "status": "error",
                "error": f"Agent '{agent_name}' has no execute_task method",
                "error_type": "AgentExecutionError",
                "agent": agent_name,
            }
        
        prev_status = self.agent_status.get(agent_name, "initialized")
        self.agent_status[agent_name] = "running"

        try:
            start_time = datetime.utcnow()
            task_payload = dict(task or {})
            if execution_context is not None:
                task_payload.setdefault("execution_context", {})
                task_payload["execution_context"] = {
                    **task_payload.get("execution_context", {}),
                    "request_id": getattr(execution_context, "request_id", None),
                    "correlation_id": getattr(execution_context, "correlation_id", None),
                    "trace_id": getattr(execution_context, "trace_id", None),
                    "task_id": getattr(execution_context, "task_id", None),
                    "agent_id": getattr(execution_context, "agent_id", None),
                    "conversation_id": getattr(execution_context, "conversation_id", None),
                    "timeout": getattr(execution_context, "timeout", None),
                    "retry_count": getattr(execution_context, "retry_count", 0),
                    "priority": getattr(execution_context, "priority", 2),
                    "deadline": getattr(execution_context, "deadline", None),
                    "span_id": getattr(execution_context, "span_id", None),
                }

            executor = getattr(agent, "execute_task_with_policies", None)
            if callable(executor):
                result = await asyncio.wait_for(executor(task_payload), timeout=timeout_seconds)
            else:
                result = await asyncio.wait_for(agent.execute_task(task_payload), timeout=timeout_seconds)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            stats = self.execution_stats.setdefault(agent_name, {})
            stats["executions"] = stats.get("executions", 0) + 1
            stats["successes"] = stats.get("successes", 0) + 1
            stats["last_execution_at"] = datetime.utcnow().isoformat()
            stats["last_duration"] = duration
            self.agent_status[agent_name] = "running" if prev_status == "running" else "idle"

            return result if isinstance(result, dict) else {"status": "completed", "result": result}
        except asyncio.TimeoutError:
            logger.error(f"agent_manager.execute_timeout agent={agent_name} timeout={timeout_seconds}s")
            self.agent_status[agent_name] = "error"
            stats = self.execution_stats.setdefault(agent_name, {})
            stats["executions"] = stats.get("executions", 0) + 1
            stats["timeouts"] = stats.get("timeouts", 0) + 1
            stats["failures"] = stats.get("failures", 0) + 1
            self.failure_history.setdefault(agent_name, []).append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": "timeout",
                "error_type": "AgentTimeoutError",
                "phase": "execute_agent_with_timeout",
            })
            return {
                "status": "timeout",
                "error": f"Agent '{agent_name}' timed out after {timeout_seconds}s",
                "error_type": "AgentTimeoutError",
                "agent": agent_name,
            }
        except Exception as exc:
            logger.error(f"agent_manager.execute_error agent={agent_name} error={exc}")
            self.agent_status[agent_name] = "error"
            stats = self.execution_stats.setdefault(agent_name, {})
            stats["executions"] = stats.get("executions", 0) + 1
            stats["failures"] = stats.get("failures", 0) + 1
            self.failure_history.setdefault(agent_name, []).append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "phase": "execute_agent_with_timeout",
            })
            return {
                "status": "error",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "agent": agent_name,
            }

    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents and their status."""
        return [
            {
                "name": name,
                "status": self.agent_status.get(name, "unknown"),
                "config": self.config.get("agents", {}).get(name, {}),
                "version": self.version_registry.get(name, "unknown"),
            }
            for name in self.agents.keys()
        ]
    
    async def start_agent(self, agent_name: str) -> bool:
        """Start a specific agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent {agent_name} not found")
            return False
        
        try:
            if hasattr(agent, "resume") and self.agent_status.get(agent_name) == "paused":
                await agent.resume()
            elif hasattr(agent, "start"):
                await agent.start()
            elif hasattr(agent, "initialize"):
                await agent.initialize()
            self.agent_status[agent_name] = "running"
            return True
        except Exception as e:
            logger.error(f"Failed to start agent {agent_name}: {e}")
            return False
    
    async def stop_agent(self, agent_name: str) -> bool:
        """Stop a specific agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent {agent_name} not found")
            return False
        
        try:
            if hasattr(agent, "shutdown"):
                await agent.shutdown()
            elif hasattr(agent, "stop"):
                await agent.stop()
            self.agent_status[agent_name] = "stopped"
            return True
        except Exception as e:
            logger.error(f"Failed to stop agent {agent_name}: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent manager."""
        return {
            "status": "running" if self.is_running else "stopped",
            "registry_size": len(self.agents),
            "capabilities": {name: sorted(list(caps)) for name, caps in self.capability_registry.items()},
            "agents": {
                name: {
                    "status": status,
                    "config": self.config.get("agents", {}).get(name, {}),
                    "version": self.version_registry.get(name, "unknown"),
                    "metadata": self.agent_metadata.get(name, {}),
                    "execution": self.execution_stats.get(name, {}),
                }
                for name, status in self.agent_status.items()
            }
        }
    
    async def monitor_agents(self):
        """Monitor the health and status of all agents."""
        while self.is_running:
            for agent_name, agent in list(self.agents.items()):
                try:
                    if hasattr(agent, "get_health"):
                        health = await agent.get_health()
                    elif hasattr(agent, "get_status"):
                        health = await agent.get_status()
                    else:
                        health = {"status": self.agent_status.get(agent_name, "unknown")}

                    current_status = health.get("status", "unknown")
                    # Also accept {'healthy': True} format from sensory agents
                    if health.get("healthy") is True:
                        current_status = "healthy"
                    # 'initialized' is a valid non-error state — don't restart
                    if current_status in {"healthy", "running", "active", "paused",
                                          "stopped", "shutdown", "initialized", "idle"}:
                        continue

                    # Only restart if not intentionally stopped
                    metadata = self.agent_metadata.get(agent_name, {})
                    if metadata.get("intentionally_stopped", False):
                        continue

                    logger.warning(f"Agent {agent_name} health check failed: {health}")
                    await self.restart_agent(agent_name)
                    await self._emit_registry_event("agent_health_changed", agent_name)

                except Exception as e:
                    logger.error(f"Error monitoring agent {agent_name}: {e}")

            await asyncio.sleep(self.config.get("monitor_interval", 30))
    
    async def restart_agent(self, agent_name: str) -> bool:
        """Restart a specific agent."""
        logger.info(f"Restarting agent {agent_name}")
        
        # Stop agent
        if not await self.stop_agent(agent_name):
            return False
        
        # Wait for agent to stop
        await asyncio.sleep(1)
        
        # Start agent
        return await self.start_agent(agent_name)

    def get_capability_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of agent availability, capabilities, health, and load."""
        available: List[str] = [
            name for name, status in self.agent_status.items()
            if status not in {"error", "stopped", "shutdown"}
        ]
        capabilities: Dict[str, List[str]] = {
            name: sorted(list(caps))
            for name, caps in self.capability_registry.items()
        }
        health: Dict[str, str] = {
            name: self.agent_status.get(name, "unknown")
            for name in self.agents
        }
        load: Dict[str, int] = {
            name: int(stats.get("executions", 0))
            for name, stats in self.execution_stats.items()
        }
        return {
            "available_agents": available,
            "agent_capabilities": capabilities,
            "agent_health": health,
            "agent_load": load,
        }

    # ─── Event-driven capability registry ──────────────────────────────────

    def subscribe_registry(self, callback: Any) -> None:
        """
        Register a callback invoked whenever the capability registry changes.
        Signature: callback(event: str, agent_name: str, snapshot: dict) -> None
        Supports both sync and async callables.
        """
        if callback not in self._registry_subscribers:
            self._registry_subscribers.append(callback)

    def unsubscribe_registry(self, callback: Any) -> None:
        try:
            self._registry_subscribers.remove(callback)
        except ValueError:
            pass

    async def _emit_registry_event(self, event: str, agent_name: str) -> None:
        """Notify all subscribers of a registry change (non-blocking, best-effort)."""
        if not self._registry_subscribers:
            return
        snapshot = self.get_capability_snapshot()
        for cb in list(self._registry_subscribers):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(event, agent_name, snapshot))
                else:
                    cb(event, agent_name, snapshot)
            except Exception as exc:
                logger.debug("agent_manager.registry_event_error event=%s error=%s", event, exc)

    async def discover_agents(self) -> List[str]:
        """Discover available agent modules from the agents package."""
        agents_root = Path(__file__).resolve().parents[1] / "agents"
        discovered = []
        if not agents_root.exists():
            return discovered
        for child in agents_root.iterdir():
            if child.is_dir() and (child / "main.py").exists():
                discovered.append(child.name)
            elif child.is_file() and child.suffix == ".py" and child.stem not in {"__init__", "base_agent"}:
                discovered.append(child.stem)
        return sorted(set(discovered))

    async def get_failure_history(self, agent_name: str) -> List[Dict[str, Any]]:
        return list(self.failure_history.get(agent_name, []))

    async def initialize(self):
        """Initialize the agent manager."""
        logger.info("Initializing agent manager...")
        # Pre-load agent configurations
        for agent_name, agent_config in self.config.get("agents", {}).items():
            self.agent_status[agent_name] = "configured"
        logger.info(f"Agent manager initialized with {len(self.agent_status)} agents configured")
    
    async def shutdown(self):
        """Shutdown the agent manager."""
        await self.stop() 
