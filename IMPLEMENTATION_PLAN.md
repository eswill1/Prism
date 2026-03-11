# Prism Implementation Plan
### Version 0.2 — Updated 2026-03-11: Harbor-style phase roadmap with checkbox tracking

---

## 0. Guiding Technical Principles

1. **Clarity over novelty.** The system exists to orient readers quickly, not maximize content throughput.
2. **The Perspective layer must be auditable.** Every material label, range, and cluster decision must be traceable.
3. **Corrections are product infrastructure.** Versioning and correction logs are part of the core system, not post-launch cleanup.
4. **Reader-facing calm requires backend rigor.** The UI should feel simple because the data pipeline is explicit, not because complexity is hidden.
5. **Subscriptions shape architecture.** Build for trust, institutional accounts, and continuity, not ad-ops complexity.

---

## 1. Proposed Stack

### 1.1 Web

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Next.js 15 | App Router, SSR, and fast editorial pages |
| Styling | CSS variables + modular global styles | Easy alignment with the design system |
| UI state | Zustand | Small, explicit client state surface |
| Animation | Framer Motion | Restrained transitions where needed |

### 1.2 API

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Node.js 22 + TypeScript | Matches Harbor's stack and team assumptions |
| API framework | Fastify | Fast, typed, operationally simple |
| Database | PostgreSQL 16 | Structured relational core with JSONB for audit payloads |
| Cache / queue | Redis / BullMQ | Cluster refresh jobs, feed polling, notification jobs |

### 1.3 ML and Data Pipeline

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Best fit for clustering and NLP tooling |
| Similarity + clustering | Sentence Transformers + rule-based merge logic | Good balance of quality and inspectability |
| Labeling helpers | Lightweight classifiers with audit output | Explanations stay inspectable |
| Data orchestration | Scheduled workers and CLI jobs | Simpler than introducing a heavy orchestrator in v1 |

---

## 2. Monorepo Layout

```text
src/
  api/
  web/
  ml/
```

Top-level doctrine docs remain at repo root so product principles stay visible.

---

## 3. Primary Services

### 3.1 Ingestion Service

Responsibilities:

- pull or receive article feeds
- normalize URLs and domain data
- extract article metadata
- deduplicate obvious repeats

### 3.2 Cluster Service

Responsibilities:

- create and update Story Clusters
- compute canonical cluster titles and summaries
- log merges, splits, and major updates

### 3.3 Perspective Service

Responsibilities:

- maintain outlet registry
- attach rater-source data
- build coverage structure
- generate Context Packs
- expose methodology and version data

### 3.4 Reader API

Responsibilities:

- serve cluster stream and cluster detail
- serve Perspective panels and Context Packs
- handle subscriptions, saved clusters, and notifications

---

## 4. Data Model Priorities

V1 schema should include:

- users
- institutions
- saved_clusters
- outlets
- articles
- story_clusters
- cluster_articles
- context_pack_items
- evidence_items
- correction_events
- version_registry

Institutional plans and saved clusters matter early because they align with the business model and the product loop.

---

## 5. API v1

### Public read APIs

- `GET /api/health`
- `GET /api/clusters`
- `GET /api/clusters/:slug`
- `GET /api/clusters/:slug/perspective`
- `GET /api/clusters/:slug/context-pack`
- `GET /api/clusters/:slug/corrections`
- `GET /api/methodology/perspective`

