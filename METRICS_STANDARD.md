# Prism Metrics Standard
### Version 0.1

---

## Purpose

This document defines the only metrics Prism is allowed to optimize directly, the safety metrics that constrain releases, and the operational metrics used to monitor quality.

The Anti-Drift Constitution is the source of truth. Metrics exist to enforce it, not to route around it.

---

## Metric Tiers

### Tier 0: Constitutional Guardrails

These are hard constraints, not KPIs.

- no prohibited Perspective features in ranking
- visible rater attribution on every Perspective panel
- visible correction logging for material changes
- no infinite scroll on the primary cluster surface

Tier 0 items must be mechanically enforced and continuously tested.

### Tier 1: Primary Success Metrics

These are the only metrics Prism may optimize directly.

- cluster clarity rate
- context usefulness rate
- evidence follow-through rate
- correction trust rate

### Tier 2: Safety and Drift Metrics

These constrain releases and can trigger rollback.

- compulsive return pattern indicators
- framing skew incidents
- correction latency
- trust degradation after Perspective changes

### Tier 3: Operational Metrics

These guide staffing and system health. They are not optimization targets.

- ingestion latency
- clustering precision and recall audits
- rater data freshness
- article normalization failure rate

---

## Core Entities

**Story Cluster**
The canonical event object grouping related coverage.

**Perspective Panel**
The expandable context layer showing outlet attributes, coverage spread, and methodology links.

**Context Pack**
A lens-specific set of alternate reads derived from a single cluster.

**Correction Event**
A logged change to cluster membership, outlet mapping, rater source usage, or context-pack methodology.

---

## Tier 1 Metrics

### 1. Cluster Clarity Rate (CCR)

**What it is**
Percent of sampled cluster visits where the reader reports that they understand the shape of the story after using Prism.

**Prompt**
"Do you feel clearer on this story now?"

**Definition**
`clear responses / total responses`

CCR is Prism's north star.

### 2. Context Usefulness Rate (CUR)

**What it is**
Percent of opened Context Packs that produce a save, compare action, or positive usefulness response.

CUR measures whether alternate reads are genuinely helpful rather than decorative.

### 3. Evidence Follow-Through Rate (EFR)

**What it is**
The rate at which readers open evidence items, source documents, or cited material from within a cluster.

High EFR means the product is helping readers inspect the evidence, not just consume summary text.

### 4. Correction Trust Rate (CTR)

**What it is**
Percent of readers who view a correction note and report that the correction increased or preserved trust.

This metric exists because visible correction discipline is part of the product promise.

---

## Tier 2 Metrics

### 5. Compulsive Return Indicator (CRI)

Tracks patterns such as repeated refreshes, rapid reopen loops after notifications, and excessive short-interval returns.

CRI is not optimized for. It is a drift detector.

### 6. Perspective Trust Degradation (PTD)

Measures whether a Perspective change causes:

- lower CCR
- higher confusion or distrust feedback
- increased complaint volume about labeling opacity

### 7. Correction Latency (CL)

Time from verified issue detection to visible correction publication.

### 8. Framing Skew Incident Rate (FSI)

Rate of audited cases where framing grouping or lens logic systematically omits a material coverage family or overstates a directional split.

### 9. Notification Backfire Rate (NBR)

Rate at which update notifications produce rapid app opens coupled with lower CCR or higher distrust feedback.

---

## Tier 3 Metrics

### 10. Cluster Freshness Latency

Median time from article ingestion to cluster availability.

### 11. Outlet Coverage Hit Rate

Percent of news articles that map to a known outlet registry entry.

### 12. Rater Freshness

Days since last refresh of rater source data.

### 13. Cluster Audit Precision

Human-audited precision for story clustering.

### 14. Cluster Audit Recall

Human-audited recall for story clustering.

---

## Perspective Firewall Metrics

These are Tier 0 and must remain perfect.

| Metric | Target | Action if violated |
|---|---|---|
| Prohibited Perspective feature appearance | 0% | immediate rollback |
| Rater attribution presence | 100% | ship block |
| Correction log visibility | 100% for material changes | ship block |
| Lens isolation compliance | 100% | immediate rollback |

Lens isolation compliance means lens selection may affect Context Pack rendering only. It may not affect default cluster prominence.

---

## Rollback Triggers

### Immediate rollback

- any prohibited Perspective feature appears in ranking or cluster-ordering code
- a Perspective panel ships without attribution
- correction visibility breaks for material changes

### Fast rollback within 24 hours

- CCR drops by 5% or more relative after a Perspective or clustering change
- PTD rises by 10% or more relative
- NBR rises materially after a notification change

### Manual review required

- metric conflict, such as higher CCR paired with higher distrust reports
- major rater-source or mapping changes affecting more than 1% of the outlet registry

---

## Reporting Rules

- publish internal weekly dashboards for CCR, PTD, CL, and audit precision
- include Perspective version and data freshness on the internal dashboard
- publish public transparency notes for significant methodology changes

Prism should prefer fewer, harder metrics over broad dashboards that tempt optimization drift.
