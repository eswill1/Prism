#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

from generate_temporary_live_feed import (
    BROAD_MATCH_TOKENS,
    FeedItem,
    LOW_SIGNAL_CLUSTER_TOKENS,
    build_cluster_payload,
    cluster_match_score,
    cluster_items,
    story_item_context_score,
    story_item_is_event_driven,
    story_item_is_contextual,
    story_item_is_title_only_stub,
    normalize_entity,
    parse_feed,
    should_join_cluster,
    summary_quality_score,
)
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
MIN_CONFIDENT_LEAD_QUALITY = 6
MIN_CONFIDENT_OPEN_ALTERNATE_QUALITY = 7
MIN_SHIPPABLE_SINGLE_SOURCE_SUMMARY_QUALITY = 6
AUGMENTATION_CLUSTER_LIMIT = 4
AUGMENTATION_FEED_ITEM_LIMIT = 25
AUGMENTATION_ITEMS_PER_CLUSTER = 2
AUGMENTATION_TOTAL_ITEM_LIMIT = 8
LOW_SIGNAL_QUERY_ENTITIES = {
    "donald trump",
    "iran",
    "israel",
    "middle east",
    "president donald trump",
    "president trump",
    "tehran",
    "trump",
    "u s",
    "united states",
    "us",
}


def infer_access_tier(article: dict[str, Any]) -> str:
    signal = article.get("access_signal")
    if isinstance(signal, str) and signal in {"open", "likely_paywalled"}:
        return signal
    domain = str(article.get("domain") or "")
    if any(domain == candidate or domain.endswith(f".{candidate}") for candidate in ("apnews.com", "bbc.com", "cbsnews.com", "abcnews.com", "nbcnews.com", "npr.org", "pbs.org", "thehill.com", "foxnews.com", "reuters.com", "politico.com", "cnn.com", "msnbc.com")):
        return "open"
    if any(domain == candidate or domain.endswith(f".{candidate}") for candidate in ("ft.com", "bloomberg.com", "nytimes.com", "wsj.com")):
        return "likely_paywalled"
    return "unknown"


def source_read_quality(article: dict[str, Any]) -> int:
    score = summary_quality_score(
        article["title"],
        article.get("summary") or article.get("feed_summary") or "",
        extraction_quality=article.get("extraction_quality") or "rss_only",
        body_text=article.get("body_text") or "",
    )
    if article.get("access_tier") == "open":
        score += 3
    elif article.get("access_tier") == "likely_paywalled":
        score -= 2
    if article.get("body_text"):
        score += 2
    return score


def choose_story_source_options(articles: list[dict[str, Any]]) -> dict[str, Any]:
    if not articles:
        return {}

    ranked = sorted(articles, key=source_read_quality, reverse=True)
    lead = ranked[0]
    lead_quality_score = source_read_quality(lead)
    lead_quality_confident = lead_quality_score >= MIN_CONFIDENT_LEAD_QUALITY

    open_alternate = next(
        (
            article
            for article in ranked
            if article.get("access_tier") == "open" and article.get("url") and article.get("outlet") != lead.get("outlet")
        ),
        None,
    )
    open_alternate_quality_score = source_read_quality(open_alternate) if open_alternate else None
    open_alternate_quality_confident = bool(
        open_alternate and open_alternate_quality_score is not None and open_alternate_quality_score >= MIN_CONFIDENT_OPEN_ALTERNATE_QUALITY
    )
    if not open_alternate_quality_confident:
        open_alternate = None
        open_alternate_quality_score = None

    return {
        "lead_outlet": lead.get("outlet"),
        "lead_url": lead.get("url"),
        "lead_access_tier": lead.get("access_tier"),
        "lead_quality_score": lead_quality_score,
        "lead_quality_confident": lead_quality_confident,
        "open_alternate_outlet": open_alternate.get("outlet") if open_alternate else None,
        "open_alternate_url": open_alternate.get("url") if open_alternate else None,
        "open_alternate_quality_score": open_alternate_quality_score,
        "open_alternate_quality_confident": open_alternate_quality_confident,
        "open_alternate_available": bool(open_alternate and open_alternate_quality_confident),
    }


def source_options_key_fact(source_options: dict[str, Any]) -> str:
    if source_options.get("lead_access_tier") == "likely_paywalled" and source_options.get("open_alternate_available"):
        return f"Prism found an open alternate read from {source_options['open_alternate_outlet']} to pair with the story."

    if source_options.get("lead_access_tier") == "open" and source_options.get("lead_quality_confident"):
        return "The strongest available source read is already open."

    if not source_options.get("lead_quality_confident"):
        return "Linked source reads are still thin, so Prism is waiting for a stronger baseline before treating this as a reliable source stack."

    return "Some linked reporting may be gated, so Prism is watching for stronger open alternates."


