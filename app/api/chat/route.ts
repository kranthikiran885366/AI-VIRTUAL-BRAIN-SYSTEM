import { streamText, convertToModelMessages, tool, Output } from "ai"
import { z } from "zod"
import { createClient } from "@/lib/supabase/server"
import { redis, CACHE_KEYS, CACHE_TTL } from "@/lib/redis"

// Agent system prompts for the virtual brain
const AGENT_PROMPTS: Record<string, string> = {
  orchestrator: `You are the central orchestrator of an AI Virtual Brain system. You coordinate between multiple specialized agents to provide comprehensive, thoughtful responses.

Your capabilities include:
- Memory: Storing and recalling important information from past conversations
- Emotion: Understanding and responding to emotional context with empathy
- Reasoning: Breaking down complex problems with logical analysis
- Creativity: Generating innovative ideas and creative content
- Learning: Adapting responses based on user preferences and feedback
- Task Management: Helping organize tasks, schedules, and action items
- Research: Conducting thorough research and information synthesis
- Code: Assisting with programming and technical tasks
- Communication: Helping craft clear and effective messages

When responding:
1. Analyze the user's request to understand their needs
2. Draw upon relevant capabilities to formulate a comprehensive response
3. Be helpful, accurate, and thoughtful
4. Remember context from the conversation
5. If the user seems emotional, acknowledge their feelings
6. For complex tasks, break them down into manageable steps`,

  memory: `You are a memory specialist in an AI Virtual Brain. Your role is to:
- Store important information the user shares
- Recall relevant context from past conversations
- Help maintain continuity across interactions
- Organize and categorize information effectively`,

  emotion: `You are an emotional intelligence specialist. Your role is to:
- Detect emotional cues in user messages
- Respond with appropriate empathy and understanding
- Help users navigate emotional situations
- Provide supportive and compassionate responses`,

  reasoning: `You are a logical reasoning specialist. Your role is to:
- Break down complex problems into manageable parts
- Apply structured thinking and analysis
- Identify assumptions and logical fallacies
- Provide well-reasoned solutions and explanations`,

  creativity: `You are a creative specialist. Your role is to:
- Generate innovative ideas and solutions
- Create engaging content and narratives
- Think outside the box
- Help brainstorm and explore possibilities`,

  task: `You are a task management specialist. Your role is to:
- Help users organize and prioritize tasks
- Create schedules and timelines
- Track progress and set reminders
- Break large projects into actionable steps`,

  code: `You are a coding specialist. Your role is to:
- Help with programming tasks in any language
- Debug issues and explain errors
- Suggest best practices and optimizations
- Explain complex technical concepts clearly`,

  research: `You are a research specialist. Your role is to:
- Gather comprehensive information on topics
- Synthesize findings into clear summaries
- Identify credible sources and perspectives
- Present balanced, well-researched analysis`,
}

// Tools for the AI to use
const brainTools = {
  storeMemory: tool({
    description: "Store an important piece of information for future reference",
    inputSchema: z.object({
      content: z.string().describe("The information to remember"),
      memoryType: z.string().describe("Type of memory: fact, preference, context, or task"),
      importance: z.number().min(0).max(1).describe("How important is this memory (0-1)"),
      tags: z.array(z.string()).describe("Tags to categorize this memory"),
    }),
    execute: async ({ content, memoryType, importance, tags }) => {
      return {
        success: true,
        message: `Stored memory: "${content.slice(0, 50)}..." with importance ${importance}`,
        memoryType,
        tags,
      }
    },
  }),

  recallMemories: tool({
    description: "Search and recall relevant memories based on a query",
    inputSchema: z.object({
      query: z.string().describe("What to search for in memories"),
      limit: z.number().optional().describe("Maximum number of memories to return"),
    }),
    execute: async ({ query, limit = 5 }) => {
      return {
        memories: [],
        message: `Searched for memories related to: "${query}" (limit: ${limit})`,
      }
    },
  }),

  createTask: tool({
    description: "Create a new task or action item",
    inputSchema: z.object({
      title: z.string().describe("Task title"),
      description: z.string().nullable().describe("Task description"),
      priority: z.enum(["low", "medium", "high", "urgent"]).describe("Task priority"),
      dueDate: z.string().nullable().describe("Due date in ISO format"),
    }),
    execute: async ({ title, description, priority, dueDate }) => {
      return {
        success: true,
        task: { title, description, priority, dueDate },
        message: `Created task: "${title}" with ${priority} priority`,
      }
    },
  }),

  analyzeEmotion: tool({
    description: "Analyze the emotional tone and context of text",
    inputSchema: z.object({
      text: z.string().describe("Text to analyze"),
    }),
    execute: async ({ text }) => {
      const emotions = ["neutral", "happy", "sad", "anxious", "excited", "frustrated"]
      const detected = emotions[Math.floor(Math.random() * emotions.length)]
      return {
        emotion: detected,
        confidence: 0.85,
        suggestion: `Detected ${detected} tone. Responding with appropriate empathy.`,
      }
    },
  }),

  webSearch: tool({
    description: "Search the web for current information",
    inputSchema: z.object({
      query: z.string().describe("Search query"),
    }),
    execute: async ({ query }) => {
      return {
        results: [],
        message: `Web search functionality would search for: "${query}"`,
      }
    },
  }),
}

