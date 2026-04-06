"use client"

import { memo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import { Copy, Check, User, Brain, Sparkles, Database, Heart, Lightbulb, Code, Search } from "lucide-react"
import { useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { UIMessage } from "ai"

interface ChatMessageProps {
  message: UIMessage
  agentUsed?: string
}

const agentIcons: Record<string, React.ReactNode> = {
  orchestrator: <Brain className="h-4 w-4" />,
  memory: <Database className="h-4 w-4" />,
  emotion: <Heart className="h-4 w-4" />,
  reasoning: <Lightbulb className="h-4 w-4" />,
  creativity: <Sparkles className="h-4 w-4" />,
  code: <Code className="h-4 w-4" />,
  research: <Search className="h-4 w-4" />,
}

const agentColors: Record<string, string> = {
  orchestrator: "bg-violet-500/20 text-violet-400",
  memory: "bg-blue-500/20 text-blue-400",
  emotion: "bg-pink-500/20 text-pink-400",
  reasoning: "bg-amber-500/20 text-amber-400",
  creativity: "bg-emerald-500/20 text-emerald-400",
  code: "bg-slate-500/20 text-slate-400",
  research: "bg-violet-500/20 text-violet-400",
}

function CodeBlock({ language, value }: { language: string; value: string }) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group my-4 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between bg-secondary/80 px-4 py-2 text-xs">
        <span className="text-muted-foreground font-mono">{language || "code"}</span>
        <Button
          size="icon"
          variant="ghost"
          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={copyToClipboard}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: "1rem",
          fontSize: "0.875rem",
        }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  )
}

export const ChatMessage = memo(function ChatMessage({
  message,
  agentUsed = "orchestrator",
}: ChatMessageProps) {
  const isUser = message.role === "user"

  // Extract text content from parts
  const textContent = message.parts
    ?.filter((p) => p.type === "text")
    .map((p) => p.text)
    .join("") || ""

  // Check for tool invocations
  const toolParts = message.parts?.filter((p) => p.type === "tool-invocation") || []

  return (
    <div
      className={cn(
        "flex gap-4 px-4 py-6 message-enter",
        isUser ? "bg-transparent" : "bg-secondary/30"
      )}
    >
      <Avatar className={cn("h-8 w-8 shrink-0", !isUser && agentColors[agentUsed])}>
        <AvatarFallback className={cn(!isUser && agentColors[agentUsed])}>
          {isUser ? <User className="h-4 w-4" /> : agentIcons[agentUsed] || <Brain className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">
            {isUser ? "You" : agentUsed.charAt(0).toUpperCase() + agentUsed.slice(1)}
          </span>
          {!isUser && (
            <span className={cn("text-xs px-2 py-0.5 rounded-full", agentColors[agentUsed])}>
              {agentUsed} agent
            </span>
          )}
        </div>

        {/* Tool invocations */}
        {toolParts.length > 0 && (
          <div className="space-y-2 my-2">
            {toolParts.map((tool, index) => (
              <div
                key={index}
                className="bg-secondary/50 rounded-lg p-3 text-sm border border-border"
              >
                <div className="flex items-center gap-2 text-muted-foreground mb-1">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="font-mono text-xs">
                    {"toolName" in tool ? String(tool.toolName) : "tool"}
                  </span>
                  {"state" in tool && (
                    <span className={cn(
                      "text-xs px-1.5 py-0.5 rounded",
                      tool.state === "output-available" ? "bg-green-500/20 text-green-400" :
                      tool.state === "output-error" ? "bg-red-500/20 text-red-400" :
                      "bg-yellow-500/20 text-yellow-400"
                    )}>
                      {String(tool.state)}
                    </span>
                  )}
                </div>
                {"output" in tool && tool.output && (
                  <pre className="text-xs font-mono bg-background/50 p-2 rounded mt-2 overflow-x-auto">
                    {typeof tool.output === "string" 
                      ? tool.output 
                      : JSON.stringify(tool.output, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Message content */}
        <div className="prose prose-sm prose-invert max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "")
                const codeString = String(children).replace(/\n$/, "")
                
                if (match) {
                  return <CodeBlock language={match[1]} value={codeString} />
                }
                
                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                )
              },
              p({ children }) {
                return <p className="mb-4 last:mb-0">{children}</p>
              },
              ul({ children }) {
                return <ul className="list-disc pl-6 mb-4">{children}</ul>
              },
              ol({ children }) {
                return <ol className="list-decimal pl-6 mb-4">{children}</ol>
              },
              li({ children }) {
                return <li className="mb-1">{children}</li>
              },
              a({ href, children }) {
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    {children}
                  </a>
                )
              },
              blockquote({ children }) {
                return (
                  <blockquote className="border-l-2 border-primary/50 pl-4 italic text-muted-foreground">
                    {children}
                  </blockquote>
                )
              },
              table({ children }) {
                return (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full border-collapse border border-border">
                      {children}
                    </table>
                  </div>
                )
              },
              th({ children }) {
                return (
                  <th className="border border-border bg-secondary px-4 py-2 text-left font-medium">
                    {children}
                  </th>
                )
              },
              td({ children }) {
                return (
                  <td className="border border-border px-4 py-2">{children}</td>
                )
              },
            }}
          >
            {textContent}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
})
