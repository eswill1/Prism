-- Prism initial schema baseline for Supabase / PostgreSQL
-- Version 0.1

create extension if not exists pgcrypto;
create extension if not exists citext;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.user_profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  handle citext not null unique,
  display_name text not null,
  subscription_tier text not null default 'free',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_profiles_subscription_tier_check
    check (subscription_tier in ('free', 'individual', 'professional', 'institutional'))
);

create table if not exists public.institutions (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug citext not null unique,
  institution_type text not null default 'workplace',
  plan_tier text not null default 'pilot',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.institution_memberships (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references public.institutions(id) on delete cascade,
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (institution_id, user_id),
  constraint institution_memberships_role_check
    check (role in ('owner', 'admin', 'member'))
);

create table if not exists public.outlets (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null,
  domain citext not null unique,
  country_code text,
  language_code text default 'en',
  outlet_type text not null default 'publication',
  reliability_range text not null default 'not_enough_data',
  framing_reference jsonb not null default '{}'::jsonb,
  rater_data jsonb not null default '{}'::jsonb,
  data_version text not null default '0.1.0',
  status text not null default 'active',
  last_rater_refresh_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint outlets_status_check
    check (status in ('active', 'watchlist', 'disabled')),
  constraint outlets_type_check
    check (outlet_type in ('wire', 'publication', 'broadcaster', 'public_media', 'regional', 'specialist'))
);

create table if not exists public.source_registry (
  id uuid primary key default gen_random_uuid(),
  outlet_id uuid references public.outlets(id) on delete set null,
  source_name text not null,
  primary_domain citext not null unique,
  launch_tier text not null default 'standard',
  ingestion_status text not null default 'candidate',
  preferred_discovery_method text not null default 'rss',
  poll_interval_seconds integer not null default 300,
  is_active boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_registry_launch_tier_check
    check (launch_tier in ('prototype', 'launch_core', 'standard', 'watchlist')),
  constraint source_registry_ingestion_status_check
    check (ingestion_status in ('candidate', 'onboarding', 'active', 'paused', 'disabled'))
);

create table if not exists public.source_feeds (
  id uuid primary key default gen_random_uuid(),
  source_registry_id uuid not null references public.source_registry(id) on delete cascade,
  feed_type text not null,
  feed_url text not null,
  poll_interval_seconds integer not null default 300,
  last_polled_at timestamptz,
  last_success_at timestamptz,
  consecutive_failures integer not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_registry_id, feed_url),
  constraint source_feeds_type_check
    check (feed_type in ('rss', 'atom', 'news_sitemap', 'sitemap', 'api'))
);

create table if not exists public.source_policies (
  source_registry_id uuid primary key references public.source_registry(id) on delete cascade,
  rights_class_default text not null default 'pointer_metadata',
  allow_preview_image boolean not null default false,
  allow_cached_preview_image boolean not null default false,
  allow_body_parse boolean not null default true,
  robots_reviewed boolean not null default false,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_policies_rights_class_check
    check (rights_class_default in ('pointer_metadata', 'preview_metadata', 'licensed_media', 'first_party'))
);

create table if not exists public.raw_discovered_urls (
  id uuid primary key default gen_random_uuid(),
  source_registry_id uuid references public.source_registry(id) on delete set null,
  source_feed_id uuid references public.source_feeds(id) on delete set null,
  discovered_url text not null,
  canonical_url text,
  discovery_method text not null,
  discovered_at timestamptz not null default now(),
  fetch_status text not null default 'pending',
  last_attempted_at timestamptz,
  error_message text,
  created_at timestamptz not null default now(),
  constraint raw_discovered_urls_fetch_status_check
    check (fetch_status in ('pending', 'normalized', 'fetched', 'failed', 'dead_letter'))
);

create table if not exists public.source_health_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_registry_id uuid not null references public.source_registry(id) on delete cascade,
  fetch_success_rate numeric(5,2),
  freshness_lag_minutes integer,
  parse_success_rate numeric(5,2),
  degraded_reason text,
  created_at timestamptz not null default now()
);

create table if not exists public.articles (
  id uuid primary key default gen_random_uuid(),
  outlet_id uuid references public.outlets(id) on delete set null,
  source_registry_id uuid references public.source_registry(id) on delete set null,
  canonical_url text not null unique,
  original_url text,
  headline text not null,
  dek text,
  summary text,
  body_text text,
  authors jsonb not null default '[]'::jsonb,
  site_name text,
  language_code text default 'en',
  published_at timestamptz not null,
  updated_at_source timestamptz,
  content_hash text,
  fingerprint text,
  rights_class text not null default 'pointer_metadata',
  preview_image_url text,
  preview_image_status text not null default 'unknown',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint articles_rights_class_check
    check (rights_class in ('pointer_metadata', 'preview_metadata', 'licensed_media', 'first_party')),
  constraint articles_preview_image_status_check
    check (preview_image_status in ('unknown', 'allowed', 'blocked', 'licensed', 'fallback_only'))
);

create table if not exists public.story_clusters (
  id uuid primary key default gen_random_uuid(),
  slug citext not null unique,
  topic_label text not null,
  canonical_headline text not null,
  summary text not null,
  status text not null default 'active',
  cluster_version text not null default '0.1.0',
  perspective_version text,
  latest_event_at timestamptz not null default now(),
  hero_article_id uuid references public.articles(id) on delete set null,
  hero_media_url text,
  hero_media_alt text,
  hero_media_credit text,
  hero_media_rights_class text,
  reliability_range text,
  outlet_count integer not null default 0,
  coverage_counts jsonb not null default '{"left":0,"center":0,"right":0}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint story_clusters_status_check
    check (status in ('active', 'developing', 'watch', 'archived')),
  constraint story_clusters_hero_media_rights_class_check
    check (
      hero_media_rights_class is null
      or hero_media_rights_class in ('pointer_metadata', 'preview_metadata', 'licensed_media', 'first_party')
    )
);

