export interface User {
  id: string
  email: string
  full_name?: string
  avatar_url?: string
  preferences?: UserPreferences
  created_at: string
  updated_at: string
}

export interface UserPreferences {
  theme?: "light" | "dark" | "system"
  default_model?: string
  show_agent_activity?: boolean
  auto_save_memories?: boolean
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  model: string
  system_prompt?: string
  metadata?: Record<string, unknown>
  is_archived: boolean
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  user_id: string
  role: "user" | "assistant" | "system" | "tool"
  content: string
  parts?: MessagePart[]
  tool_invocations?: ToolInvocation[]
  agent_used?: string
  tokens_used?: number
  latency_ms?: number
  metadata?: Record<string, unknown>
  created_at: string
}

export interface MessagePart {
  type: "text" | "tool-invocation" | "reasoning"
  text?: string
  toolName?: string
  toolCallId?: string
  state?: "input-streaming" | "input-available" | "output-available" | "output-error"
  input?: unknown
  output?: unknown
}

export interface ToolInvocation {
  toolCallId: string
  toolName: string
  args: Record<string, unknown>
  result?: unknown
  state: "pending" | "running" | "completed" | "error"
}

export interface Agent {
  id: string
  name: string
  display_name: string
  description?: string
  category: "core" | "cognitive" | "utility"
  capabilities: string[]
  model: string
  system_prompt?: string
  tools: string[]
  is_active: boolean
  priority: number
  icon?: string
  color?: string
  created_at: string
  updated_at: string
}

export interface Memory {
  id: string
  user_id: string
  content: string
  memory_type: string
  importance: number
  tags: string[]
  source_conversation_id?: string
  metadata?: Record<string, unknown>
  created_at: string
  last_accessed_at: string
}

export interface Task {
  id: string
  user_id: string
  title: string
  description?: string
  status: "pending" | "in_progress" | "completed" | "cancelled"
  priority: "low" | "medium" | "high" | "urgent"
  due_date?: string
  tags: string[]
  source_conversation_id?: string
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface AgentActivity {
  id: string
  user_id: string
  conversation_id?: string
  agent_name: string
  action_type: string
  input_data?: Record<string, unknown>
  output_data?: Record<string, unknown>
  tokens_used?: number
  latency_ms?: number
  success: boolean
  error_message?: string
  created_at: string
}

export interface ChatState {
  conversationId: string | null
  messages: Message[]
  isLoading: boolean
  activeAgent: string | null
  error: string | null
}
