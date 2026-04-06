-- AI Virtual Brain System Database Schema
-- Complete production-ready schema with RLS

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- User profiles table (linked to auth.users)
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  avatar_url text,
  preferences jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
drop policy if exists "profiles_insert_own" on public.profiles;
drop policy if exists "profiles_update_own" on public.profiles;

create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', null)
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- Conversations table
create table if not exists public.conversations (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null default 'New Conversation',
  model text default 'openai/gpt-5',
  system_prompt text,
  metadata jsonb default '{}',
  is_archived boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.conversations enable row level security;

drop policy if exists "conversations_select_own" on public.conversations;
drop policy if exists "conversations_insert_own" on public.conversations;
drop policy if exists "conversations_update_own" on public.conversations;
drop policy if exists "conversations_delete_own" on public.conversations;

create policy "conversations_select_own" on public.conversations for select using (auth.uid() = user_id);
create policy "conversations_insert_own" on public.conversations for insert with check (auth.uid() = user_id);
create policy "conversations_update_own" on public.conversations for update using (auth.uid() = user_id);
create policy "conversations_delete_own" on public.conversations for delete using (auth.uid() = user_id);

create index if not exists idx_conversations_user_id on public.conversations(user_id);
create index if not exists idx_conversations_created_at on public.conversations(created_at desc);

-- Messages table
create table if not exists public.messages (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'tool')),
  content text,
  parts jsonb default '[]',
  tool_calls jsonb,
  tool_results jsonb,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

alter table public.messages enable row level security;

drop policy if exists "messages_select_own" on public.messages;
drop policy if exists "messages_insert_own" on public.messages;
drop policy if exists "messages_update_own" on public.messages;
drop policy if exists "messages_delete_own" on public.messages;

create policy "messages_select_own" on public.messages for select using (auth.uid() = user_id);
create policy "messages_insert_own" on public.messages for insert with check (auth.uid() = user_id);
create policy "messages_update_own" on public.messages for update using (auth.uid() = user_id);
create policy "messages_delete_own" on public.messages for delete using (auth.uid() = user_id);

create index if not exists idx_messages_conversation_id on public.messages(conversation_id);
create index if not exists idx_messages_created_at on public.messages(created_at);

