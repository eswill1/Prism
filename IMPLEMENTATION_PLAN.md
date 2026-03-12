# Prism Implementation Plan
### Version 0.9 — Updated 2026-03-12: source-breadth and sitemap quality pass

---

## 0. Guiding Technical Principles

1. **Clarity over novelty.** The system exists to orient readers quickly, not maximize content throughput.
2. **The Perspective layer must be auditable.** Every material label, range, and cluster decision must be traceable.
3. **Corrections are product infrastructure.** Versioning and correction logs are part of the core system, not post-launch cleanup.
4. **Reader-facing calm requires backend rigor.** The UI should feel simple because the data pipeline is explicit, not because complexity is hidden.
5. **Subscriptions shape architecture.** Build for trust, institutional accounts, and continuity, not ad-ops complexity.
6. **Prove the core loop before broadening the product.** If Prism does not help a reader understand, inspect, save, and return to a story more effectively than ordinary news browsing, the rest of the roadmap does not matter.

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
| Similarity + clustering | Embedding-based candidate retrieval + rule-based merge guardrails | Good balance of quality and inspectability |
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

- create and update Stories
- compute canonical story titles and summaries
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

- serve story stream and story detail
- serve Perspective panels and Context Packs
- handle subscriptions, saved stories, and notifications

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

Institutional plans and saved stories matter early because they align with the business model and the product loop.

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
- [x] Homepage, story detail page, and fast-moving intake surface
- [x] Web-native preview APIs under `src/web/src/app/api`
- [x] Temporary live feed generator with heuristic clustering
- [x] Live snapshot output written into `src/web/public/data` for Vercel-safe deploys
- [x] Fast-moving story cards route into the shared story-detail surface
- [x] Story detail page includes a visible "what changed" timeline, not just static bullets
- [x] `.env.example`, Node version pinning, and GitHub workflow baseline
- [x] Doppler / Vercel / Supabase / Upstash assumptions documented
- [x] Low-cost staging plan and Vercel bootstrap docs
- [x] Core-loop acceptance checklist for manual user sessions
- [ ] First hosted Vercel preview deployment
- [ ] Doppler `staging` config wired into hosted preview
- [x] Supabase preview project created and connected

#### Success metrics:
- Homepage, story detail, and the fast-moving intake route all render locally without the Fastify API
- `npm run build:web` passes cleanly
- `/api/health` and `/api/live` return healthy preview responses
- A first-time reader can explain the story, inspect another angle, and find what changed in one session
- First hosted preview URL is online

#### Team: 1 engineer, 1 design/product lead

---

### Phase 2: Reader MVP (Months 3–5)
**Goal: Turn the preview into a credible newsroom-grade story reader, not just a static mockup.**

#### Deliverables:
- [x] Story detail prototype with evidence, corrections, and context modules
- [x] Real-media story cards with fallback handling in the live prototype
- [x] Source registry admin seed tooling
- [x] Data-backed homepage and story list
- [x] Homepage repositioned as the single real front door
- [x] Homepage story packages made fully clickable
- [x] Story page refocused around a first-party Prism Brief before Perspective
- [x] Perspective rail visually separated from the article column
- [x] Direct source links in "Reporting to read next" and "Also in the mix"
- [x] "Another angle" links rendered when source URLs are present
- [x] Connected reader surfaces restricted to real sourced live stories instead of synthetic editorial stand-ins
- [ ] Perspective panel v1 backed by real outlet data
- [x] Methodology page shell
- [x] Browser-local saved/followed story prototype
- [ ] Saved stories
- [ ] Follow story updates
- [ ] Reader account scaffolding
- [x] Subscriber pricing and subscription shell
- [ ] Core-loop user testing with a small serious-reader cohort

#### Success metrics:
- New users can explain the purpose of a Prism story within 2 minutes of landing
- Story detail page is the clear hero surface in product feedback
- The homepage consistently surfaces enough fresh linked coverage to feel active without splitting the product into two front doors
- Story pages give readers enough narrative to stay on-site before deciding whether to open original reporting
- Reader testing confirms the interface feels inspectable rather than overwhelming
- At least some users choose to save or follow stories because they want to come back

#### Team: 1–2 engineers, 1 designer

---