create table if not exists public.cluster_articles (
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  article_id uuid not null references public.articles(id) on delete cascade,
  relation_type text not null default 'member',
  rank_in_cluster integer,
  is_primary boolean not null default false,
  framing_group text,
  selection_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (cluster_id, article_id),
  constraint cluster_articles_relation_type_check
    check (relation_type in ('member', 'lead', 'context', 'duplicate')),
  constraint cluster_articles_framing_group_check
    check (framing_group is null or framing_group in ('left', 'center', 'right'))
);

create table if not exists public.cluster_key_facts (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  fact_text text not null,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.context_pack_items (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  lens text not null,
  article_id uuid not null references public.articles(id) on delete cascade,
  rank integer not null default 0,
  title_override text,
  why_included text not null,
  reason_codes jsonb not null default '[]'::jsonb,
  rule_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cluster_id, lens, article_id),
  constraint context_pack_items_lens_check
    check (lens in ('balanced_framing', 'evidence_first', 'local_impact', 'international_comparison'))
);

create table if not exists public.evidence_items (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  article_id uuid references public.articles(id) on delete set null,
  label text not null,
  source_name text not null,
  source_type text not null,
  source_url text,
  claim_status text not null default 'supported',
  notes text,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint evidence_items_claim_status_check
    check (claim_status in ('supported', 'unresolved', 'contested')),
  constraint evidence_items_source_type_check
    check (source_type in ('document', 'official_statement', 'transcript', 'dataset', 'quote', 'report', 'memo'))
);

create table if not exists public.correction_events (
  id uuid primary key default gen_random_uuid(),
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  event_type text not null,
  display_summary text not null,
  notes text not null,
  version_before text,
  version_after text,
  created_by uuid references public.user_profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint correction_events_type_check
    check (event_type in ('summary_update', 'merge', 'split', 'article_remap', 'evidence_update', 'outlet_mapping_update', 'manual_correction'))
);

create table if not exists public.version_registry (
  id uuid primary key default gen_random_uuid(),
  scope text not null,
  scope_id uuid,
  version_tag text not null,
  change_kind text not null,
  metadata jsonb not null default '{}'::jsonb,
  published_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint version_registry_scope_check
    check (scope in ('cluster', 'perspective', 'context_rules', 'outlet_ratings', 'ingestion_policy')),
  constraint version_registry_change_kind_check
    check (change_kind in ('create', 'update', 'rebuild', 'manual_override', 'rollback'))
);

create table if not exists public.saved_clusters (
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, cluster_id)
);

create table if not exists public.cluster_follows (
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  cluster_id uuid not null references public.story_clusters(id) on delete cascade,
  last_notified_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, cluster_id)
);

create index if not exists idx_source_registry_status
  on public.source_registry (launch_tier, ingestion_status, is_active);

create index if not exists idx_source_feeds_poll
  on public.source_feeds (is_active, poll_interval_seconds, last_polled_at);

create index if not exists idx_raw_discovered_urls_status
  on public.raw_discovered_urls (fetch_status, discovered_at desc);

create index if not exists idx_articles_outlet_published
  on public.articles (outlet_id, published_at desc);

create index if not exists idx_articles_fingerprint
  on public.articles (fingerprint);

create index if not exists idx_story_clusters_latest
  on public.story_clusters (latest_event_at desc);

create index if not exists idx_cluster_articles_article
  on public.cluster_articles (article_id);

create index if not exists idx_context_pack_items_cluster_lens
  on public.context_pack_items (cluster_id, lens, rank);

create index if not exists idx_evidence_items_cluster
  on public.evidence_items (cluster_id, sort_order);

create index if not exists idx_correction_events_cluster
  on public.correction_events (cluster_id, created_at desc);

create index if not exists idx_version_registry_scope
  on public.version_registry (scope, published_at desc);

create trigger set_updated_at_user_profiles
before update on public.user_profiles
for each row execute function public.set_updated_at();

create trigger set_updated_at_institutions
before update on public.institutions
for each row execute function public.set_updated_at();

create trigger set_updated_at_institution_memberships
before update on public.institution_memberships
for each row execute function public.set_updated_at();

create trigger set_updated_at_outlets
before update on public.outlets
for each row execute function public.set_updated_at();

create trigger set_updated_at_source_registry
before update on public.source_registry
for each row execute function public.set_updated_at();

create trigger set_updated_at_source_feeds
before update on public.source_feeds
for each row execute function public.set_updated_at();

create trigger set_updated_at_source_policies
before update on public.source_policies
for each row execute function public.set_updated_at();

create trigger set_updated_at_articles
before update on public.articles
for each row execute function public.set_updated_at();

create trigger set_updated_at_story_clusters
before update on public.story_clusters
for each row execute function public.set_updated_at();

create trigger set_updated_at_cluster_articles
before update on public.cluster_articles
for each row execute function public.set_updated_at();

create trigger set_updated_at_cluster_key_facts
before update on public.cluster_key_facts
for each row execute function public.set_updated_at();

create trigger set_updated_at_context_pack_items
before update on public.context_pack_items
for each row execute function public.set_updated_at();

create trigger set_updated_at_evidence_items
before update on public.evidence_items
for each row execute function public.set_updated_at();

create trigger set_updated_at_cluster_follows
before update on public.cluster_follows
for each row execute function public.set_updated_at();
