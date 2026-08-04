"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import useSWR, { mutate } from "swr"
import { 
  Brain, 
  Sparkles, 
  MessageSquare, 
  Zap, 
  Database, 
  Heart, 
  Code,
  Eye,
  Target,
  BookOpen,
  Users,
  Lightbulb,
  Activity,
  Settings2,
  ChevronRight,
  TrendingUp,
  LayoutDashboard
} from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ChatMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import { TypingIndicator } from "./typing-indicator"
import { CognitiveLoop } from "@/components/dashboard/cognitive-loop"
import { BrainNetwork } from "@/components/dashboard/brain-network"
import { MemoriesPanel } from "@/components/dashboard/memories-panel"
import { TasksPanel } from "@/components/dashboard/tasks-panel"
import { cn } from "@/lib/utils"
import type { Conversation, Message } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

// Agent icons mapping
const AGENT_ICONS: Record<string, React.ReactNode> = {
  orchestrator_agent: <Brain className="h-4 w-4" />,
  memory_agent: <Database className="h-4 w-4" />,
  emotion_agent: <Heart className="h-4 w-4" />,
  task_agent: <Target className="h-4 w-4" />,
  creativity_agent: <Sparkles className="h-4 w-4" />,
  learning_agent: <BookOpen className="h-4 w-4" />,
  reasoning_agent: <Lightbulb className="h-4 w-4" />,
  perception_agent: <Eye className="h-4 w-4" />,
  social_agent: <Users className="h-4 w-4" />,
  language_agent: <MessageSquare className="h-4 w-4" />,
  code: <Code className="h-4 w-4" />,
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator_agent: "#8B5CF6",
  memory_agent: "#3B82F6",
  emotion_agent: "#EC4899",
  task_agent: "#14B8A6",
  creativity_agent: "#10B981",
  learning_agent: "#6366F1",
  reasoning_agent: "#F59E0B",
  perception_agent: "#8B5CF6",
  social_agent: "#F97316",
  language_agent: "#0EA5E9",
  code: "#84CC16",
}

interface ChatInterfaceProps {
  conversationId: string | null
  userId: string
  onConversationCreated?: (id: string) => void
}

