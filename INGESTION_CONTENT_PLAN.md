# Prism Ingestion and Content Plan
### Version 0.1

---

## 0. Goal

Prism needs to feed itself with as little manual intervention as possible while staying:

- timely
- rights-clean
- source-diverse
- operationally stable

The system should automate:

- source discovery
- article fetch and normalization
- deduplication
- clustering
- outlet mapping
- Perspective assembly
- Context Pack candidate generation
- correction/version logging

Human intervention should be reserved for:

- source onboarding and removal
- mapping disputes
- major cluster merge/split corrections
- high-consequence editorial review

---

## 1. Core Principle

Prism should be **metadata-first and rights-aware**.

That means:

- Prism's core product surface is the Story Cluster, not the republished article
- Prism can ingest URLs, headlines, timestamps, source metadata, and structural article information at scale
- Prism should link out for full article consumption unless it has licensed republication rights
- Prism should not assume that a technically accessible image is legally reusable
- Prism should default to real media where rights are clear enough for production use

This is how Prism stays highly automated without making licensing the bottleneck.

### Product stance: real media first

Prism should look alive.

That means the default visual policy is:

1. use real photography or video thumbnails when rights are clear
2. use licensed premium media on major and homepage stories
3. use source preview imagery where policy allows
4. fall back to first-party structural visuals only when rights are unclear, assets are weak, or the story is better served by data visuals

Prism should not choose between "alive" and "safe." The system should be designed to deliver both.

---

## 2. Source Strategy

Use a tiered source stack.

### Tier A: Direct Publisher Discovery

These are the most important sources in v1.

Inputs:

- RSS feeds
- Atom feeds
- news sitemaps
- standard XML sitemaps for publishers that expose article URLs reliably

Why this tier matters:

- cheap
- fast
- direct from publisher infrastructure
- easy to poll continuously
- ideal for broad source coverage

What it provides:

- new article URLs
- publish times
- titles
- basic source metadata

What it does not guarantee:

- normalized fields across publishers
- reliable images
- full-text rights

### Tier B: Metadata Aggregator APIs

Use one normalization API in v1 to reduce source-specific scraping complexity.

Recommended use:

- bootstrap source coverage
- backfill missed items
- improve discovery of smaller publishers
- provide a secondary input for freshness checks

Candidates:

- NewsAPI for broad metadata aggregation
- later, an event-aware provider if clustering recall needs help

What it provides well:

- normalized article metadata
- broad source access through one integration
- useful backup path when direct publisher feeds are inconsistent

What it should not become:

- the sole dependency

Prism should avoid a single-provider architecture for core ingestion.

### Tier C: Licensed Premium Feeds

This tier is for visual quality, reliability, and premium editorial value.

Recommended starting point:

- AP Media API once budget and contract justify it

Use cases:

- dependable hero images
- premium breaking-news media
- graphics and video where licensed use is needed
- high-value text or archive access where contractually permitted
- editorially strong homepage and briefing visuals

This tier should be added once the product proves the need, not before.

### Tier D: First-Party and Open Assets

Use these to reduce dependency on third-party image rights.

Examples:

- source logos
- topic icons
- maps
- charts
- timelines
- public-domain or government imagery where terms allow
- first-party generated explainer graphics

This tier is important because Prism's real product value is structural understanding, not just article thumbnails.

---

## 3. Media Rights Policy

Automation is only safe if rights classes are explicit.

### Rights Class 1: Pointer Metadata

Allowed by default:

- canonical URL
- headline
- deck/summary text from metadata fields
- publication date
- source name
- author if available

Usage:

- cluster cards
- source attribution
- outbound links

### Rights Class 2: Preview Metadata

Includes:

- `og:title`
- `og:description`
- `og:url`
- source-provided preview image references

Policy:

- may be used for preview extraction and ranking-free cluster assembly
- may be displayed only if terms and usage rights are acceptable for production use
- should not be blindly mirrored or permanently stored as first-party media assets without permission

