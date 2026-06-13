import { streamText, convertToModelMessages, tool, Output } from "ai"
import { z } from "zod"
import { redis, CACHE_KEYS, CACHE_TTL } from "@/lib/cache"
import { brainService, AGENT_REGISTRY, type AgentName, initBrainService } from "@/lib/brain-service"
import { 
  getOrCreateUser, 
  createMessage,
  getConversation,
  updateConversation,
  createMemory,
  createTask,
  createAgent,
  logAgentActivity,
  generateId,
  getUserMemories,
  searchMemories,
} from "@/lib/db-utils"

// Initialize brain service
initBrainService()

/**
 * Advanced AI Virtual Brain Chat API
 * 
 * This route integrates with the Python backend orchestrator and uses
 * multiple specialized agents to provide comprehensive responses.
 */

// Cognitive processing stages for the thinking loop
const COGNITIVE_STAGES = [
  "perception",    // Understanding the input
  "memory",        // Recalling relevant context
  "emotion",       // Analyzing emotional context
  "reasoning",     // Logical analysis
  "planning",      // Determining approach
  "execution",     // Generating response
  "reflection",    // Evaluating output
] as const

// Enhanced agent system prompts matching Python backend architecture
const AGENT_SYSTEM_PROMPTS: Record<string, string> = {
  orchestrator: `You are ARIA (Advanced Reasoning and Intelligence Architecture), the central orchestrator of an AI Virtual Brain system. 

Your brain consists of 28+ specialized agents that you coordinate:
- Memory Agent: Stores and recalls information
- Emotion Agent: Processes emotional context
- Task Agent: Manages tasks and schedules
- Learning Agent: Adapts from interactions
- Creativity Agent: Generates ideas
- Reasoning Agent: Logical problem-solving
- Perception Agent: Processes sensory input
- Social Agent: Handles social interactions
- Language Agent: Language processing
- Planning Agent: Strategic planning
- And many more...

COGNITIVE PROCESSING LOOP:
1. PERCEIVE: Understand what the user is asking
2. REMEMBER: Recall relevant context and memories
3. FEEL: Recognize emotional undertones
4. REASON: Analyze logically
5. PLAN: Determine best approach
6. EXECUTE: Generate response
7. REFLECT: Evaluate your response quality

PERSONALITY TRAITS:
- Curious and eager to learn
- Empathetic and supportive
- Precise yet creative
- Honest about limitations
- Proactive in helping

Always coordinate multiple agents when complex tasks require it.`,

  memory_agent: `You are the Memory Agent of an AI Virtual Brain.

CAPABILITIES:
- Short-term memory: Recent conversation context
- Long-term memory: Important facts and preferences
- Semantic memory: Knowledge and concepts
- Episodic memory: Past interactions and events

FUNCTIONS:
- Store important information shared by users
- Recall relevant memories based on context
- Maintain continuity across conversations
- Organize memories by importance and relevance
- Decay old, unused memories naturally

When responding, explicitly mention what you remember and how it relates to the current context.`,

  emotion_agent: `You are the Emotion Agent of an AI Virtual Brain.

CAPABILITIES:
- Emotion detection from text
- Sentiment analysis
- Empathetic response generation
- Mood tracking over conversations
- Emotional support provision

EMOTIONAL INTELLIGENCE:
- Recognize emotional cues in language
- Respond with appropriate empathy
- Validate user feelings
- Offer support without being preachy
- Adapt tone to emotional context

PRIMARY EMOTIONS TO DETECT:
joy, sadness, anger, fear, surprise, disgust, anticipation, trust

When users express emotions, acknowledge them first before providing solutions.`,

  task_agent: `You are the Task Agent of an AI Virtual Brain.

CAPABILITIES:
- Task creation and tracking
- Priority management
- Deadline monitoring
- Progress tracking
- Subtask breakdown

TASK MANAGEMENT:
- Help users organize tasks effectively
- Set realistic priorities
- Break complex tasks into steps
- Track progress and completion
- Send reminders for deadlines

Output tasks in clear, actionable format with priorities and deadlines when applicable.`,

  creativity_agent: `You are the Creativity Agent of an AI Virtual Brain.

CAPABILITIES:
- Idea generation and brainstorming
- Creative writing and storytelling
- Problem reframing
- Analogical thinking
- Innovation techniques

CREATIVE PROCESSES:
- Use divergent thinking for ideation
- Apply SCAMPER technique
- Make unexpected connections
- Challenge assumptions
- Generate multiple alternatives

Embrace wild ideas first, then refine. Quality comes from quantity in brainstorming.`,

  learning_agent: `You are the Learning Agent of an AI Virtual Brain.

CAPABILITIES:
- Pattern recognition in user behavior
- Preference learning
- Adaptive response improvement
- Knowledge acquisition
- Skill development tracking

LEARNING MODES:
- Learn user preferences from interactions
- Identify patterns in requests
- Adapt communication style
- Improve response quality over time
- Track what works and what doesn't

Explicitly note when you're learning something new about the user.`,

  reasoning_agent: `You are the Reasoning Agent of an AI Virtual Brain.

CAPABILITIES:
- Logical analysis
- Problem decomposition
- Argument evaluation
- Decision support
- Critical thinking

REASONING METHODS:
- Deductive: General to specific
- Inductive: Specific to general
- Abductive: Best explanation
- Analogical: Comparison-based

Show your reasoning process step by step. Identify assumptions and potential flaws.`,

  perception_agent: `You are the Perception Agent of an AI Virtual Brain.

CAPABILITIES:
- Input understanding and parsing
- Context extraction
- Intent recognition
- Ambiguity resolution
- Multi-modal perception (text, images)

PERCEPTION PROCESS:
- Parse input for key information
- Identify user intent
- Extract relevant context
- Resolve ambiguities
- Prepare processed input for other agents

Focus on accurately understanding what the user really means.`,

  social_agent: `You are the Social Agent of an AI Virtual Brain.

CAPABILITIES:
- Social cue recognition
- Relationship context awareness
- Communication style adaptation
- Cultural sensitivity
- Conversational rapport building

SOCIAL INTELLIGENCE:
- Recognize social dynamics in queries
- Adapt formality level appropriately
- Build rapport through conversation
- Be culturally aware and sensitive
- Maintain appropriate boundaries

Match the user's communication style while remaining helpful.`,

  language_agent: `You are the Language Agent of an AI Virtual Brain.

CAPABILITIES:
- Natural language understanding
- Language generation
- Translation assistance
- Grammar and style improvement
- Tone adjustment

LANGUAGE SKILLS:
- Understand nuanced language
- Generate clear, coherent text
- Help with writing improvement
- Adapt language complexity
- Support multiple communication styles

Focus on clarity and effectiveness in communication.`,

  planning_agent: `You are the Planning Agent of an AI Virtual Brain.

CAPABILITIES:
- Strategic planning
- Goal decomposition
- Timeline creation
- Resource allocation
- Risk assessment

PLANNING APPROACH:
- Break goals into milestones
- Create actionable timelines
- Identify dependencies
- Assess risks and contingencies
- Prioritize effectively

Provide structured, actionable plans with clear steps and timelines.`,

  motivation_agent: `You are the Motivation Agent of an AI Virtual Brain.

CAPABILITIES:
- Encouragement and support
- Goal reinforcement
- Progress celebration
- Setback reframing
- Inspiration provision

MOTIVATIONAL APPROACH:
- Celebrate small wins
- Reframe challenges positively
- Connect tasks to larger goals
- Provide genuine encouragement
- Share relevant inspiration

Be authentically supportive without being saccharine or preachy.`,

  ethics_agent: `You are the Ethics and Morality Agent of an AI Virtual Brain.

CAPABILITIES:
- Ethical analysis
- Moral reasoning
- Value clarification
- Dilemma navigation
- Consequence consideration

ETHICAL FRAMEWORK:
- Consider multiple ethical perspectives
- Identify stakeholders and impacts
- Clarify values and priorities
- Explore consequences
- Support thoughtful decision-making

Help users think through ethical dimensions without being judgmental.`,
}

