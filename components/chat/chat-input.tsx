"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Paperclip, Mic, StopCircle, Sparkles, X, File, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  isLoading = false,
  disabled = false,
  placeholder = "Message ARIA Orchestrator...",
}: ChatInputProps) {
  const [input, setInput] = useState("")
  const [dragActive, setDragActive] = useState(false)
  const [uploadingFile, setUploadingFile] = useState<{ name: string; progress: number; size: number } | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [recordTimer, setRecordTimer] = useState(0)
  
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<any>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [input])

  // Voice recording timer simulation
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setRecordTimer(prev => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      setRecordTimer(0)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [isRecording])

  const handleSubmit = () => {
    if ((!input.trim() && !uploadingFile) || isLoading || disabled) return
    
    let message = input.trim()
    if (uploadingFile) {
      message = `[Attached File: ${uploadingFile.name} (${(uploadingFile.size / 1024).toFixed(1)} KB)]\n\n${message}`
    }
    
    onSend(message)
    setInput("")
    setUploadingFile(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0])
    }
  }

  const handleFileUpload = (file: File) => {
    setUploadingFile({ name: file.name, progress: 15, size: file.size })
    
    // Simulate upload progress
    let p = 15
    const interval = setInterval(() => {
      p += Math.floor(Math.random() * 25) + 10
      if (p >= 100) {
        p = 100
        clearInterval(interval)
        setUploadingFile({ name: file.name, progress: 100, size: file.size })
      } else {
        setUploadingFile({ name: file.name, progress: p, size: file.size })
      }
    }, 200)
  }

  const toggleRecording = () => {
    if (isRecording) {
      // Finish recording, insert mock transcript text
      setIsRecording(false)
      setInput("Draft a cognitive loop operations report based on active system telemetry")
    } else {
      setIsRecording(true)
    }
  }

  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s < 10 ? "0" : ""}${s}`
  }

  return (
    <TooltipProvider>
      <div 
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={cn(
          "border-t border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shrink-0",
          dragActive && "border-primary bg-primary/5 ring-1 ring-primary/30 animate-pulse"
        )}
      >
        <div className="mx-auto max-w-3xl p-4">
          
          {/* File Upload Progress status bar */}
          {uploadingFile && (
            <div className="mb-3 p-2.5 rounded-xl border border-border bg-secondary/20 flex items-center gap-3 text-xs">
              <File className="h-4.5 w-4.5 text-primary shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex justify-between font-semibold text-foreground mb-0.5">
                  <span className="truncate">{uploadingFile.name}</span>
                  <span>{uploadingFile.progress === 100 ? "Attached" : `${uploadingFile.progress}%`}</span>
                </div>
                <Progress value={uploadingFile.progress} className="h-1 bg-secondary [&>div]:bg-primary" />
              </div>
              <button 
                onClick={() => setUploadingFile(null)}
                className="p-1 rounded hover:bg-secondary/40 text-muted-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* Voice recording indicators bar */}
          {isRecording && (
            <div className="mb-3 px-4 py-2.5 rounded-xl border border-rose-500/20 bg-rose-500/5 flex items-center justify-between text-xs animate-pulse">
              <div className="flex items-center gap-2 text-rose-500 font-semibold font-mono">
                <StopCircle className="h-4 w-4 text-rose-500 animate-spin" />
                <span>REC: {formatTimer(recordTimer)}</span>
              </div>
              <div className="flex-1 max-w-[200px] h-3.5 flex items-center justify-between gap-0.5 px-3">
                {[...Array(12)].map((_, i) => (
                  <div 
                    key={i} 
                    className="w-1 bg-rose-500/80 rounded-full" 
                    style={{ height: `${Math.floor(Math.random() * 80) + 20}%` }} 
                  />
                ))}
              </div>
              <button 
                onClick={toggleRecording}
                className="text-rose-500 font-bold hover:underline"
              >
                Stop & Transcribe
              </button>
            </div>
          )}

          {/* Input text controls box */}
          <div className="relative flex items-end gap-2 rounded-2xl border border-border/60 bg-secondary/15 p-2 focus-within:border-primary/50 transition-colors">
            {/* Attachment input clicker */}
            <input 
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              className="hidden"
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Add attachment"
                  className="h-9 w-9 shrink-0 hover:bg-secondary/50 rounded-xl"
                  disabled={disabled}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Paperclip className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Attach document (PDF/Markdown)</TooltipContent>
            </Tooltip>

            {/* Input textarea */}
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={dragActive ? "Drop documents here..." : placeholder}
              disabled={disabled || isLoading || isRecording}
              className="flex-1 min-h-[44px] max-h-[200px] border-0 bg-transparent focus-visible:ring-0 resize-none py-3 px-1 text-xs leading-relaxed text-foreground placeholder:text-muted-foreground/60"
              rows={1}
            />

            {/* Send & Audio recorder buttons */}
            <div className="flex items-center gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label="Record speech input"
                    className={cn(
                      "h-9 w-9 shrink-0 hover:bg-secondary/50 rounded-xl",
                      isRecording && "bg-rose-500/10 text-rose-500 hover:bg-rose-500/20"
                    )}
                    disabled={disabled}
                    onClick={toggleRecording}
                  >
                    <Mic className="h-5 w-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{isRecording ? "Stop speech" : "Record voice input"}</TooltipContent>
              </Tooltip>

              {isLoading ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Stop generation"
                      className="h-9 w-9 shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10 rounded-xl"
                    >
                      <StopCircle className="h-5 w-5 animate-pulse" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Stop generation</TooltipContent>
                </Tooltip>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      aria-label="Send message"
                      onClick={handleSubmit}
                      disabled={(!input.trim() && !uploadingFile) || disabled}
                      className={cn(
                        "h-9 w-9 shrink-0 transition-all rounded-xl",
                        input.trim() || uploadingFile
                          ? "bg-primary text-primary-foreground hover:bg-primary/95 shadow-md shadow-primary/5"
                          : "bg-secondary text-muted-foreground"
                      )}
                    >
                      <Send className="h-4.5 w-4.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Send session query</TooltipContent>
                </Tooltip>
              )}
            </div>
          </div>

          {/* Hint prompts */}
          <div className="mt-2.5 flex items-center justify-center gap-4 text-[10px] text-muted-foreground font-medium">
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-primary animate-pulse" />
              <span>ARIA routing active across 28 specialized nodes</span>
            </div>
            <span>•</span>
            <span>Enter to send, Shift+Enter for new line</span>
          </div>

        </div>
      </div>
    </TooltipProvider>
  )
}
