"use client"

import { useEffect, useState, useCallback, useMemo } from "react"
import useSWR from "swr"
import {
  Brain,
  Database,
  Heart,
  Lightbulb,
  Sparkles,
  Zap,
  Activity,
  Eye,
  Ear,
  MessageSquare,
  Users,
  BookOpen,
  Target,
  Shield,
  Smile,
  Map,
  Layers,
  Mic,
  Command,
  AlertTriangle,
  Flame,
  Moon,
  Scale,
  Hand,
  Focus,
  Clock,
  RefreshCw,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

// Complete agent registry matching Python backend
const AGENTS = [
  { name: "memory_agent", displayName: "Memory", icon: Database, color: "#3B82F6", category: "core", position: { x: 50, y: 20 } },
  { name: "emotion_agent", displayName: "Emotion", icon: Heart, color: "#EC4899", category: "core", position: { x: 70, y: 30 } },
  { name: "task_agent", displayName: "Task", icon: Target, color: "#14B8A6", category: "core", position: { x: 30, y: 30 } },
  { name: "learning_agent", displayName: "Learning", icon: BookOpen, color: "#6366F1", category: "core", position: { x: 40, y: 50 } },
  { name: "social_agent", displayName: "Social", icon: Users, color: "#F97316", category: "social", position: { x: 60, y: 50 } },
  { name: "perception_agent", displayName: "Perception", icon: Eye, color: "#8B5CF6", category: "sensory", position: { x: 20, y: 40 } },
  { name: "creativity_agent", displayName: "Creativity", icon: Sparkles, color: "#10B981", category: "cognitive", position: { x: 80, y: 40 } },
  { name: "self_reflection_agent", displayName: "Reflection", icon: RefreshCw, color: "#6B7280", category: "cognitive", position: { x: 50, y: 80 } },
  { name: "attention_agent", displayName: "Attention", icon: Focus, color: "#EF4444", category: "core", position: { x: 50, y: 50 } },
  { name: "motor_control_agent", displayName: "Motor", icon: Hand, color: "#84CC16", category: "motor", position: { x: 25, y: 60 } },
  { name: "language_agent", displayName: "Language", icon: MessageSquare, color: "#0EA5E9", category: "cognitive", position: { x: 75, y: 60 } },
  { name: "planning_agent", displayName: "Planning", icon: Clock, color: "#D946EF", category: "executive", position: { x: 35, y: 70 } },
  { name: "motivation_agent", displayName: "Motivation", icon: Flame, color: "#F59E0B", category: "emotional", position: { x: 65, y: 70 } },
  { name: "intuition_agent", displayName: "Intuition", icon: Lightbulb, color: "#FBBF24", category: "cognitive", position: { x: 45, y: 35 } },
  { name: "sleep_rest_agent", displayName: "Rest", icon: Moon, color: "#475569", category: "regulatory", position: { x: 15, y: 75 } },
  { name: "pain_discomfort_agent", displayName: "Pain", icon: AlertTriangle, color: "#DC2626", category: "sensory", position: { x: 85, y: 75 } },
  { name: "ethics_morality_agent", displayName: "Ethics", icon: Scale, color: "#7C3AED", category: "cognitive", position: { x: 55, y: 65 } },
  { name: "humor_agent", displayName: "Humor", icon: Smile, color: "#FACC15", category: "social", position: { x: 70, y: 20 } },
  { name: "spatial_agent", displayName: "Spatial", icon: Map, color: "#2DD4BF", category: "cognitive", position: { x: 30, y: 20 } },
  { name: "sensory_integration_agent", displayName: "Sensory", icon: Layers, color: "#A78BFA", category: "sensory", position: { x: 20, y: 55 } },
  { name: "language_production_agent", displayName: "Speech", icon: Mic, color: "#38BDF8", category: "motor", position: { x: 80, y: 55 } },
  { name: "executive_function_agent", displayName: "Executive", icon: Command, color: "#4F46E5", category: "executive", position: { x: 50, y: 35 } },
  { name: "stress_anxiety_agent", displayName: "Stress", icon: Activity, color: "#EF4444", category: "emotional", position: { x: 85, y: 25 } },
  { name: "trust_relationship_agent", displayName: "Trust", icon: Shield, color: "#22C55E", category: "social", position: { x: 15, y: 25 } },
  { name: "creativity_control_agent", displayName: "Control", icon: Zap, color: "#C084FC", category: "executive", position: { x: 65, y: 85 } },
  { name: "sensory_memory_agent", displayName: "Buffer", icon: Database, color: "#FB923C", category: "memory", position: { x: 35, y: 85 } },
  { name: "body_awareness_agent", displayName: "Body", icon: Activity, color: "#E879F9", category: "sensory", position: { x: 10, y: 50 } },
  { name: "eyes_agent", displayName: "Eyes", icon: Eye, color: "#60A5FA", category: "sensory", position: { x: 90, y: 50 } },
]

// Neural connections between agents
const CONNECTIONS = [
  ["attention_agent", "memory_agent"],
  ["attention_agent", "perception_agent"],
  ["attention_agent", "emotion_agent"],
  ["memory_agent", "learning_agent"],
  ["memory_agent", "language_agent"],
  ["emotion_agent", "motivation_agent"],
  ["emotion_agent", "social_agent"],
  ["perception_agent", "sensory_integration_agent"],
  ["perception_agent", "eyes_agent"],
  ["creativity_agent", "language_agent"],
  ["creativity_agent", "intuition_agent"],
  ["planning_agent", "task_agent"],
  ["planning_agent", "executive_function_agent"],
  ["executive_function_agent", "attention_agent"],
  ["executive_function_agent", "motor_control_agent"],
  ["language_agent", "language_production_agent"],
  ["social_agent", "trust_relationship_agent"],
  ["social_agent", "humor_agent"],
  ["motivation_agent", "task_agent"],
  ["self_reflection_agent", "ethics_morality_agent"],
  ["self_reflection_agent", "learning_agent"],
  ["sensory_memory_agent", "memory_agent"],
  ["body_awareness_agent", "sensory_integration_agent"],
  ["spatial_agent", "perception_agent"],
  ["stress_anxiety_agent", "emotion_agent"],
  ["sleep_rest_agent", "body_awareness_agent"],
  ["pain_discomfort_agent", "stress_anxiety_agent"],
  ["creativity_control_agent", "creativity_agent"],
  ["intuition_agent", "emotion_agent"],
]

const CATEGORIES = {
  core: { label: "Core Processing", color: "#3B82F6" },
  cognitive: { label: "Cognitive", color: "#8B5CF6" },
  emotional: { label: "Emotional", color: "#EC4899" },
  sensory: { label: "Sensory", color: "#10B981" },
  motor: { label: "Motor", color: "#84CC16" },
  executive: { label: "Executive", color: "#4F46E5" },
  social: { label: "Social", color: "#F97316" },
  regulatory: { label: "Regulatory", color: "#475569" },
  memory: { label: "Memory", color: "#3B82F6" },
}

interface BrainNetworkProps {
  compact?: boolean
  showConnections?: boolean
}

export function BrainNetwork({ compact = false, showConnections = true }: BrainNetworkProps) {
  const { data: brainStatus, error } = useSWR("/api/brain?action=status", fetcher, {
    refreshInterval: 5000,
  })
  
  const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set())
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)
  const [signalPaths, setSignalPaths] = useState<string[]>([])

  // Simulate neural activity
  useEffect(() => {
    const interval = setInterval(() => {
      // Randomly activate agents
      const randomAgent = AGENTS[Math.floor(Math.random() * AGENTS.length)]
      setActiveAgents((prev) => {
        const next = new Set(prev)
        if (next.size > 5) {
          // Remove oldest active agents
          const arr = Array.from(next)
          arr.slice(0, 2).forEach((a) => next.delete(a))
        }
        next.add(randomAgent.name)
        return next
      })

      // Simulate signal propagation
      const randomConnection = CONNECTIONS[Math.floor(Math.random() * CONNECTIONS.length)]
      if (randomConnection) {
        setSignalPaths((prev) => {
          const key = `${randomConnection[0]}-${randomConnection[1]}`
          return [...prev.slice(-3), key]
        })
      }
    }, 1500)

    return () => clearInterval(interval)
  }, [])

  // Clear old signal paths
  useEffect(() => {
    const timeout = setTimeout(() => {
      setSignalPaths([])
    }, 3000)
    return () => clearTimeout(timeout)
  }, [signalPaths])

  // Get connected agents for hover effect
  const getConnectedAgents = useCallback((agentName: string) => {
    return CONNECTIONS
      .filter((c) => c.includes(agentName))
      .flat()
      .filter((a) => a !== agentName)
  }, [])

  const connectedAgents = useMemo(() => {
    if (!hoveredAgent) return new Set<string>()
    return new Set(getConnectedAgents(hoveredAgent))
  }, [hoveredAgent, getConnectedAgents])

  if (compact) {
    return (
      <Card className="overflow-hidden">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              Neural Network
            </CardTitle>
            <Badge variant={brainStatus?.status === "operational" ? "default" : "secondary"}>
              {brainStatus?.status || "connecting"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="grid grid-cols-7 gap-1.5">
            {AGENTS.slice(0, 14).map((agent) => {
              const Icon = agent.icon
              const isActive = activeAgents.has(agent.name)
              const activity = brainStatus?.activityStats?.[agent.name] || 0
              
              return (
                <TooltipProvider key={agent.name}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        className={cn(
                          "h-8 w-8 rounded-lg flex items-center justify-center transition-all cursor-pointer",
                          isActive ? "scale-110" : ""
                        )}
                        style={{
                          backgroundColor: isActive ? `${agent.color}30` : "var(--secondary)",
                          borderColor: isActive ? agent.color : "transparent",
                          borderWidth: "2px",
                        }}
                      >
                        <Icon
                          className="h-4 w-4"
                          style={{ color: isActive ? agent.color : "var(--muted-foreground)" }}
                        />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="font-medium">{agent.displayName}</p>
                      <p className="text-xs text-muted-foreground">
                        Activity: {activity} ops/hr
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )
            })}
          </div>
          <p className="text-xs text-muted-foreground mt-3 text-center">
            +{AGENTS.length - 14} more agents
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary brain-active" />
            Neural Agent Network
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={brainStatus?.status === "operational" ? "default" : "secondary"}>
              {brainStatus?.status || "connecting"}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {activeAgents.size} active
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Category legend */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(CATEGORIES).slice(0, 6).map(([key, { label, color }]) => (
            <div key={key} className="flex items-center gap-1.5">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>

        {/* Network visualization */}
        <div className="relative w-full aspect-[16/10] bg-secondary/20 rounded-xl overflow-hidden">
          {/* SVG connections */}
          {showConnections && (
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              <defs>
                <linearGradient id="signalGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
                  <stop offset="50%" stopColor="var(--primary)" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
                </linearGradient>
              </defs>
              
              {CONNECTIONS.map(([from, to], i) => {
                const fromAgent = AGENTS.find((a) => a.name === from)
                const toAgent = AGENTS.find((a) => a.name === to)
                if (!fromAgent || !toAgent) return null
                
                const isHighlighted = hoveredAgent && 
                  (from === hoveredAgent || to === hoveredAgent)
                const hasSignal = signalPaths.includes(`${from}-${to}`)
                
                return (
                  <g key={i}>
                    <line
                      x1={`${fromAgent.position.x}%`}
                      y1={`${fromAgent.position.y}%`}
                      x2={`${toAgent.position.x}%`}
                      y2={`${toAgent.position.y}%`}
                      stroke={isHighlighted ? "var(--primary)" : "var(--border)"}
                      strokeWidth={isHighlighted ? 2 : 1}
                      strokeOpacity={isHighlighted ? 0.8 : 0.3}
                      className="transition-all duration-300"
                    />
                    {hasSignal && (
                      <line
                        x1={`${fromAgent.position.x}%`}
                        y1={`${fromAgent.position.y}%`}
                        x2={`${toAgent.position.x}%`}
                        y2={`${toAgent.position.y}%`}
                        stroke="url(#signalGradient)"
                        strokeWidth={3}
                        className="neural-signal"
                      />
                    )}
                  </g>
                )
              })}
            </svg>
          )}

          {/* Agent nodes */}
          {AGENTS.map((agent) => {
            const Icon = agent.icon
            const isActive = activeAgents.has(agent.name)
            const isHovered = hoveredAgent === agent.name
            const isConnected = connectedAgents.has(agent.name)
            const activity = brainStatus?.activityStats?.[agent.name] || 0
            
            return (
              <TooltipProvider key={agent.name}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        "absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300 cursor-pointer",
                        isHovered && "z-20 scale-125",
                        isActive && "z-10",
                        isConnected && hoveredAgent && "z-10 scale-110"
                      )}
                      style={{
                        left: `${agent.position.x}%`,
                        top: `${agent.position.y}%`,
                      }}
                      onMouseEnter={() => setHoveredAgent(agent.name)}
                      onMouseLeave={() => setHoveredAgent(null)}
                    >
                      <div
                        className={cn(
                          "h-10 w-10 rounded-full flex items-center justify-center border-2 transition-all",
                          isActive && "shadow-lg",
                          isHovered && "ring-2 ring-offset-2 ring-offset-background"
                        )}
                        style={{
                          backgroundColor: isActive || isHovered || isConnected 
                            ? `${agent.color}40` 
                            : "var(--secondary)",
                          borderColor: isActive || isHovered 
                            ? agent.color 
                            : isConnected 
                              ? `${agent.color}80`
                              : "var(--border)",
                          boxShadow: isActive 
                            ? `0 0 20px ${agent.color}50` 
                            : undefined,
                        } as any}
                      >
                        <Icon
                          className={cn(
                            "h-4 w-4 transition-colors",
                            isActive && "animate-pulse"
                          )}
                          style={{
                            color: isActive || isHovered || isConnected 
                              ? agent.color 
                              : "var(--muted-foreground)",
                          }}
                        />
                      </div>
                      {/* Activity indicator */}
                      {(isActive || activity > 0) && (
                        <div
                          className="absolute -bottom-1 -right-1 h-3 w-3 rounded-full border border-background"
                          style={{ backgroundColor: "#22C55E" }}
                        />
                      )}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <div className="space-y-1">
                      <p className="font-medium">{agent.displayName} Agent</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {CATEGORIES[agent.category as keyof typeof CATEGORIES]?.label}
                      </p>
                      <div className="flex items-center gap-2 text-xs">
                        <span className={isActive ? "text-green-500" : "text-muted-foreground"}>
                          {isActive ? "Active" : "Idle"}
                        </span>
                        <span className="text-muted-foreground">|</span>
                        <span>{activity} ops/hr</span>
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )
          })}

          {/* Central brain indicator */}
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none">
            <div className="h-16 w-16 rounded-full bg-primary/5 border border-primary/20 flex items-center justify-center">
              <Brain className="h-8 w-8 text-primary/30" />
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-primary">{AGENTS.length}</p>
            <p className="text-xs text-muted-foreground">Total Agents</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-green-500">{activeAgents.size}</p>
            <p className="text-xs text-muted-foreground">Active Now</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-blue-500">{CONNECTIONS.length}</p>
            <p className="text-xs text-muted-foreground">Connections</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
