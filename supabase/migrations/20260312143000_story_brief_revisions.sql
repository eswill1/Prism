alter table public.version_registry
  drop constraint if exists version_registry_scope_check;

alter table public.version_registry
  add constraint version_registry_scope_check
  check (scope in ('cluster', 'perspective', 'context_rules', 'outlet_ratings', 'ingestion_policy', 'story_brief'));

create table if not exists public.story_brief_revisions (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  revision_tag text not null,
  status text not null default 'early',
  is_current boolean not null default false,
  label text not null,
  title text not null,
  generation_method text not null,
  input_signature text not null,
  source_snapshot jsonb not null default '[]'::jsonb,
  paragraphs jsonb not null default '[]'::jsonb,
  why_it_matters text not null,
  where_sources_agree text not null,
  where_coverage_differs text not null,
  what_to_watch text not null,
  supporting_points jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cluster_id, revision_tag),
  unique (cluster_id, input_signature),
  constraint story_brief_revisions_status_check
    check (status in ('early', 'full'))
);

create index if not exists idx_story_brief_revisions_cluster
  on public.story_brief_revisions (cluster_id, created_at desc);

create unique index if not exists idx_story_brief_revisions_current
  on public.story_brief_revisions (cluster_id)
  where is_current = true;

create trigger set_updated_at_story_brief_revisions
before update on public.story_brief_revisions
for each row execute function public.set_updated_at();
