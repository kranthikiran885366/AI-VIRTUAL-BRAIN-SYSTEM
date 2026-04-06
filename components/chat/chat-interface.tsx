"use client"

import { useEffect, useRef, useState } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import useSWR, { mutate } from "swr"
import { Brain, Sparkles, MessageSquare, Zap, Database, Heart, Code } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import { TypingIndicator } from "./typing-indicator"
import type { Conversation, Message } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

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

  // Fetch existing conversation
  const { data: conversation } = useSWR<Conversation & { messages: Message[] }>(
    conversationId ? `/api/conversations/${conversationId}` : null,
    fetcher
  )

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
      // Mutate conversations list to update sidebar
      mutate("/api/conversations")
    },
  })

  // Load existing messages when conversation changes
  useEffect(() => {
    if (conversation?.messages && conversation.messages.length > 0) {
      // Convert database messages to UI messages format
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
          <div className="relative mb-6">
            <Brain className="h-20 w-20 text-primary brain-active" />
            <div className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-primary flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
          </div>
          
          <h1 className="text-3xl font-bold mb-2 text-balance text-center">
            AI Virtual Brain
          </h1>
          <p className="text-muted-foreground text-center max-w-md mb-8">
            An advanced AI assistant with multiple specialized agents working together
            to help you with any task.
          </p>

          {/* Capability cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-2xl w-full">
            {[
              { icon: Brain, label: "Reasoning", desc: "Complex problem solving" },
              { icon: Database, label: "Memory", desc: "Remember context" },
              { icon: Heart, label: "Empathy", desc: "Emotional intelligence" },
              { icon: Code, label: "Code", desc: "Programming help" },
              { icon: Sparkles, label: "Creative", desc: "Generate ideas" },
              { icon: Zap, label: "Tasks", desc: "Stay organized" },
            ].map(({ icon: Icon, label, desc }) => (
              <div
                key={label}
                className="flex items-start gap-3 p-4 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer"
              >
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Icon className="h-5 w-5 text-primary" />
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
                "Write a Python function to sort a list",
                "Help me plan my week",
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
        </div>

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
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
          
          {isLoading && <TypingIndicator agentName="Brain" />}
        </div>
      </ScrollArea>

      {/* Input area */}
      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </div>
  )
}
