import { NextResponse } from "next/server"
import {
  getOrCreateUser,
  getUserMemories,
  createMemory,
  searchMemories,
  deleteMemory,
} from "@/lib/server/db-utils"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const userId = searchParams.get("userId")
    const type = searchParams.get("type")
    const query = searchParams.get("q")
    const limit = parseInt(searchParams.get("limit") || "50")

    if (!userId) return NextResponse.json({ error: "Missing userId parameter" }, { status: 400 })

    const memories = query
      ? searchMemories(userId, query, limit)
      : getUserMemories(userId, type || undefined, limit)

    return NextResponse.json(memories)
  } catch (error) {
    console.error("[memories] GET error:", error)
    return NextResponse.json({ error: "Failed to fetch memories" }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { userId, content, memory_type = "general", importance = 0.5, tags = [], source_conversation_id } = body

    if (!userId) return NextResponse.json({ error: "Missing userId" }, { status: 400 })
    if (!content) return NextResponse.json({ error: "Missing content" }, { status: 400 })

    const user = getOrCreateUser(userId, `user-${userId}@brain.local`, "AI User")
    if (!user) return NextResponse.json({ error: "Failed to create user" }, { status: 500 })

    const memory = createMemory(userId, content, memory_type, importance, tags, source_conversation_id)
    if (!memory) return NextResponse.json({ error: "Failed to create memory" }, { status: 500 })

    return NextResponse.json(memory)
  } catch (error) {
    console.error("[memories] POST error:", error)
    return NextResponse.json({ error: "Failed to create memory" }, { status: 500 })
  }
}
