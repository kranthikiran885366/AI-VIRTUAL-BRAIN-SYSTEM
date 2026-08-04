"use client"

import { useState, useRef } from "react"
import { 
  UploadCloud, 
  FileText, 
  Image, 
  FileCode, 
  File, 
  Play, 
  Music, 
  Eye, 
  Download, 
  Trash2, 
  X,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  FolderOpen
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface FileItem {
  id: string
  name: string
  size: number
  type: string
  url: string
  uploadedAt: string
  content?: string // for txt/md/code previews
}

export function FilesView({ userId }: { userId: string }) {
  const [files, setFiles] = useState<FileItem[]>([
    {
      id: "f1",
      name: "system_architecture_diagram.png",
      size: 1450000,
      type: "image/png",
      url: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=60",
      uploadedAt: new Date(Date.now() - 3600000 * 2).toISOString(),
    },
    {
      id: "f2",
      name: "cognitive_loop_documentation.md",
      size: 4500,
      type: "text/markdown",
      url: "#",
      uploadedAt: new Date(Date.now() - 3600000 * 5).toISOString(),
      content: `# AI Virtual Brain Cognitive Loop\n\nThe cognitive loop consists of 7 stages:\n1. **Perceive** - Sense input\n2. **Remember** - Memory recall\n3. **Feel** - Emotional analysis\n4. **Reason** - Logical processing\n5. **Plan** - Milestone planning\n6. **Execute** - Response generation\n7. **Reflect** - Self evaluation\n\nConfigure these settings in the Dashboard.`
    },
    {
      id: "f3",
      name: "perception_audio_stream.mp3",
      size: 3200000,
      type: "audio/mp3",
      url: "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
      uploadedAt: new Date(Date.now() - 86400000).toISOString(),
    }
  ])
  
  const [uploadQueue, setUploadQueue] = useState<{
    id: string
    name: string
    size: number
    progress: number
    status: "uploading" | "success" | "error"
    error?: string
  }[]>([])

  const [activePreview, setActivePreview] = useState<FileItem | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
      Array.from(e.dataTransfer.files).forEach(file => uploadFile(file))
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      Array.from(e.target.files).forEach(file => uploadFile(file))
    }
  }

  const uploadFile = (file: File) => {
    // Validate size (max 10MB)
    const MAX_SIZE = 10 * 1024 * 1024
    const newQueueId = Math.random().toString(36).substring(7)
    
    if (file.size > MAX_SIZE) {
      setUploadQueue(prev => [...prev, {
        id: newQueueId,
        name: file.name,
        size: file.size,
        progress: 0,
        status: "error",
        error: "File exceeds maximum size limit of 10MB"
      }])
      return
    }

    setUploadQueue(prev => [...prev, {
      id: newQueueId,
      name: file.name,
      size: file.size,
      progress: 10,
      status: "uploading"
    }])

    // Simulate upload progress
    let currentProgress = 10
    const interval = setInterval(() => {
      currentProgress += Math.floor(Math.random() * 20) + 10
      if (currentProgress >= 100) {
        currentProgress = 100
        clearInterval(interval)
        
        // Add to files list
        const reader = new FileReader()
        reader.onload = (e) => {
          const content = typeof e.target?.result === "string" ? e.target.result : undefined
          const newFile: FileItem = {
            id: Math.random().toString(36).substring(7),
            name: file.name,
            size: file.size,
            type: file.type,
            url: file.type.startsWith("image/") ? URL.createObjectURL(file) : "#",
            uploadedAt: new Date().toISOString(),
            content
          }
          setFiles(prev => [newFile, ...prev])
          // Update queue status
          setUploadQueue(prev => prev.map(q => q.id === newQueueId ? { ...q, progress: 100, status: "success" } : q))
        }
        
        if (file.type.startsWith("text/") || file.name.endsWith(".md") || file.name.endsWith(".json") || file.name.endsWith(".js") || file.name.endsWith(".ts")) {
          reader.readAsText(file)
        } else {
          reader.readAsDataURL(file)
        }
      } else {
        setUploadQueue(prev => prev.map(q => q.id === newQueueId ? { ...q, progress: currentProgress } : q))
      }
    }, 300)
  }

  const handleDeleteFile = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm("Permanently delete this file from vault?")) {
      setFiles(prev => prev.filter(f => f.id !== id))
      if (activePreview?.id === id) {
        setActivePreview(null)
      }
    }
  }

  const getFileIcon = (type: string) => {
    if (type.startsWith("image/")) return <Image className="h-5 w-5 text-emerald-400" />
    if (type.startsWith("text/") || type.includes("pdf") || type.includes("word")) return <FileText className="h-5 w-5 text-blue-400" />
    if (type.includes("javascript") || type.includes("typescript") || type.includes("json") || type.includes("css")) return <FileCode className="h-5 w-5 text-purple-400" />
    if (type.startsWith("audio/")) return <Music className="h-5 w-5 text-orange-400" />
    if (type.startsWith("video/")) return <Play className="h-5 w-5 text-pink-400" />
    return <File className="h-5 w-5 text-muted-foreground" />
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
  }

  return (
    <div className="flex h-full flex-col bg-background/50 backdrop-blur-md overflow-hidden">
      {/* View Header */}
      <div className="flex items-center justify-between border-b border-border/40 px-8 py-5 glass-panel shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <FolderOpen className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">File Vault</h1>
            <p className="text-xs text-muted-foreground">Upload and inspect knowledge documents, media streams, and datasets</p>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Side: Upload Zone & Files List */}
        <div className="flex-1 flex flex-col p-8 overflow-y-auto space-y-6">
          
          {/* Drag & Drop Upload Zone */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 flex flex-col items-center justify-center space-y-3 ${
              dragActive 
                ? "border-primary bg-primary/5 scale-[0.99]" 
                : "border-border/60 hover:border-primary/50 hover:bg-secondary/20"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileInputChange}
              className="hidden"
            />
            <div className="h-12 w-12 rounded-full bg-secondary flex items-center justify-center text-muted-foreground">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium">Drag & drop files here, or <span className="text-primary font-semibold">browse files</span></p>
              <p className="text-xs text-muted-foreground mt-1">Supports PDF, Markdown, Images, Audio, Code (Max 10MB)</p>
            </div>
          </div>

          {/* Upload Queue Section */}
          {uploadQueue.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Upload Progress</h3>
              <div className="space-y-2">
                {uploadQueue.map((item) => (
                  <div key={item.id} className="p-3.5 rounded-xl border border-border bg-secondary/10 flex items-center gap-3">
                    {item.status === "error" ? (
                      <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
                    ) : item.progress === 100 ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                    ) : (
                      <RefreshCw className="h-4.5 w-4.5 text-primary animate-spin shrink-0" />
                    )}
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between text-xs font-medium mb-1">
                        <span className="truncate">{item.name}</span>
                        <span>{item.status === "error" ? "Failed" : `${item.progress}%`}</span>
                      </div>
                      
                      {item.status === "error" ? (
                        <p className="text-xs text-destructive">{item.error}</p>
                      ) : (
                        <div className="w-full h-1 bg-secondary rounded-full overflow-hidden">
                          <div className="h-full bg-primary transition-all duration-300" style={{ width: `${item.progress}%` }} />
                        </div>
                      )}
                    </div>

                    <button 
                      onClick={() => setUploadQueue(prev => prev.filter(q => q.id !== item.id))}
                      className="p-1 rounded hover:bg-secondary/40 text-muted-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Files List */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Vault Storage ({files.length} items)</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {files.map((file) => (
                <div
                  key={file.id}
                  onClick={() => setActivePreview(file)}
                  className={`p-4 rounded-xl border border-border/50 bg-secondary/20 hover:bg-secondary/40 cursor-pointer transition-all flex items-start gap-4 card-hover ${
                    activePreview?.id === file.id ? "border-primary/50 bg-primary/5" : ""
                  }`}
                >
                  <div className="h-10 w-10 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                    {getFileIcon(file.type)}
                  </div>
                  
                  <div className="flex-1 min-w-0 space-y-1">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{formatBytes(file.size)}</span>
                      <span>•</span>
                      <span>{new Date(file.uploadedAt).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      className="h-8 w-8 hover:text-primary"
                      onClick={(e) => { e.stopPropagation(); alert("Downloading file...") }}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      className="h-8 w-8 hover:text-destructive text-destructive/70"
                      onClick={(e) => handleDeleteFile(file.id, e)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}

              {files.length === 0 && (
                <div className="col-span-full text-center py-16 text-muted-foreground">
                  <UploadCloud className="h-12 w-12 mx-auto mb-3 opacity-30 animate-pulse" />
                  <p className="font-medium text-sm">Vault is empty</p>
                  <p className="text-xs mt-1">Upload documents to attach to neural sessions</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Preview Pane */}
        {activePreview && (
          <div className="w-96 border-l border-border/40 bg-secondary/10 flex flex-col overflow-hidden glass-panel">
            <div className="p-4 border-b border-border/40 flex items-center justify-between shrink-0">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">File Preview</span>
              <button 
                onClick={() => setActivePreview(null)}
                className="p-1 rounded hover:bg-secondary/40 text-muted-foreground"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 flex flex-col justify-between">
              <div className="space-y-6">
                {/* Media Previewers */}
                {activePreview.type.startsWith("image/") && (
                  <div className="rounded-xl overflow-hidden border border-border/50 bg-black/10 aspect-video relative">
                    <img 
                      src={activePreview.url} 
                      alt={activePreview.name} 
                      className="w-full h-full object-cover" 
                    />
                  </div>
                )}

                {activePreview.type.startsWith("audio/") && (
                  <div className="p-4 rounded-xl border border-border/50 bg-secondary/30 space-y-3">
                    <div className="flex items-center gap-3">
                      <Music className="h-6 w-6 text-primary shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{activePreview.name}</p>
                        <p className="text-xs text-muted-foreground">Audio Stream</p>
                      </div>
                    </div>
                    <audio src={activePreview.url} controls className="w-full h-8" />
                  </div>
                )}

                {activePreview.type === "text/markdown" && activePreview.content && (
                  <div className="prose prose-sm prose-invert p-4 rounded-xl border border-border/50 bg-secondary/20 max-w-none text-xs font-mono max-h-96 overflow-y-auto whitespace-pre-wrap">
                    {activePreview.content}
                  </div>
                )}

                {!activePreview.type.startsWith("image/") && !activePreview.type.startsWith("audio/") && activePreview.type !== "text/markdown" && (
                  <div className="py-12 border border-border/50 rounded-xl bg-secondary/10 flex flex-col items-center justify-center text-center p-4">
                    <FileText className="h-10 w-10 text-muted-foreground mb-3" />
                    <p className="text-sm font-medium truncate max-w-[200px]">{activePreview.name}</p>
                    <p className="text-xs text-muted-foreground mt-1">Binary content viewer requires client app mounting</p>
                  </div>
                )}

                {/* File Metadata */}
                <div className="space-y-3 border-t border-border/40 pt-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Attributes</h4>
                  <div className="grid grid-cols-2 gap-y-2 text-xs">
                    <span className="text-muted-foreground">Mime Type:</span>
                    <span className="font-mono text-right truncate">{activePreview.type}</span>
                    <span className="text-muted-foreground">Byte Size:</span>
                    <span className="font-mono text-right">{formatBytes(activePreview.size)}</span>
                    <span className="text-muted-foreground">Created:</span>
                    <span className="text-right">{new Date(activePreview.uploadedAt).toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-border/40 mt-6 flex gap-2">
                <Button className="flex-1 bg-primary hover:bg-primary/90 text-white gap-2">
                  <Download className="h-4 w-4" />
                  Download
                </Button>
                <Button 
                  variant="outline" 
                  className="border-border text-destructive hover:bg-destructive/10"
                  onClick={(e) => handleDeleteFile(activePreview.id, e as any)}
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
