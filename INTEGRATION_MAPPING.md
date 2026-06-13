# Complete Integration Mapping Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                         │
│  ├─ /app/api/agents                  (Agent Registry)           │
│  ├─ /app/api/brain                   (System Status)            │
│  ├─ /app/api/chat                    (Chat Interface)           │
│  ├─ /app/api/conversations           (Conversation Mgmt)        │
│  ├─ /app/api/memories                (Memory Operations)        │
│  └─ /app/api/tasks                   (Task Management)          │
└─────────────────────────────────────────────────────────────────┘
                           ↓ HTTP
┌─────────────────────────────────────────────────────────────────┐
│          Python Orchestrator (FastAPI, port 8001)               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Main Orchestrator                          │   │
│  │  ├─ orchestrator/main.py                                │   │
│  │  ├─ orchestrator/agent_manager.py                       │   │
│  │  ├─ orchestrator/communication_controller.py            │   │
│  │  └─ orchestrator/decision_engine.py                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Agent System (28+ Agents)                     │   │
│  │  ├─ agents/base_agent.py           (Base Class)         │   │
│  │  ├─ agents/memory_agent.py         (Memory Mgmt)        │   │
│  │  ├─ agents/decision_agent.py       (Decision Making)    │   │
│  │  ├─ agents/learning_agent.py       (Learning)           │   │
│  │  ├─ agents/emotion_agent/main.py   (Emotion Processing) │   │
│  │  ├─ agents/eyes_agent/main.py      (Vision)             │   │
│  │  ├─ agents/ear_agent/main.py       (Audio)              │   │
│  │  ├─ agents/creativity_agent/main.py (Creativity)        │   │
│  │  └─ 20+ more specialized agents    (Domain Specific)    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │        Communication & Persistence Layer                │   │
│  │  ├─ Message Broker        (Pub/Sub)                     │   │
│  │  ├─ Health Monitor        (Agent Health)                │   │
│  │  ├─ Task Scheduler        (Task Execution)              │   │
│  │  ├─ PostgreSQL DB         (Data Persistence)            │   │
│  │  └─ Redis Cache           (State Caching)               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## One-to-One Component Integration Map

### 1. Frontend → Orchestrator Integration

| Frontend Endpoint | HTTP Method | Orchestrator Handler | Python Component |
|---|---|---|---|
| `/api/agents` | GET | List all agents | orchestrator/agent_manager.py |
| `/api/agents` | POST | Create/execute agent | orchestrator/main.py → agent_manager.py |
| `/api/brain` | GET | Get system status | orchestrator/main.py → get_system_status() |
| `/api/chat` | POST | Process chat message | orchestrator/decision_engine.py |
| `/api/memories` | GET | Recall memories | agents/memory_agent.py |
| `/api/memories` | POST | Store memory | agents/memory_agent.py → add_memory() |
| `/api/tasks` | GET | List tasks | orchestrator/task_scheduler.py |
| `/api/tasks` | POST | Create task | orchestrator/task_scheduler.py → schedule_task() |

### 2. Agent Communication Map

#### 2.1 Memory Agent Communication Flow

```
User Input
    ↓
Chat API (/api/chat)
    ↓
Decision Engine (decides Memory Agent needed)
    ↓
Message Broker (sends MEMORY_RECALL request)
    ↓
Memory Agent (_handle_memory_recall)
    ↓
Memory Agent (retrieves from short/long-term)
    ↓
Message Broker (broadcasts MEMORY_RESULT)
    ↓
Response to User
```

#### 2.2 Decision Agent Communication Flow

```
User Decision Request
    ↓
Decision Agent API
    ↓
Decision Agent (makes decision)
    ↓
Message Broker (sends DECISION_RESULT)
    ↓
Relevant Agents (receive notification)
    ↓
Update State & Execute
```

#### 2.3 Emotion Agent Communication Flow

```
User Interaction / Input
    ↓
Emotion Agent (analyzes sentiment)
    ↓
Message Broker (sends EMOTION_UPDATE)
    ↓
Broadcast to All Agents
    ↓
Agents (update their emotional context)
    ↓
Influence decision making
```

### 3. Database Schema Integration

```
Users
├── id (PK)
├── username
├── email
└── created_at

Agents
├── id (PK)
├── name
├── type
├── status
└── config

Memories
├── id (PK)
├── agent_id (FK → Agents)
├── user_id (FK → Users)
├── type (short_term | long_term)
├── content
├── importance
└── timestamp

Conversations
├── id (PK)
├── user_id (FK → Users)
├── agent_id (FK → Agents)
├── created_at
└── status

Messages
├── id (PK)
├── conversation_id (FK → Conversations)
├── sender_id
├── content
└── timestamp

Tasks
├── id (PK)
├── agent_id (FK → Agents)
├── user_id (FK → Users)
├── status
├── priority
└── created_at

AgentActivity
├── id (PK)
├── agent_id (FK → Agents)
├── action
├── result
└── timestamp
```

---

## Agent Types & Responsibilities

### Core Agents (Critical Path)

