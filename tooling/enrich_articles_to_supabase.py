#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import parse

from generate_temporary_live_feed import (
    choose_story_summary,
    clean_summary_snippet,
    fetch_article_enrichment,
)
from ingest_live_feeds_to_supabase import choose_story_source_options, infer_access_tier
from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_ARTICLES_PER_RUN = 24
FAILED_RETRY_MINUTES = 30
LIKELY_PAYWALLED_DOMAINS = (
    "bloomberg.com",
    "ft.com",
    "nytimes.com",
    "wsj.com",
)
OPEN_ACCESS_DOMAINS = (
    "abcnews.com",
    "apnews.com",
    "bbc.com",
    "cbsnews.com",
    "cnn.com",
    "foxnews.com",
    "msnbc.com",
    "nbcnews.com",
    "npr.org",
    "pbs.org",
    "politico.com",
    "reuters.com",
    "thehill.com",
)

STOPWORD_TOKENS = {
    "about",
    "after",
    "again",
    "amid",
    "around",
    "because",
    "before",
    "being",
    "between",
    "could",
    "despite",
    "during",
    "first",
    "from",
    "have",
    "into",
    "its",
    "just",
    "like",
    "more",
    "most",
    "over",
    "says",
    "saying",
    "than",
    "that",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "today",
    "under",
    "while",
    "with",
}

ABBREVIATION_PATTERNS = (
    r"\bU\.S\.",
    r"\bU\.K\.",
    r"\bE\.U\.",
    r"\bMr\.",
    r"\bMrs\.",
    r"\bMs\.",
    r"\bDr\.",
    r"\bSen\.",
    r"\bRep\.",
    r"\bGov\.",
    r"\bGen\.",
    r"\bLt\.",
    r"\bCol\.",
    r"\bSt\.",
)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_recent_articles(client: SupabaseRestClient) -> list[dict[str, Any]]:
    return client.get(
        "/articles?select=id,headline,original_url,canonical_url,summary,body_text,preview_image_url,preview_image_status,metadata,published_at&order=published_at.desc&limit=240"
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


def fetch_active_story_metrics(client: SupabaseRestClient) -> dict[str, dict[str, int]]:
    rows = client.get("/story_clusters?select=slug,outlet_count,metadata&order=latest_event_at.desc&limit=80") or []
    metrics: dict[str, dict[str, int]] = {}
    for row in rows:
        slug = row.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        metadata = row.get("metadata") or {}
        story_origin = metadata.get("story_origin") if isinstance(metadata, dict) else None
        if story_origin not in ("automated_feed_ingestion", "live_snapshot"):
            continue
        metrics[slug] = {
            "outlet_count": int(row.get("outlet_count") or 0),
            "substantive_source_count": int(metadata.get("substantive_source_count") or 0) if isinstance(metadata, dict) else 0,
            "quality_score": int(metadata.get("quality_score") or 0) if isinstance(metadata, dict) else 0,
        }
    return metrics


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

    if extraction_quality == "article_body" and isinstance(body_text, str) and body_text.strip() and not current_article_mismatch(article):
        return False

    if discovery:
        status = discovery.get("fetch_status")
        if status == "fetched" and isinstance(body_text, str) and body_text.strip() and not current_article_mismatch(article):
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


def normalize_matching_text(value: str | None) -> str:
    return " ".join((value or "").lower().replace("u.s.", "us").replace("u.s", "us").split())


def split_narrative_sentences(value: str | None) -> list[str]:
    cleaned = normalize_matching_text(value)
    if not cleaned:
        return []

    protected = cleaned
    replacements: dict[str, str] = {}
    for index, pattern in enumerate(ABBREVIATION_PATTERNS):
        def repl(match: re.Match[str], token_index: int = index) -> str:
            token = f"__ABBR_{token_index}_{len(replacements)}__"
            replacements[token] = match.group(0)
            return token

        protected = re.sub(pattern, repl, protected, flags=re.IGNORECASE)

    matches = re.findall(r"[^.!?]+[.!?]+", protected)
    if not matches:
        restored = protected
        for token, original in replacements.items():
            restored = restored.replace(token, original)
        return [restored]

    sentences = []
    for segment in matches:
        restored = segment
        for token, original in replacements.items():
            restored = restored.replace(token, original)
        restored = " ".join(restored.split()).strip()
        if restored:
            sentences.append(restored)
    return sentences


def first_narrative_sentences(value: str | None, count: int = 2) -> str:
    cleaned = split_narrative_sentences(value)
    if not cleaned:
        return normalize_matching_text(value)
    return " ".join(cleaned[:count]).strip()


def comparable_tokens(value: str | None) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]{4,}", normalize_matching_text(value)):
        if token in STOPWORD_TOKENS:
            continue
        tokens.add(token)
    return tokens


