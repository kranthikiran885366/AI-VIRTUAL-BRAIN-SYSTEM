import { NextResponse } from "next/server"
import { dbGet, dbRun } from "@/lib/db-utils"

export async function GET(
  req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params

    if (!id) {
      return NextResponse.json({ error: "Missing memory ID" }, { status: 400 })
    }

    const memory = dbGet("SELECT * FROM memories WHERE id = ?", [id])

    if (!memory) {
      return NextResponse.json({ error: "Memory not found" }, { status: 404 })
    }

    return NextResponse.json(memory)
  } catch (error) {
    console.error("[v0] Error fetching memory:", error)
    return NextResponse.json(
      { error: "Failed to fetch memory" },
      { status: 500 }
    )
  }
}

export async function PUT(
  req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params
    const body = await req.json()

    if (!id) {
      return NextResponse.json({ error: "Missing memory ID" }, { status: 400 })
    }

    const memory = dbGet("SELECT * FROM memories WHERE id = ?", [id])
    if (!memory) {
      return NextResponse.json({ error: "Memory not found" }, { status: 404 })
    }

    // Update allowed fields
    const updates: string[] = []
    const values: any[] = []

    if (body.content !== undefined) {
      updates.push("content = ?")
      values.push(body.content)
    }
    if (body.memory_type !== undefined) {
      updates.push("memory_type = ?")
      values.push(body.memory_type)
    }
    if (body.importance !== undefined) {
      updates.push("importance = ?")
      values.push(body.importance)
    }
    if (body.tags !== undefined) {
      updates.push("tags = ?")
      values.push(JSON.stringify(body.tags))
    }

    if (updates.length === 0) {
      return NextResponse.json(memory)
    }

    values.push(id)
    dbRun(`UPDATE memories SET ${updates.join(", ")} WHERE id = ?`, values)
    
    const updated = dbGet("SELECT * FROM memories WHERE id = ?", [id])
    return NextResponse.json(updated)
  } catch (error) {
    console.error("[v0] Error updating memory:", error)
    return NextResponse.json(
      { error: "Failed to update memory" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params

    if (!id) {
      return NextResponse.json({ error: "Missing memory ID" }, { status: 400 })
    }

    const memory = dbGet("SELECT * FROM memories WHERE id = ?", [id])
    if (!memory) {
      return NextResponse.json({ error: "Memory not found" }, { status: 404 })
    }

    dbRun("DELETE FROM memories WHERE id = ?", [id])

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("[v0] Error deleting memory:", error)
    return NextResponse.json(
      { error: "Failed to delete memory" },
      { status: 500 }
    )
  }
}
