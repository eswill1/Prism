# Prism Design Bible
### Version 0.3 — Updated 2026-03-12: source-grounded brief rules and dedicated enrichment path

---

## 0. North Star

> "Show the structure of coverage. Leave the reader in charge."

Every Prism design decision should answer one question:

**Does this increase understanding without increasing manipulation?**

If it sensationalizes disagreement, rewards compulsive checking, or hides method behind polish, it is wrong for Prism.

### 0.1 Core Loop UX Requirement

Prism's design must make this loop feel natural:

1. open a story that matters
2. understand the shape of coverage quickly
3. inspect another angle, evidence item, or correction note
4. save or follow the story
5. return later and immediately see what changed

If the interface looks impressive but does not help the reader complete that loop, the design is failing.

---

## 1. Brand Identity

### 1.1 Name and Metaphor

A prism does not invent light. It reveals structure inside it.

That metaphor defines the product:

- split the signal into visible parts
- preserve the underlying source
- help the reader inspect, compare, and recombine

Prism is not a megaphone and not a referee. It is an instrument.

### 1.2 Brand Voice

| Trait | In practice |
|---|---|
| Calm | No urgency theater, no breathless copy, no pushy verbs |
| Precise | Labels mean specific things and link to methodology |
| Serious | Looks like a tool for adults, not a trend surface |
| Transparent | "Why is this here?" and "how was this labeled?" are always answerable |
| Editorially humble | The product explains structure; it does not claim omniscience |

### 1.3 What Prism Is Not

- not a breaking-news casino
- not a hot-take leaderboard
- not a social debate arena
- not a one-paragraph AI oracle
- not a generic dashboard full of analytics chrome

---

## 2. Visual Language

### 2.1 Color System

Prism should feel like modern editorial infrastructure: paper, ink, brass, slate, and signal colors used sparingly.

#### Core palette

| Token | Name | Hex | Usage |
|---|---|---|---|
| `--prism-ink` | Ink | `#131A22` | Main text, dark surfaces |
| `--prism-paper` | Paper | `#F4F1EA` | App background |
| `--prism-sheet` | Sheet | `#FCFBF8` | Cards and panels |
| `--prism-slate` | Slate | `#5F6876` | Secondary text, rules, subdued UI |
| `--prism-brass` | Brass | `#A8742A` | Primary emphasis, active lens state |
| `--prism-teal` | Teal | `#2E6F73` | Interactive accents, links |
| `--prism-wire` | Wire | `#8C3B2A` | Correction or caution state |
| `--prism-stone` | Stone | `#D8D1C6` | Borders, separators |

#### Semantic usage

- background defaults to `--prism-paper`
- cards use `--prism-sheet`
- primary buttons use `--prism-ink` on `--prism-paper` or `--prism-brass` on light surfaces
- links and inspectable elements use `--prism-teal`
- corrections and caution states use `--prism-wire`, never bright red

#### Rules

- No flashing "breaking" red.
- No heatmap colors for ideology.
- No rainbow framing charts.
- Coverage structure should look measured, not gamified.

### 2.2 Typography

Prism uses an editorial pairing that feels distinct from generic SaaS.

| Role | Family | Rationale |
|---|---|---|
| UI sans | IBM Plex Sans | Neutral, technical, newsroom-capable |
| Headline and long-form serif | Source Serif 4 | Editorial authority without feeling nostalgic or ornamental |
| Data mono | IBM Plex Mono | Cluster IDs, versions, methodology labels |

### 2.3 Spacing and Density

Prism should feel information-rich but breathable.

- 8px spacing grid
- card padding defaults to 20px on desktop, 16px on mobile
- tables and dot grids can be dense, but never cramped
- every major section needs a visible label and a visible exit

### 2.4 Motion

Motion is restrained and functional.

- use fades and subtle horizontal slides
- no bouncing badges
- no pulsing alerts
- no looping attention animations outside explicit loading states

---

## 3. Core Surfaces

### 3.1 Story Stream

The homepage is the definitive current-news front door, not a teaser for some other "real" news page.

It should read like a real front page: finite, current, and clearly prioritized.

Its frame should feel like a serious newsroom:

- a utility strap for edition/date and quiet utility links
- a recognizable Prism masthead and mark
- a section nav bar that supports scanning without feeling like product chrome

Each story card shows:

- a real visual when available and rights-cleared
- event title
- short event summary
- timeline freshness
- number of outlets covering the story
- a visible "Open story" action

Interaction rule:

- the whole story package should be clickable wherever practical, not just a small CTA

Perspective and deeper structure can stay mostly on the story page. The homepage should stay news-first.

Rules:

- no infinite scroll as the primary mode
- clear section boundaries between time windows or topics
- broad categories such as World, Politics, Business, Technology, and Weather should help readers scan the homepage
- section labels are wayfinding, not replacements for the story-first product model
- card ordering can change with significance and freshness, but must remain explainable
- top stories should usually feel visually alive, not logo-only

Secondary page rule:

- fast-moving story movement should usually be folded into the homepage itself rather than exposed as a second primary front door

### 3.2 Story Page

This is the primary product surface.

**Required zones:**

1. Event header
2. Prism Brief
3. Reporting to read next
4. Another angle
5. Perspective rail
6. Source notes, evidence, corrections, and methodology

The page should feel like an inspectable briefing, not like a comment thread.

The current structural rule is:

- left two-thirds: article-first reading flow
- right one-third: Perspective and supporting inspection surfaces

The story must come before the comparison layer.