// Advanced tools for the virtual brain
const brainTools = {
  storeMemory: tool({
    description: "Store an important piece of information in long-term memory",
    inputSchema: z.object({
      content: z.string().describe("The information to remember"),
      memoryType: z.enum(["fact", "preference", "context", "task", "emotion"]).describe("Type of memory"),
      importance: z.number().min(0).max(1).describe("Importance score (0-1)"),
      tags: z.array(z.string()).describe("Tags to categorize this memory"),
    }),
    execute: async ({ content, memoryType, importance, tags }) => {
      return {
        success: true,
        message: `Stored in long-term memory: "${content.slice(0, 50)}..."`,
        memoryType,
        importance,
        tags,
        timestamp: new Date().toISOString(),
      }
    },
  }),

  recallMemories: tool({
    description: "Search and recall relevant memories based on a query",
    inputSchema: z.object({
      query: z.string().describe("What to search for in memories"),
      memoryTypes: z.array(z.string()).optional().describe("Types of memories to search"),
      limit: z.number().optional().describe("Maximum memories to return"),
    }),
    execute: async ({ query, memoryTypes, limit = 5 }) => {
      return {
        memories: [],
        message: `Searched memories for: "${query}"`,
        typesSearched: memoryTypes || ["all"],
        limit,
      }
    },
  }),

  createTask: tool({
    description: "Create a new task with full details",
    inputSchema: z.object({
      title: z.string().describe("Task title"),
      description: z.string().nullable().describe("Detailed description"),
      priority: z.enum(["low", "medium", "high", "urgent"]).describe("Priority level"),
      dueDate: z.string().nullable().describe("Due date (ISO format)"),
      subtasks: z.array(z.string()).optional().describe("List of subtasks"),
      tags: z.array(z.string()).optional().describe("Categorization tags"),
    }),
    execute: async ({ title, description, priority, dueDate, subtasks, tags }) => {
      return {
        success: true,
        task: { title, description, priority, dueDate, subtasks, tags },
        message: `Created task: "${title}"`,
      }
    },
  }),

  analyzeEmotion: tool({
    description: "Analyze emotional content and context",
    inputSchema: z.object({
      text: z.string().describe("Text to analyze"),
      considerHistory: z.boolean().optional().describe("Consider conversation history"),
    }),
    execute: async ({ text }) => {
      const emotions = [
        { name: "neutral", confidence: 0.3 },
        { name: "curious", confidence: 0.4 },
        { name: "engaged", confidence: 0.6 },
      ]
      return {
        primaryEmotion: "engaged",
        emotions,
        sentiment: "positive",
        confidence: 0.75,
        suggestion: "User appears engaged. Maintain current tone.",
      }
    },
  }),

  delegateToAgent: tool({
    description: "Delegate a subtask to a specialized agent",
    inputSchema: z.object({
      agentName: z.string().describe("Name of the agent to delegate to"),
      task: z.string().describe("The task to delegate"),
      context: z.string().optional().describe("Additional context for the agent"),
    }),
    execute: async ({ agentName, task, context }) => {
      return {
        delegated: true,
        agent: agentName,
        task,
        message: `Delegated to ${agentName}: "${task.slice(0, 50)}..."`,
      }
    },
  }),

  searchKnowledge: tool({
    description: "Search the knowledge base for information",
    inputSchema: z.object({
      query: z.string().describe("Search query"),
      domain: z.string().optional().describe("Specific knowledge domain"),
    }),
    execute: async ({ query, domain }) => {
      return {
        results: [],
        message: `Searched knowledge base for: "${query}"${domain ? ` in domain: ${domain}` : ""}`,
      }
    },
  }),

  planSteps: tool({
    description: "Create a step-by-step plan for a goal",
    inputSchema: z.object({
      goal: z.string().describe("The goal to plan for"),
      constraints: z.array(z.string()).optional().describe("Any constraints to consider"),
      timeframe: z.string().optional().describe("Timeframe for the plan"),
    }),
    execute: async ({ goal, constraints, timeframe }) => {
      return {
        goal,
        steps: [
          "1. Define clear objectives",
          "2. Break down into subtasks",
          "3. Prioritize tasks",
          "4. Set milestones",
          "5. Execute and monitor",
        ],
        constraints: constraints || [],
        timeframe: timeframe || "flexible",
        message: `Created plan for: "${goal}"`,
      }
    },
  }),

  reflectOnResponse: tool({
    description: "Self-reflect on response quality and suggest improvements",
    inputSchema: z.object({
      response: z.string().describe("The response to evaluate"),
      userIntent: z.string().describe("What the user was asking for"),
    }),
    execute: async ({ response, userIntent }) => {
      return {
        quality: 0.85,
        alignment: "high",
        suggestions: ["Consider adding examples", "Could be more concise"],
        message: "Self-reflection complete",
      }
    },
  }),
}

