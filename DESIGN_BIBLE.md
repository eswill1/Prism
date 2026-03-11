# Prism Design Bible
### Version 0.1

---

## 0. North Star

> "Show the structure of coverage. Leave the reader in charge."

Every Prism design decision should answer one question:

**Does this increase understanding without increasing manipulation?**

If it sensationalizes disagreement, rewards compulsive checking, or hides method behind polish, it is wrong for Prism.

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

### 3.1 Cluster Stream

The homepage is a finite stream of Story Clusters, not an endless river of links.

Each cluster card shows:

- a real visual when available and rights-cleared
- event title
- short event summary
- timeline freshness
- number of outlets in the cluster
- the collapsed Perspective strip
- a visible "Open cluster" action

Rules:

- no infinite scroll as the primary mode
- clear section boundaries between time windows or topics
- card ordering can change with significance and freshness, but must remain explainable
- top clusters should usually feel visually alive, not logo-only

### 3.2 Story Cluster Page

This is the primary product surface.

**Required zones:**

1. Event header
2. What changed
3. Coverage structure
4. Perspective layer
5. Evidence ledger
6. Context pack
7. Corrections and methodology

The page should feel like an inspectable briefing, not like a comment thread.

Visual expectation:

- most major clusters should open with real photography, video stills, or licensed editorial art
- when media is unavailable or risky, the replacement should be an intentional first-party visual, not an empty hole

### 3.3 Perspective Panel

The Perspective panel is the core signature interaction.

Collapsed state on a cluster card:

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

### 3.4 Context Pack

Context Packs are short sets of alternate reads selected from the cluster.

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

If anything material changes in the cluster, the user should see it.

Display:

- "Updated since your last visit"
- what changed
- version tag
- correction notes link

Rules:

- do not silently rewrite cluster summaries
- do not bury corrections in footers
- every substantive Perspective or clustering change needs a visible version note

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

- real media is the default on homepage hero modules, major cluster cards, and briefings where rights are clear
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
- save a cluster
- follow a cluster
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
- engagement counts on cluster cards
- fake objectivity badges
- partisan palette coding
- unlabeled AI summaries

---

## 7. First-Launch Pages

- Home
- Cluster detail
- Saved clusters
- Morning briefing
- Methodology
- Pricing
- Correction log

If a page does not help a reader get oriented, inspect the method, or manage their account, it probably does not belong in the launch set.
