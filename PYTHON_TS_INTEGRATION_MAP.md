# Python ↔ TypeScript Integration Mapping

## System Architecture Overview

```
Frontend (Next.js/TypeScript)
    ↓
API Routes (/app/api/)
    ↓
Brain Service Layer (/lib/brain-service.ts)
    ↓
Database Layer (/lib/server/db-utils.ts)
    ↓
Python Orchestrator (FastAPI, Port 8001)
    ├── Agent Manager
    ├── Communication Controller
    ├── Health Monitor
    ├── Decision Engine
    └── Task Scheduler
        ↓
    28+ Specialized Python Agents
```

## One-to-One Integration Mapping

### 1. Memory Agent
**Python Files:**
- `agents/memory_agent.py` - Core memory agent
- `agents/memory_agent/main.py` - Entry point
- `agents/memory_agent/short_term.py` - Short-term storage
- `agents/memory_agent/long_term.py` - Long-term storage
- `agents/memory_agent/memory_agent.py` - Implementation
- `agents/memory_agent/memory_storage.py` - Storage handler
- `agents/memory_agent/memory_types.py` - Type definitions

**TypeScript Integration:**
```
/app/api/memories/
  ├── route.ts - CRUD endpoints
  ├── recall/route.ts - Memory recall
  └── consolidate/route.ts - Consolidation trigger

/lib/brain-service.ts
  └── recallMemories()
  └── storeMemory()
  └── consolidateMemories()

/lib/server/db-utils.ts
  └── Memory table operations
```

**API Endpoints:**
- `GET /api/memories?userId=X&query=Y` - Recall memories
- `POST /api/memories` - Store new memory
- `POST /api/memories/consolidate` - Trigger consolidation
- `GET /api/memories/search` - Search memories

**Message Types:**
- `MEMORY_STORE` - New memory storage
- `MEMORY_RECALL` - Recall request
- `MEMORY_CONSOLIDATE` - Consolidation trigger

---

### 2. Emotion Agent
**Python Files:**
- `agents/emotion_agent/main.py` - Entry point
- `agents/emotion_agent/emotion_analyzer.py` - Analysis engine
- `agents/emotion_agent/emotion_processor.py` - Processing logic
- `agents/emotion_agent/emotion_store.py` - Persistence
- `agents/emotion_agent/emotion_automation.py` - Automated responses
- `agents/emotion_agent/config.py` - Configuration

**TypeScript Integration:**
```
/app/api/emotions/
  ├── route.ts - Emotion endpoints
  ├── analyze/route.ts - Emotion analysis
  └── state/route.ts - Current emotion state

/components/dashboard/emotion-indicator.tsx
  └── Real-time emotion display

/lib/brain-service.ts
  └── analyzeEmotion()
  └── getEmotionState()
```

**API Endpoints:**
- `POST /api/emotions/analyze` - Analyze emotion input
- `GET /api/emotions/state` - Get current emotion state
- `POST /api/emotions/update` - Update emotion
- `GET /api/emotions/history` - Emotion history

**Message Types:**
- `EMOTION_ANALYZE` - Analyze emotion
- `EMOTION_UPDATE` - Update emotion state
- `EMOTION_RESPONSE` - Emotion-based response

---

### 3. Decision Agent
**Python Files:**
- `agents/decision_agent.py` - Core decision making
- `orchestrator/decision_engine.py` - Decision engine
- `agents/learning_agent.py` - Learning for decisions

**TypeScript Integration:**
```
/app/api/decisions/
  ├── route.ts - Decision endpoints
  └── make/route.ts - Make decision

/lib/brain-service.ts
  └── makeDecision()
  └── getDecisionMetrics()

/components/chat/chat-app.tsx
  └── Decision routing for responses
```

**API Endpoints:**
- `POST /api/decisions/make` - Make a decision
- `GET /api/decisions/metrics` - Decision metrics
- `POST /api/decisions/feedback` - Provide feedback

**Message Types:**
- `DECISION_REQUEST` - Request decision
- `DECISION_MADE` - Decision response

---

### 4. Learning Agent
**Python Files:**
- `agents/learning_agent.py` - Core learning
- `agents/learning_agent/main.py` - Entry point
- `agents/learning_agent/learning_processor.py` - Processing
- `agents/learning_agent/knowledge_base.py` - Knowledge storage
- `agents/learning_agent/experience_manager.py` - Experience tracking
- `agents/learning_agent/adaptation_engine.py` - Adaptation logic

**TypeScript Integration:**
```
/app/api/learning/
  ├── route.ts - Learning endpoints
  ├── experience/route.ts - Experience tracking
  └── knowledge/route.ts - Knowledge retrieval

/lib/brain-service.ts
  └── recordExperience()
  └── updateKnowledge()
  └── getKnowledgeBase()
```

**API Endpoints:**
- `POST /api/learning/experience` - Record experience
- `GET /api/learning/knowledge` - Get knowledge
- `POST /api/learning/update` - Update knowledge

**Message Types:**
- `EXPERIENCE_RECORD` - Record experience
- `KNOWLEDGE_UPDATE` - Update knowledge

---

