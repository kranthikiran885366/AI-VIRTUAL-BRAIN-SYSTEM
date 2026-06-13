"use client"

import { useState, useEffect } from "react"
import { ChatSidebar } from "./chat-sidebar"
import { ChatInterface } from "./chat-interface"
import { Menu, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn, generateId } from "@/lib/utils"

interface ChatAppProps {
  user: any | null
  profile: {
    id: string
    email?: string
    full_name?: string
    avatar_url?: string
  } | null
}

export function ChatApp({ user, profile }: ChatAppProps) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [userId, setUserId] = useState<string>("")

  // Generate a user ID if not authenticated
  useEffect(() => {
    if (!userId) {
      const id = user?.id || generateId()
      setUserId(id)
    }
  }, [userId, user])

  const handleNewChat = () => {
    setConversationId(null)
  }

  const handleSelectConversation = (id: string) => {
    setConversationId(id)
  }

  const handleConversationCreated = (id: string) => {
    setConversationId(id)
  }

  const handleSignOut = () => {
    // Clear user ID and reset state
    setUserId("")
    setConversationId(null)
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          "fixed top-4 left-4 z-50 md:hidden",
          sidebarOpen && "hidden"
        )}
        onClick={() => setSidebarOpen(true)}
      >
        <Menu className="h-5 w-5" />
      </Button>

      {/* Sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="relative h-full">
          <ChatSidebar
            currentConversationId={conversationId || undefined}
            onNewChat={handleNewChat}
            onSelectConversation={handleSelectConversation}
            user={profile ? { email: profile.email, full_name: profile.full_name } : undefined}
            userId={userId}
            onSignOut={handleSignOut}
          />
          {/* Mobile close button */}
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-4 right-4 md:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main chat area */}
      <main className="flex-1 overflow-hidden">
        {userId && (
          <ChatInterface
            conversationId={conversationId}
            userId={userId}
            onConversationCreated={handleConversationCreated}
          />
        )}
      </main>
    </div>
  )
}