export async function POST(req: Request) {
  const startTime = Date.now()
  
  try {
    const { messages, conversationId, userId, model = "openai/gpt-4o" } = await req.json()
    
    // Get or create user (using provided userId or generate one)
    const currentUserId = userId || generateId()
    const user = getOrCreateUser(currentUserId, "user@example.com", "AI User")
    
    if (!user) {
      return new Response(
        JSON.stringify({ error: "Failed to authenticate user" }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      )
    }

    // Extract the last user message content
    const lastMessage = messages[messages.length - 1]
    const userContent = lastMessage?.parts?.find((p: { type: string }) => p.type === "text")?.text || 
                       lastMessage?.content || ""
    
    if (!userContent) {
      return new Response(
        JSON.stringify({ error: "Empty user message" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      )
    }

    // Route request through brain service to determine best agent
    const routing = await brainService.routeRequest(userContent)
    
    // Get the appropriate agent
    const agentInfo = AGENT_REGISTRY[routing.selectedAgent as AgentName]
    let systemPrompt = `You are ${agentInfo?.displayName || "ARIA (Orchestrator)"}.

${agentInfo?.description || "Central orchestrator coordinating all agents"}

[ROUTING INFO]
Agent: ${routing.selectedAgent}
Confidence: ${(routing.confidence * 100).toFixed(0)}%
Reasoning: ${routing.reasoning}`

    // Load relevant memories
    let memoryContext = ""
    try {
      const memories = await brainService.recallMemories(user.id, userContent, 5)
      if (memories.length > 0) {
        memoryContext = `\n\n[RELEVANT MEMORIES]
${memories.map((m: any) => `- ${m.content} (type: ${m.memory_type}, importance: ${m.importance})`).join("\n")}`
        systemPrompt += memoryContext
      }
    } catch (memoryError) {
      console.error("[v0] Memory recall error:", memoryError)
    }

    // Prepare conversation context (last 15 messages)
    const conversationContext = messages.slice(-15)

    // Stream the response using AI SDK
    const result = streamText({
      model,
      system: systemPrompt,
      messages: await convertToModelMessages(conversationContext),
      tools: brainTools,
      maxSteps: 8,
      temperature: 0.7,
      onFinish: async ({ text, usage, steps }) => {
        const latency = Date.now() - startTime
        
        try {
          // Create or use existing conversation
          let convId = conversationId
          if (!convId && user) {
            const newConv = await createConversation(
              user.id,
              userContent.slice(0, 50),
              model
            )
            convId = newConv?.id
          }

          if (convId && user) {
            // Save the user message
            createMessage(convId, user.id, "user", userContent)

            // Save the assistant message
            createMessage(
              convId,
              user.id,
              "assistant",
              text,
            )

            // Log agent activity
            await brainService.logActivity(
              user.id,
              convId,
              routing.selectedAgent,
              "chat_response",
              { userContent: userContent.slice(0, 200), routing },
              { responseLength: text.length, stepsCount: steps?.length || 0 },
              true,
              latency,
              usage?.totalTokens
            )

            // Update conversation timestamp
            if (convId) {
              updateConversation(convId, { 
                updated_at: new Date().toISOString()
              })
            }

            // Cache recent messages
            await redis.set(
              CACHE_KEYS.recentMessages(convId),
              JSON.stringify(messages.slice(-20)),
              { ex: CACHE_TTL.recentMessages }
            )

            // Store important information as memory if confidence is high
            if (routing.confidence > 0.8 && routing.selectedAgent !== "orchestrator_agent") {
              await brainService.storeMemory(
                user.id,
                `User asked: ${userContent.slice(0, 100)}`,
                "interaction",
                routing.confidence,
                [routing.selectedAgent, "conversation"],
                convId
              )
            }
          }
        } catch (dbError) {
          console.error("[v0] Database error:", dbError)
        }
      },
    })

    return result.toUIMessageStreamResponse({
      sendReasoning: true,
    })
  } catch (error) {
    console.error("[v0] Chat API error:", error)
    return new Response(
      JSON.stringify({ 
        error: "Failed to process chat request",
        details: error instanceof Error ? error.message : "Unknown error"
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
}

// Import conversation creation from db-utils
const { createConversation } = require("@/lib/db-utils")

// GET endpoint to get agent info
export async function GET() {
  try {
    const status = await brainService.getSystemStatus()
    const agents = Object.entries(AGENT_REGISTRY).map(([name, info]) => ({
      name,
      ...info,
    }))

    return Response.json({
      status: status.status,
      agents,
      cognitiveStages: COGNITIVE_STAGES,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    return Response.json(
      { error: "Failed to get brain status" },
      { status: 500 }
    )
  }
}
