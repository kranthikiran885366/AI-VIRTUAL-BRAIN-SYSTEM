import { NextResponse } from "next/server"
import {
  getOrCreateUser,
  getUserConversations,
  createConversation,
} from "@/lib/server/db-utils"
import { redis, CACHE_KEYS, CACHE_TTL, cacheGet, cacheSet } from "@/lib/cache"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const userId = searchParams.get("userId") || "default-user"

    const cacheKey = CACHE_KEYS.userConversations(userId)
    const cached = await cacheGet<any[]>(cacheKey)
    if (cached) return NextResponse.json(cached)

    const conversations = getUserConversations(userId, 50)
    await cacheSet(cacheKey, conversations, CACHE_TTL.userConversations)

    return NextResponse.json(conversations)
  } catch (error) {
    console.error("[conversations] GET error:", error)
    return NextResponse.json({ error: "Failed to fetch conversations" }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { userId, title = "New Conversation", model = "gpt-4o", system_prompt } = body

    const resolvedUserId = userId || "default-user"

    const user = getOrCreateUser(resolvedUserId, `user-${resolvedUserId}@brain.local`, "AI User")
    if (!user) return NextResponse.json({ error: "Failed to create user" }, { status: 500 })

    const conversation = createConversation(resolvedUserId, title, model, system_prompt)
    if (!conversation) return NextResponse.json({ error: "Failed to create conversation" }, { status: 500 })

    await redis.del(CACHE_KEYS.userConversations(resolvedUserId))

    return NextResponse.json(conversation)
  } catch (error) {
    console.error("[conversations] POST error:", error)
    return NextResponse.json({ error: "Failed to create conversation" }, { status: 500 })
  }
}
