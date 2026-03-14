# Vercel Bootstrap
### Version 0.2 — Updated 2026-03-12: story-first preview checks aligned

Use this when you create the new GitHub repo and wire Prism into the first hosted preview environment.

---

## 1. Repo Baseline

Before connecting Vercel:

- create the new GitHub repository
- push this repo content into it
- keep `.env.example` as the documented variable list
- keep `.github/workflows/web-ci.yml` enabled
- keep local development aligned with `LOCAL_DEVELOPMENT_MODEL.md`

---

## 2. Vercel Project Settings

Create a new Vercel project from the GitHub repo and set:

- **Framework Preset**: `Next.js`
- **Root Directory**: `src/web`
- **Install Command**: `npm install`
- **Build Command**: `npm run build`
- **Output Directory**: leave default
- **Node.js Version**: `22.x`

Do not point Vercel at the repo root for the first hosted pass. The preview deployment should be the web app only.

---

## 3. Secrets and Environment

Use Doppler as the source of truth for:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL`
- `DIRECT_DATABASE_URL`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `PRISM_PUBLIC_SITE_URL`

Recommended environment split:

- `dev`
- `staging`
- `prod`

For the first Vercel setup, only `staging` needs to exist.

---

## 4. GitHub Workflows

One workflow is currently scaffolded for GitHub:

- `web-ci.yml`
  - installs dependencies
  - runs `npm run build:web`

The temporary live snapshot remains available as a manual local command via `npm run refresh:live-feed`, but the old scheduled GitHub snapshot refresher has been retired because this repo now prefers the real connected ingest path over direct snapshot commits to `main`.

---

## 5. First Deploy Checks

After Vercel is connected, verify:

- `/`
- `/stories/federal-budget-deadline`
- `/api/health`
- `/api/clusters`

Expected behavior:

- the homepage renders as the definitive current-news front door without needing the Fastify API
- the story page renders as an article-first Prism Brief with a distinct Perspective rail
- `/api/health` returns `ok: true`
- `/api/clusters` returns story data from the current preview data path

---

## 6. Do Not Add Yet

Do not add these on the first hosted pass:

- separate Fastify deployment
- always-on workers
- BullMQ
- self-hosted Postgres
- self-hosted Redis
- daily-development dependence on Vercel itself

The first hosted goal is product validation, not infrastructure completeness.

---

## 7. Promotion Trigger

Stay on the Vercel preview path until one of these becomes true:

- the preview needs a real long-lived backend process
- saved clusters and follow alerts need durable server logic
- ingestion and clustering need a persistent worker
- the preview is no longer just personal or internal staging

At that point, move app compute to Fly.io and keep the rest of the stack lean.
