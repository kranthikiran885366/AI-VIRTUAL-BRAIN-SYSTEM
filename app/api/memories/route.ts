import { NextResponse } from "next/server"
import {
  getOrCreateUser,
  getUserMemories,
  createMemory,
  searchMemories,
} from "@/lib/db-utils"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const userId = searchParams.get("userId")
    const type = searchParams.get("type")
    const query = searchParams.get("q")
    const limit = parseInt(searchParams.get("limit") || "50")

    if (!userId) {
      return NextResponse.json({ error: "Missing userId parameter" }, { status: 400 })
    }

    let memories
    if (query) {
      // Search memories
      memories = searchMemories(userId, query, limit)
    } else {
      // Get user memories by type
      memories = getUserMemories(userId, type || undefined, limit)
    }

    return NextResponse.json(memories)
  } catch (error) {
    console.error("[v0] Error fetching memories:", error)
    return NextResponse.json(
      { error: "Failed to fetch memories" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const {
      userId,
      content,
      memory_type = "general",
      importance = 0.5,
      tags = [],
      source_conversation_id,
    } = body

    if (!userId) {
      return NextResponse.json({ error: "Missing userId" }, { status: 400 })
    }

    if (!content) {
      return NextResponse.json({ error: "Missing content" }, { status: 400 })
    }

    // Ensure user exists
    const user = getOrCreateUser(userId, "user@example.com", "AI User")
    if (!user) {
      return NextResponse.json({ error: "Failed to create user" }, { status: 500 })
    }

    // Create memory
    const memory = createMemory(
      userId,
      content,
      memory_type,
      importance,
      tags,
      source_conversation_id
    )

    if (!memory) {
      return NextResponse.json({ error: "Failed to create memory" }, { status: 500 })
    }

    return NextResponse.json(memory)
  } catch (error) {
    console.error("[v0] Error creating memory:", error)
    return NextResponse.json(
      { error: "Failed to create memory" },
      { status: 500 }
    )
  }
}
