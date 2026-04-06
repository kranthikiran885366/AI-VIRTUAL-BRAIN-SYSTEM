import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"
import { AGENT_REGISTRY } from "@/lib/brain-service"

// Local agent definitions matching Python backend
const LOCAL_AGENTS = Object.entries(AGENT_REGISTRY).map(([name, info], index) => ({
  id: `local-${name}`,
  name,
  display_name: info.displayName,
  description: `${info.displayName} - handles ${info.category} processing tasks`,
  category: info.category,
  is_active: true,
  icon: info.icon,
  color: info.color,
  priority: index,
}))

export async function GET() {
  try {
    const supabase = await createClient()
    
    // Try to fetch from database first
    const { data, error } = await supabase
      .from("agents")
      .select("*")
      .eq("is_active", true)
      .order("priority", { ascending: true })

    if (error) {
      console.error("Database error, using local agents:", error)
      // Return local agents as fallback
      return NextResponse.json(LOCAL_AGENTS)
    }

    // If no agents in database, return local agents
    if (!data || data.length === 0) {
      return NextResponse.json(LOCAL_AGENTS)
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching agents:", error)
    // Return local agents as fallback
    return NextResponse.json(LOCAL_AGENTS)
  }
}

export async function POST(req: Request) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = await req.json()
    const { action, agentName, ...params } = body

    // Handle agent execution
    if (action === "execute") {
      // This would call the Python backend in production
      return NextResponse.json({
        status: "success",
        agentName,
        result: { message: `Agent ${agentName} executed successfully` },
        timestamp: new Date().toISOString(),
      })
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  } catch (error) {
    console.error("Error executing agent:", error)
    return NextResponse.json(
      { error: "Failed to execute agent" },
      { status: 500 }
    )
  }
}
