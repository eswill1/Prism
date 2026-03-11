# The Prism Wire

> A serious, newsroom-grade news product built to make coverage transparent,
> inspectable, and useful without asking readers to trust a hidden consensus.

Prism exists to help people understand what is happening without turning disagreement into spectacle.

Its core unit is the **Story Cluster**, not a link feed. Each cluster shows:

- what happened
- who is covering it
- how the coverage is framed across outlets
- what evidence is in view
- where to read another angle

Prism does not issue a single "neutral" verdict. It does not ask readers to trust an AI truth oracle. It makes the structure of coverage visible and keeps the methodology auditable.

## Core Concepts

- **Story Clusters**: event-centered groupings of related coverage
- **Perspective Layer**: outlet attributes shown as sourced ranges, with disagreement visible
- **Context Packs**: small, curated alternate reads generated from reader-selected lenses
- **Evidence Ledger**: quoted sources, documents, and claims visible on the cluster page
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
| [INGESTION_CONTENT_PLAN.md](./INGESTION_CONTENT_PLAN.md) | Automated source, ingestion, and media-rights plan for feeding Prism |
| [INGESTION_JOB_CATALOG.md](./INGESTION_JOB_CATALOG.md) | Concrete ingestion workers, cadence, and failure rules |
| [STAGING_PLAN.md](./STAGING_PLAN.md) | Low-cost staging and hosting progression for early Prism development |
| [VERCEL_BOOTSTRAP.md](./VERCEL_BOOTSTRAP.md) | Exact setup path for the initial Vercel-based preview deployment |
| [UI_UX_DIRECTION.md](./UI_UX_DIRECTION.md) | Visual direction derived from current mainstream product patterns |
| [AGENT_DEVELOPMENT_STRATEGY.md](./AGENT_DEVELOPMENT_STRATEGY.md) | Multi-agent build strategy for this repo |

## Repository Shape

This repo is scaffolded as a lightweight monorepo:

- `src/web` — reader-facing web product
- `src/api` — ingestion, cluster, outlet, and subscription APIs
- `src/ml` — clustering, framing, and context-pack pipeline code

The code scaffold is intentionally minimal. The doctrine set is the primary deliverable at this stage.

## Local Bootstrap

Core commands:

- `npm run dev`
- `npm run refresh:live-feed`

Environment baseline:

- copy `.env.example` into your local secret system or Doppler project
- keep the initial hosted path aligned to `Vercel + Supabase + Upstash + GitHub Actions`
- when you create the Vercel project, set the root directory to `src/web`
- the scheduled refresh workflow writes the live snapshot into `src/web/public/data/temporary-live-feed.json`

## Why Prism Exists

Modern information systems optimize for arousal, tribal sorting, and compulsive refresh behavior. Prism is built to optimize for:

- clarity
- context
- inspectability
- reader agency

Prism is also the commercial proving ground for Harbor's broader Perspective engine. The product must stand on its own as a subscription news utility, while financing and validating infrastructure that later powers Harbor's civic experience.
