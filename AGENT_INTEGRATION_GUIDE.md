# AI Virtual Brain System - Complete Integration Guide

## System Architecture Overview

Your system consists of three main layers:

### Layer 1: Python Backend (Orchestrator)
- **Location**: `/orchestrator/` directory
- **Components**:
  - `main.py` - FastAPI orchestrator server
  - `agent_manager.py` - Manages agent lifecycle
  - `agent_communication.py` - Message broker and event bus
  - `agent_lifecycle.py` - Health monitoring and recovery
  - `api_integration.py` - REST API for frontend integration
  - `communication_controller.py` - Kafka/Redis integration
  - `task_scheduler.py` - Task management and scheduling
  - `decision_engine.py` - Decision making framework

### Layer 2: Python Agents (28+ Specialized Agents)
- **Location**: `/agents/` directory
- **Base Classes**: `BaseAgent` with message broker integration
- **Agent Types**:
  - Memory Agent - Stores and recalls information
  - Emotion Agent - Emotional processing and response
  - Learning Agent - Adaptation and learning
  - Decision Agent - Decision making
  - Creativity Agent - Idea generation
  - Eyes Agent - Visual perception
  - Ear Agent - Audio processing
  - And 20+ more specialized agents

### Layer 3: Next.js Frontend
- **Location**: `/app/` directory
- **API Routes**: `/app/api/` 
- **Services**: `/lib/brain-service.ts`, `/lib/db-utils.ts`
- **Database**: SQLite with schema for agents, memories, tasks, conversations

## Agent Communication Flow

### 1. Direct Agent-to-Agent Communication

Agents can send messages to each other through the message broker:

```python
# In any agent
message_id = await self.send_message(
    recipient_agent_id="memory_agent",
    message_type="memory_store",
    content={
        "data": "important_fact",
        "importance": 0.8,
        "tags": ["learning"]
    },
    priority="high"
)
```

### 2. Broadcasting Messages

Agents can broadcast messages to all agents:

```python
# In any agent
message_id = await self.broadcast_message(
    message_type="emotion_update",
    content={
        "emotion": "happiness",
        "intensity": 0.7,
        "trigger": "successful_task"
    }
)
```

### 3. Message Types

Available message types (defined in `agent_communication.py`):

- `MEMORY_STORE` - Store memory
- `MEMORY_RECALL` - Recall memories
- `EMOTION_UPDATE` - Update emotions
- `TASK_CREATE` - Create task
- `TASK_UPDATE` - Update task
- `DECISION_REQUEST` - Request decision
- `DECISION_RESULT` - Decision result
- `LEARNING_UPDATE` - Learning update
- `PERCEPTION_INPUT` - Perception input
- `SOCIAL_INTERACTION` - Social interaction
- `PLANNING_REQUEST` - Planning request
- `CREATIVITY_IDEA` - Creative idea
- `REASONING_REQUEST` - Reasoning request
- `LANGUAGE_PROCESS` - Language processing
- `MOTIVATION_REQUEST` - Motivation request
- `ETHICS_QUERY` - Ethics query
- `HEALTH_CHECK` - Health check
- `STATE_UPDATE` - State update
- `CONNECTION_REQUEST` - Connection request
- `HEARTBEAT` - Heartbeat signal

## Frontend Integration

### Getting System Status

```typescript
// From frontend
const response = await fetch('/api/brain?action=status');
const status = await response.json();
```

### Executing Agent Operations

```typescript
// Execute a specific agent
const response = await fetch('/api/agents', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    action: 'execute',
    agentName: 'memory_agent',
    userId: 'user123',
    input: { query: 'recall important facts' }
  })
});
```

### Storing Memories

```typescript
// Store a memory through brain service
const response = await fetch('/api/brain', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    action: 'store-memory',
    userId: 'user123',
    content: 'User prefers coffee in the morning',
    memory_type: 'preference',
    importance: 0.8,
    tags: ['user_preference', 'beverages']
  })
});
```

### Creating Tasks

```typescript
// Create a task for the task agent
const response = await fetch('/api/brain', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    action: 'create-task',
    userId: 'user123',
    title: 'Review important documents',
    description: 'Review the quarterly reports',
    priority: 'high',
    due_date: '2024-06-30',
    tags: ['work', 'review']
  })
});
```

### Chat with Multi-Agent System

```typescript
// Send a chat message that routes through multiple agents
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: 'Help me plan my week' }
    ],
    userId: 'user123',
    conversationId: 'conv_123'
  })
});

// Stream the response
const reader = response.body?.getReader();
// Process streamed response...
```

