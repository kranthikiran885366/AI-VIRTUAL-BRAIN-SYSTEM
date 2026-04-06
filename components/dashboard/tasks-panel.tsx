"use client"

import useSWR from "swr"
import { ClipboardList, Check, Circle, Clock, AlertCircle, Trash2 } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { formatDate, cn } from "@/lib/utils"
import type { Task } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

const priorityColors: Record<string, string> = {
  low: "text-slate-400",
  medium: "text-blue-400",
  high: "text-orange-400",
  urgent: "text-red-400",
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Circle className="h-4 w-4" />,
  in_progress: <Clock className="h-4 w-4 text-yellow-400" />,
  completed: <Check className="h-4 w-4 text-green-400" />,
  cancelled: <AlertCircle className="h-4 w-4 text-muted-foreground" />,
}

export function TasksPanel() {
  const { data: tasks, mutate } = useSWR<Task[]>("/api/tasks?limit=20", fetcher)

  const handleToggleStatus = async (task: Task) => {
    const newStatus = task.status === "completed" ? "pending" : "completed"
    try {
      await fetch(`/api/tasks/${task.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      })
      mutate()
    } catch (error) {
      console.error("Failed to update task:", error)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this task?")) return
    try {
      await fetch(`/api/tasks/${id}`, { method: "DELETE" })
      mutate()
    } catch (error) {
      console.error("Failed to delete task:", error)
    }
  }

  const pendingTasks = tasks?.filter((t) => t.status !== "completed") || []
  const completedTasks = tasks?.filter((t) => t.status === "completed") || []

  if (!tasks || tasks.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Tasks</h2>
        </div>
        <div className="text-center py-8 text-muted-foreground">
          <ClipboardList className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No tasks yet</p>
          <p className="text-xs mt-1">
            Ask the AI to help you organize tasks
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Tasks</h2>
        </div>
        <span className="text-xs text-muted-foreground">
          {pendingTasks.length} pending
        </span>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="space-y-2 pr-4">
          {/* Pending tasks */}
          {pendingTasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              onToggle={() => handleToggleStatus(task)}
              onDelete={() => handleDelete(task.id)}
            />
          ))}

          {/* Completed tasks */}
          {completedTasks.length > 0 && (
            <>
              <div className="text-xs text-muted-foreground pt-4 pb-2">
                Completed ({completedTasks.length})
              </div>
              {completedTasks.slice(0, 5).map((task) => (
                <TaskItem
                  key={task.id}
                  task={task}
                  onToggle={() => handleToggleStatus(task)}
                  onDelete={() => handleDelete(task.id)}
                />
              ))}
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function TaskItem({
  task,
  onToggle,
  onDelete,
}: {
  task: Task
  onToggle: () => void
  onDelete: () => void
}) {
  const isCompleted = task.status === "completed"

  return (
    <div
      className={cn(
        "group flex items-start gap-3 p-3 rounded-lg border transition-colors",
        isCompleted
          ? "border-border/50 bg-secondary/10 opacity-60"
          : "border-border bg-secondary/20 hover:bg-secondary/40"
      )}
    >
      <button
        onClick={onToggle}
        className={cn(
          "mt-0.5 flex-shrink-0 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors",
          isCompleted
            ? "bg-primary border-primary"
            : "border-muted-foreground/50 hover:border-primary"
        )}
      >
        {isCompleted && <Check className="h-3 w-3 text-primary-foreground" />}
      </button>

      <div className="flex-1 min-w-0">
        <p
          className={cn(
            "text-sm",
            isCompleted && "line-through text-muted-foreground"
          )}
        >
          {task.title}
        </p>

        {task.description && (
          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
            {task.description}
          </p>
        )}

        <div className="flex items-center gap-2 mt-2">
          <span className={cn("text-xs", priorityColors[task.priority])}>
            {task.priority}
          </span>
          {task.due_date && (
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDate(task.due_date)}
            </span>
          )}
        </div>
      </div>

      <Button
        size="icon"
        variant="ghost"
        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
        onClick={onDelete}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}
