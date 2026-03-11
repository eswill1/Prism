# Prism Agent Development Strategy
### Version 0.1

---

## Model

Prism should be developed with concern-based agents and a strict compliance review loop.

```text
Orchestrator
  Surface Agent
  API/Data Agent
  Perspective Agent
  Compliance Agent
```

---

## Agent Definitions

### Orchestrator

Context:

- all doctrine documents
- current repo state

Responsibilities:

- task breakdown
- sequencing
- cross-agent conflict resolution
- final review

Boundary:

- does not author large implementation changes directly unless no specialist split is needed

### Surface Agent

Context:

- Design Bible
- Implementation Plan web sections

Responsibilities:

- Next.js pages
- design tokens
- cluster, Perspective, and correction UI

Boundary:

- no database design
- no clustering logic

### API/Data Agent

Context:

- Implementation Plan
- Metrics Standard

Responsibilities:

- Fastify services
- schema and migrations
- auth, subscriptions, saved clusters, admin endpoints

Boundary:

- no UI decisions
- no framing or clustering methodology decisions

### Perspective Agent

Context:

- Perspective Spec
- Anti-Drift Constitution
- Metrics Standard

Responsibilities:

- story clustering
- outlet mapping
- Context Pack rules
- versioning and correction workflows

Boundary:

- no pricing or subscription UX

### Compliance Agent

Context:

- Anti-Drift Constitution
- Metrics Standard
- Perspective Spec red lines

Responsibilities:

- review every Perspective, clustering, notification, and correction-related change
- block constitutional violations

Boundary:

- no feature authorship

---

## Review Checklist

- no prohibited Perspective feature entered default ranking or ordering code
- no single-score truth or outlet badge introduced
- correction visibility preserved
- rater attribution present
- lens logic isolated to Context Packs or explicit reader actions
- no infinite scroll introduced as the primary cluster surface
- no manipulative notification pattern added

---

## Phase Sequencing

### Phase 1

- Orchestrator
- Surface Agent
- API/Data Agent
- Compliance Agent

### Phase 2

- add Perspective Agent once clustering and Context Pack work begins

Prism should add more agents only when there is real context separation to preserve.
