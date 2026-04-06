"use client"

import useSWR from "swr"
import { Database, Tag, Clock, Trash2 } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { formatDate, cn } from "@/lib/utils"
import type { Memory } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

const memoryTypeColors: Record<string, string> = {
  fact: "bg-blue-500/20 text-blue-400",
  preference: "bg-purple-500/20 text-purple-400",
  context: "bg-green-500/20 text-green-400",
  task: "bg-orange-500/20 text-orange-400",
  general: "bg-slate-500/20 text-slate-400",
}

export function MemoriesPanel() {
  const { data: memories, mutate } = useSWR<Memory[]>("/api/memories?limit=20", fetcher)

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this memory?")) return
    try {
      await fetch(`/api/memories/${id}`, { method: "DELETE" })
      mutate()
    } catch (error) {
      console.error("Failed to delete memory:", error)
    }
  }

  if (!memories || memories.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Memories</h2>
        </div>
        <div className="text-center py-8 text-muted-foreground">
          <Database className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No memories stored yet</p>
          <p className="text-xs mt-1">
            Chat with the AI and it will remember important things
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Memories</h2>
        </div>
        <span className="text-xs text-muted-foreground">
          {memories.length} stored
        </span>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="space-y-3 pr-4">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="group relative p-3 rounded-lg border border-border bg-secondary/20 hover:bg-secondary/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm line-clamp-2">{memory.content}</p>
                  
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        memoryTypeColors[memory.memory_type] ||
                          memoryTypeColors.general
                      )}
                    >
                      {memory.memory_type}
                    </span>
                    
                    {memory.tags && memory.tags.length > 0 && (
                      <div className="flex items-center gap-1">
                        <Tag className="h-3 w-3 text-muted-foreground" />
                        {memory.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="text-xs text-muted-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {formatDate(memory.created_at)}
                  </div>
                </div>

                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
                  onClick={() => handleDelete(memory.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>

              {/* Importance indicator */}
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-secondary rounded-b-lg overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${memory.importance * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
