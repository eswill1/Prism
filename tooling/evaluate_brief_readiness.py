#!/usr/bin/env python3

from __future__ import annotations

import json
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient
from generate_story_briefs_to_supabase import cluster_brief_source_metrics, infer_access_tier, is_substantive_article


MAX_STORIES = 12

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
        open_outlets: set[str] = set()
        paywalled_outlets: set[str] = set()
        brief_revision = brief_by_cluster.get(row.get("id"))
        source_metrics = cluster_brief_source_metrics(row)

        for cluster_article in sorted(cluster_articles, key=lambda item: item.get("rank_in_cluster", 0)):
            article = cluster_article.get("articles") or {}
            outlet = ((article.get("outlets") or {}).get("canonical_name") or "").strip()
            if not outlet:
                continue

            seen_outlets.add(outlet)
            access_tier = infer_access_tier(outlet, ((article.get("metadata") or {}).get("access_signal") if isinstance(article.get("metadata"), dict) else None))
            if access_tier == "open":
                open_outlets.add(outlet)
            if access_tier == "likely_paywalled":
                paywalled_outlets.add(outlet)

            article_rows.append(
                {
                    "outlet": outlet,
                    "extraction_quality": (article.get("metadata") or {}).get("extraction_quality"),
                    "has_body_text": bool((article.get("body_text") or "").strip()),
                    "is_substantive": is_substantive_article(article),
                }
            )

        stories.append(
            {
                "slug": row["slug"],
                "title": row["canonical_headline"],
                "outlet_count": len(seen_outlets),
                "substantive_source_count": source_metrics["substantive_outlet_count"],
                "article_body_source_count": source_metrics["article_body_outlet_count"],
                "full_brief_ready": source_metrics["full_brief_ready"],
                "open_outlet_count": len(open_outlets),
                "likely_paywalled_outlet_count": len(paywalled_outlets),
                "open_alternate_ready": source_metrics["substantive_outlet_count"] >= 2 and len(open_outlets) >= 1,
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
