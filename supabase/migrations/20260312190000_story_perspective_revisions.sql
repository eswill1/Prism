create table if not exists public.story_perspective_revisions (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  revision_tag text not null,
  status text not null default 'early',
  is_current boolean not null default false,
  generation_method text not null,
  input_signature text not null,
  source_snapshot jsonb not null default '[]'::jsonb,
  summary text not null,
  takeaways jsonb not null default '[]'::jsonb,
  framing_presence jsonb not null default '[]'::jsonb,
  source_family_presence jsonb not null default '[]'::jsonb,
  scope_presence jsonb not null default '[]'::jsonb,
  methodology_note text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cluster_id, revision_tag),
  unique (cluster_id, input_signature),
  constraint story_perspective_revisions_status_check
    check (status in ('early', 'ready'))
);

create index if not exists idx_story_perspective_revisions_cluster
  on public.story_perspective_revisions (cluster_id, created_at desc);

create unique index if not exists idx_story_perspective_revisions_current
  on public.story_perspective_revisions (cluster_id)
  where is_current = true;

create trigger set_updated_at_story_perspective_revisions
before update on public.story_perspective_revisions
for each row execute function public.set_updated_at();