def item_quality_score(item: FeedItem) -> int:
    haystack = f"{item.title} {item.summary} {item.url}".lower()
    score = SOURCE_PRIORITY_BONUS.get(item.source, 1)

    for pattern, points in PUBLIC_INTEREST_PATTERNS:
        if re.search(pattern, haystack):
            score += points

    for pattern, points in LOW_VALUE_PATTERNS:
        if re.search(pattern, haystack):
            score -= points

    content_score = summary_quality_score(
        item.title,
        item.summary,
        extraction_quality=item.extraction_quality,
        body_text=item.body_preview,
    )
    score += max(-8, min(8, content_score))

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


def substantive_feed_item(item: FeedItem) -> bool:
    if item.extraction_quality == "article_body" and len(item.body_preview.strip()) >= 180:
        return True
    return summary_quality_score(
        item.title,
        item.summary,
        extraction_quality=item.extraction_quality,
        body_text=item.body_preview,
    ) >= 6


def actionable_entity(entity: str) -> str:
    normalized = normalize_entity(entity)
    if len(normalized) < 4:
        return ""
    if normalized in LOW_SIGNAL_QUERY_ENTITIES:
        return ""
    if any(token in {"reporting", "editing", "standards", "trust", "reported", "reports"} for token in normalized.split()):
        return ""
    return normalized


def story_query_from_cluster(cluster: list[FeedItem]) -> tuple[set[str], set[str]]:
    anchor_items = [
        item
        for item in cluster
        if substantive_feed_item(item) and not story_item_is_contextual(item) and not story_item_is_title_only_stub(item)
    ]
    if not anchor_items:
        anchor_items = [item for item in cluster if substantive_feed_item(item) and not story_item_is_title_only_stub(item)]
    if not anchor_items:
        anchor_items = [item for item in cluster if substantive_feed_item(item)] or cluster
    token_counts = {}
    for item in anchor_items:
        for token in item.tokens:
            if token in BROAD_MATCH_TOKENS or token in LOW_SIGNAL_CLUSTER_TOKENS:
                continue
            token_counts[token] = token_counts.get(token, 0) + 1
    query_tokens = {
        token
        for token, _count in sorted(token_counts.items(), key=lambda item: (-item[1], item[0]))[:6]
    }
    if not query_tokens:
        query_tokens = {
            token
            for item in anchor_items
            for token in item.tokens
            if token not in BROAD_MATCH_TOKENS
        }

    entity_counts = {}
    for item in anchor_items:
        for entity in item.named_entities:
            normalized = actionable_entity(entity)
            if not normalized:
                continue
            entity_counts[normalized] = entity_counts.get(normalized, 0) + 1
    query_entities = {
        entity
        for entity, _count in sorted(entity_counts.items(), key=lambda item: (-item[1], item[0]))[:6]
    }
    return query_tokens, query_entities


def item_matches_story_query(item: FeedItem, query_tokens: set[str], query_entities: set[str]) -> bool:
    token_overlap = item.tokens & query_tokens
    strong_overlap = {
        token
        for token in token_overlap
        if token not in BROAD_MATCH_TOKENS and token not in LOW_SIGNAL_CLUSTER_TOKENS
    }
    entity_overlap = {
        actionable_entity(entity)
        for entity in item.named_entities
        if actionable_entity(entity)
    } & query_entities
    if entity_overlap:
        return True
    if len(strong_overlap) >= 2:
        return True
    return len(strong_overlap) >= 1 and len(token_overlap) >= 2


def should_augment_cluster(cluster: list[FeedItem]) -> bool:
    source_count = len({item.source for item in cluster})
    substantive_items = [item for item in cluster if substantive_feed_item(item)]
    event_items = [
        item
        for item in substantive_items
        if story_item_is_event_driven(item) and not story_item_is_title_only_stub(item)
    ]
    open_substantive = [item for item in substantive_items if item.access_signal == "open"]
    likely_paywalled = [item for item in cluster if item.access_signal == "likely_paywalled"]
    return (
        source_count <= 1
        or len(substantive_items) <= 1
        or len(event_items) <= 1
        or (len(open_substantive) == 0 and len(likely_paywalled) >= 1)
    )


def augmentation_priority(cluster: list[FeedItem]) -> tuple[int, int, int]:
    substantive_items = [item for item in cluster if substantive_feed_item(item)]
    event_items = [
        item
        for item in substantive_items
        if story_item_is_event_driven(item) and not story_item_is_title_only_stub(item)
    ]
    public_interest = max((item_quality_score(item) for item in cluster), default=0)
    return (
        1 if should_augment_cluster(cluster) else 0,
        len(event_items),
        public_interest,
    )


