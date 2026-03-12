#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

from generate_temporary_live_feed import FeedItem, build_cluster_payload, cluster_items, parse_feed
from sync_story_content import (
    REST_BASE,
    SUPABASE_SERVICE_ROLE_KEY,
    SupabaseRestClient,
    build_live_context_packs,
    fetch_existing_articles_index,
    fetch_source_registry,
    fetch_story_cluster_count,
    framing_for_outlet,
    infer_desk_label,
    join_sources,
    normalize_domain,
    outlet_label_for_domain,
    seed_outlets,
    sync_story,
)
from url_normalization import normalize_canonical_url

SOURCE_PRIORITY_BONUS = {
    "Associated Press": 4,
    "Reuters": 4,
    "BBC News": 3,
    "NPR": 3,
    "PBS NewsHour": 3,
    "New York Times": 3,
    "NBC News": 2,
    "ABC News": 2,
    "CBS News": 2,
    "The Hill": 2,
    "Wall Street Journal": 2,
    "Bloomberg": 2,
    "Politico": 2,
    "Fox News": 0,
}

PUBLIC_INTEREST_PATTERNS: list[tuple[str, int]] = [
    (r"\b(trump|white house|congress|senate|house|election|budget|policy|court|title ix|immigration|tariff|sanction|fed)\b", 8),
    (r"\b(iran|ukraine|gaza|israel|china|russia|europe|war|attack|missile|strait of hormuz|diplomacy)\b", 8),
    (r"\b(oil|reserve|inflation|jobs|economy|economic|trade|market|bank|shipping|consumer)\b", 7),
    (r"\b(ai|chip|technology|platform|software|regulation|cyber)\b", 6),
    (r"\b(storm|wildfire|flood|weather|energy|grid|outage|earthquake|hurricane|disaster)\b", 6),
    (r"\b(airline|plane|flight|bird strike|aviation|safety)\b", 5),
]

LOW_VALUE_PATTERNS: list[tuple[str, int]] = [
    (r"\b(bigfoot|cryptid|celebrity|actor|actress|singer|memoir|divorce|dating|romance|met gala|red carpet)\b", 12),
    (r"\b(nfl|nba|mlb|fanatics|flag football|fantasy football)\b", 10),
    (r"\b(the takeout|the story|special report|face the nation|nightly news|weekend news|evening news|exclusive interview|interview|breaks silence|joins\b|joined\b|discuss(?:es|ing)?\b)\b", 10),
    (r"^\d{1,2}/\d{1,2}:", 14),
    (r"\b(recipe|horoscope|shopping|travel|style|fashion|podcast)\b", 8),
    (r"/(entertainment|sports|travel|lifestyle|style|food|shopping|opinion|video)/", 10),
]

HIGH_VALUE_TOPICS = {"US Politics", "World", "Business", "Technology", "Climate and Infrastructure", "Weather"}


def item_quality_score(item: FeedItem) -> int:
    haystack = f"{item.title} {item.summary} {item.url}".lower()
    score = SOURCE_PRIORITY_BONUS.get(item.source, 1)

    for pattern, points in PUBLIC_INTEREST_PATTERNS:
        if re.search(pattern, haystack):
            score += points

    for pattern, points in LOW_VALUE_PATTERNS:
        if re.search(pattern, haystack):
            score -= points

    if len(item.summary) >= 120:
        score += 1

    return score


