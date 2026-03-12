#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


LOOKBACK_HOURS = 48
MAX_SOURCES = 20


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def within_window(value: str | None, *, cutoff: datetime) -> bool:
    parsed = parse_timestamp(value)
    return bool(parsed and parsed >= cutoff)


def article_is_substantive(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    summary = article.get("summary") or ""
    body_text = article.get("body_text") or ""

    if extraction_quality == "article_body" and isinstance(body_text, str) and len(body_text.strip()) >= 180:
        return True
    return isinstance(summary, str) and len(summary.strip()) >= 110


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    registry_rows = client.get(
        "/source_registry?select=id,source_name,primary_domain,preferred_discovery_method,ingestion_status,is_active&order=source_name.asc&limit=200"
    ) or []
    feed_rows = client.get(
        "/source_feeds?select=source_registry_id,feed_type,feed_url,is_active,last_success_at,consecutive_failures&limit=300"
    ) or []
    discovery_rows = client.get(
        "/raw_discovered_urls?select=source_registry_id,fetch_status,discovered_at,last_attempted_at&order=discovered_at.desc&limit=4000"
    ) or []
    article_rows = client.get(
        "/articles?select=source_registry_id,summary,body_text,published_at,metadata&order=published_at.desc&limit=4000"
    ) or []

    feeds_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feed_rows:
        source_registry_id = row.get("source_registry_id")
        if isinstance(source_registry_id, str):
            feeds_by_source[source_registry_id].append(row)

    discovery_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in discovery_rows:
        source_registry_id = row.get("source_registry_id")
        if isinstance(source_registry_id, str) and within_window(row.get("discovered_at"), cutoff=cutoff):
            discovery_by_source[source_registry_id].append(row)

    articles_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in article_rows:
        source_registry_id = row.get("source_registry_id")
        if isinstance(source_registry_id, str) and within_window(row.get("published_at"), cutoff=cutoff):
            articles_by_source[source_registry_id].append(row)

    report = []
    for registry in registry_rows:
        registry_id = registry.get("id")
        if not isinstance(registry_id, str):
            continue

        discoveries = discovery_by_source.get(registry_id, [])
        articles = articles_by_source.get(registry_id, [])
        substantive_articles = [article for article in articles if article_is_substantive(article)]
        story_slugs = {
            (article.get("metadata") or {}).get("story_slug")
            for article in articles
            if isinstance(article.get("metadata"), dict) and (article.get("metadata") or {}).get("story_slug")
        }

        fetched_count = sum(1 for row in discoveries if row.get("fetch_status") == "fetched")
        failed_count = sum(1 for row in discoveries if row.get("fetch_status") == "failed")
        pending_count = sum(1 for row in discoveries if row.get("fetch_status") in ("pending", "normalized"))
        substantive_rate = round(len(substantive_articles) / len(articles), 3) if articles else 0.0

        report.append(
            {
                "source": registry.get("source_name"),
                "domain": registry.get("primary_domain"),
                "method": registry.get("preferred_discovery_method"),
                "active": bool(registry.get("is_active")),
                "ingestion_status": registry.get("ingestion_status"),
                "feeds": [
                    {
                        "type": feed.get("feed_type"),
                        "last_success_at": feed.get("last_success_at"),
                        "consecutive_failures": feed.get("consecutive_failures"),
                    }
                    for feed in feeds_by_source.get(registry_id, [])
                    if feed.get("is_active")
                ],
                "discoveries_48h": len(discoveries),
                "fetched_48h": fetched_count,
                "pending_or_normalized_48h": pending_count,
                "failed_48h": failed_count,
                "articles_48h": len(articles),
                "substantive_articles_48h": len(substantive_articles),
                "substantive_rate_48h": substantive_rate,
                "active_story_count_48h": len(story_slugs),
            }
        )

    report.sort(
        key=lambda row: (
            row["active_story_count_48h"],
            row["substantive_articles_48h"],
            row["discoveries_48h"],
        ),
        reverse=True,
    )

    print(json.dumps({"lookback_hours": LOOKBACK_HOURS, "sources": report[:MAX_SOURCES]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