Important:
Prism should not build a business assumption around unrestricted reuse of third-party preview images.

### Rights Class 3: Licensed Media

Includes:

- AP or other licensed wire photos
- licensed video
- syndication text where contract permits

Usage:

- premium cluster visuals
- breaking-news coverage modules
- fallback when third-party preview image rights are unclear

### Rights Class 4: First-Party Rendered Assets

Includes:

- timelines
- topic maps
- data charts
- event cards
- quote panels

This class is safest and should become a larger share of Prism's UI over time.

---

## 4. Fully Automated Ingestion Pipeline

### Stage 1: Source polling

Workers poll:

- RSS and Atom feeds every 2 to 5 minutes for high-priority publishers
- news sitemaps every 5 to 10 minutes
- lower-priority sources every 15 to 30 minutes
- metadata API backfill jobs hourly

### Stage 2: URL normalization

For every discovered URL:

- resolve redirects
- strip tracking parameters
- compute canonical URL
- identify outlet domain
- assign source priority

### Stage 3: Article fetch and metadata extraction

Fetch article HTML and extract:

- page title
- Open Graph fields
- article publication time
- author/byline
- site name
- preview image reference
- body text when legally and technically retrievable

### Stage 4: Deduplication

Deduplicate on:

- canonical URL
- normalized headline similarity
- body-text fingerprint
- syndication fingerprint where available

Required outcome:

- one canonical article record per unique story URL
- explicit relation records for near duplicates or syndicated variants

### Stage 5: Story clustering

Cluster by:

- named entities
- semantic similarity
- time window
- key phrases
- source overlap

Outputs:

- cluster ID
- confidence score
- merge/split audit trail

### Stage 6: Outlet and Perspective mapping

For each article:

- map domain to known outlet
- attach rater source records
- attach reliability range
- attach framing reference data
- note unknown or unmapped outlets for review queue

### Stage 7: Evidence extraction

Extract and index:

- quoted people
- organizations
- documents
- filings
- transcripts
- official statements
- unresolved claims

### Stage 8: Context Pack candidate generation

For each cluster, generate candidates for:

- Balanced Framing
- Evidence-First
- Local Impact
- International Comparison

Each candidate must carry:

- source outlet
- selection reason codes
- lens fit score

### Stage 9: Versioning and correction logging

Any material change writes:

- cluster version
- change type
- before/after notes
- operator if manually overridden

---

## 5. Recommended v1 Architecture

### Required inputs

1. A curated publisher registry
2. Feed and sitemap pollers
3. HTML fetcher with metadata extraction
4. One metadata normalization API
5. Outlet registry and rater data store

### Deferred inputs

- licensed wire media
- full premium archive ingestion
- direct publisher syndication deals

This keeps launch scope realistic while preserving a path to richer visuals later.

---

## 6. Publisher Registry

Prism should maintain a first-party source registry with:

- outlet name
- domain
- feed URLs
- sitemap URLs
- country
- language
- outlet type
- priority tier
- reliability/rater mapping state
- fetch cadence
- active/inactive status

This registry is the control plane for automation.

Without it, ingestion becomes a pile of scripts instead of a system.

---

## 7. Automation Jobs

### Continuous jobs

- `poll_feeds`
- `poll_news_sitemaps`
- `fetch_article_metadata`
- `normalize_article`
- `dedupe_articles`
- `cluster_articles`
- `generate_context_pack_candidates`

### Scheduled jobs

- `refresh_outlet_registry`
- `refresh_rater_data`
- `recluster_recent_story_windows`
- `backfill_missed_articles`
- `stale_cluster_audit`

### Human-review queues

- unmapped outlets
- low-confidence merges
- high-consequence clusters
- mapping disputes

---

## 8. Visual Content Plan

Prism should aim to feel like a real-media news product by default.

### Default visual posture

