# The Prism Wire

> A serious, newsroom-grade news product built to make coverage transparent,
> inspectable, and useful without asking readers to trust a hidden consensus.

Prism exists to help people understand what is happening without turning disagreement into spectacle.

Current build priority:

- prove the core loop before broadening the product surface

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
- browser-local save/follow state while account persistence is still being built

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
- Prism should not force source-wrapper detours unless they add clear reader value

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
- `npm run dev:web:connected`
- `npm run refresh:live-feed`
- `npm run sync:stories`
- `npm run sources:upsert`
- `npm run ingest:feeds`

Environment baseline:

- copy `.env.example` into your local secret system or Doppler project
- this repo is now scoped locally to Doppler project `prism-wire` config `dev`
- `npm run sync:stories` upserts the current editorial seed stories plus the live snapshot into Supabase
- `npm run sources:upsert` activates the current launch feed registry in Supabase
- `npm run ingest:feeds` polls the active RSS feeds in Supabase and refreshes the automated live story set
- keep the initial hosted path aligned to `Vercel + Supabase + Upstash + GitHub Actions`
- keep local development aligned to [LOCAL_DEVELOPMENT_MODEL.md](./LOCAL_DEVELOPMENT_MODEL.md)
- when you create the Vercel project, set the root directory to `src/web`
- the scheduled refresh workflow writes the live snapshot into `src/web/public/data/temporary-live-feed.json`

## Why Prism Exists

Modern information systems optimize for arousal, tribal sorting, and compulsive refresh behavior. Prism is built to optimize for:

- clarity
- context
- inspectability
- reader agency

Prism is also the commercial proving ground for Harbor's broader Perspective engine. The product must stand on its own as a subscription news utility, while financing and validating infrastructure that later powers Harbor's civic experience.
