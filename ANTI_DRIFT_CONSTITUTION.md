# Prism Anti-Drift Constitution
### Version 0.4 — Updated 2026-03-12: hybrid clustering and inference policy

---

## Preamble

Prism exists to improve understanding of current events without reproducing the manipulation incentives that degraded modern information systems.

If a change would increase usage by making readers more anxious, tribal, compulsive, or epistemically dependent on the product, that change is out of bounds.

---

## 1. Non-Negotiable Product Invariants

These rules apply across official Prism clients.

### Stories are the reader-facing primary object

- the default reader surface is story-first, not headline-river-first
- clustering may remain an internal system primitive, but reader language and navigation should stay story-based
- individual article cards may exist, but they cannot replace the story model

### The homepage is the definitive current-news front door

- readers should not have to discover a second "real" news page
- faster-moving queues may exist as secondary or internal surfaces, but not as the primary reader path
- in connected mode, homepage and story surfaces may not be padded with synthetic editorial stand-ins when real sourced stories are available

### The Perspective layer is informational only

- Perspective data may explain coverage
- Perspective data may not act as covert editorial enforcement
- Perspective data may not silently suppress or boost content for ideological reasons

### No single neutral verdict

- Prism does not assign one proprietary truth score to a story, outlet, or frame
- Prism does not claim to compute the final neutral interpretation of an event

### Corrections are visible

- material changes to cluster membership, outlet mapping, rater sourcing, or context-pack logic are versioned and logged
- silent rewrites are prohibited for material changes

### Reader agency remains intact

- users can inspect methodology
- users can inspect rating-source attribution
- users can change lenses without losing visibility into the unfiltered cluster
- readers can move directly to original reporting when Prism presents it
- Prism may not force a wrapper detour unless that detour adds clear editorial value

### Story first, Perspective second

- the story page must explain what happened before asking the reader to decode comparison structure
- Perspective should clarify coverage, not displace the core story body

### Prism Briefs must stay source-grounded

- Prism may summarize reporting, but it may not present boilerplate or feed-only filler as if it were a mature multi-source brief
- single-source stories must remain explicitly provisional until additional substantive reporting arrives
- slower article extraction and enrichment are allowed, but they may not degrade the freshness of the main feed-polling loop

### Inference should not calcify into hard-coded folklore

- deterministic rules are allowed for normalization, source policy, safety rails, and explicit merge exclusions
- learned inference should carry more of the load for story similarity, candidate retrieval, and topic formation as the system matures
- Prism may not replace one opaque black box with another; any learned clustering path must preserve audit hooks and rollback options

---

## 2. What the System Is Allowed to Optimize

Prism may optimize for:

- clarity
- timeliness
- inspectability
- evidence visibility
- context usefulness
- correction quality

Prism may not optimize for:

- session length
- refresh frequency
- outrage response
- article click yield as a primary goal
- ideological confirmation
- notification-triggered return loops

Some of those metrics may be monitored diagnostically. None may become system objectives.

---

## 3. Product Patterns That Are Prohibited

- infinite scroll as the primary current-events surface
- autoplay video in the core reader product
- flashing or alarming breaking-news presentation
- public engagement counters on story clusters
- "people are talking about this" social proof modules
- partisan color coding intended to heighten salience
- deceptive paywall timers or false scarcity

---

## 4. Perspective Rules

### Multi-source attribution only

- outlet attributes must reference named external raters or named internal methodology artifacts
- disagreement between raters must remain visible

### No ideology-as-scoreboard

- framing may be shown as structural information
- framing may not be shown as a bar race, percentage contest, or winner/loser display

### No ranking by ideology

- Perspective features are prohibited in cluster-ordering or context-pack candidate scoring, except where the user explicitly selects a lens for secondary context rendering
- outlet lean, outlet reliability tier, and framing labels may not serve as ranking features for default cluster prominence

### Methodology is publishable

- readers can see the current Perspective version
- readers can see what changed between versions
- Prism publishes the sources and update cadence for outlet/rater data

---

## 5. Editorial and Correction Discipline

- every material error requires a logged correction
- outlet mapping disputes must have a published handling path
- changes to rater sources require a version bump and rationale
- unresolved ambiguity should be shown as ambiguity, not hidden behind stronger language

---

## 6. Funding Constraints

Prism is allowed to monetize through:

- subscriptions
- institutional plans
- educational and research licensing

Prism is not allowed to monetize through:

- behavioral advertising
- microtargeted political inventory
- sponsor influence on cluster ranking or context-pack composition

If a revenue mechanism creates incentives to maximize arousal or confusion, it fails constitutional review.

---

## 7. Notification Rules

- notifications must be sparse, legible, and tied to real informational changes
- no numerical badge games
- no "you may have missed this" compulsion loops
- follow-up alerts must correspond to actual cluster updates, corrections, or saved-story changes

---

## 8. Human Override and Auditability

- editorial overrides must be logged
- manual cluster merges or splits must be recorded with operator and timestamp
- significant algorithm changes require an RFC and rollback plan
- compliance review is mandatory for Perspective, clustering, and notification changes

---

## 9. Prime Directive

If Prism must choose between:

- making the product more habit-forming, or
- making the product more understandable and honest

Prism chooses honesty, even at the cost of growth.
