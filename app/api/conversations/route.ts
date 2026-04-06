import { createClient } from "@/lib/supabase/server"
import { redis, CACHE_KEYS, CACHE_TTL, cacheGet, cacheSet } from "@/lib/redis"
import { NextResponse } from "next/server"

export async function GET() {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    // Try cache first
    const cacheKey = CACHE_KEYS.userConversations(user.id)
    const cached = await cacheGet<unknown[]>(cacheKey)
    
    if (cached) {
      return NextResponse.json(cached)
    }

    // Fetch from database
    const { data, error } = await supabase
      .from("conversations")
      .select("*")
      .eq("user_id", user.id)
      .eq("is_archived", false)
      .order("updated_at", { ascending: false })
      .limit(50)

    if (error) {
      throw error
    }

    // Cache the result
    await cacheSet(cacheKey, data, CACHE_TTL.userConversations)

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching conversations:", error)
    return NextResponse.json(
      { error: "Failed to fetch conversations" },
      { status: 500 }
    )
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
    const { title = "New Conversation", model = "openai/gpt-4o", system_prompt } = body

    const { data, error } = await supabase
      .from("conversations")
      .insert({
        user_id: user.id,
        title,
        model,
        system_prompt,
      })
      .select()
      .single()

    if (error) {
      throw error
    }

    // Invalidate cache
    await redis.del(CACHE_KEYS.userConversations(user.id))

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error creating conversation:", error)
    return NextResponse.json(
      { error: "Failed to create conversation" },
      { status: 500 }
    )
  }
}
