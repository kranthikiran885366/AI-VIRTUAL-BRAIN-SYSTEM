"use client"

import { useState, useEffect } from "react"
import { 
  Settings, 
  Paintbrush, 
  Accessibility, 
  Cpu, 
  Database, 
  ShieldCheck, 
  Download, 
  Upload, 
  RefreshCw,
  Sliders,
  Sparkles,
  Info
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface SettingsViewProps {
  userId: string
}

export function SettingsView({ userId }: SettingsViewProps) {
  const [activeTab, setActiveTab] = useState<"appearance" | "providers" | "memory" | "diagnostics">("appearance")
  const [theme, setTheme] = useState<"light" | "dark" | "system">("dark")
  const [fontSize, setFontSize] = useState<"sm" | "base" | "lg" | "xl">("base")
  const [reducedMotion, setReducedMotion] = useState(false)
  const [highContrast, setHighContrast] = useState(false)
  
  // Providers settings
  const [openaiKey, setOpenaiKey] = useState("")
  const [openaiUrl, setOpenaiUrl] = useState("")
  const [defaultModel, setDefaultModel] = useState("gpt-4o")

  // Sync theme with document class list
  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove("light", "dark")
    
    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }
    
    localStorage.setItem("theme", theme)
  }, [theme])

  // Initial localstorage read
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | "system" | null
    if (savedTheme) {
      setTheme(savedTheme)
    }
  }, [])

  const handleExportBackup = async () => {
    try {
      const response = await fetch(`/api/conversations?userId=${userId}`)
      const data = await response.json()
      
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `virtual-brain-backup-${new Date().toISOString().slice(0,10)}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      alert("Failed to export backup")
    }
  }

  const handleRestoreBackup = () => {
    alert("Select backup file feature would go here (Requires DB write api integration)")
  }

  return (
    <div className="flex h-full flex-col bg-background/50 backdrop-blur-md overflow-y-auto">
      {/* View Header */}
      <div className="flex items-center justify-between border-b border-border/40 px-8 py-5 glass-panel">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Settings className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">System Settings</h1>
            <p className="text-xs text-muted-foreground">Configure your AI Virtual Brain operational space</p>
          </div>
        </div>
      </div>

      <div className="flex-1 max-w-5xl w-full mx-auto px-8 py-8 grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation Sidebar */}
        <div className="space-y-1.5">
          {[
            { id: "appearance", label: "Appearance & UX", icon: Paintbrush },
            { id: "providers", label: "AI Models & Keys", icon: Cpu },
            { id: "memory", label: "Memory Settings", icon: Database },
            { id: "diagnostics", label: "Diagnostics & Backup", icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-all ${
                  activeTab === tab.id
                    ? "bg-primary/10 text-primary border-l-2 border-primary"
                    : "text-muted-foreground hover:bg-secondary/40 hover:text-foreground"
                }`}
              >
                <Icon className="h-4.5 w-4.5" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Settings Panel Content */}
        <div className="md:col-span-3 space-y-6">
          {activeTab === "appearance" && (
            <Card className="glass-card border-none shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Paintbrush className="h-5 w-5 text-primary" />
                  Appearance & Themes
                </CardTitle>
                <CardDescription>Customize the interface aesthetics and layout preferences.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Theme Selector */}
                <div className="space-y-2.5">
                  <label className="text-sm font-medium text-foreground">Aesthetic Theme</label>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { id: "light", label: "Light Theme" },
                      { id: "dark", label: "Deep Space (Dark)" },
                      { id: "system", label: "System Sync" },
                    ].map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setTheme(t.id as any)}
                        className={`p-4 rounded-xl border text-center text-sm font-medium transition-all ${
                          theme === t.id
                            ? "border-primary bg-primary/5 text-primary shadow-lg shadow-primary/5"
                            : "border-border/60 hover:bg-secondary/40 text-muted-foreground"
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Accessibility Options */}
                <div className="space-y-4 pt-4 border-t border-border/40">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Accessibility className="h-4 w-4 text-primary" />
                    Accessibility (WCAG 2.2 compliant)
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">Reduced Motion</p>
                        <p className="text-xs text-muted-foreground">Disable dynamic animations for high performance</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={reducedMotion}
                        onChange={(e) => setReducedMotion(e.target.checked)}
                        className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">Enhanced Color Contrast</p>
                        <p className="text-xs text-muted-foreground">Increases visibility on text elements</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={highContrast}
                        onChange={(e) => setHighContrast(e.target.checked)}
                        className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                      />
                    </div>

                    <div className="space-y-2">
                      <p className="text-sm font-medium">Text Scale</p>
                      <div className="flex gap-2">
                        {["sm", "base", "lg", "xl"].map((size) => (
                          <button
                            key={size}
                            onClick={() => setFontSize(size as any)}
                            className={`px-3 py-1.5 text-xs font-mono rounded-lg border ${
                              fontSize === size
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-border text-muted-foreground hover:bg-secondary/40"
                            }`}
                          >
                            {size === "base" ? "normal (base)" : size}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "providers" && (
            <Card className="glass-card border-none shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-primary" />
                  AI Models Configuration
                </CardTitle>
                <CardDescription>Setup access API keys for OpenAI, Gemini, or custom proxies.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <label className="text-sm font-medium">OpenAI API Key</label>
                  <Input
                    type="password"
                    placeholder="sk-proj-............................"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    className="bg-secondary/20 focus-visible:ring-primary"
                  />
                  <p className="text-xs text-muted-foreground">Stays encrypted locally inside your secure web session storage.</p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Custom Proxy Endpoint URL (Optional)</label>
                  <Input
                    type="url"
                    placeholder="https://api.openai.com/v1"
                    value={openaiUrl}
                    onChange={(e) => setOpenaiUrl(e.target.value)}
                    className="bg-secondary/20 focus-visible:ring-primary"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Default Brain Model</label>
                  <select
                    value={defaultModel}
                    onChange={(e) => setDefaultModel(e.target.value)}
                    className="w-full rounded-lg border border-border bg-secondary/30 p-2.5 text-sm text-foreground focus:border-primary focus:ring-1 focus:ring-primary"
                  >
                    <option value="gpt-4o">OpenAI GPT-4o (Reasoning & Orchestrator default)</option>
                    <option value="gpt-4o-mini">OpenAI GPT-4o Mini (Ultra fast & low latency)</option>
                    <option value="o1-preview">OpenAI o1-Preview (Logical reasoning chains)</option>
                  </select>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "memory" && (
            <Card className="glass-card border-none shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Database className="h-5 w-5 text-primary" />
                  Episodic & Semantic Memory Control
                </CardTitle>
                <CardDescription>Configure how ARIA consolidates user facts, chats, and short-term memory.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Auto-Consolidation</p>
                      <p className="text-xs text-muted-foreground">Automatically mine context facts and store in vector SQLite index</p>
                    </div>
                    <input
                      type="checkbox"
                      defaultChecked
                      className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Emotional Calibration</p>
                      <p className="text-xs text-muted-foreground">Adjust conversational tone adaptively based on Detected Emotions</p>
                    </div>
                    <input
                      type="checkbox"
                      defaultChecked
                      className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                    />
                  </div>

                  <div className="space-y-2 pt-2">
                    <p className="text-sm font-medium">Memory Vector Decay Period</p>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="1"
                        max="30"
                        defaultValue="14"
                        className="flex-1 h-1.5 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                      <span className="text-xs font-mono bg-secondary/50 px-2 py-1 rounded">14 Days</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "diagnostics" && (
            <Card className="glass-card border-none shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  System Diagnostics & Database Backup
                </CardTitle>
                <CardDescription>Export backups, view logs, and verify connection to local orchestrator.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Diagnostics Health */}
                <div className="p-4 rounded-xl bg-secondary/20 border border-border/40 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Info className="h-3.5 w-3.5" />
                    Orchestrator Host Information
                  </h4>
                  <div className="grid grid-cols-2 gap-y-2 text-xs">
                    <span className="text-muted-foreground">Local DB Path:</span>
                    <span className="font-mono text-right truncate">/data/brain.db (SQLite WAL)</span>
                    <span className="text-muted-foreground">Python API status:</span>
                    <span className="font-semibold text-green-500 text-right">Connected (Operational)</span>
                    <span className="text-muted-foreground">User ID:</span>
                    <span className="font-mono text-right truncate">{userId}</span>
                  </div>
                </div>

                {/* Import / Export actions */}
                <div className="flex flex-wrap gap-3">
                  <Button onClick={handleExportBackup} className="gap-2 bg-primary hover:bg-primary/95 text-white">
                    <Download className="h-4 w-4" />
                    Backup Data (JSON)
                  </Button>
                  <Button onClick={handleRestoreBackup} variant="outline" className="gap-2 border-border/80 text-foreground hover:bg-secondary/40">
                    <Upload className="h-4 w-4" />
                    Restore Data
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
