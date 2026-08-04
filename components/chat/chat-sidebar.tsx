"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import {
  MessageSquare,
  Search,
  Trash2,
  Archive,
  Brain,
  Settings,
  LogOut,
  Workflow,
  FolderOpen,
  Plus
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn, formatDate, truncate } from "@/lib/utils"
import type { Conversation } from "@/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

interface ChatSidebarProps {
  currentConversationId?: string
  userId: string
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  user?: { email?: string; full_name?: string }
  onSignOut?: () => void
  currentView: "chat" | "dashboard" | "memory" | "files" | "settings"
  onChangeView: (view: "chat" | "dashboard" | "memory" | "files" | "settings") => void
}

export function ChatSidebar({
  currentConversationId,
  userId,
  onNewChat,
  onSelectConversation,
  user,
  onSignOut,
  currentView,
  onChangeView,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const { data: conversations, mutate } = useSWR<Conversation[]>(
    userId ? `/api/conversations?userId=${userId}` : null,
    fetcher,
    { refreshInterval: 30000 }
  )

  const filteredConversations = conversations?.filter((conv) =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Are you sure you want to delete this conversation?")) return

    try {
      await fetch(`/api/conversations/${id}`, { method: "DELETE" })
      mutate()
      if (currentConversationId === id) {
        onNewChat()
      }
    } catch (error) {
      console.error("Failed to delete conversation:", error)
    }
  }

  const handleArchive = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`/api/conversations/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_archived: true }),
      })
      mutate()
    } catch (error) {
      console.error("Failed to archive conversation:", error)
    }
  }

  return (
    <TooltipProvider>
      <div className="flex h-full w-64 flex-col bg-background/95 border-r border-border/40 glass-panel">
        
        {/* Sidebar Header Brand */}
        <div className="flex items-center gap-3 p-4 border-b border-border/30 shrink-0">
          <div className="relative h-9 w-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary shadow-inner">
            <Brain className="h-5 w-5 text-primary brain-active" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-sm tracking-tight">Virtual Brain</span>
            <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">Aesthetic AI OS</span>
          </div>
        </div>

        {/* Global Navigation Section */}
        <div className="p-3 space-y-1 shrink-0">
          {[
            { id: "chat", label: "Agent Session (Chat)", icon: MessageSquare },
            { id: "dashboard", label: "Brain Operations", icon: Workflow },
            { id: "files", label: "File Vault", icon: FolderOpen },
            { id: "settings", label: "Settings", icon: Settings },
          ].map((nav) => {
            const Icon = nav.icon
            const isActive = currentView === nav.id
            return (
              <button
                key={nav.id}
                onClick={() => onChangeView(nav.id as any)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 text-xs font-semibold rounded-xl transition-all",
                  isActive 
                    ? "bg-primary/10 text-primary border-l-2 border-primary" 
                    : "text-muted-foreground hover:bg-secondary/40 hover:text-foreground"
                )}
              >
                <Icon className="h-4.5 w-4.5" />
                {nav.label}
              </button>
            )
          })}
        </div>

        <Separator className="bg-border/30 px-3" />

        {/* Chat Actions */}
        <div className="p-3 shrink-0 flex items-center justify-between">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest px-1">Recent Chats</span>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={onNewChat}
                size="icon"
                variant="ghost"
                className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-secondary/50 rounded-lg"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>New session</TooltipContent>
          </Tooltip>
        </div>

        {/* Conversations Search */}
        <div className="px-3 pb-2 shrink-0">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground/60" />
            <Input
              placeholder="Search history..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8.5 h-8 text-xs bg-secondary/20 focus-visible:ring-primary border-none rounded-lg"
            />
          </div>
        </div>

        {/* Conversations List Scroll */}
        <ScrollArea className="flex-1 px-2">
          <div className="space-y-1 py-1">
            {filteredConversations?.map((conversation) => {
              const isSelected = currentConversationId === conversation.id && currentView === "chat"
              return (
                <div
                  key={conversation.id}
                  className={cn(
                    "group relative flex items-center gap-2 rounded-xl px-3 py-2 text-xs cursor-pointer transition-all",
                    isSelected
                      ? "bg-primary/10 text-primary shadow-sm"
                      : "hover:bg-secondary/30 text-foreground"
                  )}
                  onClick={() => onSelectConversation(conversation.id)}
                  onMouseEnter={() => setHoveredId(conversation.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <MessageSquare className="h-4 w-4 shrink-0 opacity-60 text-muted-foreground" />
                  <div className="flex-1 overflow-hidden">
                    <p className="truncate font-semibold">
                      {truncate(conversation.title, 22)}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {formatDate(conversation.updated_at)}
                    </p>
                  </div>

                  {/* Hover Actions */}
                  {hoveredId === conversation.id && (
                    <div className="absolute right-2 flex items-center gap-0.5 bg-background/90 p-0.5 rounded-lg border border-border/20 shadow-md">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 hover:bg-secondary"
                            onClick={(e) => handleArchive(conversation.id, e)}
                          >
                            <Archive className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Archive</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={(e) => handleDelete(conversation.id, e)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Delete</TooltipContent>
                      </Tooltip>
                    </div>
                  )}
                </div>
              )
            })}

            {filteredConversations?.length === 0 && (
              <div className="px-3 py-8 text-center text-xs text-muted-foreground">
                {searchQuery ? "No sessions found" : "No sessions yet"}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* User Account Section */}
        {user && (
          <div className="border-t border-border/30 p-3 shrink-0 bg-secondary/10">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-xl bg-primary/20 flex items-center justify-center text-primary font-bold text-xs shadow-inner">
                {user.full_name?.charAt(0) || user.email?.charAt(0) || "U"}
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-xs font-semibold">
                  {user.full_name || user.email}
                </p>
              </div>
              <div className="flex items-center gap-0.5">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      className="h-7 w-7 text-muted-foreground hover:text-primary rounded-lg"
                      onClick={() => onChangeView("settings")}
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Settings</TooltipContent>
                </Tooltip>
                {onSignOut && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive rounded-lg"
                        onClick={onSignOut}
                      >
                        <LogOut className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Sign Out</TooltipContent>
                  </Tooltip>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
