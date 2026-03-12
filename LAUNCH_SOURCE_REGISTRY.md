# Prism Launch Source Registry
### Version 0.1

This document narrows Prism's first source set for Phase 1-3 development.

It is not the full future outlet universe.
It is the first controlled launch registry that Prism can realistically ingest, compare, and maintain.

---

## 1. Launch Principles

The launch source set should be:

- broad enough to make clusters feel real
- narrow enough to onboard carefully
- diverse across source families and geographies
- weighted toward reliable machine-readable discovery paths

Prism does not need hundreds of outlets to start.
It needs a trustworthy first 20 to 30.

---

## 2. Launch Tiers

### Tier 1: Running in prototype now

These sources are already active in the temporary live feed generator.

| Outlet | Domain | Role | Discovery method | Launch status |
|---|---|---|---|---|
| NPR | `npr.org` | US public media baseline | RSS | Running in prototype |
| BBC News | `bbc.com` / `bbc.co.uk` | International baseline | RSS | Running in prototype |
| PBS NewsHour | `pbs.org` | Public-service and explainer coverage | RSS | Running in prototype |
| Wall Street Journal World | `wsj.com` | International and business angle | RSS | Running in prototype |

These are the best starting point because they already exercise the live snapshot loop.

### Tier 2: Launch-core onboarding set

These should be the first real expansion set for Prism's source registry.

| Outlet | Domain | Role in Prism | Discovery target | Rights posture target |
|---|---|---|---|---|
| Associated Press | `apnews.com` | Wire baseline and cluster backbone | RSS / sitemap / licensed feed later | Pointer metadata now, licensed media later |
| Reuters | `reuters.com` | Wire baseline and international coverage | RSS / sitemap | Pointer metadata |
| Bloomberg | `bloomberg.com` | Markets and business consequence layer | Sitemap / metadata API backup | Pointer metadata |
| Financial Times | `ft.com` | International business and policy framing | Sitemap / metadata API backup | Pointer metadata |
| Politico | `politico.com` | US policy process coverage | RSS / sitemap | Pointer metadata |
| The Hill | `thehill.com` | Congressional and policy process coverage | RSS / sitemap | Pointer metadata |
| The Guardian | `theguardian.com` | International and UK/US comparative framing | RSS / sitemap | Pointer metadata |
| Al Jazeera English | `aljazeera.com` | Non-US international framing | RSS / sitemap | Pointer metadata |
| ABC News | `abcnews.go.com` | General US national coverage | Sitemap | Pointer metadata |
| CBS News | `cbsnews.com` | General US national coverage | Sitemap | Pointer metadata |
| NBC News | `nbcnews.com` | General US national coverage | Sitemap | Pointer metadata |
| Fox News | `foxnews.com` | Right-leaning national framing presence | RSS / sitemap | Pointer metadata |
| Washington Post | `washingtonpost.com` | National policy and political coverage | Sitemap / metadata API backup | Pointer metadata |
| New York Times | `nytimes.com` | National and international agenda-setting coverage | Sitemap / metadata API backup | Pointer metadata |

### Tier 3: Early regional and sector expansion

These should come after the core registry is stable.

| Outlet | Domain | Role in Prism | Why it matters |
|---|---|---|---|
| Los Angeles Times | `latimes.com` | Major regional newsroom | Adds West Coast regional signal |
| Chicago Tribune | `chicagotribune.com` | Major regional newsroom | Adds Midwest signal |
| Miami Herald | `miamiherald.com` | Regional and Latin America adjacency | Adds regional consequence coverage |
| Texas Tribune | `texastribune.org` | Policy and statehouse depth | Strong local/public-service model |
| ProPublica | `propublica.org` | Investigative reporting | Strong evidence-heavy source |
| STAT | `statnews.com` | Health/science vertical | Good domain-specific depth |
| Ars Technica | `arstechnica.com` | Technology detail | Strong technical coverage |
| The Verge | `theverge.com` | Consumer and platform tech framing | Broader tech audience angle |

### Tier 4: Watchlist

These should not block launch but should be tracked for later onboarding.

- Newsweek
- Axios
- Semafor
- local TV station newsrooms
- specialist climate, legal, and defense outlets
- selected non-English publishers once multilingual ingestion is ready

---

## 3. Source Mix Rules

Prism's first launch set should not be optimized for ideology theater.

The mix should explicitly include:

- wire services
- public media
- national general-interest publishers
- policy/process specialists
- international publishers
- regional/public-service newsrooms
- business and sector-specific outlets

If one source family dominates the registry, the product will feel narrower than it is.

---

## 4. Onboarding Requirements

No outlet should be added to the real source registry until these are confirmed:

- canonical domain
- preferred discovery path
- rights class default
- preview image posture
- poll cadence tier
- source-health alert owner

That means launch sourcing is a controlled operational process, not a casual spreadsheet.

---

## 5. Priority Order

Onboard in this order:

1. stabilize the 4 prototype feeds already running
2. add AP and Reuters
3. add Politico, The Hill, Bloomberg, FT
4. add the major national general-interest outlets
5. add regional and sector specialists

This order improves cluster quality faster than onboarding dozens of outlets at once.

---

## 6. Rights Policy At Launch

Default launch posture:

- use pointer metadata by default
- allow preview imagery only when source policy is reviewed and acceptable
- do not mirror third-party media into first-party storage by default
- reserve licensed media budgets for high-value surfaces later

Prism should feel alive through careful source onboarding, not rights shortcuts.

---

## 7. Success Criteria

The launch registry is healthy when:

- the top stories usually include 4+ independently sourced articles
- at least one wire/public-media baseline is present in most major clusters
- international and domestic frames both appear on globally important stories
- source onboarding backlog is small enough to review carefully
- preview imagery works often enough to make the product feel alive without becoming a licensing mess

---

## 8. Immediate Next Step

The next concrete implementation task should be:

- seed `source_registry`, `source_feeds`, and `source_policies` with Tier 1 and the first 6 Tier 2 outlets

That is the right launch slice for real development.
