"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import {
  MessageSquarePlus,
  Search,
  MoreHorizontal,
  Trash2,
  Archive,
  Edit2,
  Brain,
  Settings,
  LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
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
}

export function ChatSidebar({
  currentConversationId,
  userId,
  onNewChat,
  onSelectConversation,
  user,
  onSignOut,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const router = useRouter()

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
      console.error("[v0] Failed to archive conversation:", error)
    }
  }

  return (
    <TooltipProvider>
      <div className="flex h-full w-64 flex-col bg-secondary/30 border-r border-border">
        {/* Header */}
        <div className="flex items-center gap-2 p-4 border-b border-border">
          <div className="flex items-center gap-2 flex-1">
            <div className="relative">
              <Brain className="h-8 w-8 text-primary brain-active" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-sm">Virtual Brain</span>
              <span className="text-xs text-muted-foreground">AI Assistant</span>
            </div>
          </div>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <Button
            onClick={onNewChat}
            className="w-full justify-start gap-2"
            variant="outline"
          >
            <MessageSquarePlus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 bg-background/50"
            />
          </div>
        </div>

        {/* Conversations List */}
        <ScrollArea className="flex-1 px-2">
          <div className="space-y-1 py-2">
            {filteredConversations?.map((conversation) => (
              <div
                key={conversation.id}
                className={cn(
                  "group relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
                  currentConversationId === conversation.id
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-accent text-foreground"
                )}
                onClick={() => onSelectConversation(conversation.id)}
                onMouseEnter={() => setHoveredId(conversation.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <MessageSquarePlus className="h-4 w-4 shrink-0 opacity-60" />
                <div className="flex-1 overflow-hidden">
                  <p className="truncate font-medium">
                    {truncate(conversation.title, 25)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(conversation.updated_at)}
                  </p>
                </div>

                {/* Action buttons */}
                {hoveredId === conversation.id && (
                  <div className="absolute right-2 flex items-center gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={(e) => handleArchive(conversation.id, e)}
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Archive</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={(e) => handleDelete(conversation.id, e)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete</TooltipContent>
                    </Tooltip>
                  </div>
                )}
              </div>
            ))}

            {filteredConversations?.length === 0 && (
              <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                {searchQuery ? "No conversations found" : "No conversations yet"}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* User Section */}
        {user && (
          <div className="border-t border-border p-3">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-medium text-sm">
                {user.full_name?.charAt(0) || user.email?.charAt(0) || "U"}
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium">
                  {user.full_name || user.email}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="icon" variant="ghost" className="h-8 w-8">
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
                        className="h-8 w-8"
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
