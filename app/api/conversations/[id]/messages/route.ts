import { createClient } from "@/lib/supabase/server"
import { redis, CACHE_KEYS, cacheDelete } from "@/lib/redis"
import { NextResponse } from "next/server"

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: conversationId } = await params
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = await req.json()
    const { role, content, parts, agent_used, metadata } = body

    // Verify user owns this conversation
    const { data: conversation } = await supabase
      .from("conversations")
      .select("id")
      .eq("id", conversationId)
      .eq("user_id", user.id)
      .single()

    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    const { data, error } = await supabase
      .from("messages")
      .insert({
        conversation_id: conversationId,
        user_id: user.id,
        role,
        content,
        parts,
        agent_used,
        metadata,
      })
      .select()
      .single()

    if (error) {
      throw error
    }

    // Update conversation timestamp
    await supabase
      .from("conversations")
      .update({ updated_at: new Date().toISOString() })
      .eq("id", conversationId)

    // Invalidate cache
    await cacheDelete(CACHE_KEYS.conversation(conversationId))
    await redis.del(CACHE_KEYS.userConversations(user.id))

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error creating message:", error)
    return NextResponse.json(
      { error: "Failed to create message" },
      { status: 500 }
    )
  }
}
