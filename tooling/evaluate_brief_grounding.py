#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_STORIES = 12
STOPWORDS = {
    "about",
    "across",
    "after",
    "around",
    "because",
    "between",
    "clear",
    "clearest",
    "closer",
    "coverage",
    "deserves",
    "event",
    "focus",
    "framing",
    "headline",
    "linked",
    "mostly",
    "normal",
    "outlet",
    "outlets",
    "prism",
    "report",
    "reporting",
    "sequence",
    "sources",
    "story",
    "their",
    "there",
    "these",
    "they",
    "this",
    "what",
    "while",
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", normalize_whitespace(value).lower())
        if token not in STOPWORDS
    }


def overlap_ratio(left: str, right: str) -> float:
    left_tokens = text_tokens(left)
    right_tokens = text_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens))


def fetch_active_clusters(client: SupabaseRestClient) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/story_clusters?select=id,slug,canonical_headline,latest_event_at,metadata&order=latest_event_at.desc&limit=80"
    ) or []
    active: dict[str, dict[str, Any]] = {}
    for row in rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") not in ("automated_feed_ingestion", "live_snapshot"):
            continue
        cluster_id = row.get("id")
        if isinstance(cluster_id, str) and cluster_id:
            active[cluster_id] = row
    return active


def fetch_current_briefs(client: SupabaseRestClient) -> list[dict[str, Any]]:
    return client.get(
        "/story_brief_revisions?select=cluster_id,revision_tag,status,title,paragraphs,why_it_matters,where_sources_agree,where_coverage_differs,what_to_watch,source_snapshot,metadata&is_current=eq.true&limit=200"
    ) or []


def matched_support_refs(snapshot_by_article: dict[str, dict[str, Any]], refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for ref in refs:
        article_id = ref.get("article_id")
        if isinstance(article_id, str) and article_id in snapshot_by_article:
            matched.append(snapshot_by_article[article_id])
    return matched


def support_corpus(refs: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for ref in refs:
        for field in ("headline", "focus", "used_snippet", "outlet"):
            value = ref.get(field)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
    return " ".join(chunks)


def section_result(
    *,
    name: str,
    text: str,
    refs: list[dict[str, Any]],
    snapshot_by_article: dict[str, dict[str, Any]],
    minimum_overlap: float,
    allow_event_based: bool = False,
) -> dict[str, Any]:
    cleaned_text = normalize_whitespace(text)
    if not cleaned_text:
        return {"name": name, "status": "missing", "overlap": 0.0, "supported_by": 0}

    if allow_event_based and not refs and cleaned_text.lower().startswith("watch for the next turn:"):
        return {"name": name, "status": "event_based", "overlap": 1.0, "supported_by": 0}

    matched_refs = matched_support_refs(snapshot_by_article, refs)
    if not matched_refs:
        return {"name": name, "status": "unsupported", "overlap": 0.0, "supported_by": 0}

    corpus = support_corpus(matched_refs)
    overlap = overlap_ratio(cleaned_text, corpus)
    outlet_hit = any(
        isinstance(ref.get("outlet"), str) and ref["outlet"].lower() in cleaned_text.lower() for ref in matched_refs
    )

    if overlap >= minimum_overlap or (outlet_hit and overlap >= minimum_overlap * 0.65):
        status = "grounded"
    elif overlap >= minimum_overlap * 0.55:
        status = "weak"
    else:
        status = "unsupported"

    return {
        "name": name,
        "status": status,
        "overlap": round(overlap, 3),
        "supported_by": len(matched_refs),
    }


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    clusters = fetch_active_clusters(client)
    briefs = fetch_current_briefs(client)

    results: list[dict[str, Any]] = []
    summary = {
        "stories_evaluated": 0,
        "grounded_sections": 0,
        "weak_sections": 0,
        "unsupported_sections": 0,
    }

    for brief in briefs:
        cluster = clusters.get(brief.get("cluster_id"))
        if not cluster:
            continue

        metadata = brief.get("metadata") or {}
        section_support = metadata.get("section_support") if isinstance(metadata, dict) else {}
        if not isinstance(section_support, dict):
            section_support = {}

        snapshot = brief.get("source_snapshot") or []
        snapshot_by_article = {
            row["article_id"]: row
            for row in snapshot
            if isinstance(row, dict) and isinstance(row.get("article_id"), str)
        }

        paragraph_results: list[dict[str, Any]] = []
        paragraph_support = section_support.get("paragraphs") if isinstance(section_support.get("paragraphs"), list) else []
        paragraphs = brief.get("paragraphs") if isinstance(brief.get("paragraphs"), list) else []
        for index, paragraph in enumerate(paragraphs):
            if not isinstance(paragraph, str):
                continue
            support_entry = next(
                (
                    entry
                    for entry in paragraph_support
                    if isinstance(entry, dict) and int(entry.get("index", -1)) == index
                ),
                {},
            )
            refs = support_entry.get("support") if isinstance(support_entry, dict) and isinstance(support_entry.get("support"), list) else []
            paragraph_results.append(
                section_result(
                    name=f"paragraph_{index + 1}",
                    text=paragraph,
                    refs=refs,
                    snapshot_by_article=snapshot_by_article,
                    minimum_overlap=0.16,
                )
            )

        named_sections = [
            section_result(
                name="why_it_matters",
                text=str(brief.get("why_it_matters") or ""),
                refs=section_support.get("why_it_matters") if isinstance(section_support.get("why_it_matters"), list) else [],
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=0.11,
            ),
            section_result(
                name="where_sources_agree",
                text=str(brief.get("where_sources_agree") or ""),
                refs=section_support.get("where_sources_agree") if isinstance(section_support.get("where_sources_agree"), list) else [],
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=0.14,
            ),
            section_result(
                name="where_coverage_differs",
                text=str(brief.get("where_coverage_differs") or ""),
                refs=section_support.get("where_coverage_differs") if isinstance(section_support.get("where_coverage_differs"), list) else [],
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=0.13,
            ),
            section_result(
                name="what_to_watch",
                text=str(brief.get("what_to_watch") or ""),
                refs=section_support.get("what_to_watch") if isinstance(section_support.get("what_to_watch"), list) else [],
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=0.1,
                allow_event_based=True,
            ),
        ]

        section_results = paragraph_results + named_sections
        summary["stories_evaluated"] += 1
        summary["grounded_sections"] += sum(1 for item in section_results if item["status"] in {"grounded", "event_based"})
        summary["weak_sections"] += sum(1 for item in section_results if item["status"] == "weak")
        summary["unsupported_sections"] += sum(1 for item in section_results if item["status"] in {"unsupported", "missing"})

        results.append(
            {
                "slug": cluster.get("slug"),
                "title": cluster.get("canonical_headline"),
                "revision_tag": brief.get("revision_tag"),
                "status": brief.get("status"),
                "grounding_ratio": round(
                    sum(1 for item in section_results if item["status"] in {"grounded", "event_based"})
                    / max(1, len(section_results)),
                    3,
                ),
                "unsupported_sections": [
                    item["name"] for item in section_results if item["status"] in {"unsupported", "missing"}
                ],
                "weak_sections": [item["name"] for item in section_results if item["status"] == "weak"],
                "sections": section_results,
            }
        )

    print(
        json.dumps(
            {
                "summary": summary,
                "stories": results[:MAX_STORIES],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
