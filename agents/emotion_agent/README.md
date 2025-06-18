# Emotion Agent

The Emotion Agent is a key component of the Virtual Brain system, responsible for processing, analyzing, and managing emotional states. It works in conjunction with the Memory Agent to provide a comprehensive emotional intelligence system.

## Features

- **Emotion Processing**: Real-time processing of emotional states with intensity tracking and decay
- **Emotion Analysis**: Pattern recognition and impact analysis of emotional states
- **Emotion Storage**: Persistent storage of emotional data with efficient retrieval
- **REST API**: HTTP endpoints for emotion management and analysis
- **Monitoring**: Prometheus metrics and Sentry integration for observability
- **Event-Driven**: Kafka integration for event-based communication
- **Caching**: Redis integration for high-performance caching

## Components

### EmotionProcessor
Handles real-time processing of emotions, including:
- Emotion intensity tracking
- Emotion decay over time
- Current emotional state management
- Emotion history tracking

### EmotionStore
Manages persistent storage of emotions:
- JSON-based storage
- Efficient indexing and retrieval
- Emotion search capabilities
- Data persistence and backup

### EmotionAnalyzer
Analyzes emotional patterns and impacts:
- Pattern recognition in emotional states
- Impact analysis of emotions
- Recommendation generation
- Historical analysis

## API Endpoints

### Health Check
- `GET /health`: Check agent health status
- `GET /stats`: Get emotion processing statistics

### Emotion Management
- `POST /emotions`: Add a new emotion
- `GET /emotions/{emotion_id}`: Get specific emotion
- `GET /emotions/current`: Get current emotional states
- `GET /emotions/history`: Get emotion history
- `POST /emotions/search`: Search emotions by criteria

### Analysis
- `GET /analysis/{emotion_id}`: Get emotion analysis
- `GET /analysis/patterns`: Get detected emotion patterns
- `GET /analysis/impact`: Get emotion impact analysis

## Configuration

The Emotion Agent can be configured using environment variables with the `EMOTION_AGENT_` prefix:

### API Settings
- `API_HOST`: API host address (default: localhost)
- `API_PORT`: API port (default: 8001)
- `API_DEBUG`: Enable debug mode (default: false)

### Emotion Processing
- `EMOTION_HISTORY_MAX_SIZE`: Maximum size of emotion history (default: 1000)
- `EMOTION_DECAY_RATE`: Rate of emotion intensity decay (default: 0.1)
- `EMOTION_MIN_INTENSITY`: Minimum emotion intensity threshold (default: 0.1)

### Storage
- `EMOTION_STORE_PATH`: Path to emotion storage (default: databases/emotion_db/store)

### Redis
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 1)
- `REDIS_PASSWORD`: Redis password (optional)

### Kafka
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: localhost:9092)
- `KAFKA_GROUP_ID`: Kafka consumer group ID (default: emotion_agent)
- `KAFKA_TOPICS`: List of Kafka topics to subscribe to

### Monitoring
- `ENABLE_PROMETHEUS`: Enable Prometheus metrics (default: true)
- `PROMETHEUS_PORT`: Prometheus metrics port (default: 9091)
- `ENABLE_SENTRY`: Enable Sentry error tracking (default: false)
- `SENTRY_DSN`: Sentry DSN (required if Sentry is enabled)

## Development Setup

### Prerequisites
- Python 3.9+
- Redis
- Kafka
- Docker and Docker Compose (for containerized deployment)

### Local Development
1. Clone the repository
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
   pytest agents/emotion_agent/tests/
   ```
5. Start the agent:
   ```bash
   python -m agents.emotion_agent.main
   ```

### Docker Deployment
1. Build and start the containers:
   ```bash
   docker-compose -f docker/emotion_agent/docker-compose.yml up --build
   ```
2. Access the API at `http://localhost:8001`
3. View Prometheus metrics at `http://localhost:9091/metrics`

## Testing

The Emotion Agent includes comprehensive unit tests covering:
- Emotion processing and decay
- Emotion storage and retrieval
- Emotion analysis and pattern recognition
- API endpoints and error handling
- Integration with other components

Run tests with:
```bash
pytest agents/emotion_agent/tests/
```

## Monitoring

### Prometheus Metrics
The agent exposes Prometheus metrics at `/metrics`:
- Emotion processing rate
- Emotion storage statistics
- API request metrics
- System resource usage

### Sentry Integration
Error tracking is available through Sentry:
1. Enable Sentry in configuration
2. Set your Sentry DSN
3. Monitor errors in your Sentry dashboard

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 