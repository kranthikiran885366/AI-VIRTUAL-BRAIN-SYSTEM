import { NextResponse } from "next/server"
import { 
  getOrCreateUser,
  getUserConversations,
  createConversation,
  generateId,
} from "@/lib/db-utils"
import { redis, CACHE_KEYS, CACHE_TTL, cacheGet, cacheSet } from "@/lib/cache"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const userId = searchParams.get("userId")

    if (!userId) {
      return NextResponse.json({ error: "Missing userId parameter" }, { status: 400 })
    }

    // Try cache first
    const cacheKey = CACHE_KEYS.userConversations(userId)
    const cached = await cacheGet<any[]>(cacheKey)

    if (cached) {
      return NextResponse.json(cached)
    }

    // Fetch from database
    const conversations = getUserConversations(userId, 50)

    // Cache the result
    await cacheSet(cacheKey, conversations, CACHE_TTL.userConversations)

    return NextResponse.json(conversations)
  } catch (error) {
    console.error("[v0] Error fetching conversations:", error)
    return NextResponse.json(
      { error: "Failed to fetch conversations" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { userId, title = "New Conversation", model = "openai/gpt-4o", system_prompt } = body

    if (!userId) {
      return NextResponse.json({ error: "Missing userId" }, { status: 400 })
    }

    // Ensure user exists
    const user = getOrCreateUser(userId, "user@example.com", "AI User")
    if (!user) {
      return NextResponse.json({ error: "Failed to create user" }, { status: 500 })
    }

    // Create conversation
    const conversation = createConversation(userId, title, model, system_prompt)

    if (!conversation) {
      return NextResponse.json({ error: "Failed to create conversation" }, { status: 500 })
    }

    // Invalidate cache
    await redis.del(CACHE_KEYS.userConversations(userId))

    return NextResponse.json(conversation)
  } catch (error) {
    console.error("[v0] Error creating conversation:", error)
    return NextResponse.json(
      { error: "Failed to create conversation" },
      { status: 500 }
    )
  }
}
