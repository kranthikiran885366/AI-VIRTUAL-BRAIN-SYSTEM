import { brainService, AGENT_REGISTRY } from "@/lib/brain-service"
import { createClient } from "@/lib/supabase/server"

/**
 * Brain API - Direct interface to the Python Virtual Brain backend
 * 
 * Provides endpoints for:
 * - System status
 * - Agent management
 * - Task creation/monitoring
 * - Memory operations
 * - Activity tracking
 */

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const action = searchParams.get("action") || "status"

    switch (action) {
      case "status": {
        const status = await brainService.getSystemStatus()
        const activityStats = await brainService.getActivityStats()
        
        return Response.json({
          ...status,
          activityStats,
          agents: Object.entries(AGENT_REGISTRY).map(([name, info]) => ({
            name,
            ...info,
            activity: activityStats[name] || 0,
          })),
        })
      }

      case "agents": {
        const agents = await brainService.listAgents()
        return Response.json({ agents })
      }

      case "agent-status": {
        const agentName = searchParams.get("agent")
        if (!agentName) {
          return Response.json({ error: "Agent name required" }, { status: 400 })
        }
        const status = await brainService.getAgentStatus(agentName)
        return Response.json(status)
      }

      case "task-status": {
        const taskId = searchParams.get("taskId")
        if (!taskId) {
          return Response.json({ error: "Task ID required" }, { status: 400 })
        }
        const status = await brainService.getTaskStatus(taskId)
        return Response.json(status)
      }

      case "messages": {
        const topic = searchParams.get("topic") || "general"
        const limit = parseInt(searchParams.get("limit") || "50", 10)
        const messages = await brainService.getMessages(topic, limit)
        return Response.json({ messages, topic })
      }

      case "memories": {
        const supabase = await createClient()
        const { data: { user } } = await supabase.auth.getUser()
        
        if (!user) {
          return Response.json({ error: "Unauthorized" }, { status: 401 })
        }

        const query = searchParams.get("query") || ""
        const limit = parseInt(searchParams.get("limit") || "20", 10)
        
        const memories = await brainService.recallMemories(user.id, query, limit)
        return Response.json({ memories })
      }

      case "activity": {
        const stats = await brainService.getActivityStats()
        return Response.json({ stats })
      }

      default:
        return Response.json({ error: "Unknown action" }, { status: 400 })
    }
  } catch (error) {
    console.error("Brain API error:", error)
    return Response.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { action, ...params } = body

    // Auth check for certain actions
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    switch (action) {
      case "execute-agent": {
        const { agentName, request } = params
        if (!agentName || !request) {
          return Response.json(
            { error: "Agent name and request required" },
            { status: 400 }
          )
        }
        
        const result = await brainService.executeAgent(agentName, request)
        
        // Log activity if user is authenticated
        if (user) {
          await brainService.logActivity(
            user.id,
            params.conversationId || null,
            agentName,
            "direct_execution",
            request,
            result.result,
            result.status === "success",
            result.latencyMs || 0,
            result.tokensUsed
          )
        }
        
        return Response.json(result)
      }

      case "create-task": {
        const { agentName, request, priority } = params
        if (!agentName || !request) {
          return Response.json(
            { error: "Agent name and request required" },
            { status: 400 }
          )
        }
        
        const result = await brainService.createTask({
          agentName,
          request,
          priority: priority || "medium",
        })
        
        return Response.json(result)
      }

      case "store-memory": {
        if (!user) {
          return Response.json({ error: "Unauthorized" }, { status: 401 })
        }

        const { content, memoryType, importance, tags } = params
        if (!content) {
          return Response.json({ error: "Content required" }, { status: 400 })
        }

        const success = await brainService.storeMemory(
          user.id,
          content,
          memoryType || "short_term",
          importance || 0.5,
          tags || []
        )

        return Response.json({ success })
      }

      case "publish-message": {
        const { topic, message } = params
        if (!topic || !message) {
          return Response.json(
            { error: "Topic and message required" },
            { status: 400 }
          )
        }

        const success = await brainService.publishMessage(topic, {
          ...message,
          userId: user?.id,
          timestamp: new Date().toISOString(),
        })

        return Response.json({ success })
      }

      case "route-request": {
        const { content } = params
        if (!content) {
          return Response.json({ error: "Content required" }, { status: 400 })
        }

        const routing = await brainService.routeRequest(content)
        return Response.json(routing)
      }

      default:
        return Response.json({ error: "Unknown action" }, { status: 400 })
    }
  } catch (error) {
    console.error("Brain API error:", error)
    return Response.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
