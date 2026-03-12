#!/usr/bin/env python3

from __future__ import annotations

import json
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_STORIES = 12

OPEN_OUTLETS = {
    "ABC News",
    "Associated Press",
    "BBC News",
    "CBS News",
    "CNN",
    "Fox News",
    "MSNBC",
    "NBC News",
    "NPR",
    "PBS NewsHour",
    "Politico",
    "Reuters",
    "The Hill",
}

LIKELY_PAYWALLED_OUTLETS = {
    "Bloomberg",
    "Financial Times",
    "New York Times",
    "Wall Street Journal",
}


def is_substantive_article(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = article.get("body_text")
    summary = article.get("summary")

    if extraction_quality == "article_body" and isinstance(body_text, str) and len(body_text.strip()) >= 180:
        return True

    if isinstance(summary, str) and len(summary.strip()) >= 110:
        return True

    return False


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    brief_rows = client.get(
        "/story_brief_revisions?select=cluster_id,revision_tag,status,metadata&is_current=eq.true&limit=200"
    ) or []
    brief_by_cluster = {row["cluster_id"]: row for row in brief_rows if row.get("cluster_id")}
    rows = client.get(
        "/story_clusters?select=id,slug,canonical_headline,latest_event_at,metadata,cluster_articles(rank_in_cluster,articles!inner(outlets!inner(canonical_name),summary,body_text,metadata))&order=latest_event_at.desc&limit=40"
    ) or []

    stories = []
    for row in rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") not in ("automated_feed_ingestion", "live_snapshot"):
            continue

        cluster_articles = row.get("cluster_articles") or []
        article_rows = []
        seen_outlets: set[str] = set()
        substantive_outlets: set[str] = set()
        open_outlets: set[str] = set()
        paywalled_outlets: set[str] = set()
        brief_revision = brief_by_cluster.get(row.get("id"))

        for cluster_article in sorted(cluster_articles, key=lambda item: item.get("rank_in_cluster", 0)):
            article = cluster_article.get("articles") or {}
            outlet = ((article.get("outlets") or {}).get("canonical_name") or "").strip()
            if not outlet:
                continue

            seen_outlets.add(outlet)
            if outlet in OPEN_OUTLETS:
                open_outlets.add(outlet)
            if outlet in LIKELY_PAYWALLED_OUTLETS:
                paywalled_outlets.add(outlet)
            if is_substantive_article(article):
                substantive_outlets.add(outlet)

            article_rows.append(
                {
                    "outlet": outlet,
                    "extraction_quality": (article.get("metadata") or {}).get("extraction_quality"),
                    "has_body_text": bool((article.get("body_text") or "").strip()),
                }
            )

        stories.append(
            {
                "slug": row["slug"],
                "title": row["canonical_headline"],
                "outlet_count": len(seen_outlets),
                "substantive_source_count": len(substantive_outlets),
                "full_brief_ready": len(substantive_outlets) >= 2,
                "open_outlet_count": len(open_outlets),
                "likely_paywalled_outlet_count": len(paywalled_outlets),
                "open_alternate_ready": len(open_outlets) >= 1 and len(seen_outlets) >= 2,
                "stored_brief_current": bool(brief_revision),
                "stored_brief_status": (brief_revision or {}).get("status"),
                "stored_brief_revision_tag": (brief_revision or {}).get("revision_tag"),
                "stored_brief_paragraph_count": (
                    ((brief_revision or {}).get("metadata") or {}).get("paragraph_count")
                    if isinstance((brief_revision or {}).get("metadata"), dict)
                    else None
                ),
                "stored_brief_support_strategy": (
                    ((brief_revision or {}).get("metadata") or {}).get("support_strategy_version")
                    if isinstance((brief_revision or {}).get("metadata"), dict)
                    else None
                ),
                "articles": article_rows[:4],
            }
        )

    print(json.dumps({"stories": stories[:MAX_STORIES]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
