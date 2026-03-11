-- Prism source registry and ingestion control-plane schema
-- Version 0.1

CREATE TABLE source_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  outlet_name TEXT NOT NULL,
  domain TEXT NOT NULL UNIQUE,
  country TEXT,
  language TEXT,
  outlet_type TEXT NOT NULL DEFAULT 'publication',
  priority_tier TEXT NOT NULL DEFAULT 'standard',
  fetch_interval_seconds INT NOT NULL DEFAULT 300,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE source_feeds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_registry_id UUID NOT NULL REFERENCES source_registry(id) ON DELETE CASCADE,
  feed_type TEXT NOT NULL,
  feed_url TEXT NOT NULL,
  poll_interval_seconds INT NOT NULL DEFAULT 300,
  last_polled_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  consecutive_failures INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (source_registry_id, feed_url)
);

CREATE TABLE source_policies (
  source_registry_id UUID PRIMARY KEY REFERENCES source_registry(id) ON DELETE CASCADE,
  rights_class_default TEXT NOT NULL DEFAULT 'pointer_metadata',
  allow_preview_image BOOLEAN NOT NULL DEFAULT false,
  allow_cached_preview_image BOOLEAN NOT NULL DEFAULT false,
  allow_body_parse BOOLEAN NOT NULL DEFAULT true,
  robots_reviewed BOOLEAN NOT NULL DEFAULT false,
  notes TEXT
);

CREATE TABLE raw_discovered_urls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_registry_id UUID REFERENCES source_registry(id) ON DELETE SET NULL,
  source_feed_id UUID REFERENCES source_feeds(id) ON DELETE SET NULL,
  discovered_url TEXT NOT NULL,
  discovery_method TEXT NOT NULL,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fetch_status TEXT NOT NULL DEFAULT 'pending',
  last_attempted_at TIMESTAMPTZ
);

CREATE TABLE source_health_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_registry_id UUID NOT NULL REFERENCES source_registry(id) ON DELETE CASCADE,
  fetch_success_rate NUMERIC(5,2),
  freshness_lag_minutes INT,
  parse_success_rate NUMERIC(5,2),
  degraded_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_source_registry_priority
  ON source_registry(priority_tier, is_active);

CREATE INDEX idx_source_feeds_active_poll
  ON source_feeds(is_active, poll_interval_seconds, last_polled_at);

CREATE INDEX idx_raw_discovered_urls_status
  ON raw_discovered_urls(fetch_status, discovered_at);
