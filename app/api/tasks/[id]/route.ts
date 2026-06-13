import { NextResponse } from "next/server"
import { dbGet, dbRun } from "@/lib/db-utils"

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    if (!id) {
      return NextResponse.json({ error: "Missing task ID" }, { status: 400 })
    }

    const task = dbGet("SELECT * FROM tasks WHERE id = ?", [id])

    if (!task) {
      return NextResponse.json({ error: "Task not found" }, { status: 404 })
    }

    return NextResponse.json(task)
  } catch (error) {
    console.error("[v0] Error fetching task:", error)
    return NextResponse.json(
      { error: "Failed to fetch task" },
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
      return NextResponse.json({ error: "Missing task ID" }, { status: 400 })
    }

    const task = dbGet("SELECT * FROM tasks WHERE id = ?", [id])
    if (!task) {
      return NextResponse.json({ error: "Task not found" }, { status: 404 })
    }

    // Update allowed fields
    const updates: string[] = []
    const values: any[] = []

    if (body.title !== undefined) {
      updates.push("title = ?")
      values.push(body.title)
    }
    if (body.description !== undefined) {
      updates.push("description = ?")
      values.push(body.description)
    }
    if (body.status !== undefined) {
      updates.push("status = ?")
      values.push(body.status)
      if (body.status === "completed") {
        updates.push("completed_at = ?")
        values.push(new Date().toISOString())
      }
    }
    if (body.priority !== undefined) {
      updates.push("priority = ?")
      values.push(body.priority)
    }
    if (body.due_date !== undefined) {
      updates.push("due_date = ?")
      values.push(body.due_date)
    }
    if (body.tags !== undefined) {
      updates.push("tags = ?")
      values.push(JSON.stringify(body.tags))
    }

    if (updates.length === 0) {
      return NextResponse.json(task)
    }

    updates.push("updated_at = ?")
    values.push(new Date().toISOString())
    values.push(id)

    dbRun(`UPDATE tasks SET ${updates.join(", ")} WHERE id = ?`, values)
    
    const updated = dbGet("SELECT * FROM tasks WHERE id = ?", [id])
    return NextResponse.json(updated)
  } catch (error) {
    console.error("[v0] Error updating task:", error)
    return NextResponse.json(
      { error: "Failed to update task" },
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
      return NextResponse.json({ error: "Missing task ID" }, { status: 400 })
    }

    const task = dbGet("SELECT * FROM tasks WHERE id = ?", [id])
    if (!task) {
      return NextResponse.json({ error: "Task not found" }, { status: 404 })
    }

    dbRun("DELETE FROM tasks WHERE id = ?", [id])

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("[v0] Error deleting task:", error)
    return NextResponse.json(
      { error: "Failed to delete task" },
      { status: 500 }
    )
  }
}
