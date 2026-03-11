# Prism Staging Plan
### Version 0.1

---

## 0. Decision Summary

If the goal is **the lowest possible spend that still lets Prism move forward**, the best answer is:

- **Doppler** for secrets
- **Supabase Free** for early Postgres
- **Upstash Free** for Redis-style cache / queue primitives
- **Vercel Hobby** for the first preview environment
- **GitHub Actions** for scheduled ingestion and snapshot generation

That is the cheapest workable setup for early development and UI/product validation.

Once Prism needs an **always-on Node API or worker**, the best low-cost move is:

- keep **Supabase + Upstash + Doppler**
- move app compute to **Fly.io**

If forced to pick **one paid host** today for the app layer, choose **Fly.io over Railway** on cost predictability.

---

## 1. Constraints

Current constraints:

- very limited development budget
- an existing VPS with `2 GB` RAM already carrying other projects
- no need to run the full Prism stack 24/7 yet
- priority is product iteration, design validation, and staged proof of live content

This means the wrong move is standing up:

- a full always-on web + API + worker + Postgres + Redis stack immediately
- a single-box deployment on the existing VPS
- a staging environment that behaves like production before the product surface is proven

---

## 2. Recommended Path

### Phase 1: Preview Staging

Use this while Prism is still design-heavy and product-shaping.

**Topology**

```text
Vercel Hobby
  - Next.js web app
  - lightweight route handlers if needed

Supabase Free
  - primary Postgres

Upstash Free
  - cache / queue / rate-limit primitives

GitHub Actions
  - scheduled feed pulls
  - snapshot generation
  - lightweight enrichment jobs

Doppler
  - dev / staging / prod secrets
```

**What runs here**

- homepage
- cluster detail page
- live feed prototype
- basic read APIs
- scheduled content snapshots
- light editorial/admin tooling

**What does not run here**

- BullMQ-style always-on workers
- long-lived Fastify processes
- continuous ingestion daemons
- heavy clustering or NLP workloads

**Why this is the cheapest fit**

- Vercel Hobby is free, but restricted to personal, non-commercial use
- Supabase Free gives you two free projects and a `500 MB` database per project
- Upstash Free gives one free Redis database with `256 MB` and `500K` commands per month
- GitHub Actions is free on public repos, and private repos get included minutes on GitHub Free

This is the lowest-cost setup that still feels like a real staged product.

### Phase 2: Integrated Staging

Move here when Prism needs a real backend service.

**Topology**

```text
Fly.io
  - web app and/or API container
  - autostop/autostart enabled

Supabase
  - stay on Free or move to paid compute only when needed

Upstash
  - keep Redis external

GitHub Actions
  - scheduled ingestion continues

Doppler
  - service-token driven env delivery
```

**Starter shape**

- 1 Fly app
- `shared-cpu-1x`
- `512 MB` or `1 GB` RAM
- `auto_stop_machines = "stop"`
- `auto_start_machines = true`
- `min_machines_running = 0` for cheapest staging

**Why Fly is the next step**

- Fly pricing on `shared-cpu-1x` is currently about `$1.94/month` at `256 MB`, `$3.19/month` at `512 MB`, and `$5.70/month` at `1 GB`
- stopped machines do not incur CPU/RAM charges
- autostop/autostart is built for low-traffic services
- it supports the kind of always-on Node server that Vercel is not meant for

This is the cheapest realistic path once Prism needs a durable API process.

### Phase 3: Real Shared Staging

Move here only after the product loop is working.

**Shape**

- Fly.io or another chosen app host for web + API
- managed Postgres outside Supabase if staging/prod convergence demands it
- Upstash or another managed Redis
- a separate worker process for ingestion and clustering

**Trigger conditions**

- staging is used by multiple people regularly
- live ingestion is running on a schedule throughout the day
- schema migrations and data retention matter
- Supabase Free pauses or storage limits become operationally annoying
- the app needs long-lived backend jobs

---

## 3. Host Recommendation

### Most economical choice right now

For the next stage of Prism, the most economical choice is:

1. **Vercel Hobby** for preview hosting
2. **Supabase Free** for Postgres
3. **Upstash Free** for Redis-like needs
4. **GitHub Actions** for scheduled ingestion
5. **Doppler** for secrets

That is the cheapest arrangement that still fits the bill.

### Most economical paid host once you need a real server

If you need a single paid host for the app layer, choose:

- **Fly.io**

Reason:

- lower small-instance cost than starting a real always-on stack on Railway
- explicit autostop/autostart behavior
- better fit for Prism's likely Fastify + worker shape
- easier to reason about than trying to keep Railway asleep while holding DB connections

### Why not Railway first

Railway is valid, but it is not my cost-first choice here.

Current Railway pricing is:

- `Free`: `$0/month` with `$1` of resources
- `Hobby`: `$5/month`
- resource pricing: `$10 / GB / month` RAM and `$20 / vCPU / month`

Their serverless sleep feature can reduce cost, but their docs are explicit that a service may stay awake because of:

