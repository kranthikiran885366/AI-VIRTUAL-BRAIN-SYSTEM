"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import {
  Brain,
  Database,
  Heart,
  Lightbulb,
  Code,
  Sparkles,
  Zap,
  Activity,
  TrendingUp,
} from "lucide-react"
import { cn } from "@/lib/utils"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

interface Agent {
  id: string
  name: string
  display_name: string
  description: string
  category: string
  is_active: boolean
  icon: string
  color: string
}

const iconMap: Record<string, React.ReactNode> = {
  brain: <Brain className="h-5 w-5" />,
  database: <Database className="h-5 w-5" />,
  heart: <Heart className="h-5 w-5" />,
  lightbulb: <Lightbulb className="h-5 w-5" />,
  sparkles: <Sparkles className="h-5 w-5" />,
  code: <Code className="h-5 w-5" />,
  search: <TrendingUp className="h-5 w-5" />,
  "clipboard-list": <Zap className="h-5 w-5" />,
  "academic-cap": <Activity className="h-5 w-5" />,
  chat: <Brain className="h-5 w-5" />,
}

export function BrainActivity() {
  const { data: agents } = useSWR<Agent[]>("/api/agents", fetcher)
  const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set())

  // Simulate agent activity
  useEffect(() => {
    const interval = setInterval(() => {
      if (agents && agents.length > 0) {
        const randomAgent = agents[Math.floor(Math.random() * agents.length)]
        setActiveAgents((prev) => {
          const next = new Set(prev)
          if (next.has(randomAgent.name)) {
            next.delete(randomAgent.name)
          } else {
            next.add(randomAgent.name)
          }
          return next
        })
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [agents])

  const categorizedAgents = agents?.reduce(
    (acc, agent) => {
      if (!acc[agent.category]) {
        acc[agent.category] = []
      }
      acc[agent.category].push(agent)
      return acc
    },
    {} as Record<string, Agent[]>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Brain Activity</h2>
      </div>

      {categorizedAgents &&
        Object.entries(categorizedAgents).map(([category, categoryAgents]) => (
          <div key={category} className="space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground capitalize">
              {category} Agents
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {categoryAgents.map((agent) => {
                const isActive = activeAgents.has(agent.name)
                return (
                  <div
                    key={agent.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border transition-all duration-300",
                      isActive
                        ? "border-primary/50 bg-primary/5"
                        : "border-border bg-secondary/20"
                    )}
                  >
                    <div
                      className={cn(
                        "h-10 w-10 rounded-lg flex items-center justify-center transition-all duration-300",
                        isActive ? "bg-primary/20" : "bg-secondary"
                      )}
                      style={{
                        color: isActive ? agent.color : undefined,
                      }}
                    >
                      {iconMap[agent.icon] || <Brain className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">
                        {agent.display_name}
                      </p>
                      <div className="flex items-center gap-1.5">
                        <div
                          className={cn(
                            "h-1.5 w-1.5 rounded-full transition-colors",
                            isActive ? "bg-green-500" : "bg-muted-foreground/30"
                          )}
                        />
                        <span className="text-xs text-muted-foreground">
                          {isActive ? "Active" : "Idle"}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
    </div>
  )
}