-- Agents table (brain agents configuration)
create table if not exists public.agents (
  id uuid primary key default uuid_generate_v4(),
  name text not null unique,
  display_name text not null,
  description text,
  type text not null,
  status text default 'active' check (status in ('active', 'inactive', 'error')),
  config jsonb default '{}',
  capabilities jsonb default '[]',
  icon text,
  color text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Insert default agents based on Python backend
insert into public.agents (name, display_name, description, type, capabilities, icon, color) values
  ('memory_agent', 'Memory', 'Manages short-term and long-term memory storage and retrieval', 'core', '["store_memory", "recall_memory", "search_memories", "consolidate_memories"]', 'brain', '#8B5CF6'),
  ('emotion_agent', 'Emotion', 'Processes emotional intelligence and sentiment analysis', 'core', '["analyze_emotion", "detect_sentiment", "empathy_response", "mood_tracking"]', 'heart', '#EC4899'),
  ('task_agent', 'Task', 'Handles task planning, scheduling, and execution', 'core', '["create_task", "schedule_task", "prioritize_tasks", "track_progress"]', 'check-square', '#10B981'),
  ('learning_agent', 'Learning', 'Continuous learning and knowledge adaptation', 'core', '["learn_concept", "update_knowledge", "self_improve", "error_correction"]', 'graduation-cap', '#F59E0B'),
  ('creativity_agent', 'Creativity', 'Creative thinking and idea generation', 'core', '["generate_ideas", "brainstorm", "creative_writing", "problem_solving"]', 'lightbulb', '#F97316'),
  ('social_agent', 'Social', 'Social interaction and relationship management', 'core', '["manage_relationships", "social_cues", "conversation_style", "empathy"]', 'users', '#06B6D4'),
  ('perception_agent', 'Perception', 'Multi-modal perception and sensory integration', 'core', '["visual_processing", "audio_processing", "context_awareness", "attention"]', 'eye', '#6366F1'),
  ('language_agent', 'Language', 'Natural language understanding and generation', 'core', '["understand_text", "generate_response", "translate", "summarize"]', 'message-circle', '#3B82F6'),
  ('planning_agent', 'Planning', 'Goal setting and strategic planning', 'core', '["set_goals", "create_plan", "optimize_schedule", "resource_allocation"]', 'map', '#14B8A6'),
  ('ethics_agent', 'Ethics', 'Ethical decision making and moral reasoning', 'core', '["ethical_analysis", "moral_judgement", "bias_detection", "fairness_check"]', 'scale', '#8B5CF6')
on conflict (name) do nothing;

-- Memories table (long-term memory storage)
create table if not exists public.memories (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  content text not null,
  type text not null check (type in ('episodic', 'semantic', 'procedural', 'emotional')),
  importance float default 0.5 check (importance >= 0 and importance <= 1),
  emotions jsonb default '{}',
  tags text[] default '{}',
  source text,
  context jsonb default '{}',
  embedding_data jsonb,
  access_count int default 0,
  last_accessed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.memories enable row level security;

drop policy if exists "memories_select_own" on public.memories;
drop policy if exists "memories_insert_own" on public.memories;
drop policy if exists "memories_update_own" on public.memories;
drop policy if exists "memories_delete_own" on public.memories;

create policy "memories_select_own" on public.memories for select using (auth.uid() = user_id);
create policy "memories_insert_own" on public.memories for insert with check (auth.uid() = user_id);
create policy "memories_update_own" on public.memories for update using (auth.uid() = user_id);
create policy "memories_delete_own" on public.memories for delete using (auth.uid() = user_id);

create index if not exists idx_memories_user_id on public.memories(user_id);
create index if not exists idx_memories_type on public.memories(type);
create index if not exists idx_memories_importance on public.memories(importance desc);
create index if not exists idx_memories_tags on public.memories using gin(tags);

-- Tasks table
create table if not exists public.tasks (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  description text,
  status text default 'pending' check (status in ('pending', 'in_progress', 'completed', 'cancelled', 'failed')),
  priority int default 1 check (priority >= 1 and priority <= 5),
  due_date timestamptz,
  completed_at timestamptz,
  tags text[] default '{}',
  dependencies uuid[] default '{}',
  assigned_agent text,
  result jsonb,
  metadata jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.tasks enable row level security;

drop policy if exists "tasks_select_own" on public.tasks;
drop policy if exists "tasks_insert_own" on public.tasks;
drop policy if exists "tasks_update_own" on public.tasks;
drop policy if exists "tasks_delete_own" on public.tasks;

create policy "tasks_select_own" on public.tasks for select using (auth.uid() = user_id);
create policy "tasks_insert_own" on public.tasks for insert with check (auth.uid() = user_id);
create policy "tasks_update_own" on public.tasks for update using (auth.uid() = user_id);
create policy "tasks_delete_own" on public.tasks for delete using (auth.uid() = user_id);

create index if not exists idx_tasks_user_id on public.tasks(user_id);
create index if not exists idx_tasks_status on public.tasks(status);
create index if not exists idx_tasks_priority on public.tasks(priority desc);

-- Agent activity log
create table if not exists public.agent_activity (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  agent_name text not null,
  action text not null,
  input jsonb,
  output jsonb,
  duration_ms int,
  status text default 'success' check (status in ('success', 'error', 'pending')),
  error_message text,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

alter table public.agent_activity enable row level security;

drop policy if exists "agent_activity_select_own" on public.agent_activity;
drop policy if exists "agent_activity_insert_own" on public.agent_activity;

create policy "agent_activity_select_own" on public.agent_activity for select using (auth.uid() = user_id);
create policy "agent_activity_insert_own" on public.agent_activity for insert with check (auth.uid() = user_id);

create index if not exists idx_agent_activity_user_id on public.agent_activity(user_id);
create index if not exists idx_agent_activity_agent_name on public.agent_activity(agent_name);
create index if not exists idx_agent_activity_created_at on public.agent_activity(created_at desc);

-- User settings
create table if not exists public.user_settings (
  id uuid primary key references public.profiles(id) on delete cascade,
  theme text default 'system' check (theme in ('light', 'dark', 'system')),
  language text default 'en',
  notifications_enabled boolean default true,
  voice_enabled boolean default false,
  default_model text default 'openai/gpt-5',
  active_agents text[] default ARRAY['memory_agent', 'emotion_agent', 'task_agent', 'learning_agent', 'creativity_agent', 'language_agent'],
  custom_instructions text,
  metadata jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.user_settings enable row level security;

drop policy if exists "user_settings_select_own" on public.user_settings;
drop policy if exists "user_settings_insert_own" on public.user_settings;
drop policy if exists "user_settings_update_own" on public.user_settings;

create policy "user_settings_select_own" on public.user_settings for select using (auth.uid() = id);
create policy "user_settings_insert_own" on public.user_settings for insert with check (auth.uid() = id);
create policy "user_settings_update_own" on public.user_settings for update using (auth.uid() = id);

-- Auto-create settings on profile creation
create or replace function public.handle_new_profile()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.user_settings (id)
  values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_profile_created on public.profiles;
create trigger on_profile_created
  after insert on public.profiles
  for each row
  execute function public.handle_new_profile();

-- Functions for updating timestamps
create or replace function public.update_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Apply timestamp triggers
drop trigger if exists update_profiles_updated_at on public.profiles;
create trigger update_profiles_updated_at before update on public.profiles
  for each row execute function public.update_updated_at();

drop trigger if exists update_conversations_updated_at on public.conversations;
create trigger update_conversations_updated_at before update on public.conversations
  for each row execute function public.update_updated_at();

drop trigger if exists update_agents_updated_at on public.agents;
create trigger update_agents_updated_at before update on public.agents
  for each row execute function public.update_updated_at();

drop trigger if exists update_memories_updated_at on public.memories;
create trigger update_memories_updated_at before update on public.memories
  for each row execute function public.update_updated_at();

drop trigger if exists update_tasks_updated_at on public.tasks;
create trigger update_tasks_updated_at before update on public.tasks
  for each row execute function public.update_updated_at();

drop trigger if exists update_user_settings_updated_at on public.user_settings;
create trigger update_user_settings_updated_at before update on public.user_settings
  for each row execute function public.update_updated_at();