## Database Schema

### Agents Table
```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  display_name TEXT,
  agent_type TEXT,
  description TEXT,
  category TEXT,
  icon TEXT,
  color TEXT,
  is_active BOOLEAN DEFAULT 1,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Memories Table
```sql
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  content TEXT,
  memory_type TEXT,
  importance REAL,
  tags TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Tasks Table
```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  priority TEXT,
  status TEXT,
  due_date TIMESTAMP,
  tags TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Conversations & Messages
```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  user_id TEXT,
  role TEXT,
  content TEXT,
  created_at TIMESTAMP,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Agent Activity Log
```sql
CREATE TABLE agent_activity (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  agent_name TEXT,
  action TEXT,
  input_data TEXT,
  output_data TEXT,
  success BOOLEAN,
  latency_ms INTEGER,
  created_at TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Agent Implementation Examples

### Creating a Custom Agent

1. **Create agent file** at `/agents/my_custom_agent/main.py`

```python
from ..base_agent import BaseAgent
from ...config import settings

class MyCustomAgent(BaseAgent):
    """Custom agent for specific functionality."""
    
    def __init__(self, config):
        super().__init__(agent_id="my_custom_agent", agent_type="custom")
        self.config = config
    
    async def initialize(self):
        """Initialize the agent."""
        await super().initialize()
        # Custom initialization
    
    async def execute_task(self, task):
        """Execute a task."""
        # Implement task execution logic
        
        # Send message to other agents if needed
        await self.send_message(
            recipient_agent_id="memory_agent",
            message_type="memory_store",
            content={"data": "task_result"}
        )
        
        return {"status": "completed"}
```

2. **Register in orchestrator config** (`config/orchestrator_config.yaml`)

```yaml
agents:
  my_custom_agent:
    display_name: "My Custom Agent"
    description: "Description of my agent"
    enabled: true
```

## API Endpoints Reference

### Health & Status
- `GET /health` - System health check
- `GET /agents` - List all agents
- `GET /agents/{agent_id}/status` - Get specific agent status
- `GET /stats` - Get system statistics

### Agent Management
- `POST /agents/{agent_id}/start` - Start an agent
- `POST /agents/{agent_id}/stop` - Stop an agent
- `POST /execute` - Execute agent with action

### Messaging
- `POST /messages/send` - Send point-to-point message
- `POST /messages/broadcast` - Broadcast message
- `GET /messages/history` - Get message history
- `GET /messages/queue/{agent_id}` - Get agent's message queue

## Health Monitoring & Recovery

### Automatic Health Checks
- Heartbeat timeout: 60 seconds
- Health check interval: 30 seconds
- Max errors before degradation: 10

### Recovery Mechanism
- Automatically restarts unhealthy agents
- Maintains agent state and memory
- Recovers connections with other agents

## Performance Considerations

### Message Queue Management
- Max queue size: 10,000 messages
- Priority-based processing (critical → low)
- Automatic queue trimming

### Memory Consolidation
- Short-term memory: 1,000 items max
- Long-term memory: 10,000 items max
- Consolidation threshold: 0.7 importance score

### Emotion Processing
- 5 primary emotions tracked
- Weighted emotional averaging
- Emotion history for pattern detection

## Troubleshooting

### Agent Not Responding
1. Check agent health status: `GET /agents/{agent_id}/status`
2. Review message queue: `GET /messages/queue/{agent_id}`
3. Check system logs for errors
4. Restart agent: `POST /agents/{agent_id}/stop` then start

### Messages Not Being Delivered
1. Verify recipient agent exists and is running
2. Check message type is valid
3. Review message history for failures
4. Ensure message broker is running

### Memory Not Being Stored
1. Verify memory agent is running
2. Check memory consolidation status
3. Review memory table in database
4. Check memory limits haven't been exceeded

## Next Steps

1. **Test agent communication** - Use the API to send messages between agents
2. **Implement agent handlers** - Add message handlers in each agent
3. **Connect frontend** - Update frontend to call orchestrator APIs
4. **Deploy system** - Deploy Python backend and Next.js frontend
5. **Monitor system** - Use health checks and statistics endpoints
6. **Scale agents** - Add more agents as system grows

## Support & Debugging

For debugging agent issues:
- Review logs: `/logs/main.log`
- Check message broker stats: `GET /stats`
- Monitor agent health: `GET /agents`
- Trace message flow: `GET /messages/history`
