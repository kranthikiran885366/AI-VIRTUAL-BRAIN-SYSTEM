import { createClient } from "@/lib/supabase/server"
import { redis, CACHE_KEYS, CACHE_TTL, cacheGet, cacheSet, cacheDelete } from "@/lib/redis"
import { NextResponse } from "next/server"

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    // Try cache first
    const cacheKey = CACHE_KEYS.conversation(id)
    const cached = await cacheGet<unknown>(cacheKey)
    
    if (cached) {
      return NextResponse.json(cached)
    }

    // Fetch conversation with messages
    const { data: conversation, error: convError } = await supabase
      .from("conversations")
      .select("*")
      .eq("id", id)
      .eq("user_id", user.id)
      .single()

    if (convError || !conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    const { data: messages, error: msgError } = await supabase
      .from("messages")
      .select("*")
      .eq("conversation_id", id)
      .order("created_at", { ascending: true })

    if (msgError) {
      throw msgError
    }

    const result = { ...conversation, messages: messages || [] }

    // Cache the result
    await cacheSet(cacheKey, result, CACHE_TTL.conversation)

    return NextResponse.json(result)
  } catch (error) {
    console.error("Error fetching conversation:", error)
    return NextResponse.json(
      { error: "Failed to fetch conversation" },
      { status: 500 }
    )
  }
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = await req.json()
    const { title, is_archived, system_prompt, model } = body

    const updateData: Record<string, unknown> = { updated_at: new Date().toISOString() }
    if (title !== undefined) updateData.title = title
    if (is_archived !== undefined) updateData.is_archived = is_archived
    if (system_prompt !== undefined) updateData.system_prompt = system_prompt
    if (model !== undefined) updateData.model = model

    const { data, error } = await supabase
      .from("conversations")
      .update(updateData)
      .eq("id", id)
      .eq("user_id", user.id)
      .select()
      .single()

    if (error) {
      throw error
    }

    // Invalidate caches
    await cacheDelete(CACHE_KEYS.conversation(id))
    await redis.del(CACHE_KEYS.userConversations(user.id))

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error updating conversation:", error)
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
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { error } = await supabase
      .from("conversations")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id)

    if (error) {
      throw error
    }

    // Invalidate caches
    await cacheDelete(CACHE_KEYS.conversation(id))
    await redis.del(CACHE_KEYS.userConversations(user.id))

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Error deleting conversation:", error)
    return NextResponse.json(
      { error: "Failed to delete conversation" },
      { status: 500 }
    )
  }
}