### Phase 3: Content Pipeline and Persistence (Months 6–8)
**Goal: Replace temporary feeds and mock records with a durable, automated content substrate that still fits cheap staging.**

#### Deliverables:
- [x] Scheduled GitHub Actions live snapshot refresh
- [x] Temporary URL deduplication and heuristic clustering pass
- [x] Feed ingestion adapters beyond the temporary snapshot script
- [x] Dedicated article-enrichment worker decoupled from feed polling
- [x] Default manual ingest path now chains enrichment automatically after feed polling
- [x] News sitemap ingestion
- [x] Source-specific sitemap handling for Reuters and AP
- [x] Canonical URL normalization pipeline
- [x] Semantic candidate-retrieval scaffold for story clustering
- [x] Candidate-retrieval evaluation harness against current heuristic clusters
- [x] Embedding-provider abstraction beyond local hashing fallback
- [x] Semantic similarity integrated into merge scoring behind deterministic guardrails
- [x] Offline clustering regression fixtures for known positive and negative merge cases
- [x] Article extraction beyond RSS summaries: ledes, first paragraphs, and named-entity capture
- [x] Source-grounded brief input records stored per story revision
- [x] Early-brief gating for one-source stories so single-source pages do not pretend to be full Prism Briefs
- [x] Brief-readiness evaluator for active live stories
- [x] Stored grounded brief revisions wired into the story read path
- [x] Automated brief-grounding evaluator for stored brief sections
- [ ] Brief quality evaluation harness with sampled human review
- [x] Outlet registry seed import
- [x] Supabase-backed article, outlet, cluster, evidence, and version tables
- [x] Correction and version event persistence
- [ ] Media-rights policy enforcement in the ingestion pipeline
- [ ] Scheduled enrichment jobs beyond the temporary live snapshot
- [x] Source-health reporting for active discovery inputs
- [ ] Saved/followed story state backed by real persistence
- [x] Editorial seed stories removed from connected reader surfaces instead of shipping fake source-link affordances

#### Success metrics:
- Most surfaced stories arrive through automated ingestion rather than manual seeding
- Feed polling stays fast enough to feel live because article extraction is no longer inline in the polling loop
- Active discovery is no longer RSS-only; verified sitemap feeds can contribute to the live story graph
- Reuters and AP now contribute through source-specific sitemap handling instead of generic sitemap parsing alone
- Duplicate story handling is acceptable under manual QA
- Semantic candidate retrieval meaningfully narrows cluster choices before deterministic merge rules fire
- Canonical URL cleanup reduces story fragmentation caused by tracking parameters and alias domains
- Sitemap-derived story shells do not surface reader-facing one-line summaries just because a title was discoverable
- Discovery sources can be ranked by recent substantive yield instead of only by anecdotal inspection
- Preview/staging content refreshes on a predictable cadence
- Corrections and outlet mappings are stored, not just rendered
- Returning users see meaningful "what changed" state on followed stories
- All reader-facing source stacks link to real publisher URLs or clearly indicate that no source URL exists

#### Team: 2 engineers, 1 designer

---

### Phase 4: Perspective Engine and Paid Proof (Months 9–12)
**Goal: Make Prism's differentiator operational: inspectable coverage structure, auditable methodology, and a first paid reader value loop.**

#### Deliverables:
- [ ] Framing presence group generation
- [ ] Context Pack generation for all four launch lenses
- [x] Grounded multi-source Prism Brief generation backed by extracted source text rather than feed snippets
- [x] Prism Brief expansion so mature story pages routinely deliver fuller multi-paragraph briefs rather than minimum viable summaries
- [x] Paywall-aware alternate-source matching when the strongest available source is too thin or inaccessible to the reader
- [ ] Methodology pages and version registry
- [ ] Perspective firewall tests
- [ ] Morning and evening briefing generation
- [ ] Follow alerts and topic following
- [ ] Saved-story history with visible narrative and Perspective deltas over time
- [ ] Major-story Live Tracker surface with rolling source updates and a lighter-weight live Perspective treatment
- [ ] Subscriber-only monitoring and briefing features
- [ ] Payment and account workflows
- [ ] Fly.io migration for always-on API or worker workloads