### 5. Eyes Agent (Vision/Perception)
**Python Files:**
- `agents/eyes_agent/main.py` - Entry point
- `agents/eyes_agent/eyes_agent.py` - Core agent
- `agents/eyes_agent/object_detection.py` - Object detection
- `agents/eyes_agent/face_tracking.py` - Face detection
- `agents/eyes_agent/gaze_detection.py` - Gaze tracking
- `agents/eyes_agent/emotion.py` - Emotion from faces
- `agents/eyes_agent/eye_tracking.py` - Eye tracking
- `agents/perception_agent/` - Perception processing

**TypeScript Integration:**
```
/app/api/vision/
  ├── route.ts - Vision endpoints
  ├── analyze/route.ts - Image analysis
  └── detect/route.ts - Object/face detection

/components/dashboard/visual-processor.tsx
  └── Vision visualization

/lib/brain-service.ts
  └── analyzeImage()
  └── detectObjects()
  └── detectFaces()
```

**API Endpoints:**
- `POST /api/vision/analyze` - Analyze image
- `POST /api/vision/detect` - Detect objects/faces
- `POST /api/vision/gaze` - Detect gaze

**Message Types:**
- `VISION_PROCESS` - Process vision
- `OBJECT_DETECTED` - Object detection
- `FACE_DETECTED` - Face detection

---

### 6. Ear Agent (Audio/Speech)
**Python Files:**
- `agents/ear_agent/main.py` - Entry point
- `agents/ear_agent/speech_recognizer.py` - Speech recognition
- `agents/ear_agent/audio_listener.py` - Audio input
- `agents/ear_agent/emotion_detector.py` - Emotion from speech
- `agents/ear_agent/intent_detector.py` - Intent detection
- `agents/ear_agent/language_detector.py` - Language detection
- `agents/ear_agent/sound_classifier.py` - Sound classification

**TypeScript Integration:**
```
/app/api/audio/
  ├── route.ts - Audio endpoints
  ├── recognize/route.ts - Speech recognition
  └── analyze/route.ts - Audio analysis

/lib/brain-service.ts
  └── recognizeSpeech()
  └── analyzeAudio()
  └── detectIntent()
```

**API Endpoints:**
- `POST /api/audio/recognize` - Recognize speech
- `POST /api/audio/analyze` - Analyze audio
- `POST /api/audio/intent` - Detect intent

**Message Types:**
- `AUDIO_PROCESS` - Process audio
- `SPEECH_RECOGNIZED` - Speech recognition result
- `INTENT_DETECTED` - Intent detection result

---

### 7. Mouth Agent (Speech Output)
**Python Files:**
- `agents/mouth_agent/main.py` - Entry point
- `agents/mouth_agent/speech_generator.py` - Speech generation
- `agents/mouth_agent/tts_engine.py` - Text-to-speech
- `agents/mouth_agent/voice_controller.py` - Voice control
- `agents/mouth_agent/emotion_to_tone.py` - Emotion-based tone

**TypeScript Integration:**
```
/app/api/voice/
  ├── route.ts - Voice endpoints
  ├── synthesize/route.ts - TTS
  └── speak/route.ts - Speak text

/lib/brain-service.ts
  └── synthesizeSpeech()
  └── speak()
```

**API Endpoints:**
- `POST /api/voice/synthesize` - Generate speech
- `POST /api/voice/speak` - Speak text with emotion
- `GET /api/voice/voices` - List available voices

**Message Types:**
- `SPEECH_GENERATE` - Generate speech
- `VOICE_OUTPUT` - Output speech

---

### 8. Creativity Agent
**Python Files:**
- `agents/creativity_agent/main.py` - Entry point
- `agents/creativity_agent/idea_generator.py` - Idea generation
- `agents/creativity_agent/inspiration_engine.py` - Inspiration
- `agents/creativity_agent/pattern_recognizer.py` - Pattern recognition

**TypeScript Integration:**
```
/app/api/creativity/
  ├── route.ts - Creativity endpoints
  ├── ideas/route.ts - Generate ideas
  └── inspire/route.ts - Get inspiration

/lib/brain-service.ts
  └── generateIdea()
  └── getInspiration()
```

**API Endpoints:**
- `POST /api/creativity/ideas` - Generate ideas
- `GET /api/creativity/inspire` - Get inspiration
- `POST /api/creativity/explore` - Explore concepts

**Message Types:**
- `CREATIVITY_REQUEST` - Request creative content
- `IDEA_GENERATED` - Idea generation result

---

### 9. Social Agent
**Python Files:**
- `agents/social_agent/main.py` - Entry point
- `agents/social_agent/relationship_manager.py` - Relationship tracking
- `agents/social_agent/social_cues_parser.py` - Social cue parsing

**TypeScript Integration:**
```
/app/api/social/
  ├── route.ts - Social endpoints
  ├── relationships/route.ts - Relationship management
  └── cues/route.ts - Social cue detection

/lib/brain-service.ts
  └── analyzeRelationship()
  └── parseSocialCues()
```

**API Endpoints:**
- `POST /api/social/relationships` - Manage relationships
- `POST /api/social/cues` - Analyze social cues
- `GET /api/social/status` - Get social status

