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
import { cn } from "@/lib/utils"
import type { Conversation, Message } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

// Agent icons mapping
const AGENT_ICONS: Record<string, React.ReactNode> = {
  orchestrator: <Brain className="h-4 w-4" />,
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
  orchestrator: "#8B5CF6",
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
  onConversationCreated?: (id: string) => void
}

export function ChatInterface({
  conversationId,
  onConversationCreated,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [activeAgent, setActiveAgent] = useState("orchestrator")
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
          model: "openai/gpt-4o",
        },
      }),
    }),
    onFinish: async (message) => {
      mutate("/api/conversations")
      setRoutingInfo(null)
    },
  })

  // Route request to get agent info before sending
  const routeRequest = useCallback(async (content: string) => {
    try {
      const response = await fetch("/api/brain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "route-request", content }),
      })
      const routing = await response.json()
      setRoutingInfo(routing)
      setActiveAgent(routing.selectedAgent)
      return routing
    } catch (error) {
      console.error("Routing error:", error)
      return null
    }
  }, [])

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
            title: content.slice(0, 50) + (content.length > 50 ? "..." : ""),
          }),
        })
        const newConv = await res.json()
        currentConversationId = newConv.id
        onConversationCreated?.(newConv.id)
      } catch (error) {
        console.error("Failed to create conversation:", error)
        return
      }
    }

    // Save user message to database
    try {
      await fetch(`/api/conversations/${currentConversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "user",
          content,
        }),
      })
    } catch (error) {
      console.error("Failed to save user message:", error)
    }

    // Send to AI
    sendMessage({ text: content })
  }

  const isStreaming = status === "streaming"
  const isLoading = status === "submitted" || isStreaming

  // Empty state
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          {/* Brain visualization header */}
          <div className="relative mb-6">
            <div className="h-24 w-24 rounded-full bg-primary/10 flex items-center justify-center">
              <Brain className="h-12 w-12 text-primary brain-active" />
            </div>
            <div className="absolute -bottom-1 -right-1 h-8 w-8 rounded-full bg-green-500 flex items-center justify-center border-4 border-background">
              <Activity className="h-4 w-4 text-white" />
            </div>
          </div>
          
          <h1 className="text-3xl font-bold mb-2 text-balance text-center gradient-text">
            AI Virtual Brain System
          </h1>
          <p className="text-muted-foreground text-center max-w-md mb-2">
            A cognitive AI with {brainStatus?.agents?.length || 28} specialized neural agents
            working together through advanced orchestration.
          </p>
          
          {/* System status */}
          <div className="flex items-center gap-2 mb-8">
            <Badge 
              variant={brainStatus?.status === "operational" ? "default" : "secondary"}
              className="gap-1"
            >
              <div className={cn(
                "h-2 w-2 rounded-full",
                brainStatus?.status === "operational" ? "bg-green-500 status-online" : "bg-muted-foreground"
              )} />
              {brainStatus?.status || "Connecting..."}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Python Backend Connected
            </span>
          </div>

          {/* Capability cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-2xl w-full">
            {[
              { icon: Brain, label: "Reasoning", desc: "Complex problem solving", agent: "reasoning_agent" },
              { icon: Database, label: "Memory", desc: "Long-term recall", agent: "memory_agent" },
              { icon: Heart, label: "Emotion", desc: "Emotional intelligence", agent: "emotion_agent" },
              { icon: Code, label: "Code", desc: "Programming help", agent: "language_agent" },
              { icon: Sparkles, label: "Creative", desc: "Generate ideas", agent: "creativity_agent" },
              { icon: Zap, label: "Tasks", desc: "Stay organized", agent: "task_agent" },
            ].map(({ icon: Icon, label, desc, agent }) => (
              <div
                key={label}
                className="flex items-start gap-3 p-4 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer card-hover"
                onClick={() => handleSend(`Help me with ${label.toLowerCase()}-related tasks`)}
              >
                <div 
                  className="h-10 w-10 rounded-lg flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${AGENT_COLORS[agent] || AGENT_COLORS.orchestrator}20` }}
                >
                  <Icon 
                    className="h-5 w-5" 
                    style={{ color: AGENT_COLORS[agent] || AGENT_COLORS.orchestrator }}
                  />
                </div>
                <div>
                  <p className="font-medium text-sm">{label}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Suggested prompts */}
          <div className="mt-8 w-full max-w-2xl">
            <p className="text-sm text-muted-foreground mb-3 text-center">
              Try asking:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                "Help me brainstorm ideas for a new project",
                "Explain how neural networks work",
                "Remember that I prefer concise answers",
                "Help me plan my week productively",
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSend(prompt)}
                  className="text-left p-3 rounded-lg border border-border hover:bg-secondary/50 text-sm transition-colors"
                >
                  <MessageSquare className="h-4 w-4 inline mr-2 opacity-50" />
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Mini brain network preview */}
          <div className="mt-8 w-full max-w-md">
            <BrainNetwork compact />
          </div>
        </div>

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header with agent info */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <div 
              className="h-8 w-8 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator}20` }}
            >
              {AGENT_ICONS[activeAgent] || <Brain className="h-4 w-4" />}
            </div>
            <div>
              <p className="font-medium text-sm capitalize">
                {activeAgent.replace("_agent", "").replace("_", " ")} Agent
              </p>
              {routingInfo && (
                <p className="text-xs text-muted-foreground">
                  Confidence: {(routingInfo.confidence * 100).toFixed(0)}%
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {isLoading && <CognitiveLoop isProcessing compact />}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowBrainPanel(!showBrainPanel)}
                    className={cn(showBrainPanel && "bg-secondary")}
                  >
                    <Settings2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {showBrainPanel ? "Hide" : "Show"} Brain Panel
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Messages area */}
        <ScrollArea className="flex-1" ref={scrollRef}>
          <div className="max-w-3xl mx-auto">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                agentUsed={activeAgent}
              />
            ))}
            
            {isLoading && (
              <div className="px-4 py-2">
                <div className="flex items-center gap-2 mb-2">
                  <div 
                    className="h-6 w-6 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${AGENT_COLORS[activeAgent] || AGENT_COLORS.orchestrator}20` }}
                  >
                    {AGENT_ICONS[activeAgent] || <Brain className="h-3 w-3" />}
                  </div>
                  <span className="text-xs text-muted-foreground capitalize">
                    {activeAgent.replace("_agent", "").replace("_", " ")} is thinking...
                  </span>
                </div>
                <TypingIndicator agentName={activeAgent.replace("_agent", "")} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input area */}
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

      {/* Brain panel (collapsible) */}
      {showBrainPanel && (
        <div className="w-80 border-l border-border p-4 overflow-y-auto hidden lg:block">
          <div className="space-y-4">
            <CognitiveLoop isProcessing={isLoading} />
            <BrainNetwork compact />
          </div>
        </div>
      )}
    </div>
  )
}