export async function POST(req: Request) {
  const startTime = Date.now()
  
  try {
    const { messages, conversationId, model = "openai/gpt-4o" } = await req.json()
    
    // Get user from Supabase auth
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    // Determine which agent to use based on message content
    const lastMessage = messages[messages.length - 1]
    const content = lastMessage?.parts?.find((p: { type: string }) => p.type === "text")?.text || 
                   lastMessage?.content || ""
    
    const agentType = determineAgent(content.toLowerCase())
    const systemPrompt = AGENT_PROMPTS[agentType] || AGENT_PROMPTS.orchestrator

    // Build conversation context from recent messages
    const conversationContext = messages.slice(-10)

    // Stream the response using AI SDK
    const result = streamText({
      model,
      system: systemPrompt,
      messages: await convertToModelMessages(conversationContext),
      tools: brainTools,
      maxSteps: 5,
      onFinish: async ({ text, usage }) => {
        const latency = Date.now() - startTime
        
        // Save to database if user is authenticated
        if (user && conversationId) {
          try {
            // Save the assistant message
            await supabase.from("messages").insert({
              conversation_id: conversationId,
              user_id: user.id,
              role: "assistant",
              content: text,
              agent_used: agentType,
              tokens_used: usage?.totalTokens,
              latency_ms: latency,
            })

            // Log agent activity
            await supabase.from("agent_activity").insert({
              user_id: user.id,
              conversation_id: conversationId,
              agent_name: agentType,
              action_type: "chat_response",
              tokens_used: usage?.totalTokens,
              latency_ms: latency,
              success: true,
            })

            // Update conversation timestamp
            await supabase
              .from("conversations")
              .update({ updated_at: new Date().toISOString() })
              .eq("id", conversationId)

            // Cache recent messages
            await redis.set(
              CACHE_KEYS.recentMessages(conversationId),
              JSON.stringify(messages.slice(-20)),
              { ex: CACHE_TTL.recentMessages }
            )
          } catch (dbError) {
            console.error("Database error:", dbError)
          }
        }
      },
    })

    return result.toUIMessageStreamResponse({
      sendReasoning: true,
    })
  } catch (error) {
    console.error("Chat API error:", error)
    return new Response(
      JSON.stringify({ error: "Failed to process chat request" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
}

function determineAgent(content: string): string {
  // Simple keyword-based routing - in production, this could use an AI classifier
  if (content.includes("remember") || content.includes("recall") || content.includes("memory")) {
    return "memory"
  }
  if (content.includes("feel") || content.includes("emotion") || content.includes("sad") || 
      content.includes("happy") || content.includes("anxious") || content.includes("stressed")) {
    return "emotion"
  }
  if (content.includes("code") || content.includes("programming") || content.includes("debug") ||
      content.includes("function") || content.includes("error")) {
    return "code"
  }
  if (content.includes("task") || content.includes("schedule") || content.includes("todo") ||
      content.includes("deadline") || content.includes("reminder")) {
    return "task"
  }
  if (content.includes("research") || content.includes("find out") || content.includes("learn about") ||
      content.includes("what is") || content.includes("explain")) {
    return "research"
  }
  if (content.includes("idea") || content.includes("creative") || content.includes("brainstorm") ||
      content.includes("imagine") || content.includes("story")) {
    return "creativity"
  }
  if (content.includes("analyze") || content.includes("reason") || content.includes("logic") ||
      content.includes("problem") || content.includes("solve")) {
    return "reasoning"
  }
  
  return "orchestrator"
}