**Message Types:**
- `SOCIAL_ANALYZE` - Analyze social situation
- `RELATIONSHIP_UPDATE` - Update relationship

---

### 10. Motivation Agent
**Python Files:**
- `agents/motivation_agent/main.py` - Entry point
- `agents/motivation_agent/goal_tracker.py` - Goal tracking
- `agents/motivation_agent/incentive_engine.py` - Incentive management

**TypeScript Integration:**
```
/app/api/motivation/
  ├── route.ts - Motivation endpoints
  ├── goals/route.ts - Goal management
  └── incentives/route.ts - Incentive tracking

/lib/brain-service.ts
  └── setGoal()
  └── updateMotivation()
```

**API Endpoints:**
- `POST /api/motivation/goals` - Set goals
- `POST /api/motivation/update` - Update motivation
- `GET /api/motivation/status` - Get motivation status

**Message Types:**
- `GOAL_SET` - Set goal
- `MOTIVATION_UPDATE` - Update motivation

---

### 11-28+ Other Specialized Agents
(Time Agent, Planning Agent, Priority Agent, Search Agent, etc.)

Each follows the same pattern:
- Python implementation in `/agents/`
- TypeScript API route in `/app/api/`
- Message types in communication protocol
- Database persistence in `/lib/server/db-utils.ts`

## Integration Workflow

### Adding New Agent Integration

1. **Define Python Agent:**
   - Create agent in `/agents/`
   - Implement message handlers
   - Register with orchestrator

2. **Create API Route:**
   - Create `/app/api/[agent]/route.ts`
   - Add handler functions
   - Connect to database

3. **Update Brain Service:**
   - Add agent method to `/lib/brain-service.ts`
   - Register agent in `AGENT_REGISTRY`

4. **Update Database:**
   - Add tables if needed
   - Add logging queries
   - Update type definitions

5. **Update Components:**
   - Create UI components for agent interaction
   - Add visualizations if needed
   - Connect to API routes

## Message Flow Example: User Query

```
Frontend (Chat Input)
    ↓
POST /api/chat (TypeScript)
    ↓
Brain Service (TypeScript)
    ├─→ detectLanguage() [Ear Agent]
    ├─→ analyzeEmotion() [Emotion Agent]
    └─→ makeDecision() [Decision Agent]
    ↓
Python Orchestrator
    ├─→ LanguageAgent processes input
    ├─→ EmotionAgent analyzes tone
    └─→ DecisionAgent routes to handlers
    ↓
Specialized Agents (e.g., Memory, Creativity, Social)
    ↓
Response Generation (Mouth Agent)
    ↓
Response to Frontend

Frontend (Chat Response)
    ↓
Store in Database
    ↓
Update UI
```

## Database Schema Integration

```sql
-- User and Session
users (id, name, email, created_at)
sessions (id, user_id, created_at, expires_at)

-- Agent Data
agents (id, name, display_name, category, is_active)
agent_activity (id, agent_id, user_id, action, data, created_at)

-- Memories
memories (id, user_id, type, content, importance, created_at)
memory_access (id, memory_id, user_id, accessed_at)

-- Tasks
tasks (id, user_id, title, description, status, created_at)
task_progress (id, task_id, status, progress_data, updated_at)

-- Conversations
conversations (id, user_id, topic, created_at)
messages (id, conversation_id, role, content, created_at)

-- Emotions
emotions (id, user_id, emotion_type, intensity, cause, created_at)
emotion_trend (id, user_id, emotion_type, trend_data, updated_at)

-- Knowledge Base
knowledge_entries (id, user_id, key, value, source, created_at)
knowledge_updates (id, entry_id, old_value, new_value, updated_at)
```

## Testing Integration

```bash
# Start Python Orchestrator
python -m orchestrator.main

# Run Integration Tests
pytest tests/test_agent_integration.py -v

# Health Check
curl http://localhost:8001/health

# Agent Status
curl http://localhost:8001/agents/status
```

## Deployment Checklist

- [ ] All Python agents initialized and running
- [ ] API routes connected to orchestrator
- [ ] Database migrations applied
- [ ] Message broker operational
- [ ] Health monitor active
- [ ] Logging configured
- [ ] Metrics collecting
- [ ] Frontend tests passing
- [ ] Backend tests passing
- [ ] Integration tests passing
- [ ] Performance benchmarks met

## Monitoring & Metrics

### Key Metrics to Track

1. **Agent Metrics:**
   - Agent uptime/downtime
   - Message processing latency
   - Error rates
   - Response times

2. **System Metrics:**
   - Total message throughput
   - Queue depths
   - Memory usage
   - CPU usage

3. **Business Metrics:**
   - User engagement
   - Task completion rate
   - Memory recall accuracy
   - Decision quality

### Health Monitoring

- Heartbeat interval: 5 seconds
- Unhealthy threshold: 3 missed heartbeats
- Auto-recovery attempts: 3
- Recovery timeout: 10 seconds

---

This mapping ensures complete one-to-one integration between Python backend agents and TypeScript frontend routes with proper message passing and database persistence.