export function ChatInterface({
  conversationId,
  userId,
  onConversationCreated,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [activeAgent, setActiveAgent] = useState("orchestrator_agent")
  const [showBrainPanel, setShowBrainPanel] = useState(false)
  const [routingInfo, setRoutingInfo] = useState<{
    selectedAgent: string
    confidence: number
    reasoning: string
  } | null>(null)

  // Fetch existing conversation
  const { data: conversation } = useSWR<Conversation & { messages: Message[] }>(
    conversationId ? `/api/conversations/${conversationId}` : null,
    fetcher
  )

  // Fetch brain status
  const { data: brainStatus } = useSWR("/api/brain?action=status", fetcher, {
    refreshInterval: 10000,
  })

  // Initialize chat with AI SDK
  const { messages, sendMessage, status, setMessages } = useChat({
    id: conversationId || undefined,
    transport: new DefaultChatTransport({
      api: "/api/chat",
      prepareSendMessagesRequest: ({ id, messages }) => ({
        body: {
          messages,
          conversationId: id,
          userId,
          model: "gpt-4o",
        },
      }),
    }),
    onFinish: async (message) => {
      if (userId) {
        mutate(`/api/conversations?userId=${userId}`)
      }
      setRoutingInfo(null)
    },
  })

  // Route request to get agent info before sending
  const routeRequest = useCallback(async (content: string) => {
    try {
      const response = await fetch("/api/brain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "route-request", content, userId }),
      })
      const routing = await response.json()
      setRoutingInfo(routing)
      setActiveAgent(routing.selectedAgent)
      return routing
    } catch (error) {
      console.error("[v0] Routing error:", error)
      return null
    }
  }, [userId])

  // Load existing messages when conversation changes
  useEffect(() => {
    if (conversation?.messages && conversation.messages.length > 0) {
      const uiMessages = conversation.messages.map((msg) => ({
        id: msg.id,
        role: msg.role as "user" | "assistant",
        parts: [{ type: "text" as const, text: msg.content }],
        createdAt: new Date(msg.created_at),
      }))
      setMessages(uiMessages)
    } else if (!conversationId) {
      setMessages([])
    }
  }, [conversation, conversationId, setMessages])

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, status])

  const handleSend = async (content: string) => {
    // Route the request first
    await routeRequest(content)

    // Create conversation if none exists
    let currentConversationId = conversationId
    
    if (!currentConversationId) {
      try {
        const res = await fetch("/api/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            userId,
            title: content.slice(0, 50) + (content.length > 50 ? "..." : ""),
          }),
        })
        const newConv = await res.json()
        currentConversationId = newConv.id
        onConversationCreated?.(newConv.id)
      } catch (error) {
        console.error("[v0] Failed to create conversation:", error)
        return
      }
    }

    // Save user message to database
    try {
      await fetch(`/api/conversations/${currentConversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId,
          role: "user",
          content,
        }),
      })
    } catch (error) {
      console.error("[v0] Failed to save user message:", error)
    }

    // Send to AI
    sendMessage({ text: content })
  }

  const isStreaming = status === "streaming"
  const isLoading = status === "submitted" || isStreaming

  // Empty state
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full flex-col bg-background/40 backdrop-blur-md">
        <ScrollArea className="flex-1">
          <div className="flex flex-col items-center justify-center p-8 max-w-4xl mx-auto space-y-8 pt-16">
            
            {/* Brain visualization header */}
            <div className="relative">
              <div className="h-20 w-20 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-lg shadow-primary/5">
                <Brain className="h-10 w-10 text-primary brain-active" />
              </div>
              <div className="absolute -bottom-1 -right-1 h-7 w-7 rounded-full bg-green-500 flex items-center justify-center border-4 border-background shadow-md">
                <Activity className="h-3.5 w-3.5 text-white animate-pulse" />
              </div>
            </div>
            
            <div className="text-center space-y-2">
              <h1 className="text-3xl font-extrabold tracking-tight gradient-text">
                AI Virtual Brain System
              </h1>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                A cognitive architecture powered by {brainStatus?.agents?.length || 28} specialized neural agents routing decisions collaboratively.
              </p>
            </div>
            
            {/* System status pill */}
            <div className="flex items-center gap-2.5 bg-secondary/20 px-3.5 py-1.5 rounded-full border border-border/40 text-xs">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              <span className="font-semibold capitalize text-foreground">{brainStatus?.status || "operational"}</span>
              <span className="text-muted-foreground">|</span>
              <span className="text-muted-foreground text-[10px] uppercase font-bold font-mono">Host Connect OK</span>
            </div>

            {/* Capability cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full">
              {[
                { icon: Brain, label: "Reasoning Agent", desc: "Logical decomposition & multi-step proof evaluation", agent: "reasoning_agent" },
                { icon: Database, label: "Memory Agent", desc: "Syncs semantic knowledge indices & decays past interactions", agent: "memory_agent" },
                { icon: Heart, label: "Emotion Agent", desc: "Tracks mood, expressions and sentiment alignment", agent: "emotion_agent" },
                { icon: Code, label: "Language/Code Agent", desc: "Drafts code snippets, handles translation & stylistic revision", agent: "language_agent" },
                { icon: Sparkles, label: "Creativity Agent", desc: "Generates divergent concepts &SCAMPER patterns", agent: "creativity_agent" },
                { icon: Zap, label: "Task Operations", desc: "Manages priorities, Gantt timelines and alerts", agent: "task_agent" },
              ].map(({ icon: Icon, label, desc, agent }) => (
                <div
                  key={label}
                  className="flex items-start gap-4 p-5 rounded-2xl border border-border/50 bg-secondary/15 hover:bg-secondary/35 transition-all cursor-pointer card-hover"
                  onClick={() => handleSend(`Coordinate ${label.toLowerCase()} to inspect resources`)}
                >
                  <div 
                    className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0 border shadow-inner"
                    style={{ 
                      backgroundColor: `${AGENT_COLORS[agent] || AGENT_COLORS.orchestrator_agent}15`,
                      borderColor: `${AGENT_COLORS[agent] || AGENT_COLORS.orchestrator_agent}30` 
                    }}
                  >
                    <Icon 
                      className="h-5 w-5" 
                      style={{ color: AGENT_COLORS[agent] || AGENT_COLORS.orchestrator_agent }}
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="font-semibold text-sm text-foreground">{label}</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Suggested prompts list */}
            <div className="w-full space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground text-center">Suggested Operational Prompts</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {[
                  "Draft a logical plan to study neural network structures",
                  "Consolidate memory: I prefer programming using TypeScript",
                  "Create high priority task: Complete AI Brain testing by Friday",
                  "Brainstorm creative UI layouts for system monitoring",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="text-left p-3.5 rounded-xl border border-border/50 bg-secondary/10 hover:bg-secondary/30 text-xs font-medium transition-all text-muted-foreground hover:text-foreground"
                  >
                    <MessageSquare className="h-3.5 w-3.5 inline mr-2 text-primary opacity-70" />
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Compact Brain preview graphics */}
            <div className="w-full">
              <BrainNetwork compact />
            </div>

          </div>
        </ScrollArea>

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    )
  }

  return (
    <div className="flex h-full bg-background/40 backdrop-blur-md">
      {/* Main chat viewport */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Header with selected agent info */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/40 bg-background/50 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3">
            <div 
              className="h-9 w-9 rounded-xl flex items-center justify-center border shadow-inner"
              style={{ 
                backgroundColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator_agent}15`,
                borderColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator_agent}30`
              }}
            >
              {AGENT_ICONS[activeAgent] || <Brain className="h-5 w-5" />}
            </div>
            <div>
              <p className="font-bold text-sm capitalize text-foreground">
                {activeAgent.replace("_agent", "").replace("_", " ")} Agent
              </p>
              {routingInfo && (
                <p className="text-[10px] text-muted-foreground font-mono">
                  Confidence: <span className="font-semibold text-primary">{(routingInfo.confidence * 100).toFixed(0)}%</span> • Reasoning Matched
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {isLoading && <CognitiveLoop isProcessing compact />}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowBrainPanel(!showBrainPanel)}
                    className={cn("h-8 w-8 rounded-lg", showBrainPanel && "bg-secondary")}
                  >
                    <Settings2 className="h-4.5 w-4.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{showBrainPanel ? "Hide" : "Show"} Telemetry panel</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Messages feed */}
        <ScrollArea className="flex-1" ref={scrollRef}>
          <div className="max-w-3xl mx-auto py-6">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                agentUsed={activeAgent}
              />
            ))}
            
            {isLoading && (
              <div className="px-6 py-6 border-b border-border/20 bg-secondary/10 flex items-start gap-4">
                <div 
                  className="h-8 w-8 rounded-xl flex items-center justify-center shrink-0 border"
                  style={{ 
                    backgroundColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator_agent}15`,
                    borderColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator_agent}30`
                  }}
                >
                  {AGENT_ICONS[activeAgent] || <Brain className="h-4 w-4" />}
                </div>
                <div className="flex-1 space-y-2">
                  <span className="text-xs text-muted-foreground capitalize font-semibold font-mono">
                    {activeAgent.replace("_agent", "").replace("_", " ")} processing...
                  </span>
                  <TypingIndicator agentName={activeAgent.replace("_agent", "")} />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Floating Input */}
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

      {/* Right Telemetry panel (collapsible) */}
      {showBrainPanel && (
        <div className="w-80 border-l border-border/40 p-5 overflow-y-auto hidden xl:block bg-secondary/5 glass-panel shrink-0">
          <div className="space-y-6">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">Cognitive States</h3>
              <CognitiveLoop isProcessing={isLoading} />
            </div>
            
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">Active Connections</h3>
              <BrainNetwork compact />
            </div>
            
            <Separator className="bg-border/30" />
            
            <MemoriesPanel userId={userId} />
            
            <Separator className="bg-border/30" />
            
            <TasksPanel userId={userId} />
          </div>
        </div>
      )}
    </div>
  )
}

function Separator({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-border", className)} />
}
