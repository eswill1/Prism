# Prism Ingestion Job Catalog
### Version 0.2

---

## Purpose

This is the execution companion to the ingestion/content plan. It defines the jobs Prism should actually run, what each job owns, how often it runs, and what counts as failure.

The system goal is maximum automation with narrow human-review points.

---

## Job Groups

### 1. Source Discovery

#### `poll_feeds`

- cadence: every 2 to 5 minutes for priority sources
- input: `source_registry`, `source_feeds`
- output: `raw_discovered_urls`
- failure rule: source marked degraded after 3 consecutive failures

#### `poll_news_sitemaps`

- cadence: every 5 to 10 minutes
- input: `source_registry`, sitemap URLs
- output: `raw_discovered_urls`
- failure rule: retry with backoff, then source-health alert
- current state: implemented inside the active discovery poller for verified sitemap sources
- quality rule: sitemap-only items without substantive extracted text are allowed into discovery, but should not be promoted as homepage-ready story shells on title text alone
- source-specific rule: Reuters and AP use source-specific filtering; Politico remains behind a strict allowlist because its public news sitemap is dominated by newsletters and house material

#### `backfill_metadata_api`

- cadence: hourly
- input: external metadata provider + recent topic windows
- output: `raw_discovered_urls`
- failure rule: no pipeline halt; mark as degraded secondary source

---

### 2. Fetch and Normalize

#### `normalize_discovered_url`

- cadence: queue-driven
- input: `raw_discovered_urls`
- output: canonical URL, outlet domain, source priority
- failure rule: send malformed URLs to dead-letter queue

#### `fetch_article_metadata`

- cadence: queue-driven
- input: canonical URL
- output: `article_metadata`
- extracted fields: title, description, published time, author, site name, Open Graph data
- failure rule: retry 3 times, then mark fetch failed

#### `enrich_article_content`

- cadence: queue-driven after `poll_feeds`, or scheduled in short batches during early staging
- input: recent linked articles with `fetch_status = pending|normalized`
- output: lede, first paragraphs, named entities, extracted-body quality markers on `articles`
- follow-on effect: refresh active `story_clusters.summary` so reader-facing story decks improve after enrichment rather than staying stuck on ingest-time snippets
- failure rule: mark discovery row failed with retry cooldown; do not block feed polling
- current state: the default operator command `npm run ingest:feeds` now chains this enrichment pass immediately after feed polling; `npm run ingest:feeds:raw` remains available only for explicit ingest-only runs
- future follow-up: longer Prism Brief generation should consume these richer article bodies instead of settling for one-paragraph summaries when the source set is mature

#### `generate_story_briefs`

- cadence: queue-driven after `enrich_article_content`, or chained directly after the enrich pass during early staging
- input: active `story_clusters`, linked enriched articles, key facts, and recent correction/change labels
- output: `story_brief_revisions` plus `version_registry` events for current brief changes
- grounding rule: only use extracted source text and stored cluster facts; do not invent unsupported disagreement language
- failure rule: keep the previous current brief revision in place; do not blank out story pages
- current state: `npm run ingest:feeds` now runs brief generation after enrichment, and `npm run brief:generate` can be run directly for brief-only refreshes

#### `classify_media_rights`

- cadence: immediately after metadata fetch
- input: article metadata + source policy
- output: rights class on the article record
- failure rule: default to stricter rights class

---

### 3. Content Quality

#### `dedupe_articles`

- cadence: queue-driven + scheduled sweep
- input: new or updated article metadata
- output: duplicate links, canonical article mapping
- failure rule: duplicates remain visible only inside internal queue until processed

#### `detect_syndication_variants`

- cadence: every 15 minutes
- input: recent article corpus
- output: relation records between source variants
- failure rule: non-blocking

#### `find_open_reporting_alternates`

- cadence: queue-driven after article ingest for paywalled or thin-source stories
- input: canonical URL, title, named entities, active story cluster
- output: alternate linked article candidates with lower access friction
- failure rule: keep the original story intact; do not substitute weak alternates just to avoid a paywall

#### `score_article_quality`

- cadence: queue-driven
- input: metadata + parsed content
- output: extraction confidence, structural quality flags
- failure rule: article remains usable, but with lower enrichment confidence

---

### 4. Clustering

#### `cluster_recent_articles`

- cadence: continuous batches every 1 to 3 minutes
- input: recent article pool
- output: cluster membership assignments
- failure rule: retry batch; recent articles remain in unclustered queue

#### `recluster_recent_windows`

- cadence: every 15 minutes
- input: last 24 to 72 hours of article/cluster data
- output: improved merges, splits, and confidence updates
- failure rule: no user-facing interruption; defer to next window

#### `queue_low_confidence_clusters`

- cadence: after clustering pass
- input: cluster confidence thresholds
- output: review queue entries
- failure rule: no pipeline halt

---

### 5. Perspective and Evidence

#### `map_outlets`

- cadence: queue-driven after metadata fetch
- input: article domain
- output: outlet ID or unmapped-outlet queue item
- failure rule: article stays live with source-domain fallback

#### `refresh_rater_data`

- cadence: daily
- input: official rater sources and outlet registry
- output: refreshed outlet attribution and version record
- failure rule: preserve last good dataset and open alert

#### `extract_evidence_items`

- cadence: queue-driven after article parse
- input: article content
- output: evidence items, quoted entities, source references
- failure rule: cluster remains live without evidence enrichment

#### `generate_context_pack_candidates`

- cadence: every cluster update
- input: cluster membership + outlet mapping + lens rules
- output: candidate sets for each launch lens
- failure rule: cluster stays live; pack falls back to minimal set

---

### 6. Publishing and Monitoring

#### `publish_cluster_updates`

- cadence: queue-driven after cluster change
- input: cluster version diff
- output: live cluster cache refresh
- failure rule: serve previous good cluster version until publish succeeds

#### `emit_correction_events`

- cadence: on every material cluster or mapping change
- input: before/after state diff
- output: `correction_events`
- failure rule: publish blocked if correction logging fails

#### `compute_source_health`

- cadence: every 30 minutes
- input: fetch success rates, freshness lag, parse rates
- output: source-health score
- failure rule: alert only
- current state: available locally and in staging as `npm run sources:health`

---

## Review Queues

Prism should keep human review narrow and explicit.

Queues:

- unmapped outlets
- low-confidence cluster merges
- rights-policy exceptions
- high-consequence story reviews
- source-health degradations

---

## Success Rules

The pipeline is healthy when:

- fresh URLs are discovered continuously
- metadata extraction succeeds at high rates
- clusters form quickly enough to feel live
- outlet mapping backlog remains small
- correction events are always logged

---

## Implementation Order

Build these jobs in order:

1. `poll_feeds`
2. `normalize_discovered_url`
3. `enrich_article_content`
4. `generate_story_briefs`
5. `dedupe_articles`
6. `cluster_recent_articles`
7. `map_outlets`
8. `generate_context_pack_candidates`
9. `emit_correction_events`
10. `poll_news_sitemaps`

That sequence gets Prism from a static mockup to a living cluster product with the fewest moving parts.
