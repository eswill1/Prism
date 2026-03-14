create table if not exists public.cluster_reader_state (
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  last_viewed_at timestamptz,
  last_seen_brief_revision_tag text,
  last_seen_perspective_revision_tag text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, cluster_id)
);

create index if not exists idx_cluster_reader_state_recent
  on public.cluster_reader_state (user_id, last_viewed_at desc);

create trigger set_updated_at_cluster_reader_state
before update on public.cluster_reader_state
for each row execute function public.set_updated_at();
