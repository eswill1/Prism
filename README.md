# The Prism Wire

> A serious, newsroom-grade news product built to make coverage transparent,
> inspectable, and useful without asking readers to trust a hidden consensus.

Prism exists to help people understand what is happening without turning disagreement into spectacle.

Current build priority:

- prove the core loop before broadening the product surface
- improve source-grounded Prism Brief quality by separating fast feed polling from slower article enrichment
- move story formation toward hybrid semantic clustering while keeping deterministic merge guardrails
- expand mature multi-source briefs beyond minimum viable summaries
- add paywall-aware alternate-source matching so thin or inaccessible lead sources do not dead-end the reader
- push paywall-aware alternate-source matching upstream into ingestion metadata so story records know their best open fallback before the reader layer renders
- generate stored Perspective revisions and Context Packs from linked story coverage instead of inventing Perspective entirely in the page layer

Prism's core loop is:

1. a reader opens a major story
2. they understand the shape of the story quickly
3. they inspect another angle, evidence item, or change note
4. they save or follow the story
5. they return because Prism made the story easier to track

The current local product direction now supports that flow across:

- a newsroom-style homepage that is the definitive current-news front door
- an article-first story page with a distinct Perspective rail
- direct source links in the reporting stack and alternate-read sections
- optional account-backed save/follow sync, with browser-local tracking still available when readers stay signed out

Its core unit is the **Story**, not a link feed. Each story shows:

- what happened
- who is covering it
- how the coverage is framed across outlets
- what evidence is in view
- where to read another angle

Prism does not issue a single "neutral" verdict. It does not ask readers to trust an AI truth oracle. It makes the structure of coverage visible and keeps the methodology auditable.

Current product decisions locked in:

- the homepage is the live news surface; `Latest` and `Live` are secondary only
- the story page gives the reader the story first, then Perspective second
- homepage story packages should be fully clickable
- source reads go directly to original reporting when a real source URL exists
- when the lead source is likely paywalled or thin, Prism should surface a credible open alternate in the read stack when one exists
- story metadata should preserve lead-source plus open-alternate options so the pipeline, not just the UI, can reason about access and fallback quality
- Prism should not force source-wrapper detours unless they add clear reader value
- when Supabase-backed live data is available, connected Prism should surface real sourced stories only, not synthetic editorial stand-ins
- feed polling stays fast; article-page extraction runs in a dedicated enrichment worker instead of blocking ingest
- grounded story briefs should be persisted as versioned revisions and read from storage before the page falls back to inline brief assembly
- clustering is transitioning to a hybrid model: semantic candidate retrieval first, explicit merge guardrails second

## Core Concepts

- **Stories**: event-centered groupings of related coverage
- **Perspective Layer**: outlet attributes shown as sourced ranges, with disagreement visible
- **Context Packs**: small, curated alternate reads generated from reader-selected lenses
- **Evidence Ledger**: quoted sources, documents, and claims visible on the story page
- **Corrections Log**: versioned changes to clustering, outlet mappings, and context rules

## Documentation

