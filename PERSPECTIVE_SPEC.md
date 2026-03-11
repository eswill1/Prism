# Prism Perspective Specification
### Version 0.1

---

## 0. Glossary

| Term | Definition |
|---|---|
| Story Cluster | Canonical event object grouping related coverage |
| Article | A single ingested story from a source outlet or publication |
| Outlet | A publication or publisher mapped from article domains |
| Perspective Layer | The read-only context system attached to a cluster |
| Context Pack | A lens-specific set of alternate reads for a cluster |
| Lens | User-selected context mode: Balanced Framing, Evidence-First, Local Impact, International Comparison |
| Evidence Item | Source document, quote, filing, transcript, or official statement linked to a cluster |

---

## 1. Goals

- cluster related reporting around the same event
- make outlet and framing structure visible
- provide useful alternate reads without implying a single approved interpretation
- keep all Perspective logic auditable and versioned

## 2. Non-Goals

- computing a single truth score
- ranking by ideology
- using outlet reliability as a hidden enforcement mechanism
- maximizing clicks into external articles

---

## 3. Shared Pipeline

### Stage A: Ingestion and Normalization

Input sources:

- RSS feeds
- first-party crawlers
- licensed article feeds
- manual editorial seed inputs

For each article:

- normalize canonical URL
- resolve outlet domain
- extract publish time, headline, dek, body text, tags, byline
- compute content hash and near-duplicate fingerprint

### Stage B: Story Clustering

Candidate grouping is based on:

- named entities
- semantic similarity
- temporal proximity
- shared event terms
- article update relationships

Rules:

- split clusters when the dominant event subject changes
- merge clusters only when the event core is materially shared
- log manual merges and splits

### Stage C: Outlet Registry Join

Match the normalized domain against `perspective_outlets`.

Attach:

- outlet name
- rater-source records
- reliability range label
- framing reference data
- last update timestamp

### Stage D: Coverage Structure Assembly

For each cluster, compute:

- total outlet count
- outlet family spread
- framing presence groups
- local, national, and international coverage categories

Important:
Coverage structure describes presence. It does not claim correctness.

### Stage E: Evidence Ledger Assembly

Extract and link:

- quoted people
- cited documents
- filings, rulings, transcripts, or datasets
- unresolved claims needing stronger sourcing

Evidence extraction should prefer explainable heuristics and source references over opaque summarization.

### Stage F: Context Pack Selection

Context packs are generated from cluster candidates according to explicit lens rules.

**Balanced Framing**
- prioritize source-family diversity
- ensure meaningful framing variety
- avoid duplicate articles making the same interpretive move

**Evidence-First**
- prioritize direct reporting, documents, transcripts, and primary-source-heavy coverage

**Local Impact**
- prioritize regional reporting and sector-specific consequences

**International Comparison**
- prioritize cross-border source families and non-US framing differences

Each selected item must carry a machine-readable reason code.

### Stage G: Versioning and Logging

Persist:

- cluster version
- Perspective data version
- context-pack rule version
- manual override log entries
- correction events

---

## 4. Prohibited Feature Firewall

The following fields are prohibited in default cluster-ordering or recommendation models:

- `perspective_outlets.*`
- `perspective_article_labels.*`
- `perspective_context_rules.*`
- `outlet_reliability_range`
- `outlet_framing_direction`
- `cluster_framing_mix`
- `lens_preference`

Exception:
`lens_preference` may shape Context Pack rendering after the user opens a cluster and explicitly selects a lens. It may not affect the default home ordering.

---

## 5. Default Cluster Ordering

Prism may order clusters using:

- recency
- update significance
- source diversity
- follow state
- saved-cluster state
- topic subscriptions

Prism may not order clusters using:

- outlet ideology
- outlet reliability tier
- article rage response
- raw click-through volume

---

## 6. Data Model Sketch

```sql
CREATE TABLE outlets (
  id UUID PRIMARY KEY,
  domain TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  rater_data JSONB NOT NULL DEFAULT '{}',
  reliability_range TEXT NOT NULL,
  framing_reference JSONB NOT NULL DEFAULT '{}',
  data_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE articles (
  id UUID PRIMARY KEY,
  outlet_id UUID REFERENCES outlets(id),
  canonical_url TEXT UNIQUE NOT NULL,
  headline TEXT NOT NULL,
  summary TEXT,
  body_text TEXT,
  published_at TIMESTAMPTZ NOT NULL,
  fingerprint TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE story_clusters (
  id UUID PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  canonical_headline TEXT NOT NULL,
  summary TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  cluster_version TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE cluster_articles (
  cluster_id UUID REFERENCES story_clusters(id),
  article_id UUID REFERENCES articles(id),
  relation_type TEXT NOT NULL DEFAULT 'member',
  PRIMARY KEY (cluster_id, article_id)
);

CREATE TABLE evidence_items (
  id UUID PRIMARY KEY,
  cluster_id UUID REFERENCES story_clusters(id),
  label TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_url TEXT,
  notes TEXT
);

CREATE TABLE context_pack_items (
  id UUID PRIMARY KEY,
  cluster_id UUID REFERENCES story_clusters(id),
  lens TEXT NOT NULL,
  article_id UUID REFERENCES articles(id),
  reason_codes JSONB NOT NULL,
  rule_version TEXT NOT NULL
);

CREATE TABLE correction_events (
  id UUID PRIMARY KEY,
  cluster_id UUID REFERENCES story_clusters(id),
  event_type TEXT NOT NULL,
  notes TEXT NOT NULL,
  version_before TEXT,
  version_after TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. API Surface

```text
GET /api/health
GET /api/clusters
GET /api/clusters/:slug
GET /api/clusters/:slug/perspective
GET /api/clusters/:slug/context-pack?lens=balanced_framing
GET /api/clusters/:slug/corrections
GET /api/methodology/perspective
POST /api/subscriptions/checkout
```

---

## 8. Testing Requirements

- fixture-based cluster merge and split tests
- outlet mapping tests
- Perspective firewall tests
- lens isolation tests
- correction-log visibility tests

Any change to clustering, outlet mapping, or context-pack selection must carry a version bump and test coverage.