Prism Brief rule:

- the main brief must be grounded in extracted source text where available, not padded boilerplate
- if Prism only has feed-snippet quality inputs, the page should remain visibly provisional
- richer article extraction belongs in a separate enrichment pass, not in the homepage feed-polling loop
- the visible brief structure should stay stable: what happened, why it matters, where sources agree, where coverage differs, and what to watch
- mature multi-source stories should usually resolve into a fuller multi-paragraph brief, not a one-paragraph placeholder
- if the strongest available reporting is paywalled or too thin, Prism should try to surface a credible open alternate rather than leaving the reader at a dead end
- read selection should be accessibility-aware: a likely paywalled lead can still appear, but Prism should prefer to pair it with a strong open alternate when one is available

Single-source rule:

- if Prism only has one substantive linked report, the page should present an explicit early brief rather than pretending to offer a mature multi-source synthesis

The story page must also support the full Prism loop:

- orient first
- inspect second
- retain through save/follow third
- make return visits legible through visible change tracking

Visual expectation:

- most major stories should open with real photography, video stills, or licensed editorial art
- when media is unavailable or risky, the replacement should be an intentional first-party visual, not an empty hole

Linking rule:

- source reads should open original reporting directly when a real source URL exists
- Prism should not add an intermediate wrapper page unless that wrapper adds clear editorial value

### 3.3 Perspective Panel

The Perspective panel is the core signature interaction.

Collapsed state on a story card:

- outlet count
- reliability range
- "View Perspective"

Expanded state:

- outlet registry matches
- rating-source attribution and update date
- coverage split
- framing distribution shown as presence, not percentage
- lens selector
- methodology link

Rules:

- never display a single "bias score"
- show rater disagreement honestly
- coverage split must not imply truth
- labels are informational, not punitive
- the opening Perspective summary should read like a note, not a second article body
- the rail should be visually distinct from the article column without overpowering it

### 3.4 Context Pack

Context Packs are short sets of alternate reads selected from the story.

Supported lenses in v1:

- Balanced Framing
- Evidence-First
- Local Impact
- International Comparison

Each pack should contain 3 to 5 items and explain why each item is included.

Rules:

- packs are curated by explicit lens logic, not generic recommendation bait
- packs should diversify source families and framing approaches
- pack labels must never read like endorsements

### 3.5 Evidence Ledger

A structured section listing:

- quoted people
- referenced documents
- official statements
- source material links
- unresolved claims

The evidence ledger is one of Prism's main trust surfaces. It should look durable, tabular, and boring in a good way.

### 3.6 Corrections Ribbon

If anything material changes in the story, the user should see it.

Display:

- "Updated since your last visit"
- what changed
- version tag
- correction notes link

Rules:

- do not silently rewrite story summaries
- do not bury corrections in footers
- every substantive Perspective or clustering change needs a visible version note

This is not just a trust affordance. It is part of the return loop. Readers should feel that Prism is the place to come back when a story evolves.

---

## 4. Component Rules

### 4.1 Coverage Split

Allowed formats:

- dot groups
- grouped lists
- outlet chips

Not allowed:

- ideology percentages
- stacked bars implying vote share
- red vs. blue theatrics

### 4.2 Outlet Attribute Display

Display outlet attributes as:

- range labels
- rater list
- last updated date

Do not display:

- one proprietary Prism score
- "good source" or "bad source" badges
- ranking rank numbers

### 4.3 Breaking News Treatment

Breaking-news UI should communicate recency, not panic.

- use a timestamp and "developing" label
- avoid sirens, animation, or all-caps alerts
- allow readers to compare what changed between updates

### 4.4 Subscription and Paywall UX

Prism is subscription-funded, so the paywall has to feel aligned with the product's integrity.

- explain what the subscription protects
- emphasize transparency infrastructure and institutional access
- do not use countdown timers or fake scarcity

### 4.5 Media Policy on the Surface

Prism should look like a living news product.

Rules:

- real media is the default on homepage hero modules, major story cards, and briefings where rights are clear
- premium or licensed media should be prioritized on major stories
- preview images from source pages must obey production media policy and rights constraints
- fallback states should use first-party timelines, maps, charts, or structured cards with intent
- no broken-image shells and no generic stock-photo filler

---

## 5. Editorial Interaction Principles

### 5.1 Reader Agency

The reader can:

- choose a lens
- inspect the rating sources
- save a story
- follow a story
- compare alternate reads

The reader cannot:

- toggle hidden ideological weighting
- ask the system to show only confirming viewpoints by default
- mistake a label for an enforcement action

### 5.2 Honest Uncertainty

If Prism lacks confidence:

- widen the range
- show uncertainty
- reduce the claim strength
- expose the limitation in plain language

Never compensate for uncertainty with stronger visual certainty.

### 5.3 Corrections Over Quiet Rewrites

Visible correction discipline is part of the product identity. Silent cleanup is not.

---

## 6. Anti-Patterns

- infinite scroll for breaking-news consumption
- autoplay video blocks
- trending outrage rails
- "people are furious" modules
- engagement counts on story cards
- fake objectivity badges
- partisan palette coding
- unlabeled AI summaries

---

## 7. First-Launch Pages

- Home
- Story detail
- Saved stories
- Morning briefing
- Methodology
- Pricing
- Correction log

Tracked later surfaces:

- major-story Live Tracker
- saved-story history views with visible narrative and Perspective deltas

If a page does not help a reader get oriented, inspect the method, or manage their account, it probably does not belong in the launch set.