| Document | Description |
|---|---|
| [DESIGN_BIBLE.md](./DESIGN_BIBLE.md) | Brand system, UI patterns, editorial interaction rules |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Architecture, stack, schema, roadmap, and delivery phases |
| [PRODUCT_STRATEGY.md](./PRODUCT_STRATEGY.md) | Positioning, wedge, funding model, and Harbor relationship |
| [ANTI_DRIFT_CONSTITUTION.md](./ANTI_DRIFT_CONSTITUTION.md) | Product and algorithm rules that prevent attention-market drift |
| [METRICS_STANDARD.md](./METRICS_STANDARD.md) | Allowed success metrics, safety constraints, and rollback rules |
| [PERSPECTIVE_SPEC.md](./PERSPECTIVE_SPEC.md) | Story clustering and Perspective engine specification |
| [DATA_MODEL_V1.md](./DATA_MODEL_V1.md) | Initial Supabase/Postgres data model baseline for real development |
| [CORE_LOOP_ACCEPTANCE.md](./CORE_LOOP_ACCEPTANCE.md) | Manual checklist for validating Prism's local story loop before hosted services are wired |
| [INGESTION_CONTENT_PLAN.md](./INGESTION_CONTENT_PLAN.md) | Automated source, ingestion, and media-rights plan for feeding Prism |
| [INGESTION_JOB_CATALOG.md](./INGESTION_JOB_CATALOG.md) | Concrete ingestion workers, cadence, and failure rules |
| [LAUNCH_SOURCE_REGISTRY.md](./LAUNCH_SOURCE_REGISTRY.md) | First controlled source set and onboarding order for Prism launch |
| [INFORMATION_ARCHITECTURE.md](./INFORMATION_ARCHITECTURE.md) | Reader-first nav, homepage, and section taxonomy redesign |
| [FRONT_PAGE_BENCHMARK.md](./FRONT_PAGE_BENCHMARK.md) | Ten-outlet mainstream homepage benchmark used to shape Prism's front page |
| [MASTHEAD_DIRECTIONS.md](./MASTHEAD_DIRECTIONS.md) | Three masthead/logo directions and the chosen live default |
| [STAGING_PLAN.md](./STAGING_PLAN.md) | Low-cost staging and hosting progression for early Prism development |
| [COMPONENT_SPEC.md](./COMPONENT_SPEC.md) | Component-level states and acceptance criteria for Prism reader surfaces |
| [LOCAL_DEVELOPMENT_MODEL.md](./LOCAL_DEVELOPMENT_MODEL.md) | Official local-first development posture, Node isolation policy, and service split |
| [VERCEL_BOOTSTRAP.md](./VERCEL_BOOTSTRAP.md) | Exact setup path for the initial Vercel-based preview deployment |
| [UI_UX_DIRECTION.md](./UI_UX_DIRECTION.md) | Visual direction derived from current mainstream product patterns |
| [AGENT_DEVELOPMENT_STRATEGY.md](./AGENT_DEVELOPMENT_STRATEGY.md) | Multi-agent build strategy for this repo |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Feature-branch, PR, and validation workflow for Prism development |

## Repository Shape

This repo is scaffolded as a lightweight monorepo:

- `src/web` — reader-facing web product
- `src/api` — ingestion, cluster, outlet, and subscription APIs
- `src/ml` — clustering, framing, and context-pack pipeline code
- `supabase/migrations` — early database migrations for the cheap staging path

The code scaffold is intentionally minimal. The doctrine set is the primary deliverable at this stage.

## Local Bootstrap

Core commands:

- `npm run dev`
- `npm run validate`
- `npm run dev:web:connected`
- `npm run dev:web:connected:web-only`
- `npm run ingest:local:scheduler`
- `npm run ingest:local:status`
- `npm run ingest:local:launchd:install`
- `npm run ingest:local:launchd:uninstall`
- `npm run refresh:live-feed`
- `npm run sync:stories`
- `npm run sources:upsert`
- `npm run ingest:feeds`
- `npm run ingest:feeds:raw`
- `npm run enrich:articles`
- `npm run brief:generate`
- `npm run brief:readiness`
- `npm run brief:grounding`
- `npm run brief:quality`
- `npm run perspective:generate`
- `npm run perspective:readiness`
- `npm run sources:health`
- `npm run cluster:candidates`

Environment baseline:

