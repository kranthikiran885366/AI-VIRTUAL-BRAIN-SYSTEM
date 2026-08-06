"use client"

import { memo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import { 
  Copy, 
  Check, 
  User, 
  Brain, 
  Sparkles, 
  Database, 
  Heart, 
  Lightbulb, 
  Code, 
  Search,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Share2,
  ChevronDown,
  ChevronUp,
  Terminal,
  Cpu
} from "lucide-react"
import { useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { UIMessage } from "ai"

interface ChatMessageProps {
  message: UIMessage
  agentUsed?: string
}

const agentIcons: Record<string, React.ReactNode> = {
  orchestrator_agent: <Brain className="h-4 w-4" />,
  memory_agent: <Database className="h-4 w-4" />,
  emotion_agent: <Heart className="h-4 w-4" />,
  reasoning_agent: <Lightbulb className="h-4 w-4" />,
  creativity_agent: <Sparkles className="h-4 w-4" />,
  language_agent: <Code className="h-4 w-4" />,
  code: <Code className="h-4 w-4" />,
  research: <Search className="h-4 w-4" />,
}

const agentColors: Record<string, string> = {
  orchestrator_agent: "bg-violet-500/20 text-violet-400 border border-violet-500/30",
  memory_agent: "bg-blue-500/20 text-blue-400 border border-blue-500/30",
  emotion_agent: "bg-pink-500/20 text-pink-400 border border-pink-500/30",
  reasoning_agent: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  creativity_agent: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  language_agent: "bg-slate-500/20 text-slate-400 border border-slate-500/30",
  code: "bg-slate-500/20 text-slate-400 border border-slate-500/30",
  research: "bg-violet-500/20 text-violet-400 border border-violet-500/30",
}

function CodeBlock({ language, value }: { language: string; value: string }) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group my-4 rounded-xl overflow-hidden border border-border/40 glass-card">
      <div className="flex items-center justify-between bg-secondary/60 px-4 py-2.5 text-[10px] font-mono text-muted-foreground">
        <span className="flex items-center gap-1.5 font-semibold">
          <Terminal className="h-3.5 w-3.5 text-primary" />
          {language ? language.toUpperCase() : "CODE"}
        </span>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Copy code block"
          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-secondary/80 rounded-md"
          onClick={copyToClipboard}
        >
          {copied ? (
            <Check className="h-3 w-3 text-green-500" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </Button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: "1.25rem",
          fontSize: "0.8rem",
          background: "transparent"
        }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  )
}

export const ChatMessage = memo(function ChatMessage({
  message,
  agentUsed = "orchestrator_agent",
}: ChatMessageProps) {
  const isUser = message.role === "user"
  const [copied, setCopied] = useState(false)
  const [liked, setLiked] = useState<boolean | null>(null)
  const [toolsExpanded, setToolsExpanded] = useState<Record<number, boolean>>({})

  // Extract text content from parts
  const textContent = [
    message.parts
      ?.filter((p: any) => p.type === "text")
      .map((p: any) => p.text)
      .join(""),
    typeof (message as any).content === "string" ? (message as any).content : "",
  ].filter(Boolean).join("") || ""

  // Check for tool invocations
  const toolParts = message.parts?.filter((p) => p.type === "tool-invocation") || []

  const copyMessage = async () => {
    await navigator.clipboard.writeText(textContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const toggleTool = (idx: number) => {
    setToolsExpanded(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div
      className={cn(
        "flex gap-4 px-6 py-6 message-enter border-b border-border/15",
        isUser ? "bg-transparent" : "bg-secondary/15 backdrop-blur-sm"
      )}
    >
      <Avatar className={cn("h-8.5 w-8.5 shrink-0 rounded-xl", isUser ? "bg-primary/20 text-primary" : agentColors[agentUsed])}>
        <AvatarFallback className="rounded-xl">
          {isUser ? <User className="h-4 w-4" /> : agentIcons[agentUsed] || <Brain className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 space-y-3 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-xs text-foreground">
              {isUser ? "You" : agentUsed.replace("_agent","").toUpperCase()}
            </span>
            {!isUser && (
              <span className={cn("text-[9px] px-2 py-0.5 rounded-full font-bold font-mono tracking-wider", agentColors[agentUsed])}>
                {agentUsed.replace("_agent","").toUpperCase()}
              </span>
            )}
          </div>
          
          {/* Bubble utilities */}
          {!isUser && (
            <div className="flex items-center gap-1">
              <Button 
                size="icon" 
                variant="ghost" 
                aria-label="Copy response"
                className="h-7 w-7 text-muted-foreground hover:text-foreground rounded-md"
                onClick={copyMessage}
              >
                {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
              <Button 
                size="icon" 
                variant="ghost" 
                aria-label="Regenerate"
                className="h-7 w-7 text-muted-foreground hover:text-foreground rounded-md"
                onClick={() => alert("Simulating response regeneration...")}
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              <Button 
                size="icon" 
                variant="ghost" 
                aria-label="Helpful"
                className={cn("h-7 w-7 rounded-md", liked === true ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground")}
                onClick={() => setLiked(liked === true ? null : true)}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </Button>
              <Button 
                size="icon" 
                variant="ghost" 
                aria-label="Not helpful"
                className={cn("h-7 w-7 rounded-md", liked === false ? "text-destructive bg-destructive/10" : "text-muted-foreground hover:text-foreground")}
                onClick={() => setLiked(liked === false ? null : false)}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>

        {/* Tool Invocations Drawer */}
        {toolParts.length > 0 && (
          <div className="space-y-2 my-3">
            {toolParts.map((tool, index) => {
              const isExpanded = !!toolsExpanded[index]
              return (
                <div
                  key={index}
                  className="bg-secondary/15 rounded-xl border border-border/40 overflow-hidden text-xs"
                >
                  <button
                    onClick={() => toggleTool(index)}
                    className="w-full flex items-center justify-between p-3 hover:bg-secondary/30 transition-colors"
                  >
                    <div className="flex items-center gap-2 font-mono text-[10px]">
                      <Cpu className="h-3.5 w-3.5 text-primary shrink-0 animate-pulse" />
                      <span className="font-bold">TOOL CALL:</span>
                      <span className="text-muted-foreground">{"toolName" in tool ? String(tool.toolName) : "tool"}</span>
                      {"state" in tool && (
                        <Badge className={cn(
                          "text-[9px] font-mono",
                          tool.state === "output-available" ? "bg-green-500/20 text-green-400 hover:bg-green-500/20" :
                          tool.state === "output-error" ? "bg-red-500/20 text-red-400 hover:bg-red-500/20" :
                          "bg-amber-500/20 text-amber-400 hover:bg-amber-500/20"
                        )}>
                          {String(tool.state)}
                        </Badge>
                      )}
                    </div>
                    {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                  
                  {isExpanded && "output" in tool && (tool as any).output && (
                    <pre className="p-3.5 font-mono text-[10px] bg-black/30 border-t border-border/30 overflow-x-auto text-muted-foreground whitespace-pre-wrap">
                      {typeof (tool as any).output === "string" 
                        ? (tool as any).output 
                        : JSON.stringify((tool as any).output, null, 2)}
                    </pre>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Message content Markdown */}
        <div className="prose prose-sm prose-invert max-w-none text-foreground/90 leading-relaxed text-xs">
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
                  <code className={cn("bg-secondary/40 px-1.5 py-0.5 rounded font-mono text-[11px] text-primary-foreground", className)} {...props}>
                    {children}
                  </code>
                )
              },
              p({ children }) {
                return <p className="mb-3.5 last:mb-0">{children}</p>
              },
              ul({ children }) {
                return <ul className="list-disc pl-5 mb-3.5 space-y-1">{children}</ul>
              },
              ol({ children }) {
                return <ol className="list-decimal pl-5 mb-3.5 space-y-1">{children}</ol>
              },
              li({ children }) {
                return <li className="mb-0.5">{children}</li>
              },
              a({ href, children }) {
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline font-semibold"
                  >
                    {children}
                  </a>
                )
              },
              blockquote({ children }) {
                return (
                  <blockquote className="border-l-3 border-primary/50 pl-4 py-1 italic bg-secondary/10 rounded-r-lg text-muted-foreground">
                    {children}
                  </blockquote>
                )
              },
              table({ children }) {
                return (
                  <div className="overflow-x-auto my-4 rounded-xl border border-border/40">
                    <table className="min-w-full border-collapse text-left">
                      {children}
                    </table>
                  </div>
                )
              },
              th({ children }) {
                return (
                  <th className="bg-secondary/60 px-4 py-2.5 font-bold font-mono text-[10px] tracking-wider uppercase text-muted-foreground border-b border-border/30">
                    {children}
                  </th>
                )
              },
              td({ children }) {
                return (
                  <td className="px-4 py-2.5 border-b border-border/20 text-foreground/80">
                    {children}
                  </td>
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
