import { NextResponse } from "next/server"
import {
  getOrCreateUser,
  getUserTasks,
  createTask,
  updateTask,
  generateId,
} from "@/lib/server/db-utils"

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const userId = searchParams.get("userId")
    const status = searchParams.get("status")
    const limit = parseInt(searchParams.get("limit") || "50")

    if (!userId) {
      return NextResponse.json({ error: "Missing userId parameter" }, { status: 400 })
    }

    // Fetch user tasks
    const tasks = getUserTasks(userId, status || undefined, limit)

    return NextResponse.json(tasks)
  } catch (error) {
    console.error("[v0] Error fetching tasks:", error)
    return NextResponse.json(
      { error: "Failed to fetch tasks" },
      { status: 500 }
    )
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const {
      userId,
      title,
      description,
      priority = "medium",
      due_date,
      tags = [],
      source_conversation_id,
    } = body

    if (!userId) {
      return NextResponse.json({ error: "Missing userId" }, { status: 400 })
    }

    if (!title) {
      return NextResponse.json({ error: "Missing task title" }, { status: 400 })
    }

    // Ensure user exists
    const user = getOrCreateUser(userId, "user@example.com", "AI User")
    if (!user) {
      return NextResponse.json({ error: "Failed to create user" }, { status: 500 })
    }

    // Create task
    const task = createTask(
      userId,
      title,
      description,
      priority,
      due_date,
      tags,
      source_conversation_id
    )

    if (!task) {
      return NextResponse.json({ error: "Failed to create task" }, { status: 500 })
    }

    return NextResponse.json(task)
  } catch (error) {
    console.error("[v0] Error creating task:", error)
    return NextResponse.json(
      { error: "Failed to create task" },
      { status: 500 }
    )
  }
}
