import { brainService, AGENT_REGISTRY, initBrainService } from "@/lib/brain-service"
import {
  getAllAgents,
  getOrCreateUser,
  searchMemories,
  createMemory,
  createTask,
  dbAll,
  logAgentActivity,
} from "@/lib/server/db-utils"

/**
 * Brain API - Direct interface to the AI Virtual Brain backend
 * 
 * Provides endpoints for:
 * - System status
 * - Agent management
 * - Task creation/monitoring
 * - Memory operations
 * - Activity tracking
 */

export async function GET(req: Request) {
  initBrainService()
  try {
    const { searchParams } = new URL(req.url)
    const action = searchParams.get("action") || "status"
    const userId = searchParams.get("userId")

    switch (action) {
      case "status": {
        const status = await brainService.getSystemStatus()
        const agents = getAllAgents(true)
        
        return Response.json({
          ...status,
          agents: agents.map((a: any) => ({
            id: a.id,
            name: a.name,
            display_name: a.display_name,
            is_active: a.is_active,
            category: a.category,
            icon: a.icon,
            color: a.color,
          })),
        })
      }

      case "agents": {
        const agents = getAllAgents(true)
        return Response.json({ agents })
      }

      case "agent-status": {
        const agentName = searchParams.get("agent")
        if (!agentName) {
          return Response.json({ error: "Agent name required" }, { status: 400 })
        }
        const agent = agents.find((a: any) => a.name === agentName)
        return Response.json({ agent: agent || null, status: agent ? "active" : "inactive" })
      }

      case "memories": {
        if (!userId) {
          return Response.json({ error: "userId required" }, { status: 400 })
        }

        const query = searchParams.get("query") || ""
        const limit = parseInt(searchParams.get("limit") || "20", 10)
        
        const memories = await brainService.recallMemories(userId, query, limit)
        return Response.json({ memories })
      }

      case "activity": {
        if (!userId) {
          return Response.json({ error: "userId required" }, { status: 400 })
        }
        
        const activity = dbAll(
          `SELECT * FROM agent_activity WHERE user_id = ? ORDER BY created_at DESC LIMIT 100`,
          [userId]
        )
        return Response.json({ activity })
      }

      default:
        return Response.json({ error: "Unknown action" }, { status: 400 })
    }
  } catch (error) {
    console.error("[v0] Brain API error:", error)
    return Response.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  initBrainService()
  try {
    const body = await req.json()
    const { action, ...params } = body
    const { userId, agentName } = params

    // Get or create user if provided
    let user = null
    if (userId) {
      user = getOrCreateUser(userId, "user@example.com", "AI User")
    }

    switch (action) {
      case "route-request": {
        const { content } = params
        if (!content) {
          return Response.json({ error: "Content required" }, { status: 400 })
        }

        const routing = await brainService.routeRequest(content)
        return Response.json(routing)
      }

      case "store-memory": {
        if (!user) {
          return Response.json({ error: "User not found" }, { status: 400 })
        }

        const { content, memory_type = "general", importance = 0.5, tags = [] } = params
        if (!content) {
          return Response.json({ error: "Content required" }, { status: 400 })
        }

        const memory = await brainService.storeMemory(
          (user as any).id,
          content,
          memory_type,
          importance,
          tags
        )

        return Response.json({ success: !!memory, memory })
      }

      case "create-task": {
        if (!user) {
          return Response.json({ error: "User not found" }, { status: 400 })
        }

        const { title, description, priority = "medium", due_date, tags = [] } = params
        if (!title) {
          return Response.json({ error: "Title required" }, { status: 400 })
        }

        const task = createTask(
          (user as any).id,
          title,
          description,
          priority,
          due_date,
          tags
        )

        return Response.json({ success: !!task, task })
      }

      case "recall-memories": {
        if (!user) {
          return Response.json({ error: "User not found" }, { status: 400 })
        }

        const { query, limit = 10 } = params
        if (!query) {
          return Response.json({ error: "Query required" }, { status: 400 })
        }

        const memories = await brainService.recallMemories((user as any).id, query, limit)
        return Response.json({ memories })
      }

      default:
        return Response.json({ error: "Unknown action" }, { status: 400 })
    }
  } catch (error) {
    console.error("[v0] Brain API error:", error)
    return Response.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

const agents = getAllAgents(true)