- homepage hero modules should expect real imagery
- top clusters should usually have a real photo or video thumbnail
- briefing products should feel visually alive, not text-only
- structural fallback visuals exist to preserve quality when rights or source assets are weak

This is a product requirement, not a decorative preference.

### Default card hierarchy

Priority order:

1. licensed or first-party hero visual
2. rights-cleared publisher preview image
3. source logo + structured cluster card
4. first-party generated chart/timeline card

This ensures the UI does not collapse when image rights are uncertain.

### Fallback stance

The site must still feel authoritative when a cluster has:

- no photo
- only logos
- only charts
- only a text-first summary

That is a product-design requirement, not just a content fallback.

---

## 9. Data Model Additions

Recommended ingestion tables:

```sql
CREATE TABLE source_registry (
  id UUID PRIMARY KEY,
  outlet_name TEXT NOT NULL,
  domain TEXT NOT NULL UNIQUE,
  feed_urls JSONB NOT NULL DEFAULT '[]',
  sitemap_urls JSONB NOT NULL DEFAULT '[]',
  country TEXT,
  language TEXT,
  priority_tier TEXT NOT NULL,
  fetch_interval_seconds INT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE raw_discovered_urls (
  id UUID PRIMARY KEY,
  source_registry_id UUID REFERENCES source_registry(id),
  discovered_url TEXT NOT NULL,
  discovery_method TEXT NOT NULL,
  discovered_at TIMESTAMPTZ DEFAULT NOW(),
  fetch_status TEXT DEFAULT 'pending'
);

CREATE TABLE article_metadata (
  article_id UUID PRIMARY KEY,
  canonical_url TEXT NOT NULL UNIQUE,
  source_registry_id UUID REFERENCES source_registry(id),
  title TEXT,
  description TEXT,
  author TEXT,
  published_at TIMESTAMPTZ,
  og_image_url TEXT,
  site_name TEXT,
  rights_class TEXT NOT NULL,
  fetch_hash TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ingestion_events (
  id UUID PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 10. Operational Guardrails

### Respectful fetch policy

- per-domain concurrency caps
- adaptive retry with backoff
- `If-Modified-Since` and `ETag` support when available
- robots and terms review for source onboarding

### Resilience

- queue-based pipeline
- dead-letter queues for failed fetches
- replay support for reclustering
- source health scoring

### Metrics

Track:

- feed freshness lag
- fetch success rate
- metadata extraction rate
- dedupe rate
- cluster latency
- cluster precision audit score
- unmapped outlet backlog

---

## 11. Launch Recommendation

### Launch stack

- curated publisher registry of top national, international, financial, and regional outlets
- RSS and news sitemap polling as the primary discovery layer
- NewsAPI as a secondary normalization and miss-recovery layer
- Open Graph extraction for preview metadata
- no assumption of unrestricted third-party image storage
- real-media cards as the default where rights are acceptable
- first-party charts, logos, and structured cards as the designed fallback system

### Add after launch

- AP Media API for premium licensed visuals and richer wire content
- broader regional and international source expansion
- higher-confidence evidence extraction
- direct publisher relationships where strategically useful

---

## 12. Concrete Recommendation

If Prism wants to be highly automated, the right v1 posture is:

> **Automate URL discovery and structural understanding first. License premium media second.**

That gives Prism:

- a large content surface
- a sustainable ingestion cost profile
- lower legal risk
- faster time to launch
- a product identity centered on understanding rather than republishing

---

## Sources

- Google Feedfetcher: https://developers.google.com/crawling/docs/crawlers-fetchers/feedfetcher
- Google News sitemaps: https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap
- Open Graph protocol: https://ogp.me/
- NewsAPI docs: https://newsapi.org/docs/get-started and https://newsapi.org/docs
- AP Media API getting started: https://api.ap.org/media/v/docs/Getting_Started_API.htm
- AP Feed documentation: https://api.ap.org/media/v/docs/Feed.htm
