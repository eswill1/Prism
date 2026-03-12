#!/usr/bin/env python3

from __future__ import annotations

import json

from generate_temporary_live_feed import FEEDS, cluster_items, parse_feed
from semantic_story_candidates import build_similarity_lookup


MAX_ITEMS = 60


def main() -> int:
    all_items = []
    for feed in FEEDS:
        all_items.extend(parse_feed(feed, enrich_articles=False))

    deduped = list({item.url: item for item in all_items}.values())[:MAX_ITEMS]
    heuristic_clusters = cluster_items(deduped)
    flat_clusters = {
        item.url: {other.url for other in cluster if other.url != item.url}
        for cluster in heuristic_clusters
        for item in cluster
    }

    neighbor_lookup, _similarity_lookup = build_similarity_lookup(deduped)
    evaluated = 0
    with_mates = 0
    hit_at_6 = 0
    recall_total = 0.0
    examples = []

    for item in deduped:
        expected = flat_clusters.get(item.url, set())
        candidates = neighbor_lookup.get(item.url, [])
        evaluated += 1
        if not expected:
            continue
        with_mates += 1
        hits = [url for url in candidates if url in expected]
        recall = len(hits) / len(expected) if expected else 0.0
        recall_total += recall
        if hits:
            hit_at_6 += 1
        if len(examples) < 6:
            examples.append(
                {
                    "title": item.title,
                    "expected_cluster_mates": len(expected),
                    "candidate_count": len(candidates),
                    "hits": len(hits),
                    "recall_at_6": round(recall, 3),
                }
            )

    report = {
        "items_evaluated": evaluated,
        "items_with_cluster_mates": with_mates,
        "candidate_hit_rate_at_6": round(hit_at_6 / with_mates, 3) if with_mates else 0.0,
        "average_candidate_recall_at_6": round(recall_total / with_mates, 3) if with_mates else 0.0,
        "example_rows": examples,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