def alignment_score(reference_text: str, candidate_text: str) -> float:
    reference_tokens = comparable_tokens(reference_text)
    candidate_tokens = comparable_tokens(candidate_text)
    if len(reference_tokens) < 4 or len(candidate_tokens) < 4:
        return 1.0
    overlap = reference_tokens & candidate_tokens
    return len(overlap) / max(1, min(len(reference_tokens), len(candidate_tokens)))


def extraction_mismatch(article: dict[str, Any], enrichment: dict[str, Any]) -> bool:
    metadata = article.get("metadata") if isinstance(article.get("metadata"), dict) else {}
    reference_text = " ".join(
        filter(
            None,
            [
                article.get("headline"),
                metadata.get("feed_summary") if isinstance(metadata, dict) else None,
            ],
        )
    )
    candidate_text = first_narrative_sentences(
        " ".join(filter(None, [enrichment.get("lede"), enrichment.get("body_preview")])),
        2,
    )
    if not candidate_text.strip():
        return False
    return alignment_score(reference_text, candidate_text) < 0.16


def current_article_mismatch(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") if isinstance(article.get("metadata"), dict) else {}
    reference_text = " ".join(
        filter(
            None,
            [
                article.get("headline"),
                metadata.get("feed_summary") if isinstance(metadata, dict) else None,
            ],
        )
    )
    candidate_text = first_narrative_sentences(
        article.get("body_text") or article.get("summary"),
        2,
    )
    if not reference_text.strip() or not candidate_text.strip():
        return False
    return alignment_score(reference_text, candidate_text) < 0.16


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


def infer_access_signal(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    access_signal = metadata.get("access_signal") if isinstance(metadata, dict) else None
    if isinstance(access_signal, str) and access_signal.strip():
        return access_signal

    for value in (article.get("canonical_url"), article.get("original_url")):
        if not isinstance(value, str) or not value.strip():
            continue
        hostname = parse.urlparse(value).hostname or ""
        domain = hostname.replace("www.", "").lower()
        if any(domain == candidate or domain.endswith(f".{candidate}") for candidate in LIKELY_PAYWALLED_DOMAINS):
            return "likely_paywalled"
        if any(domain == candidate or domain.endswith(f".{candidate}") for candidate in OPEN_ACCESS_DOMAINS):
            return "open"

    return "unknown"


def refresh_story_cluster_summary(client: SupabaseRestClient, story_slug: str) -> bool:
    encoded_slug = parse.quote(story_slug, safe="")
    rows = client.get(
        f"/story_clusters?select=id,slug,canonical_headline,outlet_count,metadata,cluster_articles!inner(rank_in_cluster,articles!inner(headline,summary,body_text,original_url,canonical_url,metadata,site_name))&slug=eq.{encoded_slug}&limit=1"
    ) or []
    if not rows:
        return False

    row = rows[0]
    relation_rows = row.get("cluster_articles") or []
    ordered_relations = sorted(
        relation_rows,
        key=lambda item: (
            item.get("rank_in_cluster") if isinstance(item, dict) else 999,
        ),
    )

    articles: list[dict[str, Any]] = []
    sources: list[str] = []
    for relation in ordered_relations:
        article = relation.get("articles") if isinstance(relation, dict) else None
        if not isinstance(article, dict):
            continue
        metadata = article.get("metadata") if isinstance(article.get("metadata"), dict) else {}
        site_name = article.get("site_name") or ""
        articles.append(
            {
                "source": site_name,
                "site_name": site_name,
                "title": article.get("headline") or row.get("canonical_headline") or "",
                "summary": article.get("summary") or "",
                "feed_summary": metadata.get("feed_summary") or article.get("summary") or "",
                "lede": article.get("summary") or metadata.get("feed_summary") or "",
                "body_preview": article.get("body_text") or "",
                "body_text": article.get("body_text") or "",
                "extraction_quality": metadata.get("extraction_quality") or "rss_only",
                "url": article.get("original_url") or article.get("canonical_url") or "",
                "domain": parse.urlparse(article.get("original_url") or article.get("canonical_url") or "").hostname or "",
                "access_signal": metadata.get("access_signal") or "unknown",
                "outlet": site_name,
            }
        )
        if site_name:
            sources.append(site_name)

    if not articles:
        return False

    headline = row.get("canonical_headline") or story_slug.replace("-", " ").title()
    summary, summary_quality, substantive_source_count = choose_story_summary(articles, headline, sources)
    metadata = dict(row.get("metadata") or {})
    outlet_count = int(row.get("outlet_count") or 0)
    metadata["summary_quality_score"] = summary_quality
    metadata["substantive_source_count"] = substantive_source_count
    metadata["homepage_eligible"] = outlet_count >= 2 and (
        substantive_source_count >= 2 or summary_quality >= 8
    )
    for article in articles:
        article["access_tier"] = infer_access_tier(article)
    metadata["source_options"] = choose_story_source_options(articles)
    metadata["summary_refreshed_at"] = datetime.now(timezone.utc).isoformat()

    client.patch(
        f"/story_clusters?id=eq.{row['id']}",
        {"summary": summary, "metadata": metadata},
        prefer="return=minimal",
    )
    return True


def candidate_articles(client: SupabaseRestClient) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    discoveries = fetch_discovery_status(client)
    active_story_slugs = fetch_active_story_slugs(client)
    active_story_metrics = fetch_active_story_metrics(client)
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
        summary_text = article.get("summary")
        needs_article_body = extraction_quality != "article_body" or not (isinstance(body_text, str) and body_text.strip())
        thin_summary = not (isinstance(summary_text, str) and len(summary_text.strip()) >= 110)
        access_signal = infer_access_signal(article)
        story_metrics = active_story_metrics.get(story_slug) if isinstance(story_slug, str) else None
        outlet_count = int((story_metrics or {}).get("outlet_count") or 0)
        substantive_source_count = int((story_metrics or {}).get("substantive_source_count") or 0)

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
        one_source_story_priority = 0 if active_story_priority == 0 and outlet_count <= 1 else 1
        thin_story_priority = 0 if active_story_priority == 0 and substantive_source_count <= 1 else 1
        access_priority = 0 if access_signal == "likely_paywalled" else 1 if access_signal == "unknown" else 2
        thin_article_priority = 0 if thin_summary else 1
        return (
            active_story_priority,
            one_source_story_priority,
            thin_story_priority,
            access_priority,
            0 if needs_article_body else 1,
            thin_article_priority,
            status_priority,
            queue_timestamp,
            published_at,
        )

    candidates.sort(key=candidate_priority)
    return candidates[:MAX_ARTICLES_PER_RUN]


def merge_article_metadata(article: dict[str, Any], enrichment: dict[str, Any], attempted_at: str) -> dict[str, Any]:
    metadata = dict(article.get("metadata") or {})
    if "feed_summary" not in metadata and article.get("summary"):
        metadata["feed_summary"] = article["summary"]

    metadata["named_entities"] = enrichment.get("named_entities") or []
    metadata["extraction_quality"] = enrichment.get("extraction_quality") or "rss_only"
    metadata["access_signal"] = enrichment.get("access_signal") or metadata.get("access_signal") or "unknown"
    metadata["enrichment_last_attempted_at"] = attempted_at
    metadata["enrichment_worker_version"] = "0.2.0"
    if enrichment.get("body_mismatch_detected"):
        metadata["body_mismatch_detected"] = True
    else:
        metadata.pop("body_mismatch_detected", None)
    if enrichment.get("fetch_blocked"):
        metadata["fetch_blocked"] = True
        metadata["fetch_block_reason"] = enrichment.get("fetch_block_reason") or "anti_bot_challenge"
        if enrichment.get("fetch_block_vendor"):
            metadata["fetch_block_vendor"] = enrichment["fetch_block_vendor"]
        metadata["fetch_blocked_at"] = attempted_at
    else:
        metadata.pop("fetch_blocked", None)
        metadata.pop("fetch_block_reason", None)
        metadata.pop("fetch_block_vendor", None)
        metadata.pop("fetch_blocked_at", None)
    if enrichment.get("fetch_strategy"):
        metadata["fetch_strategy"] = enrichment["fetch_strategy"]
    if enrichment.get("source_api_attempted") is True:
        metadata["source_api_attempted"] = True
    else:
        metadata.pop("source_api_attempted", None)
    if enrichment.get("source_api_used"):
        metadata["source_api_used"] = enrichment["source_api_used"]
        if enrichment.get("source_api_endpoint"):
            metadata["source_api_endpoint"] = enrichment["source_api_endpoint"]
    else:
        metadata.pop("source_api_used", None)
        metadata.pop("source_api_endpoint", None)
    if enrichment.get("source_api_fallback_error"):
        metadata["source_api_fallback_error"] = enrichment["source_api_fallback_error"]
    else:
        metadata.pop("source_api_fallback_error", None)
    if enrichment.get("browser_attempted") is True:
        metadata["browser_attempted"] = True
    else:
        metadata.pop("browser_attempted", None)
    if enrichment.get("browser_rendered") is True:
        metadata["browser_rendered"] = True
        if enrichment.get("browser_executable"):
            metadata["browser_executable"] = enrichment["browser_executable"]
        if enrichment.get("browser_final_url"):
            metadata["browser_final_url"] = enrichment["browser_final_url"]
    else:
        metadata.pop("browser_rendered", None)
        metadata.pop("browser_executable", None)
        metadata.pop("browser_final_url", None)
    if enrichment.get("browser_fallback_error"):
        metadata["browser_fallback_error"] = enrichment["browser_fallback_error"]
    else:
        metadata.pop("browser_fallback_error", None)
    return metadata


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    candidates = candidate_articles(client)
    attempted = 0
    enriched = 0
    failed = 0
    skipped = 0
    blocked = 0
    refreshed_clusters = 0
    touched_story_slugs: set[str] = set()

    for article, discovery in candidates:
        attempted += 1
        url = article["original_url"]
        attempted_at = datetime.now(timezone.utc).isoformat()
        metadata = article.get("metadata") if isinstance(article.get("metadata"), dict) else {}
        story_slug = metadata.get("story_slug") if isinstance(metadata, dict) else None
        if isinstance(story_slug, str) and story_slug:
            touched_story_slugs.add(story_slug)

        try:
            fallback_summary = fallback_summary_for_article(article)
            enrichment = fetch_article_enrichment(url, fallback_summary)
            mismatch_detected = extraction_mismatch(article, enrichment)
            summary = clean_summary_snippet(str(enrichment.get("lede", "")) or fallback_summary, 320)
            body_preview = str(enrichment.get("body_preview", "") or "").strip()
            extraction_quality = str(enrichment.get("extraction_quality", "rss_only"))
            fetch_blocked = enrichment.get("fetch_blocked") is True

            if mismatch_detected:
                enrichment["body_mismatch_detected"] = True
                summary = clean_summary_snippet(fallback_summary, 320) or article.get("summary") or ""
                body_preview = ""
                extraction_quality = "rss_only"
                enrichment["extraction_quality"] = extraction_quality

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
                        "fetch_status": (
                            "failed"
                            if fetch_blocked
                            else "fetched" if extraction_quality != "rss_only" else "normalized"
                        ),
                        "last_attempted_at": attempted_at,
                        "error_message": (
                            f"fetch_blocked:{enrichment.get('fetch_block_reason') or 'anti_bot_challenge'}"
                            if fetch_blocked
                            else None
                        ),
                    },
                )

            if fetch_blocked:
                blocked += 1
                skipped += 1
            elif extraction_quality == "rss_only":
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

    for story_slug in sorted(touched_story_slugs):
        if refresh_story_cluster_summary(client, story_slug):
            refreshed_clusters += 1

    print(
        json.dumps(
            {
                "candidate_articles": len(candidates),
                "attempted": attempted,
                "enriched": enriched,
                "rss_only_fallbacks": skipped,
                "fetch_blocked": blocked,
                "failed": failed,
                "refreshed_clusters": refreshed_clusters,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
