# Memory Agent

A sophisticated memory management system that implements both short-term and long-term memory storage with semantic search capabilities.

## Features

- **Short-term Memory**: Fast, temporary storage for recent experiences and information
- **Long-term Memory**: Persistent storage for important memories
- **Memory Consolidation**: Automatic transfer of important short-term memories to long-term storage
- **Semantic Search**: Find memories using natural language queries
- **Emotional Context**: Track emotional associations with memories
- **Performance Metrics**: Monitor system performance and memory usage
- **Background Tasks**: Automatic cleanup and memory consolidation

## Architecture

The memory agent consists of several key components:

1. **Memory Types** (`memory_types.py`):
   - Defines different types of memories (short-term, long-term, emotional, etc.)
   - Specifies memory metadata and structure

2. **Memory Storage** (`memory_storage.py`):
   - Handles persistent storage using SQLite
   - Implements vector storage using FAISS for semantic search
   - Manages memory embeddings using sentence transformers

3. **Short-term Memory** (`short_term_memory.py`):
   - Manages temporary memory storage
   - Implements memory importance scoring
   - Handles memory expiration

4. **Long-term Memory** (`long_term_memory.py`):
   - Manages persistent memory storage
   - Implements memory consolidation
   - Tracks memory statistics

5. **Memory Agent** (`memory_agent.py`):
   - Coordinates between short-term and long-term memory
   - Provides a unified interface for memory operations
   - Manages background tasks

## Usage

```python
from memory_agent import MemoryAgent, MemorySource, EmotionType

# Initialize the memory agent
config = {
    "sqlite_path": "memory.db",
    "vector_dim": 768,
    "embedding_model": "all-MiniLM-L6-v2",
    "max_size": 1000,
    "consolidation_threshold": 0.7,
    "consolidation_interval": 3600
}
agent = MemoryAgent(config)

# Store a memory
memory_id = agent.store(
    data={
        "text": "The sky is blue",
        "confidence": 0.9,
        "context": {"location": "outside", "is_important": True}
    },
    source=MemorySource.EYES,
    emotion=EmotionType.JOY
)

# Retrieve a memory
memory = agent.retrieve(memory_id)

# Search memories
results = agent.search("What color is the sky?")

# Update a memory
agent.update(memory_id, {"confidence": 0.95})

# Delete a memory
agent.delete(memory_id)

# Get performance metrics
metrics = agent.get_performance_metrics()

# Clean up
agent.close()
```

## Configuration

The memory agent can be configured using the following parameters:

- `sqlite_path`: Path to SQLite database file
- `vector_dim`: Dimension of memory embeddings
- `embedding_model`: Name of the sentence transformer model
- `max_size`: Maximum number of short-term memories
- `consolidation_threshold`: Importance threshold for memory consolidation
- `consolidation_interval`: Time between consolidation runs (in seconds)

## Dependencies

- numpy: Numerical computing
- faiss-cpu: Vector similarity search
- sentence-transformers: Text embeddings
- python-dateutil: Date handling

## Performance Considerations

- Short-term memories are stored in memory for fast access
- Long-term memories are stored in SQLite for persistence
- Vector search is optimized using FAISS
- Background tasks run periodically to maintain system health
- Memory importance scoring helps prioritize important memories

## Error Handling

The system includes comprehensive error handling:
- All operations are wrapped in try-except blocks
- Errors are logged with detailed information
- Failed operations return None or False
- Background tasks automatically retry on failure

## Memory Types

The system supports several types of memories:

1. **Short-term Memory**:
   - Temporary storage
   - Fast access
   - Automatic expiration

2. **Long-term Memory**:
   - Persistent storage
   - Semantic search
   - Importance-based retention

3. **Emotional Memory**:
   - Emotional context
   - Higher importance weight
   - Longer retention

4. **Semantic Memory**:
   - Factual information
   - Concept relationships
   - Knowledge base

5. **Episodic Memory**:
   - Event sequences
   - Temporal context
   - Experience records

6. **Procedural Memory**:
   - Skill information
   - Action sequences
   - Learning patterns

## Components

1. **ShortTermMemory**: Handles recent memories with configurable retention period
2. **LongTermMemory**: Manages persistent storage of important memories
3. **ContextManager**: Maintains current context and context history
4. **MemoryStore**: Provides a unified interface for memory operations

## API Endpoints

- `GET /health`: Health check endpoint
- `GET /stats`: Get memory statistics
- `POST /memories`: Add a new memory
- `GET /memories/{memory_id}`: Get a specific memory
- `POST /memories/search`: Search memories
- `GET /context`: Get current context
- `GET /context/history`: Get context history

## Configuration

The Memory Agent can be configured using environment variables with the `MEMORY_AGENT_` prefix:

```bash
# API settings
MEMORY_AGENT_API_HOST=localhost
MEMORY_AGENT_API_PORT=8000
MEMORY_AGENT_API_DEBUG=false

# Memory settings
MEMORY_AGENT_SHORT_TERM_MEMORY_MAX_SIZE=1000
MEMORY_AGENT_SHORT_TERM_MEMORY_RETENTION_PERIOD=3600
MEMORY_AGENT_MEMORY_IMPORTANCE_THRESHOLD=0.7

# Context settings
MEMORY_AGENT_CONTEXT_HISTORY_MAX_SIZE=100
MEMORY_AGENT_CONTEXT_WINDOW_SIZE=10

# Redis settings
MEMORY_AGENT_REDIS_HOST=localhost
MEMORY_AGENT_REDIS_PORT=6379
MEMORY_AGENT_REDIS_DB=0
MEMORY_AGENT_REDIS_PASSWORD=

# Kafka settings
MEMORY_AGENT_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
MEMORY_AGENT_KAFKA_GROUP_ID=memory_agent
MEMORY_AGENT_KAFKA_TOPICS=["memory_events", "memory_commands"]

# Monitoring settings
MEMORY_AGENT_ENABLE_PROMETHEUS=true
MEMORY_AGENT_PROMETHEUS_PORT=9090
MEMORY_AGENT_ENABLE_SENTRY=false
MEMORY_AGENT_SENTRY_DSN=
```

## Development

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Redis
- Kafka

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/virtual-brain.git
cd virtual-brain
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run tests:
```bash
pytest tests/unit/test_memory_agent.py -v
```

### Docker

Build and run using Docker Compose:

```bash
cd docker/memory_agent
docker-compose up --build
```

## Testing

The Memory Agent includes comprehensive unit tests covering:

- Memory operations (add, get, search)
- Context management
- Memory consolidation
- Memory cleanup
- Statistics and monitoring

Run tests with:

```bash
pytest tests/unit/test_memory_agent.py -v
```

## Monitoring

The Memory Agent exposes Prometheus metrics at `/metrics` and can be integrated with Sentry for error tracking.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 