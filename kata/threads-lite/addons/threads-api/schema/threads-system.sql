-- Generic database schema for a Threads automation system.
-- Target: Postgres / Supabase.

create table if not exists content_topics (
  id bigserial primary key,
  title text not null,
  audience text,
  keywords jsonb not null default '[]'::jsonb,
  angle text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists agent_runs (
  id bigserial primary key,
  agent_name text not null,
  skill_name text,
  run_type text not null,
  status text not null,
  input_ref text,
  output_ref text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  error_message text
);

create table if not exists threads_drafts (
  id bigserial primary key,
  topic_id bigint references content_topics(id) on delete set null,
  agent_run_id bigint references agent_runs(id) on delete set null,
  strategy text not null,
  hook_type text,
  audience text,
  cta_type text,
  hypothesis text,
  body text not null check (char_length(body) <= 500),
  link_url text,
  metadata jsonb not null default '{}'::jsonb,
  status text not null default 'draft',
  target_metric text,
  risk_notes jsonb not null default '[]'::jsonb,
  created_by_agent text not null default 'threads-draft-strategist',
  approved_by text,
  approved_at timestamptz,
  rejected_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists threads_posts (
  id bigserial primary key,
  draft_id bigint references threads_drafts(id) on delete set null,
  threads_post_id text unique,
  creation_id text,
  publish_status text not null default 'pending',
  post_url text,
  http_status integer,
  error_message text,
  posted_at timestamptz,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists threads_metrics (
  id bigserial primary key,
  post_id bigint references threads_posts(id) on delete cascade,
  captured_at timestamptz not null default now(),
  views integer,
  likes integer,
  replies integer,
  reposts integer,
  quotes integer,
  profile_clicks integer,
  link_clicks integer,
  raw_payload jsonb not null default '{}'::jsonb
);

create table if not exists threads_lessons (
  id bigserial primary key,
  strategy text,
  lesson text not null,
  evidence jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  created_at timestamptz not null default now()
);

create index if not exists idx_threads_drafts_status on threads_drafts(status);
create index if not exists idx_threads_posts_status on threads_posts(publish_status);
create index if not exists idx_threads_metrics_post_time on threads_metrics(post_id, captured_at desc);
create index if not exists idx_agent_runs_type_time on agent_runs(run_type, started_at desc);