### Authenticated APIs

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/user/me`
- `POST /api/clusters/:slug/save`
- `DELETE /api/clusters/:slug/save`
- `POST /api/subscriptions/checkout`

### Admin / ops APIs

- `POST /api/admin/outlets/refresh`
- `POST /api/admin/clusters/rebuild`
- `GET /api/admin/corrections`
- `POST /api/admin/corrections`

---

## 6. Phase Roadmap

### Phase 1: Preview Foundation (Months 1–2)
**Goal: A Vercel-ready Prism preview with the core reader surfaces, live snapshot loop, and low-cost staging discipline in place.**

#### Deliverables:
- [x] Doctrine set and repo scaffold
- [x] Local Next.js reader shell
- [x] Homepage, cluster detail page, and live prototype surface
- [x] Web-native preview APIs under `src/web/src/app/api`
- [x] Temporary live feed generator with heuristic clustering
- [x] Live snapshot output written into `src/web/public/data` for Vercel-safe deploys
- [x] `.env.example`, Node version pinning, and GitHub workflow baseline
- [x] Doppler / Vercel / Supabase / Upstash assumptions documented
- [x] Low-cost staging plan and Vercel bootstrap docs
- [ ] First hosted Vercel preview deployment
- [ ] Doppler `staging` config wired into hosted preview
- [ ] Supabase preview project created and connected

#### Success metrics:
- Homepage, cluster detail, and `/live` all render locally without the Fastify API
- `npm run build:web` passes cleanly
- `/api/health` and `/api/live` return healthy preview responses
- First hosted preview URL is online

#### Team: 1 engineer, 1 design/product lead

---

### Phase 2: Reader MVP (Months 3–5)
**Goal: Turn the preview into a credible newsroom-grade cluster reader, not just a static mockup.**

#### Deliverables:
- [x] Cluster detail prototype with evidence, corrections, and context modules
- [x] Real-media cluster cards with fallback handling in the live prototype
- [ ] Source registry admin seed tooling
- [ ] Data-backed homepage and cluster list
- [ ] Perspective panel v1 backed by real outlet data
- [ ] Methodology page shell
- [ ] Saved clusters
- [ ] Reader account scaffolding
- [ ] Subscriber pricing and subscription shell

#### Success metrics:
- New users can explain the purpose of a Story Cluster within 2 minutes of landing
- Cluster detail page is the clear hero surface in product feedback
- Live prototype consistently surfaces enough fresh linked coverage to feel active
- Reader testing confirms the interface feels inspectable rather than overwhelming

#### Team: 1–2 engineers, 1 designer

---

### Phase 3: Content Pipeline and Persistence (Months 6–8)
**Goal: Replace temporary feeds and mock records with a durable, automated content substrate that still fits cheap staging.**

#### Deliverables:
- [x] Scheduled GitHub Actions live snapshot refresh
- [x] Temporary URL deduplication and heuristic clustering pass
- [ ] Feed ingestion adapters beyond the temporary snapshot script
- [ ] News sitemap ingestion
- [ ] Canonical URL normalization pipeline
- [ ] Outlet registry seed import
- [ ] Supabase-backed article, outlet, cluster, evidence, and version tables
- [ ] Correction and version event persistence
- [ ] Media-rights policy enforcement in the ingestion pipeline
- [ ] Scheduled enrichment jobs beyond the temporary live snapshot

#### Success metrics:
- Most surfaced stories arrive through automated ingestion rather than manual seeding
- Duplicate story handling is acceptable under manual QA
- Preview/staging content refreshes on a predictable cadence
- Corrections and outlet mappings are stored, not just rendered

#### Team: 2 engineers, 1 designer

---

### Phase 4: Perspective Engine and Paid Proof (Months 9–12)
**Goal: Make Prism's differentiator operational: inspectable coverage structure, auditable methodology, and a first paid reader value loop.**

#### Deliverables:
- [ ] Framing presence group generation
- [ ] Context Pack generation for all four launch lenses
- [ ] Methodology pages and version registry
- [ ] Perspective firewall tests
- [ ] Morning and evening briefing generation
- [ ] Follow alerts and topic following
- [ ] Subscriber-only monitoring and briefing features
- [ ] Payment and account workflows
- [ ] Fly.io migration for always-on API or worker workloads

#### Success metrics:
- Readers use alternate lenses and Context Packs repeatedly
- Methodology and correction surfaces are visible enough to build trust
- Early subscribers demonstrate willingness to pay for clarity and monitoring value
- No Perspective data leaks into ranking or recommendation logic

#### Team: 2–4 engineers, 1 data/ML engineer, 1 designer

---

### Phase 5: Institutional and Harbor Integration (Months 13–18)
**Goal: Turn Prism into durable infrastructure that funds itself and can safely power Harbor's Perspective layer later.**

#### Deliverables:
- [ ] Institutional account management
- [ ] Team, school, library, and workplace provisioning
- [ ] Admin reporting and usage controls
- [ ] Public transparency reporting
- [ ] Correction and outlet-dispute workflows
- [ ] Shared Perspective service contracts for Harbor
- [ ] Export and audit interfaces for institutional users
- [ ] Production hosting convergence beyond the early Supabase preview posture

#### Success metrics:
- First institutional pilots are live
- Correction turnaround is operationally reliable
- Harbor can consume shared Perspective services without ranking contamination
- Prism has a credible path from paid reader product to public-trust infrastructure

#### Team: 3–5 engineers, 1 designer, 1 PM

---

## 7. Development Progression

Development should progress in commercial order, not just technical order.

### Step 1: Prove the hero surface

Build first:

- cluster detail page
- Perspective panel
- evidence ledger
- correction ribbon
- real-media cluster cards with fallback states

If this surface is not compelling, the rest of the system does not matter.

### Step 2: Prove the cheap hosted loop

Before standing up a real backend, prove that Prism can feel alive on cheap infrastructure.

Build:

- Vercel-hosted preview deployment
- GitHub Actions live feed refresh
- Supabase-backed schema draft
- Doppler-managed staging secrets

If this loop is too brittle, fix it before adding always-on services.

### Step 3: Prove automated intake

Once the surface works, build:

- source registry
- feed and sitemap ingestion
- metadata extraction
- deduplication
- initial clustering

This gets Prism from mockup to a living product.

### Step 4: Prove repeat-use value

Then build:

- saved clusters
- follow-up alerts
- morning and evening briefings
- topic following

This is the first true retention layer.

### Step 5: Prove willingness to pay

Then ship:

- paywall and subscription flow
- pricing page
- subscriber-only briefing and monitoring features
- professional tier experiments

Revenue should come after the core value is visible, but before scaling ambition outruns proof.

### Step 6: Prove institutional fit

Then build:

- seat management
- team or classroom provisioning
- library and school deployment workflows
- admin reporting and compliance surfaces

This is where Prism becomes infrastructure rather than only an app.

---

## 8. Go-To-Market Dependencies

Each commercial motion depends on a product milestone.

| Motion | Product requirement |
|---|---|
| Individual launch | Cluster page + Perspective panel + enough live coverage to feel real |
| Paid conversion | Saved clusters, follow alerts, strong daily briefing value |
| Professional tier | Monitoring, exports, topic depth, audit history |
| Institutional sales | Admin controls, seat provisioning, methodology documentation |

---

## 9. Local Development Expectations

Root commands:

- `npm run dev`
- `npm run dev:web`
- `npm run dev:api`
- `npm run refresh:live-feed`

Python pipeline work is intentionally lightweight in this scaffold and can be run directly from `src/ml`.

Local defaults should match the first hosted path:

- `Doppler` for secrets
- `Vercel` for preview hosting
- `Supabase` for early Postgres
- `Upstash` for cache or queue primitives
- `GitHub Actions` for scheduled refresh jobs

---

## 10. Testing Plan

### API

- health and cluster endpoint smoke tests
- schema validation tests
- Perspective firewall assertion tests

### Web

- cluster page rendering tests
- Perspective panel interaction tests
- correction ribbon visibility tests

### ML

- clustering fixtures
- outlet mapping fixtures
- Context Pack reason-code tests

---

## 11. Open Questions for Later Phases

- which paid or licensed ingestion sources are required beyond RSS
- how much manual editorial review is needed for high-consequence clusters
- what level of institutional admin tooling is required at launch
- where Harbor should consume shared Perspective services versus shared data artifacts

These are intentionally deferred. The current goal is to establish the framework cleanly.