#### Immediate next branch:
- [x] Add brief-depth rules so mature multi-source stories target fuller multi-paragraph Prism Briefs instead of minimum viable summary text
- [x] Build paywall-aware alternate-source matching using existing discovery and clustering signals so inaccessible lead sources can point to credible open reporting
- [x] Use `sources:health` plus `brief:readiness` as the tuning loop for this branch, with the explicit goal of raising full-brief-ready story count without lowering source quality
- [x] Move paywall/open-alternate handling upstream so active story metadata stores lead-source and open-alternate options instead of leaving access logic entirely to the reader layer
- [x] Add section-level support metadata plus `brief:grounding` so stored briefs can be audited for weak or unsupported language

#### Success metrics:
- Readers use alternate lenses and Context Packs repeatedly
- Methodology and correction surfaces are visible enough to build trust
- Early subscribers demonstrate willingness to pay for clarity and monitoring value
- Mature multi-source stories usually produce briefs that can stand on their own without forcing an immediate outbound click
- Thin or gated source mixes should still leave the story with a usable open fallback path recorded in metadata when the cluster has one
- Paywalled-source stories still retain usable reader value because Prism can surface a credible open alternative when available
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

### Step 1: Prove the core loop

Before expanding breadth, prove this sequence:

- a reader opens a story
- understands the story quickly
- inspects another angle, evidence item, or change note
- saves or follows the story
- returns because Prism is the easiest place to see what changed

If this loop is weak, stop broadening the product and fix it first.

### Step 2: Upgrade clustering without losing auditability

Prism should not keep accreting hand-written merge rules forever.

The intended progression is:

- deterministic normalization and URL hygiene
- semantic candidate retrieval over enriched article text
- semantic similarity folded into merge scoring behind explicit thresholds
- explicit merge and split guardrails
- audited versioning for material clustering changes

The system should prefer ML for inference and rules for boundaries.

### Step 2: Prove the hero surface

Build first:

- story detail page
- story-first Prism Brief body
- direct source-read stack
- Perspective panel
- evidence ledger
- correction ribbon
- real-media story cards with fallback states

If this surface is not compelling, the rest of the system does not matter.

### Step 3: Prove the cheap hosted loop

Before standing up a real backend, prove that Prism can feel alive on cheap infrastructure.

Build:

- Vercel-hosted preview deployment
- GitHub Actions live feed refresh
- Supabase-backed schema draft
- Doppler-managed staging secrets

If this loop is too brittle, fix it before adding always-on services.

### Step 4: Prove automated intake

Once the surface works, build:

- source registry
- feed and sitemap ingestion
- metadata extraction
- article text extraction for brief generation
- separate article enrichment so feed polling stays fast
- deduplication
- initial clustering

This gets Prism from mockup to a living product.

### Step 4.5: Prove brief quality

Before shipping model-generated briefs broadly, build:

- source-grounded brief inputs per story
- one-source early-brief rules
- multi-source brief generation
- live-story readiness reporting so the team can see which stories qualify for full briefs versus early briefs
- automated grounding evaluation against stored section support
- sampled human QA and regression checks

If the brief is not materially better than a normal RSS summary, the feature is not ready.

### Step 5: Prove repeat-use value

Then build:

- saved stories
- follow-up alerts
- morning and evening briefings
- topic following

This is the first true retention layer.

### Step 6: Prove willingness to pay

Then ship:

- paywall and subscription flow
- pricing page
- subscriber-only briefing and monitoring features
- professional tier experiments

Revenue should come after the core value is visible, but before scaling ambition outruns proof.

### Step 7: Prove institutional fit

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
| Individual launch | Story page + Perspective panel + enough live coverage to feel real |
| Paid conversion | Saved stories, follow alerts, strong daily briefing value |
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

Official local posture:

- develop locally on the MacBook first
- do not change the global Node installation for other repos
- use project-level Node 22 isolation when needed
- do not run the full stack locally by default
- use remote managed services instead of local Postgres/Redis unless a task explicitly requires otherwise
- deploy to Vercel only for reviewable preview checkpoints

---

## 10. Testing Plan

### API

- health and story endpoint smoke tests
- schema validation tests
- Perspective firewall assertion tests

### Web

- story page rendering tests
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
- what thresholds should promote a story into a dedicated Live Tracker surface
- how saved-story history should show narrative change versus Perspective change without becoming noisy

These are intentionally deferred. The current goal is to establish the framework cleanly.