def select_story_augmentation_candidates(
    cluster: list[FeedItem],
    candidates: list[FeedItem],
    *,
    limit: int,
) -> list[FeedItem]:
    existing_urls = {item.url for item in cluster}
    existing_sources = {item.source for item in cluster}
    query_tokens, query_entities = story_query_from_cluster(cluster)
    cluster_prefers_event = any(story_item_is_event_driven(item) and not story_item_is_title_only_stub(item) for item in cluster)
    ranked: list[tuple[float, FeedItem]] = []
    for item in candidates:
        if item.url in existing_urls or item.source in existing_sources:
            continue
        if not item_matches_story_query(item, query_tokens, query_entities):
            continue
        query_token_overlap = item.tokens & query_tokens
        strong_query_overlap = {
            token
            for token in query_token_overlap
            if token not in BROAD_MATCH_TOKENS and token not in LOW_SIGNAL_CLUSTER_TOKENS
        }
        query_entity_overlap = {
            actionable_entity(entity)
            for entity in item.named_entities
            if actionable_entity(entity)
        } & query_entities
        if cluster_prefers_event and (story_item_is_contextual(item) or story_item_is_title_only_stub(item)) and len(strong_query_overlap) < 2 and len(query_entity_overlap) < 2:
            continue
        join_match = should_join_cluster(item, cluster)
        if not join_match and not query_entity_overlap and len(strong_query_overlap) < 2:
            continue
        score = cluster_match_score(item, cluster)
        score += len(strong_query_overlap) * 3
        score += len(query_entity_overlap) * 2
        if join_match:
            score += 2
        score -= story_item_context_score(item) * 4
        score -= 8 if story_item_is_title_only_stub(item) else 0
        score += summary_quality_score(
            item.title,
            item.summary,
            extraction_quality=item.extraction_quality,
            body_text=item.body_preview,
        )
        if item.access_signal == "open":
            score += 3
        if item.extraction_quality == "article_body":
            score += 4
        if story_item_is_event_driven(item) and not story_item_is_title_only_stub(item):
            score += 5
        ranked.append((score, item))

    selected: list[FeedItem] = []
    seen_sources: set[str] = set()
    for _score, item in sorted(ranked, key=lambda pair: pair[0], reverse=True):
        if item.source in seen_sources:
            continue
        seen_sources.add(item.source)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def augment_thin_clusters(
    items: list[FeedItem],
    clusters: list[list[FeedItem]],
    feeds: list[dict[str, Any]],
) -> list[FeedItem]:
    selected_clusters = [
        cluster
        for cluster in sorted(clusters, key=augmentation_priority, reverse=True)
        if should_augment_cluster(cluster)
    ][:AUGMENTATION_CLUSTER_LIMIT]
    if not selected_clusters:
        return []

    feed_cache: dict[str, list[FeedItem]] = {}
    existing_urls = {item.url for item in items}
    augmented: list[FeedItem] = []

    candidate_feeds = sorted(
        feeds,
        key=lambda feed: SOURCE_PRIORITY_BONUS.get(feed["source"], 0),
        reverse=True,
    )

    for cluster in selected_clusters:
        cluster_candidates: list[FeedItem] = []
        cluster_sources = {item.source for item in cluster}
        for feed in candidate_feeds:
            if feed["source"] in cluster_sources:
                continue
            if feed["feed_url"] not in feed_cache:
                feed_cache[feed["feed_url"]] = parse_feed(
                    {
                        "source": feed["source"],
                        "feed_url": feed["feed_url"],
                        "feed_type": feed["feed_type"],
                    },
                    enrich_articles=False,
                    item_limit=AUGMENTATION_FEED_ITEM_LIMIT,
                )
            parsed_items = [
                item
                for item in feed_cache[feed["feed_url"]]
                if item.url not in existing_urls and item.url not in {candidate.url for candidate in augmented}
            ]
            if not parsed_items:
                continue
            cluster_candidates.extend(
                select_story_augmentation_candidates(
                    cluster,
                    parsed_items,
                    limit=1,
                )
            )
            if len(cluster_candidates) >= AUGMENTATION_ITEMS_PER_CLUSTER:
                break

        for item in select_story_augmentation_candidates(
            cluster,
            cluster_candidates,
            limit=AUGMENTATION_ITEMS_PER_CLUSTER,
        ):
            if item.url in existing_urls or item.url in {candidate.url for candidate in augmented}:
                continue
            augmented.append(item)
            if len(augmented) >= AUGMENTATION_TOTAL_ITEM_LIMIT:
                return augmented

    return augmented


