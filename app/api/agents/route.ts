import { NextResponse } from "next/server"
import {
  getAllAgents,
  getAgent,
  logAgentActivity,
  getOrCreateUser,
  generateId,
} from "@/lib/server/db-utils"
import { AGENT_REGISTRY, brainService, initBrainService } from "@/lib/brain-service"

export async function GET(req: Request) {
  initBrainService()
  try {
    const { searchParams } = new URL(req.url)
    const name = searchParams.get("name")
    const activeOnly = searchParams.get("activeOnly") !== "false"

    if (name) {
      const agent = getAgent(name)
      if (!agent) return NextResponse.json({ error: "Agent not found" }, { status: 404 })
      return NextResponse.json(agent)
    }

    const agents = getAllAgents(activeOnly)
    return NextResponse.json(agents)
  } catch (error) {
    console.error("[agents] GET error:", error)
    return NextResponse.json({ error: "Failed to fetch agents" }, { status: 500 })
  }
}

export async function POST(req: Request) {
  initBrainService()
  try {
    const body = await req.json()
    const { action, agentName, userId, input, inputData, conversationId } = body

    let user = null
    if (userId) {
      user = getOrCreateUser(userId, `user-${userId}@brain.local`, "AI User")
    }

    if (action === "execute") {
      if (!agentName) return NextResponse.json({ error: "Agent name required" }, { status: 400 })

      const agent = getAgent(agentName)
      if (!agent) return NextResponse.json({ error: "Agent not found" }, { status: 404 })

      const startTime = Date.now()

      const pyResult = await brainService.executeAgent(
        agentName,
        inputData?.action || "process",
        inputData || input || {},
        userId
      )

      const latencyMs = Date.now() - startTime

      if (user) {
        logAgentActivity(
          (user as any).id,
          agentName,
          "execution",
          { input: input || inputData },
          pyResult || { status: "success" },
          true,
          undefined,
          undefined,
          latencyMs,
          conversationId
        )
      }

      return NextResponse.json({
        status: "success",
        agentName,
        agent,
        result: pyResult || {
          message: `Agent ${(agent as any).display_name} executed successfully`,
          timestamp: new Date().toISOString(),
        },
        latencyMs,
      })
    }

    if (action === "list") {
      const agents = getAllAgents(true)
      return NextResponse.json({ agents, count: agents.length })
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  } catch (error) {
    console.error("[agents] POST error:", error)
    return NextResponse.json({ error: "Failed to execute agent" }, { status: 500 })
  }
}
