# Prism Data Model V1
### Version 0.1

This document defines the first real database baseline for Prism's early development stack.

The corresponding SQL migration lives at:

- `supabase/migrations/20260311030000_initial_prism_schema.sql`

The goal is not to model every future feature. The goal is to create a durable Phase 1-3 schema that supports:

- source onboarding
- article ingestion
- story clustering
- Perspective rendering
- evidence and correction logging
- saved and followed clusters

---

## 1. Design Principles

1. The **Story Cluster** is the primary product object.
2. Perspective data is **read-only context**, not a ranking signal.
3. Corrections and versioning are first-class records, not UI-only copy.
4. The schema should work on Supabase now without trapping Prism inside Supabase forever.
5. Reader accounts and institutional accounts should be possible early, but auth coupling should stay light.

---

## 2. Schema Domains

### Reader and access

- `user_profiles`
- `institutions`
- `institution_memberships`
- `saved_clusters`
- `cluster_follows`

These tables support early product loops without forcing the rest of the system to wait on complex account infrastructure.

### Source registry and ingestion control plane

- `outlets`
- `source_registry`
- `source_feeds`
- `source_policies`
- `raw_discovered_urls`
- `source_health_snapshots`

These are the operational backbone for automated intake.

### Content and clustering

- `articles`
- `story_clusters`
- `cluster_articles`
- `cluster_key_facts`

These define the core unit Prism serves to readers.

### Perspective, evidence, and audit

- `context_pack_items`
- `evidence_items`
- `correction_events`
- `version_registry`

These tables make the product inspectable and correction-friendly.

---

## 3. Core Entity Notes

### `user_profiles`

Purpose:

- application-level user identity
- handle and display name
- subscription tier and settings

Important note:

- `auth_user_id` is nullable and unique
- this keeps the schema compatible with Supabase Auth now without making it mandatory forever

### `outlets`

Purpose:

- canonical publication registry
- domain-level identity
- rater data and reliability range

This is the base table for Perspective joins.

### `source_registry`

Purpose:

- ingestion-facing source control plane
- polling cadence
- launch priority
- onboarding status

`outlets` and `source_registry` are intentionally separate:

- `outlets` describes the publication
- `source_registry` describes how Prism ingests it

### `articles`

Purpose:

- canonical article record
- metadata-first content storage
- rights classification
- preview media references

Important boundaries:

- full text is allowed as an ingestion field, but production use should still honor rights rules
- media reuse policy should not be inferred from technical accessibility

### `story_clusters`

Purpose:

- canonical event object
- reader-facing title, summary, topic, freshness, and hero media
- cluster-level reliability range and coverage counts for the reader surface
- version hooks for Perspective and correction surfaces

### `cluster_articles`

Purpose:

- membership mapping between clusters and articles
- ranking/order inside a cluster
- primary/canonical article designation where needed
- optional framing group and inclusion reason for the reader UI

### `context_pack_items`

Purpose:

- lens-specific alternate reads
- stored reason codes
- explicit rule version

This is important because Context Packs must be auditable, not magical.

### `evidence_items`

Purpose:

- structured source ledger for each cluster
- documents, statements, transcripts, datasets, and unresolved claims

### `correction_events`

Purpose:

- visible correction and update log
- before/after version linkage
- optional human-readable display summary

### `version_registry`

Purpose:

- generic version ledger across cluster, Perspective, context rules, and outlet data

This table makes versioning queryable instead of scattering version tags across product tables.

---

## 4. Phase Boundaries

### Included now

- ingestion control plane
- cluster reader core
- Perspective rendering primitives
- saved and followed clusters
- correction and version history

### Deferred to later phases

- billing tables
- notification delivery logs
- editorial assignment workflows
- advanced institutional analytics
- heavier ML feature stores
- RLS hardening and public/private policy matrix

Those should come after the reader and ingestion loops are real.

---

## 5. Supabase Posture

For early development, Supabase is being used as:

- managed Postgres
- migration runner
- optional auth source later

The initial schema deliberately:

- does not require Supabase Auth to exist before data work begins
- avoids provider-specific function dependencies beyond standard Postgres extensions
- leaves RLS hardening for the phase when reader accounts become real

That is the right tradeoff for Prism's current stage.

---

## 6. Immediate Build Targets

The first implementation work this schema should support is:

1. source registry seed import
2. discovered URL ingestion
3. article normalization and insert/update
4. cluster creation and article attachment
5. cluster detail read APIs
6. saved cluster and follow state
7. correction and version rendering

If a schema change does not help one of those seven things, it probably does not belong in V1.
