#!/usr/bin/env python3

from __future__ import annotations

import json
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_STORIES = 12


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
    rows = client.get(
        "/story_clusters?select=slug,canonical_headline,latest_event_at,metadata,cluster_articles(rank_in_cluster,articles!inner(outlets!inner(canonical_name),summary,body_text,metadata))&order=latest_event_at.desc&limit=40"
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

        for cluster_article in sorted(cluster_articles, key=lambda item: item.get("rank_in_cluster", 0)):
            article = cluster_article.get("articles") or {}
            outlet = ((article.get("outlets") or {}).get("canonical_name") or "").strip()
            if not outlet:
                continue

            seen_outlets.add(outlet)
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
                "articles": article_rows[:4],
            }
        )

    print(json.dumps({"stories": stories[:MAX_STORIES]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