- active database connections
- framework telemetry
- outbound traffic
- private-network traffic

That is workable, but it makes spend less predictable for a project that will eventually have DB-backed APIs and ingestion behavior.

### Why not Render free

Render free is fine for throwaway previews, but not the main Prism staging path.

Their current docs say:

- free web services spin down after `15 minutes` idle
- free Postgres expires after `30 days`
- free Postgres has no backups

That is too disposable for Prism's staged development.

---

## 4. Budget Targets

### Phase 1 target

Expected incremental infrastructure spend:

- `Vercel Hobby`: `$0`
- `Supabase Free`: `$0`
- `Upstash Free`: `$0`
- `GitHub Actions`: `$0` on a public repo, otherwise constrained by included minutes
- `Doppler`: likely `$0` incremental if you are already using the Developer plan baseline

**Target:** `~$0/month` to very low single digits

### Phase 2 target

Expected incremental infrastructure spend:

- `Fly.io`: about `$3 to $6/month` for a small app machine if it runs continuously, potentially less with autostop
- `Supabase`: still `$0` if Free remains acceptable
- `Upstash`: still `$0` if Free remains acceptable

**Target:** `~$3 to $10/month`

### Phase 3 target

This is the first stage where real monthly cost creep begins.

The cost drivers will be:

- a paid database tier
- a real worker process
- media storage and image processing
- higher ingestion frequency

Do not enter this phase until the product surface is clearly worth it.

---

## 5. Supabase Position

Supabase is a good early-development database home for Prism.

Use it as:

- managed Postgres
- connection pooler
- simple admin surface

Do **not** build Prism so that it depends on Supabase-specific features unless they clearly save time.

Preferred posture:

- schema and migrations stay in the repo
- application code owns business logic
- auth, storage, edge functions, and realtime are optional rather than assumed

That keeps the migration path open when staging and production converge on another host.

---

## 6. Doppler Position

Doppler should be the baseline secrets layer across all phases.

Recommended setup:

- `dev`, `staging`, and `prod` configs
- service tokens for deployed workloads
- `.env.example` committed for repo clarity

Do not tie deployed environments to personal tokens.

---

## 7. Operational Rules

1. Do not run always-on ingestion in early staging.
2. Use scheduled pulls and snapshot generation first.
3. Keep the public-facing app online before you keep background machinery online.
4. Keep Postgres managed before you self-host databases.
5. Treat the existing `2 GB` VPS as unrelated infrastructure, not Prism's default staging home.

---

## 8. Migration Triggers

Move from **Vercel Hobby** to **Fly.io** when any of these become true:

- Prism needs a long-lived Fastify API
- you want BullMQ or Redis-backed workers
- you need persistent server-side processes
- the environment is no longer purely personal / non-commercial

Move from **Supabase Free** to a paid or different Postgres host when:

- the `500 MB` limit becomes tight
- pauses become disruptive
- staging data needs to stay reliably warm
- connection/concurrency limits start shaping product behavior

Move from **scheduled jobs** to **real workers** when:

- clustering quality depends on frequent updates
- feeds need near-real-time freshness
- enrichment pipelines are too slow for cron-only execution

---

## 9. Concrete Recommendation For Prism

Use this order:

1. Keep **local development** as the main engineering environment.
2. Put **preview/staging** on **Vercel Hobby** first.
3. Use **Supabase Free** and **Upstash Free** underneath it.
4. Run ingestion through **GitHub Actions** on a schedule.
5. Move app compute to **Fly.io** only when a real API/worker is needed.

That is the lowest-cost path that still lets Prism become a credible staged product.

---

## 10. Sources

- Doppler pricing: https://www.doppler.com/pricing
- Doppler service tokens: https://docs.doppler.com/docs/service-tokens
- Doppler CLI: https://docs.doppler.com/docs/cli
- Supabase billing and free plan: https://supabase.com/docs/guides/platform/billing-on-supabase
- Supabase compute sizes: https://supabase.com/docs/guides/platform/compute-add-ons
- Supabase free-project restore behavior: https://supabase.com/changelog?next=Y3Vyc29yOnYyOpK0MjAyNC0wNy0yNFQwMDo1MjoxN1rOAGpbsQ%3D%3D&restPage=2
- Fly.io pricing: https://fly.io/docs/about/pricing/
- Fly.io autostop/autostart: https://fly.io/docs/launch/autostop-autostart/
- Railway pricing: https://docs.railway.com/pricing
- Railway serverless sleep behavior: https://docs.railway.com/reference/app-sleeping
- Render free-tier limits: https://render.com/docs/free
- Upstash pricing: https://upstash.com/docs/redis/overall/pricing
- Vercel pricing: https://vercel.com/pricing
- Vercel Hobby plan: https://vercel.com/docs/plans/hobby
- Vercel limits: https://vercel.com/docs/limits
- Vercel cron jobs: https://vercel.com/docs/cron-jobs/
- GitHub Actions billing: https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions
