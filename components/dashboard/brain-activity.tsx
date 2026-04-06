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
  RefreshCw,
  BarChart3,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

// Complete icon map for all agents
const iconMap: Record<string, React.ReactNode> = {
  brain: <Brain className="h-5 w-5" />,
  database: <Database className="h-5 w-5" />,
  heart: <Heart className="h-5 w-5" />,
  lightbulb: <Lightbulb className="h-5 w-5" />,
  sparkles: <Sparkles className="h-5 w-5" />,
  code: <Code className="h-5 w-5" />,
  search: <TrendingUp className="h-5 w-5" />,
  "clipboard-list": <Target className="h-5 w-5" />,
  "academic-cap": <BookOpen className="h-5 w-5" />,
  chat: <MessageSquare className="h-5 w-5" />,
  eye: <Eye className="h-5 w-5" />,
  ear: <Ear className="h-5 w-5" />,
  users: <Users className="h-5 w-5" />,
  shield: <Shield className="h-5 w-5" />,
  smile: <Smile className="h-5 w-5" />,
  map: <Map className="h-5 w-5" />,
  layers: <Layers className="h-5 w-5" />,
  microphone: <Mic className="h-5 w-5" />,
  command: <Command className="h-5 w-5" />,
  activity: <Activity className="h-5 w-5" />,
  flame: <Flame className="h-5 w-5" />,
  moon: <Moon className="h-5 w-5" />,
  scale: <Scale className="h-5 w-5" />,
  hand: <Hand className="h-5 w-5" />,
  focus: <Focus className="h-5 w-5" />,
  alert: <AlertTriangle className="h-5 w-5" />,
  mirror: <RefreshCw className="h-5 w-5" />,
  wand: <Sparkles className="h-5 w-5" />,
  memory: <Database className="h-5 w-5" />,
  body: <Activity className="h-5 w-5" />,
  calendar: <Target className="h-5 w-5" />,
  translate: <MessageSquare className="h-5 w-5" />,
}

// Agent definitions matching Python backend
const AGENT_DEFINITIONS = [
  { name: "memory_agent", displayName: "Memory Agent", icon: "database", color: "#3B82F6", category: "core" },
  { name: "emotion_agent", displayName: "Emotion Agent", icon: "heart", color: "#EC4899", category: "core" },
  { name: "task_agent", displayName: "Task Agent", icon: "clipboard-list", color: "#14B8A6", category: "core" },
  { name: "learning_agent", displayName: "Learning Agent", icon: "academic-cap", color: "#6366F1", category: "core" },
  { name: "social_agent", displayName: "Social Agent", icon: "users", color: "#F97316", category: "social" },
  { name: "perception_agent", displayName: "Perception Agent", icon: "eye", color: "#8B5CF6", category: "sensory" },
  { name: "creativity_agent", displayName: "Creativity Agent", icon: "sparkles", color: "#10B981", category: "cognitive" },
  { name: "self_reflection_agent", displayName: "Self Reflection", icon: "mirror", color: "#6B7280", category: "cognitive" },
  { name: "attention_agent", displayName: "Attention Agent", icon: "focus", color: "#EF4444", category: "core" },
  { name: "motor_control_agent", displayName: "Motor Control", icon: "hand", color: "#84CC16", category: "motor" },
  { name: "language_agent", displayName: "Language Agent", icon: "translate", color: "#0EA5E9", category: "cognitive" },
  { name: "planning_agent", displayName: "Planning Agent", icon: "calendar", color: "#D946EF", category: "executive" },
  { name: "motivation_agent", displayName: "Motivation Agent", icon: "flame", color: "#F59E0B", category: "emotional" },
  { name: "intuition_agent", displayName: "Intuition Agent", icon: "lightbulb", color: "#FBBF24", category: "cognitive" },
  { name: "sleep_rest_agent", displayName: "Sleep/Rest Agent", icon: "moon", color: "#475569", category: "regulatory" },
  { name: "pain_discomfort_agent", displayName: "Pain Agent", icon: "alert", color: "#DC2626", category: "sensory" },
  { name: "ethics_morality_agent", displayName: "Ethics Agent", icon: "scale", color: "#7C3AED", category: "cognitive" },
  { name: "humor_agent", displayName: "Humor Agent", icon: "smile", color: "#FACC15", category: "social" },
  { name: "spatial_agent", displayName: "Spatial Agent", icon: "map", color: "#2DD4BF", category: "cognitive" },
  { name: "sensory_integration_agent", displayName: "Sensory Integration", icon: "layers", color: "#A78BFA", category: "sensory" },
  { name: "language_production_agent", displayName: "Language Production", icon: "microphone", color: "#38BDF8", category: "motor" },
  { name: "executive_function_agent", displayName: "Executive Function", icon: "command", color: "#4F46E5", category: "executive" },
  { name: "stress_anxiety_agent", displayName: "Stress/Anxiety Agent", icon: "activity", color: "#EF4444", category: "emotional" },
  { name: "trust_relationship_agent", displayName: "Trust Agent", icon: "shield", color: "#22C55E", category: "social" },
  { name: "creativity_control_agent", displayName: "Creativity Control", icon: "wand", color: "#C084FC", category: "executive" },
  { name: "sensory_memory_agent", displayName: "Sensory Memory", icon: "memory", color: "#FB923C", category: "memory" },
  { name: "body_awareness_agent", displayName: "Body Awareness", icon: "body", color: "#E879F9", category: "sensory" },
  { name: "eyes_agent", displayName: "Eyes Agent", icon: "eye", color: "#60A5FA", category: "sensory" },
]

