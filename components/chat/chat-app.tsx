"use client"

import { useState, useEffect } from "react"
import { ChatSidebar } from "./chat-sidebar"
import { ChatInterface } from "./chat-interface"
import { DashboardView } from "../dashboard/dashboard-view"
import { FilesView } from "../files/files-view"
import { SettingsView } from "../settings/settings-view"
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
  const [currentView, setCurrentView] = useState<"chat" | "dashboard" | "memory" | "files" | "settings">("chat")

  // Generate a user ID if not authenticated
  useEffect(() => {
    if (!userId) {
      const id = user?.id || generateId()
      setUserId(id)
    }
  }, [userId, user])

  // Sync theme setting on load
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme")
    const root = window.document.documentElement
    if (savedTheme === "light") {
      root.classList.remove("dark")
      root.classList.add("light")
    } else {
      root.classList.remove("light")
      root.classList.add("dark")
    }
  }, [])

  const handleNewChat = () => {
    setConversationId(null)
    setCurrentView("chat")
  }

  const handleSelectConversation = (id: string) => {
    setConversationId(id)
    setCurrentView("chat")
  }

  const handleConversationCreated = (id: string) => {
    setConversationId(id)
  }

  const handleSignOut = () => {
    setUserId("")
    setConversationId(null)
    setCurrentView("chat")
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      {/* Mobile menu button */}
      <Button
        aria-label="Toggle Navigation menu"
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

      {/* Sidebar navigation */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 shrink-0",
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
            currentView={currentView}
            onChangeView={setCurrentView}
          />
          {/* Mobile close button */}
          <Button
            aria-label="Close menu"
            variant="ghost"
            size="icon"
            className="absolute top-4 right-4 md:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main panel routing */}
      <main className="flex-1 overflow-hidden relative">
        {userId && (
          <div className="h-full w-full">
            {currentView === "chat" && (
              <ChatInterface
                conversationId={conversationId}
                userId={userId}
                onConversationCreated={handleConversationCreated}
              />
            )}
            
            {currentView === "dashboard" && (
              <DashboardView userId={userId} />
            )}

            {currentView === "memory" && (
              <DashboardView userId={userId} />
            )}

            {currentView === "files" && (
              <FilesView userId={userId} />
            )}

            {currentView === "settings" && (
              <SettingsView userId={userId} />
            )}
          </div>
        )}
      </main>
    </div>
  )
}