- copy `.env.example` into your local secret system or Doppler project
- this repo is now scoped locally to Doppler project `prism-wire` config `dev`
- `npm run validate` is the default pre-PR check: it builds the web app, compiles Python tooling, and runs the smoke suite, including the TypeScript Perspective/ranking regressions
- `npm run dev:web:connected` is now the preferred local real-news loop: it starts the connected app on `127.0.0.1:3002` and reruns `npm run ingest:feeds` on a fixed interval while the server is alive; the default attached cadence is conservative for casual development at one full ingest every 12 hours after a 30 minute startup delay, and you can still tune it with `PRISM_LOCAL_INGEST_INTERVAL_SECONDS` if needed
- `npm run dev:web:connected:web-only` keeps the older server-only behavior when you explicitly do not want the ingest loop
- `npm run ingest:local:scheduler` is the new always-on local ingest service: it runs raw feed discovery every 6 hours and the full ingest/enrich/brief/Perspective pipeline every 12 hours by default, with a 30 minute startup delay and 1 hour retry delay; a local lock prevents manual runs and background runs from overlapping, and this remains an intentional local-only bridge until Prism moves to a hosted worker/scheduler
- `npm run ingest:local:status` reads the local scheduler state from `.local/local-ingest/status.json` and shows last raw/full outcomes plus the next due windows
- `npm run ingest:local:launchd:install` writes and loads a macOS LaunchAgent so the scheduler can keep running in the background even when you are not holding open a terminal session; `npm run ingest:local:launchd:uninstall` removes it
- `npm run sync:stories` is now for explicit snapshot or manual sync work only; connected Prism should rely on real sourced stories
- `NEXT_PUBLIC_PRISM_READER_EMAIL_AUTH_MODE` controls the sync-page auth UI: keep it at `magic_link` for normal use, or temporarily set it to `otp` only when the Supabase email template is also switched to emit `{{ .Token }}` for code-entry testing
- `npm run sources:upsert` activates the current launch feed registry in Supabase
- `npm run ingest:feeds` is the default operator path: it now goes through the local ingest lock/status wrapper before running the full pipeline, so manual runs will wait rather than colliding with the attached dev loop or the always-on local scheduler
- `npm run ingest:feeds:raw` does the same for the fast discovery and story-sync-only pass
- `npm run enrich:articles` performs the slower article-page extraction pass for recent linked articles, upgrades Prism Brief inputs beyond feed snippets, and refreshes active story summaries after enrichment lands
- `npm run brief:generate` builds grounded story-brief revisions from enriched article inputs and advances the current brief revision for each active story when the input signature changes
- `npm run brief:readiness` reports which active live stories are still limited to early briefs, which have enough substantive sourcing for full Prism Briefs, and whether they already have a usable open alternate
- `npm run brief:grounding` audits current stored brief sections against their recorded support references so weak or unsupported brief language is visible before it ships
- `npm run brief:quality` combines readiness, grounding, support concentration, and text-quality heuristics into a sampled review report for active live stories; pass `--format markdown` after `--` when you want a human-review document instead of JSON
- `npm run perspective:generate` builds stored Perspective revisions plus Context Pack selections from current linked coverage and advances the current Perspective revision when the input signature changes
- `npm run perspective:readiness` reports which active live stories already have current Perspective revisions, which lenses are actually justified by the current source mix, and which stories still need manual Perspective review
- `npm run sources:health` reports which discovery sources are contributing recent articles, substantive extraction, and active story coverage versus just generating queue noise
- `npm run sources:health` now also shows open vs likely-paywalled article volume and highlights thin paywalled sources that still need better fallback handling
- enrichment now persists article-level access signals so the reader layer and the brief generator can distinguish open reads from likely paywalled ones using article evidence, not outlet lists alone
- active story metadata now only advertises lead-source confidence and open alternates when those reads clear a minimum quality floor; Prism does not surface weak alternates just because they are open
- automated live stories with a single weak source and no substantive extracted reporting are now pruned from the active live set instead of shipping one-sentence placeholder briefs
- Perspective now uses stored revisions and generated Context Packs in connected mode, with quality gating so only lenses justified by the current source mix populate reads while the UI still shows the full launch lens set
- `npm run cluster:candidates` reports how well semantic candidate retrieval covers the current heuristic clusters and validates the offline regression fixtures
- clustering now shares canonical URL normalization across ingest, sync, and evaluation so tracking parameters and alias domains do not fragment stories
- sitemap-derived items are now demoted unless they have substantive extracted text or enough source breadth to support a reader-facing story shell
- `PRISM_EMBEDDING_PROVIDER` currently supports `hashing`, `sentence-transformers`, and `openai`; local development should stay on `hashing` unless a real provider is configured
- the current source upsert path activates Bloomberg, FT, AP, Reuters, and Politico sitemap discovery; Reuters and AP now use source-specific filtering, while Politico remains low-yield under the current strict allowlist
- keep the initial hosted path aligned to `Vercel + Supabase + Upstash + GitHub Actions`
- keep local development aligned to [LOCAL_DEVELOPMENT_MODEL.md](./LOCAL_DEVELOPMENT_MODEL.md)
- when you create the Vercel project, set the root directory to `src/web`
- `npm run refresh:live-feed` remains a manual fallback-only snapshot generator for UI mode; the old scheduled GitHub snapshot refresher has been retired

## Why Prism Exists

Modern information systems optimize for arousal, tribal sorting, and compulsive refresh behavior. Prism is built to optimize for:

- clarity
- context
- inspectability
- reader agency

Prism is also the commercial proving ground for Harbor's broader Perspective engine. The product must stand on its own as a subscription news utility, while financing and validating infrastructure that later powers Harbor's civic experience.