def story_priority_score(cluster: dict[str, Any]) -> int:
    topic = infer_desk_label(cluster["title"], cluster["dek"])
    sources = len(cluster["sources"])
    article_count = int(cluster["article_count"])
    summary_quality = int(cluster.get("summary_quality_score") or 0)
    substantive_source_count = int(cluster.get("substantive_source_count") or 0)
    haystack = f"{cluster['title']} {cluster['dek']}".lower()

    score = sources * 12 + article_count * 4
    score += 10 if topic in HIGH_VALUE_TOPICS else -10
    score += max(-10, min(12, summary_quality))
    score += substantive_source_count * 6

    if sources >= 3:
        score += 8
    elif sources == 1:
        score -= 8

    if substantive_source_count == 0:
        score -= 8
    elif substantive_source_count == 1:
        score -= 2

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
                "access_signal": article.get("access_signal") or "unknown",
            }
        )

    unique_sources = list(dict.fromkeys(unique_sources))
    coverage_counts = {"left": 0, "center": 0, "right": 0}
    for source in unique_sources:
        coverage_counts[framing_for_outlet(source)] += 1

    for article in articles:
        article["access_tier"] = infer_access_tier(article)

    source_options = choose_story_source_options(articles)

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
        "reliability_range": (
            "Mixed source set"
            if cluster.get("substantive_source_count", 0) >= 2 or len(unique_sources) >= 3
            else "Early source set"
        ),
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
            (
                source_options_key_fact(source_options)
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
            "substantive_source_count": int(cluster.get("substantive_source_count") or 0),
            "summary_quality_score": int(cluster.get("summary_quality_score") or 0),
            "quality_score": priority_score,
            "homepage_eligible": homepage_eligible,
            "sync_source": "tooling/ingest_live_feeds_to_supabase.py",
            "source_options": source_options,
        },
    }


def is_shippable_story(story: dict[str, Any]) -> bool:
    metadata = story.get("metadata") or {}
    source_count = int(metadata.get("source_count") or story.get("outlet_count") or 0)
    substantive_source_count = int(metadata.get("substantive_source_count") or 0)
    summary_quality = int(metadata.get("summary_quality_score") or 0)
    source_options = metadata.get("source_options") or {}
    lead_quality_confident = bool(source_options.get("lead_quality_confident"))

    if source_count <= 1 and substantive_source_count == 0 and summary_quality < MIN_SHIPPABLE_SINGLE_SOURCE_SUMMARY_QUALITY:
        return False

    if source_count <= 1 and substantive_source_count == 0 and not lead_quality_confident:
        return False

    return True


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

    initial_deduped = {item.url: item for item in all_items}
    initial_filtered_items = filter_candidate_items(list(initial_deduped.values()))
    initial_clusters = cluster_items(initial_filtered_items)
    augmented_items = augment_thin_clusters(initial_filtered_items, initial_clusters, feeds)
    if augmented_items:
        all_items.extend(augmented_items)

    deduped = {item.url: item for item in all_items}
    raw_discovered_count = insert_raw_discovered_urls(client, list(deduped.values()), feed_map)

    filtered_items = filter_candidate_items(list(deduped.values()))
    clustered = cluster_items(filtered_items)

    ranked_clusters = []
    for cluster in clustered:
        payload = build_cluster_payload(len(ranked_clusters) + 1, cluster)
        priority = story_priority_score(payload)
        source_count = len(payload["sources"])
        substantive_source_count = int(payload.get("substantive_source_count") or 0)
        summary_quality = int(payload.get("summary_quality_score") or 0)
        homepage_eligible = (
            priority >= 18
            and source_count >= 2
            and (substantive_source_count >= 2 or summary_quality >= 8)
        )
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

    stories: list[dict[str, Any]] = []
    dropped_low_quality = 0
    for priority, homepage_eligible, cluster in primary_clusters:
        story = build_story_from_cluster(
            {
                **cluster,
                "slug": f"live-{len(stories) + 1}-{cluster['slug'].split('-', 2)[-1]}",
            },
            priority_score=priority,
            homepage_eligible=homepage_eligible,
        )
        if not is_shippable_story(story):
            dropped_low_quality += 1
            continue
        stories.append(story)
        if len(stories) >= 14:
            break

    if not stories:
        print(
            json.dumps(
                {
                    "feeds_polled": len(feeds),
                    "feed_errors": len(feed_errors),
                    "raw_discovered_inserted": raw_discovered_count,
                    "augmented_items_discovered": len(augmented_items),
                    "live_stories_synced": 0,
                    "low_quality_live_clusters_dropped": dropped_low_quality,
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
                "augmented_items_discovered": len(augmented_items),
                "live_stories_synced": len(stories),
                "low_quality_live_clusters_dropped": dropped_low_quality,
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
