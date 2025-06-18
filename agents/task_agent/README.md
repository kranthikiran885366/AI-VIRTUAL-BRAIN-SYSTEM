# Task Agent

The Task Agent is a key component of the Virtual Brain system responsible for managing, processing, and automating tasks in conjunction with the Memory and Emotion agents.

## Features

- Task Processing: Handle task creation, updates, and lifecycle management
- Task Analysis: Analyze tasks for patterns, metrics, and generate recommendations
- Task Automation: Define and execute automation rules for tasks
- Task Storage: Persistent storage of tasks and their metadata
- REST API: HTTP endpoints for task management
- Event-Driven: Kafka integration for task events
- Caching: Redis integration for performance optimization
- Monitoring: Prometheus metrics and health checks

## Components

### TaskProcessor
Handles task processing and scheduling:
- Task lifecycle management
- Task scheduling and execution
- Task status updates
- Task history tracking

### TaskStore
Manages persistent storage of tasks:
- Task storage and retrieval
- Task indexing and search
- Task backup and recovery
- Task metadata management

### TaskAnalyzer
Analyzes tasks and their patterns:
- Pattern detection
- Metric calculation
- Recommendation generation
- Analysis history tracking

### TaskAutomation
Handles task automation rules:
- Rule management
- Rule execution
- Action handling
- Execution history tracking

## API Endpoints

### Health Check
- `GET /api/v1/tasks/health`: Check agent health
- `GET /api/v1/tasks/stats`: Get agent statistics

### Task Management
- `POST /api/v1/tasks`: Create a new task
- `GET /api/v1/tasks/{task_id}`: Get a specific task
- `PUT /api/v1/tasks/{task_id}`: Update a task
- `DELETE /api/v1/tasks/{task_id}`: Delete a task
- `GET /api/v1/tasks/search`: Search tasks
- `GET /api/v1/tasks/current`: Get current tasks

### Automation
- `POST /api/v1/tasks/automation/rules`: Add automation rule
- `GET /api/v1/tasks/automation/rules`: Get all rules
- `GET /api/v1/tasks/automation/rules/{rule_id}`: Get specific rule
- `PUT /api/v1/tasks/automation/rules/{rule_id}`: Update rule
- `DELETE /api/v1/tasks/automation/rules/{rule_id}`: Delete rule

## Configuration

The Task Agent can be configured using environment variables:

### API Settings
- `TASK_AGENT_API_HOST`: API host (default: 0.0.0.0)
- `TASK_AGENT_API_PORT`: API port (default: 8002)
- `TASK_AGENT_API_PREFIX`: API prefix (default: /api/v1/tasks)

### Task Processing
- `TASK_AGENT_TASK_PROCESSING_INTERVAL`: Processing interval in seconds
- `TASK_AGENT_TASK_HISTORY_MAX_SIZE`: Maximum history size
- `TASK_AGENT_TASK_ANALYSIS_HISTORY_SIZE`: Analysis history size
- `TASK_AGENT_TASK_AUTOMATION_HISTORY_SIZE`: Automation history size

### Storage
- `TASK_AGENT_TASK_STORE_PATH`: Task storage path
- `TASK_AGENT_TASK_STORE_BACKUP_INTERVAL`: Backup interval in seconds
- `TASK_AGENT_TASK_STORE_MAX_BACKUPS`: Maximum number of backups

### Redis
- `TASK_AGENT_REDIS_HOST`: Redis host
- `TASK_AGENT_REDIS_PORT`: Redis port
- `TASK_AGENT_REDIS_DB`: Redis database
- `TASK_AGENT_REDIS_PASSWORD`: Redis password

### Kafka
- `TASK_AGENT_KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers
- `TASK_AGENT_KAFKA_CONSUMER_GROUP`: Kafka consumer group

### Monitoring
- `TASK_AGENT_PROMETHEUS_PORT`: Prometheus metrics port
- `TASK_AGENT_SENTRY_DSN`: Sentry DSN for error tracking

### Service URLs
- `TASK_AGENT_MEMORY_AGENT_URL`: Memory Agent URL
- `TASK_AGENT_EMOTION_AGENT_URL`: Emotion Agent URL

## Development Setup

### Prerequisites
- Python 3.9+
- Redis
- Kafka
- Docker and Docker Compose

### Local Development
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables
4. Run the agent:
   ```bash
   python -m agents.task_agent.main
   ```

### Docker Deployment
1. Build and start services:
   ```bash
   docker-compose -f docker/task_agent/docker-compose.yml up -d
   ```
2. View logs:
   ```bash
   docker-compose -f docker/task_agent/docker-compose.yml logs -f
   ```

## Testing

The Task Agent includes comprehensive unit tests:
```bash
pytest agents/task_agent/test_task_agent.py
```

## Monitoring

### Prometheus Metrics
- Task processing metrics
- Task storage metrics
- Task analysis metrics
- Task automation metrics
- API endpoint metrics

### Health Checks
- Component health status
- Service dependencies
- Resource usage
- Error rates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License. 