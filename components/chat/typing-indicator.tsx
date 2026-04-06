"use client"

import { Brain } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface TypingIndicatorProps {
  agentName?: string
}

export function TypingIndicator({ agentName = "Brain" }: TypingIndicatorProps) {
  return (
    <div className="flex gap-4 px-4 py-6 bg-secondary/30 message-enter">
      <Avatar className="h-8 w-8 shrink-0 bg-violet-500/20 text-violet-400">
        <AvatarFallback className="bg-violet-500/20 text-violet-400">
          <Brain className="h-4 w-4 brain-active" />
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{agentName}</span>
          <span className="text-xs text-muted-foreground">is thinking...</span>
        </div>
        
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-primary/60 typing-dot" />
          <div className="h-2 w-2 rounded-full bg-primary/60 typing-dot" />
          <div className="h-2 w-2 rounded-full bg-primary/60 typing-dot" />
        </div>
      </div>
    </div>
  )
}
