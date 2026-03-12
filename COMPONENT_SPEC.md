# Prism Component Specification
### Version 0.2 — Updated 2026-03-12: homepage-first navigation and story-first reading flow

This document turns the design bible into buildable UI surfaces.

The design bible defines the principles.
This document defines the component behaviors, required states, and acceptance criteria.

---

## 1. Scope

This spec covers the initial reader surfaces:

- homepage briefing
- story detail page
- temporary live feed page
- global shell and shared interactive states

It is intentionally focused on Phase 1-2 work.

---

## 2. Shared Rules

### 2.1 Global shell

The app shell should provide:

- a stable page frame
- top-level navigation
- visible access to methodology and corrections
- enough spacing to make the product feel editorial, not dashboard-like

### 2.2 Shared loading state

All major surfaces need:

- skeleton blocks for hero media and title
- placeholder rows for cards and ledgers
- no spinner-only full page state unless absolutely necessary

### 2.3 Shared empty state

Every empty state must answer:

- what this surface is for
- why there is no content yet
- what the reader can do next

### 2.4 Shared error state

Every error state must:

- avoid vague "something went wrong" copy
- say whether the issue is temporary, data-related, or permission-related
- preserve the surrounding navigation frame

### 2.5 Dark mode

Dark mode is required before wider user testing.

Rules:

- preserve editorial contrast
- avoid glowing accent colors
- keep evidence and correction surfaces legible
- never use ideology colors as luminous emphasis

---

## 3. Homepage Briefing

Route:

- `/`

Purpose:

- orient the reader quickly
- establish Prism's value proposition
- surface the top stories with enough proof to invite deeper inspection

### 3.1 Masthead

Contents:

- product name
- one-line thesis
- navigation links

States:

- default
- compact on mobile
- sticky-on-scroll later if it improves orientation without clutter

Acceptance criteria:

- nav does not dominate the page
- headline communicates product category in one glance
- the current masthead should feel like a national newsroom identity, not a product dashboard

### 3.2 Hero Story

Contents:

- real or prototype hero media
- story title
- summary/dek
- freshness line
- outlet count
- proof tiles
- primary CTA

States:

- media present
- media fallback visual
- stale-content warning if freshness threshold is exceeded later

Acceptance criteria:

- hero feels like a serious editorial entry point, not marketing chrome
- CTA clearly opens the story, not a generic article
- the full hero package should be clickable, not just the CTA text

### 3.3 Story Card Grid

Each card must include:

- image or fallback visual
- topic label
- status chip
- freshness
- title
- dek
- outlet count
- open-story action

States:

- image present
- image fallback
- developing / new / watch visual states
- saved state later

Acceptance criteria:

- cards are scannable in under 3 seconds each
- cards feel alive when real media is present
- cards still feel intentional when media is absent
- the whole card should open the story wherever practical

---

## 4. Story Detail Page

Route:

- `/stories/[slug]`

Purpose:

- act as Prism's hero surface
- let the reader understand a story, inspect the coverage structure, and decide what to read next

### 4.1 Story Topbar

Contents:

- back action
- save action
- follow action

States:

- default
- saved
- followed
- signed-out prompt state later

Acceptance criteria:

- topbar is useful without becoming app chrome

### 4.2 Story Hero

Contents:

- topic label
- title
- dek
- freshness
- outlet count
- hero media and credit

States:

- media present
- licensed/fallback visual
- updated story

Acceptance criteria:

- title and dek remain dominant over media
- media helps orientation but does not replace structure

### 4.3 Story Body

Contents:

- Prism Brief
- Why it matters
- What to watch
- key facts

Desktop behavior:

- primary article column

Mobile behavior:

- stacked directly under the story hero

Acceptance criteria:

- the reader can understand the story before interacting with Perspective
- the body feels like a real article summary, not product filler

### 4.4 Reporting Stack

Contents:

- Reporting to read next
- Also in the mix
- Another angle

Acceptance criteria:

- source reads are visually scannable
- source items link directly to original reporting when a real URL exists
- non-linkable items should not look clickable
- "what changed" is visible without searching

### 4.4 Coverage Stack

Contents:

- article cards inside the story
- outlet
- publish time
- framing presence label
- summary
- "why included" reason

States:

- fully populated
- thin story with 1 to 2 items
- low-confidence story warning later

Acceptance criteria:

- cards show why each item matters
- stack feels like a comparison surface, not a feed clone

### 4.5 Context Pack

Contents:

- selected lens label
- 3 to 5 alternate reads
- why-included explanation per item

States:

- populated
- no-pack-yet placeholder
- alternate lens tabs later

Acceptance criteria:

- each item has a clear inclusion reason
- pack does not read like algorithmic filler

### 4.6 Perspective Panel

Contents:

- outlet count
- coverage structure rows
- reliability range
- methodology reminder

States:

- collapsed on smaller screens later
- loading
- insufficient-data

Acceptance criteria:

- never implies a single truth score
- dots/chips read as presence, not vote share

### 4.7 Evidence Ledger

Contents:

- label
- source type
- source name

States:

- populated
- no-evidence-yet placeholder
- expandable details later

Acceptance criteria:

- ledger feels durable and factual
- rows are easy to scan

### 4.8 Corrections and Versioning

Contents:

- time
- visible note

States:

- no-corrections-yet placeholder
- updated-since-last-visit later

Acceptance criteria:

- correction history is visible without scrolling to a hidden footer

---

## 5. Temporary Live Feed Page

Route:

- `/live`

Purpose:

- give Prism a live-feeling content input surface before the production ingestion pipeline exists

### 5.1 Live Header

Contents:

- generated timestamp
- article/feed counts
- back link

States:

- ready
- no snapshot available

Acceptance criteria:

- the page clearly communicates that it is a prototype surface
- freshness is obvious

### 5.2 Source Coverage Panel

Contents:

- source list
- optional feed warnings

States:

- normal
- partial failure with warning state

Acceptance criteria:

- source diversity is visible
- failures are not hidden

### 5.3 Live Story Cards

Contents:

- topic label
- title
- dek
- source chips
- hero media or generated fallback
- article cards with outbound links

States:

- media present
- media fallback
- thin story

Acceptance criteria:

- stories feel structurally similar to the eventual product
- outbound links are obvious and safe

---

## 6. Responsive Behavior

### Desktop

Priority:

- three-column story workstation
- visible simultaneous context

### Tablet

Priority:

- preserve hierarchy without forcing tiny rails
- summary and inspector may stack under the main column

### Mobile

Priority:

- story summary first
- main reading column second
- Perspective/evidence/corrections as fast modules, not buried appendix content

Do not simply shrink the desktop layout.

---

## 7. Accessibility Rules

Every surface in this spec must:

- pass WCAG AA contrast
- preserve keyboard focus visibility
- keep tap targets large enough on mobile
- avoid motion that becomes disorienting with reduced motion enabled
- use meaningful image alt text or intentional decorative treatment

---

## 8. Implementation Order

Build and refine in this order:

1. homepage hero + story grid
2. story detail page shell
3. Perspective panel and evidence ledger
4. secondary live queue page
5. saved/follow states
6. dark mode
7. empty/error/loading refinements

If the story detail page is not excellent, the rest of the product will not matter.
