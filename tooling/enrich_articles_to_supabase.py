#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import parse

from generate_temporary_live_feed import clean_summary_snippet, fetch_article_enrichment
from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_ARTICLES_PER_RUN = 12
FAILED_RETRY_MINUTES = 30


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_recent_articles(client: SupabaseRestClient) -> list[dict[str, Any]]:
    return client.get(
        "/articles?select=id,original_url,canonical_url,summary,body_text,preview_image_url,preview_image_status,metadata,published_at&order=published_at.desc&limit=240"
    ) or []


def fetch_active_story_slugs(client: SupabaseRestClient) -> set[str]:
    rows = client.get("/story_clusters?select=slug,metadata&order=latest_event_at.desc&limit=40") or []
    active: set[str] = set()
    for row in rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") not in (
            "automated_feed_ingestion",
            "live_snapshot",
        ):
            continue

        slug = row.get("slug")
        if isinstance(slug, str) and slug:
            active.add(slug)

    return active


def fetch_discovery_status(client: SupabaseRestClient) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/raw_discovered_urls?select=id,discovered_url,canonical_url,fetch_status,discovered_at,last_attempted_at,error_message&order=discovered_at.desc&limit=1000"
    ) or []

    by_url: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in (row.get("canonical_url"), row.get("discovered_url")):
            if isinstance(key, str) and key and key not in by_url:
                by_url[key] = row
    return by_url


def should_enrich(article: dict[str, Any], discovery: dict[str, Any] | None) -> bool:
    url = article.get("original_url")
    if not isinstance(url, str) or not url.strip():
        return False

    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = article.get("body_text")

    if extraction_quality == "article_body" and isinstance(body_text, str) and body_text.strip():
        return False

    if discovery:
        status = discovery.get("fetch_status")
        if status == "fetched" and isinstance(body_text, str) and body_text.strip():
            return False

        if status == "failed":
            attempted_at = parse_timestamp(discovery.get("last_attempted_at"))
            if attempted_at and attempted_at > datetime.now(timezone.utc) - timedelta(minutes=FAILED_RETRY_MINUTES):
                return False

    return True


def fallback_summary_for_article(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    if isinstance(metadata, dict):
        feed_summary = metadata.get("feed_summary")
        if isinstance(feed_summary, str) and feed_summary.strip():
            return feed_summary

    summary = article.get("summary")
    return summary if isinstance(summary, str) else ""


def patch_discovery_row(client: SupabaseRestClient, discovery_id: str, values: dict[str, Any]) -> None:
    client.patch(
        f"/raw_discovered_urls?id=eq.{discovery_id}",
        values,
        prefer="return=minimal",
    )


def patch_article_row(client: SupabaseRestClient, article_id: str, values: dict[str, Any]) -> None:
    client.patch(
        f"/articles?id=eq.{article_id}",
        values,
        prefer="return=minimal",
    )


def candidate_articles(client: SupabaseRestClient) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    discoveries = fetch_discovery_status(client)
    active_story_slugs = fetch_active_story_slugs(client)
    candidates: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    for article in fetch_recent_articles(client):
        url = article.get("original_url")
        if not isinstance(url, str) or not url:
            continue

        discovery = discoveries.get(url) or discoveries.get(article.get("canonical_url") or "")
        if not should_enrich(article, discovery):
            continue

        candidates.append((article, discovery))

    def candidate_priority(item: tuple[dict[str, Any], dict[str, Any] | None]) -> tuple[int, int, int, datetime, datetime]:
        article, discovery = item
        metadata = article.get("metadata") or {}
        extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
        story_slug = metadata.get("story_slug") if isinstance(metadata, dict) else None
        body_text = article.get("body_text")
        needs_article_body = extraction_quality != "article_body" or not (isinstance(body_text, str) and body_text.strip())

        status = (discovery or {}).get("fetch_status")
        status_priority = {
            "pending": 0,
            "normalized": 1,
            "failed": 2,
            "fetched": 3,
        }.get(status, 4)

        queue_timestamp = (
            parse_timestamp((discovery or {}).get("last_attempted_at"))
            or parse_timestamp((discovery or {}).get("discovered_at"))
            or parse_timestamp(article.get("published_at"))
            or datetime.now(timezone.utc)
        )
        published_at = parse_timestamp(article.get("published_at")) or datetime.now(timezone.utc)
        active_story_priority = 0 if isinstance(story_slug, str) and story_slug in active_story_slugs else 1
        return (active_story_priority, 0 if needs_article_body else 1, status_priority, queue_timestamp, published_at)

    candidates.sort(key=candidate_priority)
    return candidates[:MAX_ARTICLES_PER_RUN]


def merge_article_metadata(article: dict[str, Any], enrichment: dict[str, Any], attempted_at: str) -> dict[str, Any]:
    metadata = dict(article.get("metadata") or {})
    if "feed_summary" not in metadata and article.get("summary"):
        metadata["feed_summary"] = article["summary"]

    metadata["named_entities"] = enrichment.get("named_entities") or []
    metadata["extraction_quality"] = enrichment.get("extraction_quality") or "rss_only"
    metadata["enrichment_last_attempted_at"] = attempted_at
    metadata["enrichment_worker_version"] = "0.1.0"
    return metadata


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    candidates = candidate_articles(client)
    attempted = 0
    enriched = 0
    failed = 0
    skipped = 0

    for article, discovery in candidates:
        attempted += 1
        url = article["original_url"]
        attempted_at = datetime.now(timezone.utc).isoformat()

        try:
            fallback_summary = fallback_summary_for_article(article)
            enrichment = fetch_article_enrichment(url, fallback_summary)
            summary = clean_summary_snippet(str(enrichment.get("lede", "")) or fallback_summary, 320)
            body_preview = str(enrichment.get("body_preview", "") or "").strip()
            extraction_quality = str(enrichment.get("extraction_quality", "rss_only"))

            metadata = merge_article_metadata(article, enrichment, attempted_at)
            patch_payload = {
                "summary": summary or article.get("summary"),
                "body_text": body_preview or article.get("body_text"),
                "metadata": metadata,
            }

            if not article.get("preview_image_url") and enrichment.get("image"):
                patch_payload["preview_image_url"] = enrichment["image"]

            patch_article_row(client, article["id"], patch_payload)

            if discovery:
                patch_discovery_row(
                    client,
                    discovery["id"],
                    {
                        "fetch_status": "fetched" if extraction_quality != "rss_only" else "normalized",
                        "last_attempted_at": attempted_at,
                        "error_message": None,
                    },
                )

            if extraction_quality == "rss_only":
                skipped += 1
            else:
                enriched += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            if discovery:
                patch_discovery_row(
                    client,
                    discovery["id"],
                    {
                        "fetch_status": "failed",
                        "last_attempted_at": attempted_at,
                        "error_message": str(exc)[:500],
                    },
                )
        time.sleep(0.2)

    print(
        json.dumps(
            {
                "candidate_articles": len(candidates),
                "attempted": attempted,
                "enriched": enriched,
                "rss_only_fallbacks": skipped,
                "failed": failed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