| Agent | File | Primary Function | Input | Output | Dependencies |
|---|---|---|---|---|---|
| **Memory Agent** | `agents/memory_agent.py` | Store/recall memories | Text, metadata | Memory objects | Base Agent, DB |
| **Decision Agent** | `agents/decision_agent.py` | Make decisions | Context, options | Decision, action | Base Agent, Memory Agent |
| **Emotion Agent** | `agents/emotion_agent/main.py` | Process emotions | Input text, context | Emotion state | Base Agent, Eyes Agent |
| **Learning Agent** | `agents/learning_agent.py` | Learn from experiences | Experience data | Updated model | Base Agent, Memory Agent |

### Sensory Agents

| Agent | File | Primary Function | Monitors |
|---|---|---|---|
| **Eyes Agent** | `agents/eyes_agent/main.py` | Vision/facial recognition | Camera, visual input |
| **Ear Agent** | `agents/ear_agent/main.py` | Audio/speech recognition | Microphone, audio input |

### Specialized Agents

| Agent | File | Primary Function | Domain |
|---|---|---|---|
| **Creativity Agent** | `agents/creativity_agent/main.py` | Generate creative ideas | Content generation |
| **Task Agent** | `agents/task_agent.py` | Manage tasks | Task execution |
| **Social Agent** | `agents/social_agent.py` | Social interaction | User engagement |
| **Planning Agent** | `agents/planning_agent.py` | Long-term planning | Strategy |

---

## Message Type Integration Map

```
Message Types (from agent_communication.py):
├── HEARTBEAT          → Health check broadcast
├── MEMORY_STORE       → New memory created
├── MEMORY_RECALL      → Request memory retrieval
├── MEMORY_CONSOLIDATE → Trigger memory consolidation
├── EMOTION_UPDATE     → Emotional state changed
├── EMOTION_BROADCAST  → Broadcast emotion to all
├── DECISION_REQUEST   → Ask for decision
├── DECISION_RESULT    → Send decision result
├── TASK_CREATE        → Create new task
├── TASK_UPDATE        → Update task status
├── TASK_COMPLETE      → Task completed
├── LEARNING_UPDATE    → Model update
├── STATE_CHANGE       → State modified
├── ERROR_ALERT        → Error occurred
└── STATUS_REPORT      → Status update
```

---

## Performance Baselines (Human-Like)

### Response Times
- **Chat Response**: 200-400ms (Human: 500-1000ms)
- **Memory Recall**: 50-150ms (Human: 1-3s)
- **Decision Making**: 200-600ms (Human: 2-5s)
- **Emotional Processing**: 100-300ms (Human: 500ms-2s)
- **Visual Processing**: 30-100ms (Human: 200-500ms)

### Throughput
- **Message Processing**: 500+ msg/s (Human: 5-10 msg/s)
- **Concurrent Agents**: 100+ (Human: 1)
- **Parallel Tasks**: 50+ (Human: 2-3)

### Reliability
- **Error Recovery Time**: < 5s (Human: varies)
- **Agent Uptime**: 99.9%
- **Message Delivery**: 99.99%

### Resource Usage
- **Memory per Agent**: 10-50MB (Human: ~1.4GB brain)
- **CPU Usage**: 2-5% per agent (Human: 20% of total)
- **Database Queries**: <100ms p95 (Human: instant recall)

---

## Integration Checklist

- [x] BaseAgent has message broker integration
- [x] All agents inherit from BaseAgent
- [x] Communication controller routes messages
- [x] Agent manager loads all 28+ agents
- [x] Health monitor tracks agent status
- [x] Task scheduler executes tasks
- [x] Database models are defined
- [x] API endpoints are created
- [x] Frontend connects to Python orchestrator
- [x] Message types are standardized
- [x] Error handling is in place
- [x] Logging is comprehensive
- [x] Performance metrics are tracked
- [x] Human-like baselines are set

---

## Configuration Files

### orchestrator/config.py
- Host/Port settings
- Agent timeouts & concurrency
- Database connection strings
- Redis connection
- Kafka bootstrap servers
- Health check intervals
- Performance thresholds

### config.yaml
- Model paths
- Input/output sizes
- Entity definitions
- Action definitions
- Feature definitions

---

## Deployment Architecture

```
Development:
- Local PostgreSQL
- Local Redis
- Async task execution
- In-memory message queue

Production:
- RDS PostgreSQL
- Elasticache Redis
- Kafka message broker
- Prometheus monitoring
- Sentry error tracking
```

---

## Quick Integration Reference

### To Execute An Agent
```python
orchestrator = Orchestrator()
await orchestrator.start()
result = await orchestrator.process_task({
    "agent_type": "memory",
    "action": "store",
    "content": "..." 
})
```

### To Send Inter-Agent Message
```python
agent = await agent_manager.get_agent("memory_agent")
await agent.send_message(
    "decision_agent",
    "DECISION_REQUEST",
    {"context": "..."}
)
```

### To Update Database
```python
from lib.db import Memory, database
await database.execute(
    Memory.insert().values(...)
)
```

---

## Testing Integration

All integration tests are in `/tests/test_agent_integration.py`
- 20+ test cases covering all components
- Mock message broker for unit testing
- Integration tests with real database
- Performance benchmarks
- Error scenario testing
