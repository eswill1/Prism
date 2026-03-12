# Prism Local Development Model
### Version 0.2 — Updated 2026-03-12: connected story-first local development model

This document defines how Prism should be developed day to day during the early build phase.

The objective is to protect velocity, protect the MacBook, avoid unnecessary local infrastructure, and keep Prism aligned with its cheap preview-stage architecture.

---

## 1. Default Operating Model

Prism is a **local-first development project** with **remote managed services**.

That means:

- build the web product locally on the MacBook
- commit and push to GitHub as normal
- use Vercel only for milestone previews and selective review windows
- use Supabase for the database as needed
- use Doppler for secrets as needed
- do **not** run the full stack locally by default

This is the official development posture until Prism has proven the core loop and actually needs more infrastructure.

---

## 2. What Runs Where

### On the MacBook

Default local work should include:

- `src/web`
- selective local scripts
- temporary feed generation when needed
- UI review and product iteration
- connected story-page and homepage refinement against remote Supabase data when available

This machine is the primary product-development environment, not a miniature production cluster.

### On managed services

Use remote services for:

- Postgres via Supabase
- secrets via Doppler
- optional lightweight queue/cache primitives via Upstash later

### On Vercel

Use Vercel for:

- preview deployments
- partner/share links when a demo checkpoint is ready
- selective alpha-style preview windows only while still within the intended preview posture

Vercel is **not** the day-to-day runtime during development.

---

## 3. What We Do Not Run Locally By Default

Do not assume local development means all of these are running:

- local Postgres
- local Redis
- local Fastify API
- local always-on workers
- local ingestion daemons
- local full-stack Docker Compose

Those are exception modes, not the default.

If a specific task requires one of them, add it intentionally for that task only.

---

## 4. Supported Development Modes

### Mode A: UI Mode

Use when:

- working on layout
- refining component behavior
- testing mock or snapshot-backed flows

Run:

- local Next.js app only

This should be the most common mode in the early project.

### Mode B: Connected Mode

Use when:

- building DB-backed read flows
- testing real saved/follow state
- validating schema and API contracts

Run:

- local Next.js app
- remote Supabase data
- Doppler-backed secrets
- prefer `npm run dev:web:connected` from the repo root once Doppler is configured

This is the preferred mode for early real product work.

### Mode C: Pipeline Mode

Use when:

- testing ingestion scripts
- seeding source registries
- validating article normalization or clustering logic

Run:

- local targeted scripts only
- remote managed services where needed

This is still not full-stack local development.

### Mode D: Full Local Stack

Use only when a task clearly requires it.

Examples:

- debugging service-to-service behavior that cannot be isolated
- queue worker development that truly depends on local process orchestration
- migration or networking work that cannot be tested against managed services

This mode should be rare.

---

## 5. Node Version Policy

Prism targets **Node 22** at the project level.

That does **not** mean the MacBook's global Node installation should be changed.

Rules:

- do not replace the global Node used by other projects
- use a per-project version manager when Prism needs Node 22 locally
- keep `.nvmrc` as the Prism repo signal
- let other repos stay on their own Node versions

Acceptable tools:

- `nvm`
- `mise`
- `asdf`
- `volta`

The important rule is isolation by project, not one global Node version for the entire machine.

---

## 6. Vercel Usage Rule

Vercel is for **reviewable checkpoints**, not continuous daily development.

Use it when:

- a design or product checkpoint is worth sharing
- a partner-facing preview is ready
- a selective test window is needed

Do not use it as:

- the default daily dev environment
- the ingestion runner
- the always-on application backend

If Prism moves into real external alpha or commercial-facing usage, the hosting plan should move beyond Hobby.

---

## 7. Success Criteria For This Model

This development model is working when:

- local product work is fast and low-friction
- the other Node 20 project on the MacBook remains unaffected
- Prism can use Supabase and Doppler without needing local service sprawl
- Vercel deployments are occasional, intentional, and easy to understand

---

## 8. Immediate Practical Rule

Until there is a strong reason otherwise, assume this is how Prism is built:

1. develop locally
2. connect to managed services
3. deploy to Vercel only for preview checkpoints
4. avoid full local stack complexity

That is the working model.
