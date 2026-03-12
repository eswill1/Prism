-- Prism launch source seed baseline
-- Seeds Tier 1 running sources plus the first Tier 2 onboarding slice.
-- Feed URLs are only included where the current Prism prototype has already verified them.

insert into public.outlets (
  canonical_name,
  domain,
  country_code,
  language_code,
  outlet_type,
  status
)
values
  ('NPR', 'npr.org', 'US', 'en', 'public_media', 'active'),
  ('BBC News', 'bbc.com', 'GB', 'en', 'public_media', 'active'),
  ('PBS NewsHour', 'pbs.org', 'US', 'en', 'public_media', 'active'),
  ('Wall Street Journal', 'wsj.com', 'US', 'en', 'publication', 'active'),
  ('Associated Press', 'apnews.com', 'US', 'en', 'wire', 'active'),
  ('Reuters', 'reuters.com', 'GB', 'en', 'wire', 'active'),
  ('Bloomberg', 'bloomberg.com', 'US', 'en', 'publication', 'active'),
  ('Financial Times', 'ft.com', 'GB', 'en', 'publication', 'active'),
  ('Politico', 'politico.com', 'US', 'en', 'publication', 'active'),
  ('The Hill', 'thehill.com', 'US', 'en', 'publication', 'active'),
  ('NBC News', 'nbcnews.com', 'US', 'en', 'broadcaster', 'active'),
  ('ABC News', 'abcnews.com', 'US', 'en', 'broadcaster', 'active'),
  ('CBS News', 'cbsnews.com', 'US', 'en', 'broadcaster', 'active'),
  ('New York Times', 'nytimes.com', 'US', 'en', 'publication', 'active'),
  ('Fox News', 'foxnews.com', 'US', 'en', 'broadcaster', 'active')
on conflict (domain) do update
set
  canonical_name = excluded.canonical_name,
  country_code = excluded.country_code,
  language_code = excluded.language_code,
  outlet_type = excluded.outlet_type,
  status = excluded.status,
  updated_at = now();

insert into public.source_registry (
  outlet_id,
  source_name,
  primary_domain,
  launch_tier,
  ingestion_status,
  preferred_discovery_method,
  poll_interval_seconds,
  is_active,
  notes
)
select
  o.id,
  o.canonical_name,
  o.domain,
  case
    when o.domain in ('npr.org', 'bbc.com', 'pbs.org', 'wsj.com') then 'prototype'
    when o.domain in ('apnews.com', 'reuters.com', 'bloomberg.com', 'ft.com', 'politico.com', 'thehill.com', 'nbcnews.com', 'abcnews.com', 'cbsnews.com', 'nytimes.com', 'foxnews.com') then 'launch_core'
    else 'standard'
  end,
  case
    when o.domain in ('npr.org', 'bbc.com', 'pbs.org', 'wsj.com', 'thehill.com', 'nbcnews.com', 'abcnews.com', 'cbsnews.com', 'nytimes.com', 'foxnews.com') then 'active'
    else 'onboarding'
  end,
  case
    when o.domain in ('npr.org', 'bbc.com', 'pbs.org', 'wsj.com', 'thehill.com', 'nbcnews.com', 'abcnews.com', 'cbsnews.com', 'nytimes.com', 'foxnews.com') then 'rss'
    else 'manual_review'
  end,
  case
    when o.domain in ('npr.org', 'bbc.com', 'pbs.org', 'wsj.com', 'thehill.com', 'nbcnews.com', 'abcnews.com', 'cbsnews.com', 'nytimes.com', 'foxnews.com') then 300
    else 900
  end,
  true,
  case
    when o.domain in ('apnews.com', 'reuters.com', 'bloomberg.com', 'ft.com', 'politico.com')
      then 'Launch-core source seeded before feed/sitemap verification.'
    when o.domain in ('thehill.com', 'nbcnews.com', 'abcnews.com', 'cbsnews.com', 'nytimes.com', 'foxnews.com')
      then 'Launch-core source activated with a verified public RSS feed for live-story overlap testing.'
    else 'Prototype source currently used by the temporary live feed.'
  end
from public.outlets o
where o.domain in (
  'npr.org',
  'bbc.com',
  'pbs.org',
  'wsj.com',
  'apnews.com',
  'reuters.com',
  'bloomberg.com',
  'ft.com',
  'politico.com',
  'thehill.com',
  'nbcnews.com',
  'abcnews.com',
  'cbsnews.com',
  'nytimes.com',
  'foxnews.com'
)
on conflict (primary_domain) do update
set
  outlet_id = excluded.outlet_id,
  source_name = excluded.source_name,
  launch_tier = excluded.launch_tier,
  ingestion_status = excluded.ingestion_status,
  preferred_discovery_method = excluded.preferred_discovery_method,
  poll_interval_seconds = excluded.poll_interval_seconds,
  is_active = excluded.is_active,
  notes = excluded.notes,
  updated_at = now();

insert into public.source_policies (
  source_registry_id,
  rights_class_default,
  allow_preview_image,
  allow_cached_preview_image,
  allow_body_parse,
  robots_reviewed,
  notes
)
select
  sr.id,
  'pointer_metadata',
  false,
  false,
  true,
  false,
  'Default launch posture: pointer metadata only until rights posture is reviewed.'
from public.source_registry sr
where sr.primary_domain in (
  'npr.org',
  'bbc.com',
  'pbs.org',
  'wsj.com',
  'apnews.com',
  'reuters.com',
  'bloomberg.com',
  'ft.com',
  'politico.com',
  'thehill.com',
  'nbcnews.com',
  'abcnews.com',
  'cbsnews.com',
  'nytimes.com',
  'foxnews.com'
)
on conflict (source_registry_id) do update
set
  rights_class_default = excluded.rights_class_default,
  allow_preview_image = excluded.allow_preview_image,
  allow_cached_preview_image = excluded.allow_cached_preview_image,
  allow_body_parse = excluded.allow_body_parse,
  robots_reviewed = excluded.robots_reviewed,
  notes = excluded.notes,
  updated_at = now();

insert into public.source_feeds (
  source_registry_id,
  feed_type,
  feed_url,
  poll_interval_seconds,
  is_active
)
select
  sr.id,
  data.feed_type,
  data.feed_url,
  data.poll_interval_seconds,
  true
from public.source_registry sr
join (
  values
    ('npr.org', 'rss', 'https://feeds.npr.org/1001/rss.xml', 300),
    ('bbc.com', 'rss', 'https://feeds.bbci.co.uk/news/world/rss.xml', 300),
    ('pbs.org', 'rss', 'https://www.pbs.org/newshour/feeds/rss/headlines', 300),
    ('wsj.com', 'rss', 'https://feeds.a.dj.com/rss/RSSWorldNews.xml', 300),
    ('thehill.com', 'rss', 'https://thehill.com/feed/', 300),
    ('nbcnews.com', 'rss', 'https://feeds.nbcnews.com/nbcnews/public/news', 300),
    ('abcnews.com', 'rss', 'https://abcnews.go.com/abcnews/topstories', 300),
    ('cbsnews.com', 'rss', 'https://www.cbsnews.com/latest/rss/main', 300),
    ('nytimes.com', 'rss', 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', 300),
    ('foxnews.com', 'rss', 'https://moxie.foxnews.com/google-publisher/latest.xml', 300)
) as data(domain, feed_type, feed_url, poll_interval_seconds)
  on sr.primary_domain = data.domain
on conflict (source_registry_id, feed_url) do update
set
  feed_type = excluded.feed_type,
  poll_interval_seconds = excluded.poll_interval_seconds,
  is_active = excluded.is_active,
  updated_at = now();
