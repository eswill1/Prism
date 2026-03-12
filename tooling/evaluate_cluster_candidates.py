#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

try:
    from tooling.generate_temporary_live_feed import FEEDS, FeedItem, cluster_items, parse_feed
    from tooling.semantic_story_candidates import build_similarity_lookup
    from tooling.url_normalization import normalize_canonical_url
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from generate_temporary_live_feed import FEEDS, FeedItem, cluster_items, parse_feed
    from semantic_story_candidates import build_similarity_lookup
    from url_normalization import normalize_canonical_url


MAX_ITEMS = 60
FIXTURES_PATH = Path(__file__).with_name("clustering_regression_fixtures.json")


def load_fixture_items() -> tuple[list[dict[str, object]], list[str]]:
    if not FIXTURES_PATH.exists():
        return [], []

    cases = json.loads(FIXTURES_PATH.read_text())
    failure_messages: list[str] = []
    reports: list[dict[str, object]] = []

    for case in cases:
        items = [
            FeedItem(
                source=item["source"],
                feed_url=f"https://example.com/{item['source'].lower()}",
                title=item["title"],
                url=normalize_canonical_url(item["url"]),
                published_at="2026-03-11T12:00:00+00:00",
                summary=item["summary"],
                feed_summary=item["summary"],
                lede=item["lede"],
                body_preview=item["body_preview"],
                named_entities=item["named_entities"],
                extraction_quality="article_body",
                image=None,
                tokens=set(item["tokens"]),
                event_tags=set(item["event_tags"]),
            )
            for item in case["items"]
        ]
        clusters = cluster_items(items)
        cluster_groups = sorted(sorted(entry.url for entry in cluster) for cluster in clusters)
        expected_groups = sorted(sorted(group) for group in case["expected_cluster_groups"])
        if cluster_groups != expected_groups:
            failure_messages.append(
                f"{case['name']}: expected clusters {expected_groups}, got {cluster_groups}"
            )

        neighbors, _similarity_lookup = build_similarity_lookup(items)
        for url, expected_neighbors in case.get("expected_neighbors", {}).items():
            actual_neighbors = neighbors.get(url, [])
            if actual_neighbors[: len(expected_neighbors)] != expected_neighbors:
                failure_messages.append(
                    f"{case['name']}: expected neighbors for {url} to start with {expected_neighbors}, got {actual_neighbors}"
                )

        reports.append(
            {
                "name": case["name"],
                "cluster_groups": cluster_groups,
                "neighbor_counts": {url: len(urls) for url, urls in neighbors.items()},
            }
        )

    return reports, failure_messages


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
    fixture_reports, fixture_failures = load_fixture_items()
    report["fixture_reports"] = fixture_reports
    print(json.dumps(report, indent=2))
    if fixture_failures:
        raise SystemExit("\n".join(fixture_failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
