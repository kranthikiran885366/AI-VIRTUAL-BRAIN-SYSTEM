"use client"

import { useState, useEffect } from "react"
import {
  Eye,
  Brain,
  Heart,
  Lightbulb,
  Target,
  Zap,
  RefreshCw,
  ArrowRight,
  CheckCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

// Cognitive processing stages matching Python backend architecture
const COGNITIVE_STAGES = [
  {
    id: "perception",
    name: "Perceive",
    description: "Understanding input",
    icon: Eye,
    color: "#8B5CF6",
  },
  {
    id: "memory",
    name: "Remember",
    description: "Recalling context",
    icon: Brain,
    color: "#3B82F6",
  },
  {
    id: "emotion",
    name: "Feel",
    description: "Emotional analysis",
    icon: Heart,
    color: "#EC4899",
  },
  {
    id: "reasoning",
    name: "Reason",
    description: "Logical analysis",
    icon: Lightbulb,
    color: "#F59E0B",
  },
  {
    id: "planning",
    name: "Plan",
    description: "Determining approach",
    icon: Target,
    color: "#14B8A6",
  },
  {
    id: "execution",
    name: "Execute",
    description: "Generating response",
    icon: Zap,
    color: "#10B981",
  },
  {
    id: "reflection",
    name: "Reflect",
    description: "Quality evaluation",
    icon: RefreshCw,
    color: "#6366F1",
  },
]

interface CognitiveLoopProps {
  isProcessing?: boolean
  currentStage?: string
  compact?: boolean
}

export function CognitiveLoop({ 
  isProcessing = false, 
  currentStage,
  compact = false 
}: CognitiveLoopProps) {
  const [activeStage, setActiveStage] = useState(0)
  const [completedStages, setCompletedStages] = useState<number[]>([])

  // Animate through stages when processing
  useEffect(() => {
    if (!isProcessing) {
      setActiveStage(0)
      setCompletedStages([])
      return
    }

    const interval = setInterval(() => {
      setActiveStage((prev) => {
        const next = (prev + 1) % COGNITIVE_STAGES.length
        if (next > prev) {
          setCompletedStages((completed) => [...completed, prev])
        } else {
          setCompletedStages([])
        }
        return next
      })
    }, 800)

    return () => clearInterval(interval)
  }, [isProcessing])

  // Set stage from prop
  useEffect(() => {
    if (currentStage) {
      const index = COGNITIVE_STAGES.findIndex((s) => s.id === currentStage)
      if (index !== -1) {
        setActiveStage(index)
      }
    }
  }, [currentStage])

  if (compact) {
    return (
      <div className="flex items-center gap-1.5">
        {COGNITIVE_STAGES.map((stage, index) => {
          const Icon = stage.icon
          const isActive = isProcessing && index === activeStage
          const isCompleted = completedStages.includes(index)
          
          return (
            <div
              key={stage.id}
              className={cn(
                "h-6 w-6 rounded-full flex items-center justify-center transition-all duration-300",
                isActive && "scale-125",
                isCompleted && "opacity-50"
              )}
              style={{
                backgroundColor: isActive ? `${stage.color}30` : "var(--secondary)",
                borderColor: isActive ? stage.color : "transparent",
                borderWidth: "2px",
              }}
            >
              {isCompleted ? (
                <CheckCircle className="h-3 w-3 text-green-500" />
              ) : (
                <Icon
                  className={cn("h-3 w-3", isActive && "animate-pulse")}
                  style={{ color: isActive ? stage.color : "var(--muted-foreground)" }}
                />
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            Cognitive Processing Loop
          </CardTitle>
          <Badge variant={isProcessing ? "default" : "secondary"}>
            {isProcessing ? "Processing" : "Idle"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Linear visualization */}
        <div className="flex items-center justify-between gap-1 mb-4">
          {COGNITIVE_STAGES.map((stage, index) => {
            const Icon = stage.icon
            const isActive = isProcessing && index === activeStage
            const isCompleted = completedStages.includes(index)
            const isPending = !isCompleted && index > activeStage
            
            return (
              <div key={stage.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={cn(
                      "h-10 w-10 rounded-full flex items-center justify-center transition-all duration-300 border-2",
                      isActive && "scale-110 shadow-lg",
                      isCompleted && "border-green-500/50 bg-green-500/10",
                      isPending && "opacity-40"
                    )}
                    style={{
                      backgroundColor: isActive ? `${stage.color}20` : "var(--secondary)",
                      borderColor: isActive ? stage.color : isCompleted ? "#22C55E" : "var(--border)",
                      boxShadow: isActive ? `0 0 20px ${stage.color}40` : undefined,
                    }}
                  >
                    {isCompleted ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : (
                      <Icon
                        className={cn("h-5 w-5", isActive && "animate-pulse")}
                        style={{ color: isActive ? stage.color : "var(--muted-foreground)" }}
                      />
                    )}
                  </div>
                  <span className={cn(
                    "text-xs mt-1.5 text-center",
                    isActive ? "font-medium" : "text-muted-foreground"
                  )}>
                    {stage.name}
                  </span>
                </div>
                
                {index < COGNITIVE_STAGES.length - 1 && (
                  <ArrowRight
                    className={cn(
                      "h-4 w-4 text-muted-foreground/30 shrink-0 mx-1",
                      isProcessing && index === activeStage && "text-primary animate-pulse"
                    )}
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* Current stage description */}
        {isProcessing && (
          <div className="p-3 rounded-lg bg-secondary/30 text-center">
            <p className="text-sm font-medium" style={{ color: COGNITIVE_STAGES[activeStage].color }}>
              {COGNITIVE_STAGES[activeStage].name}
            </p>
            <p className="text-xs text-muted-foreground">
              {COGNITIVE_STAGES[activeStage].description}
            </p>
          </div>
        )}

        {/* Circular visualization */}
        <div className="relative w-48 h-48 mx-auto mt-6">
          <svg className="w-full h-full -rotate-90">
            {/* Background circle */}
            <circle
              cx="50%"
              cy="50%"
              r="40%"
              fill="none"
              stroke="var(--border)"
              strokeWidth="4"
            />
            
            {/* Progress arc */}
            {isProcessing && (
              <circle
                cx="50%"
                cy="50%"
                r="40%"
                fill="none"
                stroke="hsl(var(--primary))"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={`${(completedStages.length / COGNITIVE_STAGES.length) * 251.2} 251.2`}
                className="transition-all duration-300"
              />
            )}
          </svg>

          {/* Center content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {isProcessing ? (
              <>
                <div
                  className="h-16 w-16 rounded-full flex items-center justify-center thinking-animation"
                  style={{
                    backgroundColor: `${COGNITIVE_STAGES[activeStage].color}20`,
                  }}
                >
                  {(() => {
                    const Icon = COGNITIVE_STAGES[activeStage].icon
                    return (
                      <Icon
                        className="h-8 w-8"
                        style={{ color: COGNITIVE_STAGES[activeStage].color }}
                      />
                    )
                  })()}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Step {activeStage + 1} of {COGNITIVE_STAGES.length}
                </p>
              </>
            ) : (
              <>
                <Brain className="h-10 w-10 text-muted-foreground/50" />
                <p className="text-xs text-muted-foreground mt-2">Ready</p>
              </>
            )}
          </div>

          {/* Stage indicators around the circle */}
          {COGNITIVE_STAGES.map((stage, index) => {
            const angle = (index / COGNITIVE_STAGES.length) * 360 - 90
            const radians = (angle * Math.PI) / 180
            const radius = 75
            const x = 50 + radius * Math.cos(radians) / 1.5
            const y = 50 + radius * Math.sin(radians) / 1.5
            const Icon = stage.icon
            const isActive = isProcessing && index === activeStage
            
            return (
              <div
                key={stage.id}
                className={cn(
                  "absolute h-6 w-6 rounded-full flex items-center justify-center transition-all duration-300",
                  isActive && "scale-125"
                )}
                style={{
                  left: `${x}%`,
                  top: `${y}%`,
                  transform: "translate(-50%, -50%)",
                  backgroundColor: isActive ? `${stage.color}40` : "var(--secondary)",
                  borderWidth: "2px",
                  borderColor: isActive ? stage.color : "var(--border)",
                }}
              >
                <Icon
                  className="h-3 w-3"
                  style={{ color: isActive ? stage.color : "var(--muted-foreground)" }}
                />
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
