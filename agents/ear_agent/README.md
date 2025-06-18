# Ear Agent

The Ear Agent is a sophisticated audio processing system that mimics human ear behavior by capturing and processing audio input, recognizing speech and sounds, detecting emotions, and integrating with other agents in the system.

## Features

- **Audio Capture**: High-quality audio input processing with noise filtering
- **Speech Recognition**: Convert speech to text using multiple engines
- **Sound Classification**: Detect and classify non-speech sounds
- **Speaker Identification**: Recognize and differentiate between speakers
- **Emotion Detection**: Analyze emotional content in speech
- **Language Detection**: Identify spoken languages
- **Intent Detection**: Understand user intents and commands
- **Agent Integration**: Seamless communication with other agents

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download required models:
```bash
python -c "from speechbrain.pretrained import EncoderClassifier; EncoderClassifier.from_hparams(source='speechbrain/emotion-recognition-wav2vec2-IEMOCAP', savedir='models/emotion-recognition-wav2vec2-IEMOCAP')"
python -c "import fasttext; fasttext.util.download_model('lid.176.bin', if_exists='ignore')"
```

## Configuration

The Ear Agent is configured using a YAML file (`config/ear_agent_config.yaml`). Key configuration sections include:

- **Audio Capture**: Sample rate, channels, chunk size, etc.
- **Speech Recognition**: Engine selection, language models, confidence thresholds
- **Sound Classification**: Model settings, supported sounds
- **Speaker Identification**: Model parameters, confidence thresholds
- **Emotion Detection**: Supported emotions, detection thresholds
- **Language Detection**: Supported languages, detection thresholds
- **Intent Detection**: Model settings, supported intents
- **Agent Integration**: Endpoints for other agents

## Usage

### Basic Usage

```python
from ear_agent.main import EarAgent

async def main():
    # Initialize agent
    agent = EarAgent()
    await agent.initialize()
    
    try:
        # Start agent
        await agent.start()
        
        # Run for desired duration
        await asyncio.sleep(60)  # Run for 1 minute
        
        # Get conversation history
        history = agent.get_conversation_history()
        print("Conversation history:", history)
        
    finally:
        # Stop and cleanup
        await agent.stop()
        await agent.cleanup()

asyncio.run(main())
```

### Advanced Usage

#### Custom Event Handling

```python
def custom_callback(event):
    print(f"Received event: {event}")

# Start agent with custom callback
agent.start(callback=custom_callback)
```

#### Agent Integration

```python
from ear_agent.agent_integration import AgentIntegration

async def main():
    # Initialize integration
    integration = AgentIntegration()
    await integration.initialize()
    
    try:
        # Get emotional context
        context = await integration.get_emotion_context()
        print("Emotional context:", context)
        
        # Notify Brain Agent
        await integration.notify_brain("speech", {
            "text": "Hello, how are you?",
            "confidence": 0.95
        })
        
    finally:
        await integration.cleanup()

asyncio.run(main())
```

## Component Details

### Audio Listener

Handles audio input capture and preprocessing:
- Configurable sample rate and channels
- Noise filtering
- Voice activity detection
- Device selection

### Speech Recognizer

Converts speech to text:
- Multiple recognition engines (Whisper, Vosk, Google)
- Language model selection
- Confidence thresholds
- Wake word detection

### Sound Classifier

Detects and classifies non-speech sounds:
- YAMNet model integration
- Custom sound categories
- Confidence thresholds
- Real-time classification

### Speaker Identifier

Recognizes individual speakers:
- Resemblyzer model integration
- Speaker profile management
- Confidence thresholds
- Real-time identification

### Emotion Detector

Analyzes emotional content:
- SpeechBrain model integration
- Multiple emotion categories
- Confidence thresholds
- Real-time detection

### Language Detector

Identifies spoken languages:
- FastText and Wav2Vec2 models
- Multiple language support
- Confidence thresholds
- Real-time detection

### Intent Detector

Understands user intents:
- Rasa and Wav2Vec2 models
- Custom intent definitions
- Entity extraction
- Real-time detection

## Integration Points

The Ear Agent integrates with other agents through the `AgentIntegration` class:

- **Brain Agent**: Event notification, status updates
- **Emotion Agent**: Emotional context retrieval
- **Memory Agent**: Memory context querying
- **Personality Agent**: Personality trait retrieval

## Error Handling

The Ear Agent includes comprehensive error handling:
- Component initialization errors
- Processing pipeline errors
- Integration communication errors
- Resource cleanup errors

## Logging

Logging is configured to provide detailed information about:
- Component initialization
- Processing events
- Error conditions
- Integration status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 