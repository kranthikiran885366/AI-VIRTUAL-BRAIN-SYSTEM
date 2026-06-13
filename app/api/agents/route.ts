import { NextResponse } from "next/server"
import {
  getAllAgents,
  getAgent,
  logAgentActivity,
  getOrCreateUser,
  generateId,
} from "@/lib/db-utils"
import { AGENT_REGISTRY, initBrainService } from "@/lib/brain-service"

// Initialize agents on startup
initBrainService()

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const name = searchParams.get("name")
    const activeOnly = searchParams.get("activeOnly") !== "false"

    if (name) {
      // Get specific agent
      const agent = getAgent(name)
      if (!agent) {
        return NextResponse.json({ error: "Agent not found" }, { status: 404 })
      }
      return NextResponse.json(agent)
    }

    // Get all agents
    const agents = getAllAgents(activeOnly)
    return NextResponse.json(agents)
  } catch (error) {
    console.error("[v0] Error fetching agents:", error)
    return NextResponse.json(
      { error: "Failed to fetch agents" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { action, agentName, userId, input, conversationId } = body

    // Create user if provided
    let user = null
    if (userId) {
      user = getOrCreateUser(userId, "user@example.com", "AI User")
    }

    if (action === "execute") {
      if (!agentName) {
        return NextResponse.json({ error: "Agent name required" }, { status: 400 })
      }

      const agent = getAgent(agentName)
      if (!agent) {
        return NextResponse.json({ error: "Agent not found" }, { status: 404 })
      }

      const startTime = Date.now()

      // Log agent activity
      if (user) {
        logAgentActivity(
          (user as any).id,
          agentName,
          "execution",
          { input },
          { status: "success", message: "Agent executed" },
          true,
          undefined,
          0,
          Date.now() - startTime,
          conversationId
        )
      }

      return NextResponse.json({
        status: "success",
        agentName,
        agent,
        result: {
          message: `Agent ${(agent as any).display_name} executed successfully`,
          timestamp: new Date().toISOString(),
        },
        latencyMs: Date.now() - startTime,
      })
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  } catch (error) {
    console.error("[v0] Error executing agent:", error)
    return NextResponse.json(
      { error: "Failed to execute agent" },
      { status: 500 }
    )
  }
}
