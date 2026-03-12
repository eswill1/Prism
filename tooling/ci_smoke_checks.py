#!/usr/bin/env python3

from __future__ import annotations

try:
    from tooling.generate_temporary_live_feed import FeedItem, cluster_items
    from tooling.semantic_story_candidates import build_similarity_lookup
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from generate_temporary_live_feed import FeedItem, cluster_items
    from semantic_story_candidates import build_similarity_lookup


def build_item(
    *,
    source: str,
    title: str,
    url: str,
    summary: str,
    tokens: set[str],
    event_tags: set[str],
) -> FeedItem:
    return FeedItem(
        source=source,
        feed_url=f"https://example.com/{source.lower()}",
        title=title,
        url=url,
        published_at="2026-03-11T12:00:00+00:00",
        summary=summary,
        feed_summary=summary,
        lede=summary,
        body_preview="",
        named_entities=[],
        extraction_quality="rss_only",
        image=None,
        tokens=tokens,
        event_tags=event_tags,
    )


def main() -> int:
    oil_one = build_item(
        source="NPR",
        title="US to release emergency oil reserves as prices rise",
        url="https://example.com/oil-1",
        summary="Oil reserve release as prices rise.",
        tokens={"oil", "reserve", "release", "price"},
        event_tags={"oil_reserve_release"},
    )
    oil_two = build_item(
        source="BBC",
        title="Emergency oil reserve release announced amid fuel price fears",
        url="https://example.com/oil-2",
        summary="Oil reserve release amid fuel price fears.",
        tokens={"oil", "reserve", "release", "fuel", "price"},
        event_tags={"oil_reserve_release"},
    )
    unrelated = build_item(
        source="BBC",
        title="West Bank settlers face sanctions review",
        url="https://example.com/west-bank",
        summary="West Bank settlers story.",
        tokens={"west", "bank", "settlers", "sanctions", "review"},
        event_tags=set(),
    )

    items = [oil_one, oil_two, unrelated]
    clusters = cluster_items(items)
    cluster_sizes = sorted(len(cluster) for cluster in clusters)
    if cluster_sizes != [1, 2]:
        raise SystemExit(f"unexpected cluster sizes: {cluster_sizes}")

    neighbors, _similarities = build_similarity_lookup(items)
    if neighbors.get(oil_one.url) != [oil_two.url]:
        raise SystemExit(f"unexpected semantic candidates for oil_one: {neighbors.get(oil_one.url)}")
    if neighbors.get(unrelated.url):
        raise SystemExit(f"unexpected semantic candidates for unrelated story: {neighbors.get(unrelated.url)}")

    print("Python pipeline smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
