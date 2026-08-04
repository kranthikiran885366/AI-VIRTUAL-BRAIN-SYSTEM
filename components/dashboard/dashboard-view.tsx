"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import useSWR from "swr"
import { 
  Brain, 
  Cpu, 
  Database, 
  Layers, 
  Workflow, 
  Lightbulb, 
  Target, 
  Sparkles, 
  Clock, 
  Flame, 
  Activity, 
  ChevronRight, 
  Settings2,
  TrendingUp,
  AlertTriangle,
  Play,
  RotateCcw,
  Search,
  Sliders,
  Filter,
  CheckCircle2,
  AlertCircle,
  FileText
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

// Mapping for category color pills
const CATEGORY_COLORS: Record<string, string> = {
  core: "#3B82F6",
  cognitive: "#8B5CF6",
  emotional: "#EC4899",
  sensory: "#10B981",
  motor: "#84CC16",
  executive: "#4F46E5",
  social: "#F97316",
  regulatory: "#475569",
  memory: "#3B82F6",
}

const CATEGORY_LABELS: Record<string, string> = {
  core: "Core Processing",
  cognitive: "Cognitive Logic",
  emotional: "Emotional Context",
  sensory: "Sensory Integration",
  motor: "Motor Control",
  executive: "Executive Actions",
  social: "Social Relationship",
  regulatory: "Regulatory/Sleep",
  memory: "Episodic Buffer",
}

export function DashboardView({ userId }: { userId: string }) {
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "agents" | "reasoning" | "planning" | "learning" | "monitor">("overview")
  const [selectedAgentName, setSelectedAgentName] = useState<string | null>(null)
  const [agentFilter, setAgentFilter] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  // Fetch brain status and agents
  const { data: brainStatus } = useSWR("/api/brain?action=status", fetcher, {
    refreshInterval: 5000,
  })

  // Fetch agent activities
  const { data: activityData } = useSWR(
    userId ? `/api/brain?action=activity&userId=${userId}` : null,
    fetcher,
    { refreshInterval: 6000 }
  )

  // System stats logs mock timelines for graphs
  const [mockStats, setMockStats] = useState({
    cpu: [45, 52, 49, 62, 55, 41, 48, 56, 50, 48],
    gpu: [30, 35, 42, 60, 52, 28, 36, 45, 48, 40],
    latency: [220, 240, 310, 190, 260, 290, 200, 250, 280, 230],
  })

  // Simulate stats updates
  useEffect(() => {
    const interval = setInterval(() => {
      setMockStats((prev) => ({
        cpu: [...prev.cpu.slice(1), Math.floor(Math.random() * 30) + 35],
        gpu: [...prev.gpu.slice(1), Math.floor(Math.random() * 40) + 20],
        latency: [...prev.latency.slice(1), Math.floor(Math.random() * 150) + 180],
      }))
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  const agents = brainStatus?.agents || []
  
  // Filter and search agents
  const filteredAgents = useMemo(() => {
    return agents.filter((agent: any) => {
      const matchesCategory = agentFilter === "all" || agent.category === agentFilter
      const matchesSearch = agent.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            agent.name.toLowerCase().includes(searchQuery.toLowerCase())
      return matchesCategory && matchesSearch
    })
  }, [agents, agentFilter, searchQuery])

  const selectedAgentDetails = useMemo(() => {
    if (!selectedAgentName) return null
    return agents.find((a: any) => a.name === selectedAgentName) || null
  }, [selectedAgentName, agents])

  // Get active agents count
  const activeAgentsCount = useMemo(() => {
    return agents.filter((a: any) => a.is_active).length
  }, [agents])

  // Get activity list for selected agent
  const agentActivities = useMemo(() => {
    if (!activityData?.activity || !selectedAgentName) return []
    return activityData.activity.filter((act: any) => act.agent_name === selectedAgentName)
  }, [activityData, selectedAgentName])

  return (
    <div className="flex h-full flex-col bg-background/50 backdrop-blur-md overflow-hidden">
      {/* View Header */}
      <div className="flex items-center justify-between border-b border-border/40 px-8 py-4 glass-panel shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Brain className="h-5 w-5 brain-active" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Brain Operations Dashboard</h1>
            <p className="text-xs text-muted-foreground">Monitor real-time cognitive metrics, planning queues, and neural routing</p>
          </div>
        </div>
        
        {/* API connection indicator */}
        <Badge variant={brainStatus?.pythonBackend === "connected" ? "default" : "secondary"} className="gap-1.5 px-3 py-1">
          <div className={`h-2 w-2 rounded-full ${
            brainStatus?.pythonBackend === "connected" ? "bg-green-500 status-online" : "bg-muted-foreground"
          }`} />
          Python Backend: {brainStatus?.pythonBackend || "offline"}
        </Badge>
      </div>

      {/* Internal Navigation Sub-Tabs */}
      <div className="flex items-center gap-1.5 px-8 py-2 bg-secondary/10 border-b border-border/30 shrink-0">
        {[
          { id: "overview", label: "Operations Overview", icon: Activity },
          { id: "agents", label: "Agent Visualizer", icon: Workflow },
          { id: "reasoning", label: "Reasoning Tree", icon: Lightbulb },
          { id: "planning", label: "Milestone Planner", icon: Target },
          { id: "learning", label: "Learning Engine", icon: TrendingUp },
          { id: "monitor", label: "Telemetry & Logs", icon: Cpu },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeSubTab === tab.id
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-secondary/40 hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Main Content Workspace */}
      <div className="flex-1 overflow-hidden flex">
        <div className="flex-1 overflow-y-auto p-8 space-y-6">

          {/* TAB 1: OPERATIONS OVERVIEW */}
          {activeSubTab === "overview" && (
            <div className="space-y-6">
              {/* Telemetry metrics cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="glass-card border-none">
                  <CardContent className="pt-6 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Cognitive Load</p>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold font-mono">
                        {((activeAgentsCount / Math.max(agents.length, 1)) * 100).toFixed(0)}%
                      </span>
                      <span className="text-xs text-green-400">Normal</span>
                    </div>
                    <Progress value={(activeAgentsCount / Math.max(agents.length, 1)) * 100} className="h-1.5 bg-secondary" />
                  </CardContent>
                </Card>

                <Card className="glass-card border-none">
                  <CardContent className="pt-6 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Average Latency</p>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold font-mono">
                        {mockStats.latency[mockStats.latency.length - 1]} ms
                      </span>
                      <span className="text-xs text-muted-foreground">Inference loop</span>
                    </div>
                    <div className="h-1.5 flex gap-0.5 items-end">
                      {mockStats.latency.map((val, i) => (
                        <div key={i} className="flex-1 bg-primary/30 rounded-t" style={{ height: `${(val / 400) * 100}%` }} />
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card className="glass-card border-none">
                  <CardContent className="pt-6 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Operational Health</p>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold text-green-500">99.8%</span>
                      <span className="text-xs text-muted-foreground">Global Brain</span>
                    </div>
                    <Progress value={99.8} className="h-1.5 bg-secondary [&>div]:bg-green-500" />
                  </CardContent>
                </Card>

                <Card className="glass-card border-none">
                  <CardContent className="pt-6 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Specialized Agents</p>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold font-mono">{agents.length} Nodes</span>
                      <span className="text-xs text-muted-foreground">Active: {activeAgentsCount}</span>
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      Category balance operational
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Task queue execution graphs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="glass-card border-none">
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Cpu className="h-4.5 w-4.5 text-primary" />
                      Host Resources Shimmer (CPU / GPU Timeline)
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="h-48 flex items-end gap-3 pt-4">
                    {/* CPU Timeline */}
                    <div className="flex-1 h-full flex flex-col justify-between">
                      <div className="flex-1 flex items-end gap-1 border-b border-border/30 pb-1">
                        {mockStats.cpu.map((val, i) => (
                          <div 
                            key={i} 
                            className="flex-1 bg-primary/70 rounded-t transition-all duration-500" 
                            style={{ height: `${val}%` }} 
                          />
                        ))}
                      </div>
                      <div className="flex justify-between text-[10px] text-muted-foreground pt-1.5 font-mono">
                        <span>CPU Load: {mockStats.cpu[mockStats.cpu.length - 1]}%</span>
                        <span>Telemetry Realtime</span>
                      </div>
                    </div>
                    
                    {/* GPU Timeline */}
                    <div className="flex-1 h-full flex flex-col justify-between">
                      <div className="flex-1 flex items-end gap-1 border-b border-border/30 pb-1">
                        {mockStats.gpu.map((val, i) => (
                          <div 
                            key={i} 
                            className="flex-1 bg-emerald-500/70 rounded-t transition-all duration-500" 
                            style={{ height: `${val}%` }} 
                          />
                        ))}
                      </div>
                      <div className="flex justify-between text-[10px] text-muted-foreground pt-1.5 font-mono">
                        <span>GPU Load: {mockStats.gpu[mockStats.gpu.length - 1]}%</span>
                        <span>VRAM Active</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Running timeline events */}
                <Card className="glass-card border-none">
                  <CardHeader>
                    <CardTitle className="text-sm">Active Cognitive Activity Streams</CardTitle>
                  </CardHeader>
                  <CardContent className="h-48 overflow-y-auto space-y-3 pr-2">
                    {activityData?.activity?.slice(0, 5).map((act: any) => (
                      <div key={act.id} className="flex items-center justify-between p-2.5 rounded-lg bg-secondary/20 text-xs">
                        <div className="flex items-center gap-2">
                          <div 
                            className="h-2 w-2 rounded-full" 
                            style={{ backgroundColor: CATEGORY_COLORS[act.agent_name.replace("_agent","")] || "#8B5CF6" }} 
                          />
                          <span className="font-semibold capitalize">{act.agent_name.replace("_agent","")}</span>
                          <span className="text-muted-foreground truncate max-w-[120px]">{act.action_type}</span>
                        </div>
                        <div className="flex items-center gap-3 font-mono text-muted-foreground">
                          <span>{act.latency_ms || "140"} ms</span>
                          <span className={act.success ? "text-green-500" : "text-destructive"}>
                            {act.success ? "success" : "failed"}
                          </span>
                        </div>
                      </div>
                    ))}
                    {(!activityData?.activity || activityData.activity.length === 0) && (
                      <div className="h-full flex items-center justify-center text-xs text-muted-foreground py-10">
                        No recent cognitive activity streams recorded
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 2: AGENTS VISUALIZER */}
          {activeSubTab === "agents" && (
            <div className="space-y-6">
              {/* Filter controls */}
              <div className="flex flex-wrap items-center gap-4 bg-secondary/15 p-3 rounded-xl border border-border/40 shrink-0">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search neural agents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 bg-background/50 border-none focus-visible:ring-primary"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <select
                    value={agentFilter}
                    onChange={(e) => setAgentFilter(e.target.value)}
                    className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:ring-1 focus:ring-primary"
                  >
                    <option value="all">All Category Classes</option>
                    <option value="core">Core Architecture</option>
                    <option value="cognitive">Cognitive Processes</option>
                    <option value="sensory">Sensory Translation</option>
                    <option value="utility">Utility Agents</option>
                  </select>
                </div>
              </div>

              {/* Grid of Agent Nodes */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {filteredAgents.map((agent: any) => (
                  <div
                    key={agent.id}
                    onClick={() => setSelectedAgentName(agent.name)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between card-hover ${
                      selectedAgentName === agent.name 
                        ? "border-primary bg-primary/5 shadow-lg shadow-primary/5" 
                        : "border-border/60 bg-secondary/25"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div 
                        className="h-9 w-9 rounded-lg flex items-center justify-center text-white"
                        style={{ backgroundColor: `${agent.color || "#8B5CF6"}20`, color: agent.color || "#8B5CF6" }}
                      >
                        <Brain className="h-5 w-5" />
                      </div>
                      <Badge variant={agent.is_active ? "default" : "secondary"} className="text-[10px] scale-90">
                        {agent.is_active ? "active" : "idle"}
                      </Badge>
                    </div>

                    <div className="mt-4">
                      <h4 className="font-semibold text-sm truncate">{agent.display_name}</h4>
                      <p className="text-xs text-muted-foreground capitalize mt-0.5">{agent.category} agent</p>
                    </div>

                    <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                      <span>Model: {agent.model.split("/")[1] || "gpt-4o"}</span>
                      <span>Priority: {agent.priority}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: REASONING TREE */}
          {activeSubTab === "reasoning" && (
            <div className="space-y-6">
              <Card className="glass-card border-none">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-primary" />
                    Neural Execution Plan Decision Tree
                  </CardTitle>
                  <CardDescription>Decomposing query objectives into logical routing strategies.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Mock Decision Flow Diagram */}
                  <div className="p-6 rounded-2xl bg-secondary/15 border border-border/30 relative overflow-hidden flex flex-col items-center space-y-4">
                    {/* User Query Node */}
                    <div className="px-5 py-3 rounded-xl border border-primary/50 bg-primary/10 text-center text-xs font-semibold shadow-md">
                      [Input Session] User Prompt Detected
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground rotate-90" />
                    
                    {/* Orchestrator node */}
                    <div className="px-5 py-3 rounded-xl border border-purple-500/50 bg-purple-500/10 text-center text-xs font-semibold shadow-md flex items-center gap-2">
                      <Brain className="h-4 w-4 text-purple-400" />
                      ARIA Orchestrator Router
                    </div>
                    
                    <div className="flex justify-between w-full max-w-lg">
                      <ChevronRight className="h-5 w-5 text-muted-foreground rotate-[135deg]" />
                      <ChevronRight className="h-5 w-5 text-muted-foreground rotate-90" />
                      <ChevronRight className="h-5 w-5 text-muted-foreground rotate-[45deg]" />
                    </div>

                    {/* Lower branched nodes */}
                    <div className="grid grid-cols-3 gap-6 w-full max-w-xl text-center">
                      <div className="p-3 rounded-xl border border-blue-500/40 bg-blue-500/5 text-xs">
                        <span className="font-semibold text-blue-400 block mb-1">Memory Buffer</span>
                        Recall contextual preferences
                      </div>
                      <div className="p-3 rounded-xl border border-amber-500/40 bg-amber-500/5 text-xs">
                        <span className="font-semibold text-amber-400 block mb-1">Reasoning Agent</span>
                        Verify logic and evidence tree
                      </div>
                      <div className="p-3 rounded-xl border border-emerald-500/40 bg-emerald-500/5 text-xs">
                        <span className="font-semibold text-emerald-400 block mb-1">Task Planner</span>
                        Check dependencies list
                      </div>
                    </div>
                  </div>

                  {/* Evidence & Contradictions List */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Inference Evidence Evaluation</h3>
                    <div className="space-y-2">
                      <div className="p-3.5 rounded-xl border border-border/60 bg-secondary/10 flex items-start gap-3 text-xs">
                        <CheckCircle2 className="h-4.5 w-4.5 text-green-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="font-medium text-foreground">User Preferences Alignment</p>
                          <p className="text-muted-foreground mt-0.5">Retrieved episodic preference "Prepares concise structured tables" (Confidence 94%)</p>
                        </div>
                      </div>
                      <div className="p-3.5 rounded-xl border border-border/60 bg-secondary/10 flex items-start gap-3 text-xs">
                        <AlertCircle className="h-4.5 w-4.5 text-amber-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="font-medium text-foreground">Resource Constraint Alert</p>
                          <p className="text-muted-foreground mt-0.5">Memory agent latency exceeded 200ms threshold during query indexing (Conflict resolved by cache fallback)</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* TAB 4: MILESTONE PLANNER */}
          {activeSubTab === "planning" && (
            <div className="space-y-6">
              <Card className="glass-card border-none">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Target className="h-5 w-5 text-primary" />
                    Cognitive Tasks & Execution Plan (Gantt View)
                  </CardTitle>
                  <CardDescription>Visualizing project objectives, dependencies, and risks.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Mock Gantt Chart */}
                  <div className="space-y-4">
                    {[
                      { task: "Episodic Recall", start: "0%", width: "25%", color: "bg-blue-500", status: "completed" },
                      { task: "Emotion Alignment", start: "20%", width: "30%", color: "bg-pink-500", status: "completed" },
                      { task: "Reasoning Tree", start: "45%", width: "40%", color: "bg-amber-500", status: "in_progress" },
                      { task: "Task Execution Output", start: "75%", width: "25%", color: "bg-emerald-500", status: "pending" },
                    ].map((row, i) => (
                      <div key={i} className="grid grid-cols-4 items-center gap-4 text-xs">
                        <span className="font-medium truncate col-span-1">{row.task}</span>
                        <div className="col-span-3 bg-secondary/30 h-6 rounded-lg relative overflow-hidden border border-border/30">
                          <div 
                            className={`h-full rounded-md ${row.color} opacity-85 absolute flex items-center px-2 text-[10px] text-white font-mono justify-end`}
                            style={{ left: row.start, width: row.width }}
                          >
                            {row.status}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Risk Assessment alert */}
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs flex items-start gap-3">
                    <AlertTriangle className="h-4.5 w-4.5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-amber-500">Critical Path Risk Detected</p>
                      <p className="text-muted-foreground mt-0.5">
                        Multiple concurrent agent calls may trigger rate-limiting thresholds if response validation fails. Priority has been adjusted dynamically.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* TAB 5: LEARNING ENGINE */}
          {activeSubTab === "learning" && (
            <div className="space-y-6">
              <Card className="glass-card border-none">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    Experience Replay & Knowledge Growth
                  </CardTitle>
                  <CardDescription>Tracking preference adaptation and self-evaluation models.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Stats Progress grid */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-4 rounded-xl bg-secondary/20 border border-border/40 text-center space-y-1">
                      <span className="text-2xl font-bold font-mono">142</span>
                      <p className="text-xs text-muted-foreground">Replay Sessions</p>
                    </div>
                    <div className="p-4 rounded-xl bg-secondary/20 border border-border/40 text-center space-y-1">
                      <span className="text-2xl font-bold font-mono">+12.4%</span>
                      <p className="text-xs text-muted-foreground">Knowledge Density</p>
                    </div>
                    <div className="p-4 rounded-xl bg-secondary/20 border border-border/40 text-center space-y-1">
                      <span className="text-2xl font-bold font-mono">96.4%</span>
                      <p className="text-xs text-muted-foreground">Self-Correction Rate</p>
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">System Recommendations</h3>
                    <div className="p-4 rounded-xl border border-border/50 bg-secondary/20 space-y-2 text-xs">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <span className="font-semibold text-foreground">Optimize Context Recall size</span>
                      </div>
                      <p className="text-muted-foreground">
                        Analysis of the last 20 queries indicates that setting memory recall limits to 5 results provides the best trade-off between semantic relevance and execution speed.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* TAB 6: TELEMETRY & LOGS */}
          {activeSubTab === "monitor" && (
            <Card className="glass-card border-none flex flex-col h-[500px]">
              <CardHeader className="shrink-0">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  Live Operational Logs stream
                </CardTitle>
                <CardDescription>Real-time execution telemetry and system alerts.</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 min-h-0 p-6 pt-0">
                <div className="h-full bg-black/35 rounded-xl border border-border/40 p-4 font-mono text-xs overflow-y-auto space-y-2 text-muted-foreground">
                  <div>[2026-08-04T09:34:01Z] <span className="text-purple-400">INFO</span> [ARIA] Initializing neural orchestrator service...</div>
                  <div>[2026-08-04T09:34:02Z] <span className="text-purple-400">INFO</span> [db] SQLite connection established in WAL mode.</div>
                  <div>[2026-08-04T09:34:04Z] <span className="text-purple-400">INFO</span> [cache] Memory Cache initialized (Upstash offline).</div>
                  <div>[2026-08-04T09:34:10Z] <span className="text-purple-400">INFO</span> [agent_registry] Seeded 17 core neural agents in local db.</div>
                  <div>[2026-08-04T09:34:15Z] <span className="text-yellow-400">WARN</span> [memory_agent] Vector retrieval latency exceeded 150ms.</div>
                  <div>[2026-08-04T09:34:20Z] <span className="text-purple-400">INFO</span> [chat_api] Stream initialized for session user-524ed3.</div>
                  <div className="text-foreground animate-pulse">&gt; Ready for neural activities...</div>
                </div>
              </CardContent>
            </Card>
          )}

        </div>

        {/* DETAILS SIDEBAR PANEL (Collapsible, shown when an agent is selected) */}
        {selectedAgentDetails && (
          <div className="w-80 border-l border-border/40 bg-secondary/15 flex flex-col overflow-hidden glass-panel shrink-0">
            <div className="p-4 border-b border-border/40 flex items-center justify-between shrink-0">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Agent Inspector</span>
              <button 
                onClick={() => setSelectedAgentName(null)}
                className="p-1 rounded hover:bg-secondary/40 text-muted-foreground"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Agent Overview */}
              <div className="space-y-4 text-center">
                <div 
                  className="h-16 w-16 mx-auto rounded-xl flex items-center justify-center text-white"
                  style={{ 
                    backgroundColor: `${selectedAgentDetails.color || "#8B5CF6"}20`, 
                    color: selectedAgentDetails.color || "#8B5CF6",
                    boxShadow: `0 0 15px ${selectedAgentDetails.color || "#8B5CF6"}20`
                  }}
                >
                  <Brain className="h-8 w-8" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-foreground">{selectedAgentDetails.display_name}</h3>
                  <Badge className="capitalize mt-1" style={{ backgroundColor: selectedAgentDetails.color }}>
                    {selectedAgentDetails.category} agent
                  </Badge>
                </div>
              </div>

              {/* Agent Metadata attributes */}
              <div className="space-y-3 pt-4 border-t border-border/30 text-xs">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Profile Parameters</h4>
                <div className="grid grid-cols-2 gap-y-2">
                  <span className="text-muted-foreground">Model mapping:</span>
                  <span className="text-right truncate">{selectedAgentDetails.model}</span>
                  <span className="text-muted-foreground">State:</span>
                  <span className="text-right font-semibold text-green-500">Operational</span>
                  <span className="text-muted-foreground">Priority class:</span>
                  <span className="text-right font-mono">{selectedAgentDetails.priority}</span>
                </div>
              </div>

              {/* Agent description */}
              <div className="space-y-2 pt-4 border-t border-border/30 text-xs">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Description</h4>
                <p className="text-muted-foreground leading-relaxed">{selectedAgentDetails.description || "No specific details provided."}</p>
              </div>

              {/* Recent Activities for Agent */}
              <div className="space-y-3 pt-4 border-t border-border/30 text-xs">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Recent Inferences</h4>
                <div className="space-y-2">
                  {agentActivities.slice(0, 3).map((act: any) => (
                    <div key={act.id} className="p-2 rounded bg-secondary/30 text-[10px] space-y-1 border border-border/20">
                      <div className="flex justify-between font-semibold">
                        <span>{act.action_type}</span>
                        <span className="text-green-500">success</span>
                      </div>
                      <p className="text-muted-foreground truncate">{JSON.stringify(act.input_data)}</p>
                    </div>
                  ))}
                  {agentActivities.length === 0 && (
                    <p className="text-muted-foreground italic text-center py-4">No recent activities for this agent node</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function X({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  )
}