def filter_candidate_items(items: list[FeedItem]) -> list[FeedItem]:
    scored = [(item, item_quality_score(item)) for item in items]
    keep = [item for item, score in scored if score >= 4]

    per_source_cap: dict[str, int] = {}
    capped_keep: list[FeedItem] = []
    for item, score in sorted(
        ((item, score) for item, score in scored if item in keep),
        key=lambda pair: pair[1],
        reverse=True,
    ):
        if per_source_cap.get(item.source, 0) >= 4:
            continue
        per_source_cap[item.source] = per_source_cap.get(item.source, 0) + 1
        capped_keep.append(item)

    if len(capped_keep) >= 18:
        return capped_keep

    return [
        item
        for item, _score in sorted(scored, key=lambda pair: pair[1], reverse=True)[: max(18, len(scored) // 2)]
    ]


def story_priority_score(cluster: dict[str, Any]) -> int:
    topic = infer_desk_label(cluster["title"], cluster["dek"])
    sources = len(cluster["sources"])
    article_count = int(cluster["article_count"])
    haystack = f"{cluster['title']} {cluster['dek']}".lower()

    score = sources * 12 + article_count * 4
    score += 10 if topic in HIGH_VALUE_TOPICS else -10

    if sources >= 3:
        score += 8
    elif sources == 1:
        score -= 8

    for pattern, points in PUBLIC_INTEREST_PATTERNS:
        if re.search(pattern, haystack):
            score += max(2, points // 2)

    for pattern, points in LOW_VALUE_PATTERNS:
        if re.search(pattern, haystack):
            score -= points

    return score


def fetch_active_discovery_feeds(client: SupabaseRestClient) -> list[dict[str, Any]]:
    rows = client.get(
        "/source_feeds?select=id,feed_type,feed_url,poll_interval_seconds,consecutive_failures,source_registry_id,source_registry(source_name,primary_domain,ingestion_status,is_active)&is_active=eq.true&limit=150"
    ) or []

    active = []
    for row in rows:
        registry = row.get("source_registry") or {}
        if not registry or not registry.get("is_active"):
            continue
        if registry.get("ingestion_status") not in ("active", "onboarding"):
            continue
        if row.get("feed_type") not in {"rss", "atom", "news_sitemap", "sitemap"}:
            continue
        active.append(
            {
                "feed_id": row["id"],
                "feed_type": row["feed_type"],
                "feed_url": row["feed_url"],
                "source": registry["source_name"],
                "primary_domain": registry["primary_domain"],
                "source_registry_id": row["source_registry_id"],
                "consecutive_failures": row.get("consecutive_failures", 0),
            }
        )
    return active


def patch_feed_state(client: SupabaseRestClient, feed_id: str, values: dict[str, Any]) -> None:
    client._request(  # noqa: SLF001
        "PATCH",
        f"/source_feeds?id=eq.{feed_id}",
        body=values,
        prefer="return=minimal",
    )


def fetch_existing_discovered_urls(client: SupabaseRestClient) -> set[tuple[str, str]]:
    rows = client.get("/raw_discovered_urls?select=source_registry_id,discovered_url,canonical_url&limit=5000") or []
    existing = set()
    for row in rows:
        canonical_url = row.get("canonical_url") or row.get("discovered_url")
        if canonical_url:
            existing.add((row["source_registry_id"], canonical_url))
    return existing


def insert_raw_discovered_urls(
    client: SupabaseRestClient,
    items: list[FeedItem],
    feed_map: dict[str, dict[str, Any]],
) -> int:
    existing = fetch_existing_discovered_urls(client)
    rows = []
    for item in items:
        feed = feed_map[item.feed_url]
        canonical_url = normalize_canonical_url(item.url) or item.url
        key = (feed["source_registry_id"], canonical_url)
        if key in existing:
            continue
        rows.append(
            {
                "source_registry_id": feed["source_registry_id"],
                "source_feed_id": feed["feed_id"],
                "discovered_url": item.url,
                "canonical_url": canonical_url,
                "discovery_method": "rss",
                "discovered_at": item.published_at,
                "fetch_status": "pending",
            }
        )
    if rows:
        client.post("/raw_discovered_urls", rows, prefer="return=minimal")
    return len(rows)


def build_story_from_cluster(
    cluster: dict[str, Any],
    *,
    priority_score: int,
    homepage_eligible: bool,
) -> dict[str, Any]:
    articles = []
    unique_sources = []

    for article in cluster["articles"]:
        domain = normalize_domain(article.get("domain"))
        canonical_outlet = outlet_label_for_domain(domain) if domain else article["source"]
        unique_sources.append(canonical_outlet)
        articles.append(
            {
                "outlet": canonical_outlet,
                "site_name": article["source"],
                "title": article["title"],
                "summary": article.get("summary") or domain,
                "feed_summary": article.get("feed_summary") or article.get("summary") or domain,
                "body_text": article.get("body_preview") or "",
                "named_entities": article.get("named_entities") or [],
                "extraction_quality": article.get("extraction_quality") or "rss_only",
                "published_at": article["published_at"],
                "framing": framing_for_outlet(canonical_outlet),
                "image": article.get("image") or cluster["hero_image"],
                "reason": f"{canonical_outlet} adds a visible live reporting angle to the story stack.",
                "url": article["url"],
                "domain": domain,
            }
        )

    unique_sources = list(dict.fromkeys(unique_sources))
    coverage_counts = {"left": 0, "center": 0, "right": 0}
    for source in unique_sources:
        coverage_counts[framing_for_outlet(source)] += 1

    latest_article = max(articles, key=lambda item: item["published_at"], default=None)
    timeline = [
        {
            "timestamp": cluster["latest_at"],
            "kind": "summary",
            "label": f"Story shell refreshed from {len(unique_sources)} publisher signals",
            "detail": f"Prism regenerated this live story using {cluster['article_count']} linked inputs across {join_sources(unique_sources)}.",
        }
    ]
    if latest_article:
        timeline.append(
            {
                "timestamp": latest_article["published_at"],
                "kind": "coverage",
                "label": f"{latest_article['outlet']} added the latest visible turn",
                "detail": latest_article["title"],
            }
        )
    if cluster.get("hero_image"):
        timeline.append(
            {
                "timestamp": cluster["latest_at"],
                "kind": "evidence",
                "label": "Representative publisher media attached to the story shell",
                "detail": "The current hero image comes from linked publisher metadata and is shown as a preview rather than a definitive visual claim.",
            }
        )

    return {
        "slug": cluster["slug"],
        "topic": infer_desk_label(cluster["title"], cluster["dek"]),
        "title": cluster["title"],
        "dek": cluster["dek"],
        "updated_at": cluster["latest_at"],
        "display_status": "Live intake",
        "db_status": "developing",
        "hero_image": cluster.get("hero_image") or f"https://picsum.photos/seed/{cluster['slug']}/1600/900",
        "hero_alt": f"{cluster['title']} preview image from linked publisher metadata.",
        "hero_credit": cluster.get("hero_credit") or "Publisher preview image",
        "hero_rights_class": "pointer_metadata",
        "outlet_count": len(unique_sources),
        "reliability_range": "Mixed source set" if len(unique_sources) >= 3 else "Early source set",
        "coverage_counts": coverage_counts,
        "key_facts": [
            (
                f"Prism has {cluster['article_count']} linked reports across {len(unique_sources)} publishers in this story so far."
                if len(unique_sources) >= 2
                else "Prism has one linked report in this story so far, so the comparison view is still early."
            ),
            (
                f"The latest linked reporting came from {latest_article['outlet']}."
                if latest_article
                else "The story shell is waiting for the first linked article payload."
            ),
            (
                f"The comparison set is already broad enough to inspect framing differences across {join_sources(unique_sources)}."
                if len(unique_sources) >= 2
                else "The comparison set is still thin, so this story may move quickly as additional publishers enter the frame."
            ),
        ],
        "change_timeline": timeline,
        "articles": articles,
        "evidence": [
            {"label": "Primary linked reporting set", "source": join_sources(unique_sources), "type": "report"},
            {"label": "Latest refresh in the live intake queue", "source": cluster["latest_at"], "type": "dataset"},
            {
                "label": "Current source breadth",
                "source": f"{cluster['article_count']} linked articles across {len(unique_sources)} publishers",
                "type": "report",
            },
        ],
        "context_packs": build_live_context_packs(articles),
        "metadata": {
            "display_status": "Live intake",
            "story_origin": "automated_feed_ingestion",
            "source_count": len(unique_sources),
            "quality_score": priority_score,
            "homepage_eligible": homepage_eligible,
            "sync_source": "tooling/ingest_live_feeds_to_supabase.py",
        },
    }


def cleanup_stale_live_clusters(client: SupabaseRestClient, current_slugs: set[str]) -> int:
    rows = client.get("/story_clusters?select=id,slug,metadata&limit=200") or []
    removed = 0
    for row in rows:
        metadata = row.get("metadata") or {}
        if metadata.get("story_origin") not in ("live_snapshot", "automated_feed_ingestion"):
            continue
        if row["slug"] in current_slugs:
            continue
        client.delete(f"/story_clusters?id=eq.{row['id']}")
        removed += 1
    return removed


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    feeds = fetch_active_discovery_feeds(client)
    feed_map = {feed["feed_url"]: feed for feed in feeds}
    all_items: list[FeedItem] = []
    feed_errors: list[dict[str, str]] = []

    for feed in feeds:
        now = datetime.now(timezone.utc).isoformat()
        try:
            parsed = parse_feed(
                {"source": feed["source"], "feed_url": feed["feed_url"], "feed_type": feed["feed_type"]},
                enrich_articles=False,
            )
            all_items.extend(parsed)
            patch_feed_state(
                client,
                feed["feed_id"],
                {
                    "last_polled_at": now,
                    "last_success_at": now,
                    "consecutive_failures": 0,
                },
            )
        except Exception as exc:  # noqa: BLE001
            feed_errors.append({"feed_url": feed["feed_url"], "source": feed["source"], "error": str(exc)})
            patch_feed_state(
                client,
                feed["feed_id"],
                {
                    "last_polled_at": now,
                    "consecutive_failures": int(feed.get("consecutive_failures", 0)) + 1,
                },
            )
        time.sleep(0.25)

    if not all_items:
        print(
            json.dumps(
                {
                    "feeds_polled": len(feeds),
                    "feed_errors": len(feed_errors),
                    "raw_discovered_inserted": 0,
                    "live_stories_synced": 0,
                    "stale_live_clusters_removed": 0,
                    "story_cluster_count": fetch_story_cluster_count(client),
                },
                indent=2,
            )
        )
        if feed_errors:
            print(json.dumps({"feed_errors": feed_errors}, indent=2), file=sys.stderr)
        return 1

    deduped = {item.url: item for item in all_items}
    raw_discovered_count = insert_raw_discovered_urls(client, list(deduped.values()), feed_map)

    filtered_items = filter_candidate_items(list(deduped.values()))
    clustered = cluster_items(filtered_items)

    ranked_clusters = []
    for cluster in clustered:
        payload = build_cluster_payload(len(ranked_clusters) + 1, cluster)
        priority = story_priority_score(payload)
        source_count = len(payload["sources"])
        homepage_eligible = priority >= 18 and source_count >= 2
        ranked_clusters.append((priority, homepage_eligible, payload))

    ranked_clusters.sort(
        key=lambda item: (item[0], len(item[2]["sources"]), item[2]["latest_at"]),
        reverse=True,
    )

    primary_clusters = [item for item in ranked_clusters if item[0] >= 6]
    if len(primary_clusters) < 10:
        primary_clusters = ranked_clusters[:14]
    else:
        primary_clusters = primary_clusters[:14]

    stories = [
        build_story_from_cluster(
            {
                **cluster,
                "slug": f"live-{index}-{cluster['slug'].split('-', 2)[-1]}",
            },
            priority_score=priority,
            homepage_eligible=homepage_eligible,
        )
        for index, (priority, homepage_eligible, cluster) in enumerate(primary_clusters, start=1)
    ]

    if not stories:
        print(
            json.dumps(
                {
                    "feeds_polled": len(feeds),
                    "feed_errors": len(feed_errors),
                    "raw_discovered_inserted": raw_discovered_count,
                    "live_stories_synced": 0,
                    "stale_live_clusters_removed": 0,
                    "story_cluster_count": fetch_story_cluster_count(client),
                },
                indent=2,
            )
        )
        if feed_errors:
            print(json.dumps({"feed_errors": feed_errors}, indent=2), file=sys.stderr)
        return 1

    outlet_rows = seed_outlets(client, stories)
    source_registry = fetch_source_registry(client)
    existing_articles = fetch_existing_articles_index(client)
    for story in stories:
        sync_story(client, story, outlet_rows, source_registry, existing_articles)

    removed = cleanup_stale_live_clusters(client, {story["slug"] for story in stories})

    print(
        json.dumps(
            {
                "feeds_polled": len(feeds),
                "feed_errors": len(feed_errors),
                "raw_discovered_inserted": raw_discovered_count,
                "live_stories_synced": len(stories),
                "stale_live_clusters_removed": removed,
                "story_cluster_count": fetch_story_cluster_count(client),
            },
            indent=2,
        )
    )

    if feed_errors:
        print(json.dumps({"feed_errors": feed_errors}, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
