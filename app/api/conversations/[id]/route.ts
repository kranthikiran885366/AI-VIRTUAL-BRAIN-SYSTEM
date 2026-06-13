import { NextResponse } from "next/server"
import {
  getConversation,
  updateConversation,
  dbAll,
} from "@/lib/server/db-utils"
import { redis, CACHE_KEYS, CACHE_TTL } from "@/lib/cache"

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    if (!id) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 })
    }

    const conversation = getConversation(id)

    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    // Fetch messages for this conversation
    const messages = dbAll(
      `SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC`,
      [id]
    )

    const result = { ...conversation, messages }

    // Cache the result
    await redis.set(CACHE_KEYS.conversationMessages(id), JSON.stringify(result), {
      ex: CACHE_TTL.conversationMessages,
    })

    return NextResponse.json(result)
  } catch (error) {
    console.error("[v0] Error fetching conversation:", error)
    return NextResponse.json(
      { error: "Failed to fetch conversation" },
      { status: 500 }
    )
  }
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await req.json()

    if (!id) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 })
    }

    const conversation = getConversation(id)
    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    // Update allowed fields only
    const updates: Record<string, any> = {}
    if (body.title) updates.title = body.title
    if (body.system_prompt !== undefined) updates.system_prompt = body.system_prompt
    if (body.is_archived !== undefined) updates.is_archived = body.is_archived ? 1 : 0
    if (body.model) updates.model = body.model

    if (Object.keys(updates).length === 0) {
      return NextResponse.json(conversation)
    }

    const updated = updateConversation(id, updates)

    // Invalidate caches
    await redis.del(CACHE_KEYS.conversationMessages(id))
    await redis.del(CACHE_KEYS.userConversations((conversation as any).user_id))

    return NextResponse.json(updated)
  } catch (error) {
    console.error("[v0] Error updating conversation:", error)
    return NextResponse.json(
      { error: "Failed to update conversation" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    if (!id) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 })
    }

    const conversation = getConversation(id)
    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    // Soft delete by archiving
    updateConversation(id, { is_archived: 1 })

    // Invalidate caches
    await redis.del(CACHE_KEYS.conversationMessages(id))
    await redis.del(CACHE_KEYS.userConversations((conversation as any).user_id))

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("[v0] Error deleting conversation:", error)
    return NextResponse.json(
      { error: "Failed to delete conversation" },
      { status: 500 }
    )
  }
}