const CATEGORIES = {
  core: { label: "Core", color: "#3B82F6" },
  cognitive: { label: "Cognitive", color: "#8B5CF6" },
  emotional: { label: "Emotional", color: "#EC4899" },
  sensory: { label: "Sensory", color: "#10B981" },
  motor: { label: "Motor", color: "#84CC16" },
  executive: { label: "Executive", color: "#4F46E5" },
  social: { label: "Social", color: "#F97316" },
  regulatory: { label: "Regulatory", color: "#475569" },
  memory: { label: "Memory", color: "#3B82F6" },
}

export function BrainActivity() {
  const { data: brainStatus, error } = useSWR("/api/brain?action=status", fetcher, {
    refreshInterval: 5000,
  })
  
  const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set())
  const [activityLevels, setActivityLevels] = useState<Record<string, number>>({})

  // Simulate agent activity
  useEffect(() => {
    const interval = setInterval(() => {
      // Randomly activate agents based on real activity stats
      const activityStats = brainStatus?.activityStats || {}
      
      setActiveAgents((prev) => {
        const next = new Set(prev)
        const randomAgent = AGENT_DEFINITIONS[Math.floor(Math.random() * AGENT_DEFINITIONS.length)]
        
        if (next.has(randomAgent.name)) {
          next.delete(randomAgent.name)
        } else if (next.size < 8) {
          next.add(randomAgent.name)
        }
        return next
      })

      // Update activity levels
      setActivityLevels((prev) => {
        const next = { ...prev }
        AGENT_DEFINITIONS.forEach((agent) => {
          const baseActivity = activityStats[agent.name] || 0
          const noise = Math.random() * 20 - 10
          next[agent.name] = Math.max(0, Math.min(100, baseActivity * 2 + noise + (activeAgents.has(agent.name) ? 30 : 0)))
        })
        return next
      })
    }, 2000)

    return () => clearInterval(interval)
  }, [brainStatus, activeAgents])

  // Group agents by category
  const categorizedAgents = AGENT_DEFINITIONS.reduce(
    (acc, agent) => {
      const category = agent.category || "core"
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category].push(agent)
      return acc
    },
    {} as Record<string, typeof AGENT_DEFINITIONS>
  )

  const totalActive = activeAgents.size
  const systemLoad = (totalActive / AGENT_DEFINITIONS.length) * 100

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Brain Activity</h2>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={brainStatus?.status === "operational" ? "default" : "secondary"}>
            {brainStatus?.status || "connecting"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {totalActive}/{AGENT_DEFINITIONS.length} active
          </span>
        </div>
      </div>

      {/* System load indicator */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">System Load</span>
          <span className="font-medium">{systemLoad.toFixed(0)}%</span>
        </div>
        <Progress value={systemLoad} className="h-2" />
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-secondary/30 text-center">
          <BarChart3 className="h-4 w-4 mx-auto mb-1 text-primary" />
          <p className="text-lg font-bold">{AGENT_DEFINITIONS.length}</p>
          <p className="text-xs text-muted-foreground">Total Agents</p>
        </div>
        <div className="p-3 rounded-lg bg-secondary/30 text-center">
          <Activity className="h-4 w-4 mx-auto mb-1 text-green-500" />
          <p className="text-lg font-bold text-green-500">{totalActive}</p>
          <p className="text-xs text-muted-foreground">Active Now</p>
        </div>
        <div className="p-3 rounded-lg bg-secondary/30 text-center">
          <Zap className="h-4 w-4 mx-auto mb-1 text-yellow-500" />
          <p className="text-lg font-bold text-yellow-500">
            {Object.values(brainStatus?.activityStats || {}).reduce((a, b: unknown) => a + (b as number || 0), 0)}
          </p>
          <p className="text-xs text-muted-foreground">Ops/hr</p>
        </div>
      </div>

      {/* Agents by category */}
      <ScrollArea className="h-[400px]">
        <div className="space-y-4 pr-4">
          {Object.entries(categorizedAgents).map(([category, categoryAgents]) => (
            <div key={category} className="space-y-2">
              <div className="flex items-center gap-2">
                <div
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: CATEGORIES[category as keyof typeof CATEGORIES]?.color }}
                />
                <h3 className="text-sm font-medium text-muted-foreground">
                  {CATEGORIES[category as keyof typeof CATEGORIES]?.label || category}
                </h3>
                <span className="text-xs text-muted-foreground">
                  ({categoryAgents.filter((a) => activeAgents.has(a.name)).length}/{categoryAgents.length})
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-2">
                {categoryAgents.map((agent) => {
                  const isActive = activeAgents.has(agent.name)
                  const activityLevel = activityLevels[agent.name] || 0
                  
                  return (
                    <div
                      key={agent.name}
                      className={cn(
                        "flex items-center gap-3 p-3 rounded-lg border transition-all duration-300",
                        isActive
                          ? "border-primary/50 bg-primary/5"
                          : "border-border bg-secondary/20"
                      )}
                    >
                      <div
                        className={cn(
                          "h-10 w-10 rounded-lg flex items-center justify-center transition-all duration-300 shrink-0",
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
                          {agent.displayName}
                        </p>
                        <div className="flex items-center gap-1.5 mt-1">
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
                        {/* Activity bar */}
                        <div className="mt-1.5 h-1 bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${activityLevel}%`,
                              backgroundColor: agent.color,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
