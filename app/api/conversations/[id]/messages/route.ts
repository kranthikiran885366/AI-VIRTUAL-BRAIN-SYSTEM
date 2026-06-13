import { NextResponse } from "next/server"
import {
  getConversation,
  createMessage,
  updateConversation,
  dbAll,
} from "@/lib/db-utils"
import { redis, CACHE_KEYS } from "@/lib/cache"

export async function GET(
  req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { id: conversationId } = params

    if (!conversationId) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 })
    }

    const conversation = getConversation(conversationId)
    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    const messages = dbAll(
      `SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC`,
      [conversationId]
    )

    return NextResponse.json(messages)
  } catch (error) {
    console.error("[v0] Error fetching messages:", error)
    return NextResponse.json(
      { error: "Failed to fetch messages" },
      { status: 500 }
    )
  }
}

export async function POST(
  req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { id: conversationId } = params
    const body = await req.json()
    const { userId, role, content } = body

    if (!conversationId) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 })
    }

    if (!userId || !role || !content) {
      return NextResponse.json(
        { error: "Missing required fields: userId, role, content" },
        { status: 400 }
      )
    }

    // Verify conversation exists
    const conversation = getConversation(conversationId)
    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    // Create message
    const message = createMessage(conversationId, userId, role as any, content)

    if (!message) {
      return NextResponse.json({ error: "Failed to create message" }, { status: 500 })
    }

    // Update conversation timestamp
    updateConversation(conversationId, { updated_at: new Date().toISOString() })

    // Invalidate caches
    await redis.del(CACHE_KEYS.conversationMessages(conversationId))
    await redis.del(CACHE_KEYS.userConversations(conversation.user_id))

    return NextResponse.json(message)
  } catch (error) {
    console.error("[v0] Error creating message:", error)
    return NextResponse.json(
      { error: "Failed to create message" },
      { status: 500 }
    )
  }
}
