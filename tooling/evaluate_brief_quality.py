#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

try:
    from tooling.evaluate_brief_grounding import section_result
    from tooling.generate_story_briefs_to_supabase import (
        cluster_brief_source_metrics,
        cluster_open_alternate_source,
        infer_access_tier,
        is_substantive_article,
        normalize_whitespace,
    )
    from tooling.sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from evaluate_brief_grounding import section_result
    from generate_story_briefs_to_supabase import (
        cluster_brief_source_metrics,
        cluster_open_alternate_source,
        infer_access_tier,
        is_substantive_article,
        normalize_whitespace,
    )
    from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


DEFAULT_SCAN_LIMIT = 80
DEFAULT_SAMPLE_LIMIT = 12
DEFAULT_CONTROL_COUNT = 2
MAX_BRIEFS = 200

EARLY_SPLIT_SENTINEL = "It is too early to call a real split in coverage."
ONE_SOURCE_SENTINEL = "one-source early brief"
FOLLOW_ON_SENTINEL = "Prism has also linked an open follow-on read from"
SECTION_SUPPORT_NAMES = (
    "why_it_matters",
    "where_sources_agree",
    "where_coverage_differs",
    "what_to_watch",
)
SEVERITY_WEIGHT = {
    "critical": 30,
    "warning": 12,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate current stored Prism Brief quality for active live stories by combining "
            "brief readiness, section grounding, and text-quality review heuristics."
        )
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SAMPLE_LIMIT,
        help=(
            "Target number of review stories before adding clean controls. "
            "All critical stories are still included even if this is exceeded. Defaults to %(default)s."
        ),
    )
    parser.add_argument(
        "--control-count",
        type=int,
        default=DEFAULT_CONTROL_COUNT,
        help="Number of clean-control stories to include when warnings or critical failures exist. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=DEFAULT_SCAN_LIMIT,
        help="Maximum number of active stories to scan. Defaults to %(default)s.",
    )
    return parser.parse_args()


def isoformat_utc(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    return current.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_active_clusters(client: SupabaseRestClient, *, scan_limit: int) -> list[dict[str, Any]]:
    rows = client.get(
        "/story_clusters?select=id,slug,canonical_headline,summary,latest_event_at,metadata,cluster_articles(rank_in_cluster,articles!inner(id,headline,summary,body_text,canonical_url,original_url,site_name,metadata,outlets!inner(canonical_name)))"
        f"&order=latest_event_at.desc&limit={scan_limit}"
    ) or []
    active: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") not in ("automated_feed_ingestion", "live_snapshot"):
            continue
        active.append(row)
    return active


def fetch_current_briefs(client: SupabaseRestClient) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/story_brief_revisions?select=cluster_id,revision_tag,status,title,paragraphs,why_it_matters,where_sources_agree,where_coverage_differs,what_to_watch,source_snapshot,metadata&is_current=eq.true"
        f"&limit={MAX_BRIEFS}"
    ) or []
    return {row["cluster_id"]: row for row in rows if isinstance(row.get("cluster_id"), str)}


def make_flag(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def quote_balance_issue(text: str) -> bool:
    if not text:
        return False
    return text.count("“") != text.count("”") or text.count('"') % 2 == 1


def duplicate_paragraph_pairs(paragraphs: list[str]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    cleaned = [normalize_whitespace(paragraph) for paragraph in paragraphs if isinstance(paragraph, str)]
    for left_index, left in enumerate(cleaned):
        if not left:
            continue
        left_tokens = set(re.findall(r"[a-z0-9]{4,}", left.lower()))
        for right_index in range(left_index + 1, len(cleaned)):
            right = cleaned[right_index]
            if not right:
                continue
            right_tokens = set(re.findall(r"[a-z0-9]{4,}", right.lower()))
            if not left_tokens or not right_tokens:
                continue
            overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
            if overlap >= 0.82:
                pairs.append(
                    {
                        "left": left_index + 1,
                        "right": right_index + 1,
                        "overlap": round(overlap, 3),
                    }
                )
    return pairs


def build_cluster_article_rows(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relation in sorted(cluster.get("cluster_articles") or [], key=lambda item: item.get("rank_in_cluster") or 999):
        article = relation.get("articles") if isinstance(relation, dict) else None
        if not isinstance(article, dict):
            continue

        metadata = article.get("metadata") or {}
        outlet = ((article.get("outlets") or {}).get("canonical_name") or article.get("site_name") or "Unknown outlet").strip()
        access_signal = metadata.get("access_signal") if isinstance(metadata, dict) else None
        rows.append(
            {
                "article_id": article.get("id"),
                "outlet": outlet,
                "headline": article.get("headline") or cluster.get("canonical_headline") or "",
                "summary": article.get("summary") or "",
                "extraction_quality": metadata.get("extraction_quality") if isinstance(metadata, dict) else None,
                "access_tier": infer_access_tier(outlet, access_signal if isinstance(access_signal, str) else None),
                "fetch_blocked": bool(isinstance(metadata, dict) and metadata.get("fetch_blocked") is True),
                "is_substantive": is_substantive_article(article),
            }
        )
    return rows


def brief_sections(brief: dict[str, Any]) -> dict[str, str]:
    paragraphs = brief.get("paragraphs") if isinstance(brief.get("paragraphs"), list) else []
    sections = {f"paragraph_{index + 1}": paragraph for index, paragraph in enumerate(paragraphs) if isinstance(paragraph, str)}
    for name in SECTION_SUPPORT_NAMES:
        value = brief.get(name)
        if isinstance(value, str) and value.strip():
            sections[name] = value
    return sections


def evaluate_grounding_sections(brief: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = brief.get("metadata") or {}
    section_support = metadata.get("section_support") if isinstance(metadata, dict) else {}
    if not isinstance(section_support, dict):
        section_support = {}
    section_grounding_mode = metadata.get("section_grounding_mode") if isinstance(metadata, dict) else {}
    if not isinstance(section_grounding_mode, dict):
        section_grounding_mode = {}

    snapshot = brief.get("source_snapshot") if isinstance(brief.get("source_snapshot"), list) else []
    snapshot_by_article = {
        row["article_id"]: row
        for row in snapshot
        if isinstance(row, dict) and isinstance(row.get("article_id"), str)
    }

    results: list[dict[str, Any]] = []
    paragraphs = brief.get("paragraphs") if isinstance(brief.get("paragraphs"), list) else []
    paragraph_support = section_support.get("paragraphs") if isinstance(section_support.get("paragraphs"), list) else []
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
        grounding_mode = (
            support_entry.get("grounding_mode")
            if isinstance(support_entry, dict) and isinstance(support_entry.get("grounding_mode"), str)
            else "required"
        )
        if grounding_mode == "scaffold":
            results.append({"name": f"paragraph_{index + 1}", "status": "scaffold", "overlap": 1.0, "supported_by": 0})
            continue
        refs = support_entry.get("support") if isinstance(support_entry, dict) and isinstance(support_entry.get("support"), list) else []
        results.append(
            section_result(
                name=f"paragraph_{index + 1}",
                text=paragraph,
                refs=refs,
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=0.16,
            )
        )

    for name, minimum_overlap, allow_event_based in (
        ("why_it_matters", 0.11, False),
        ("where_sources_agree", 0.14, False),
        ("where_coverage_differs", 0.13, False),
        ("what_to_watch", 0.1, True),
    ):
        if section_grounding_mode.get(name) == "scaffold":
            results.append({"name": name, "status": "scaffold", "overlap": 1.0, "supported_by": 0})
            continue
        results.append(
            section_result(
                name=name,
                text=str(brief.get(name) or ""),
                refs=section_support.get(name) if isinstance(section_support.get(name), list) else [],
                snapshot_by_article=snapshot_by_article,
                minimum_overlap=minimum_overlap,
                allow_event_based=allow_event_based,
            )
        )
    return results


def flatten_support_refs(brief: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = brief.get("metadata") or {}
    section_support = metadata.get("section_support") if isinstance(metadata, dict) else {}
    if not isinstance(section_support, dict):
        return []

    refs: list[dict[str, Any]] = []
    paragraphs = section_support.get("paragraphs")
    if isinstance(paragraphs, list):
        for entry in paragraphs:
            support = entry.get("support") if isinstance(entry, dict) else None
            if isinstance(support, list):
                refs.extend(ref for ref in support if isinstance(ref, dict))
    for name in SECTION_SUPPORT_NAMES:
        section_refs = section_support.get(name)
        if isinstance(section_refs, list):
            refs.extend(ref for ref in section_refs if isinstance(ref, dict))
    return refs


def summarize_support(brief: dict[str, Any]) -> dict[str, Any]:
    refs = flatten_support_refs(brief)
    article_counts: Counter[str] = Counter()
    outlet_counts: Counter[str] = Counter()
    snapshot = brief.get("source_snapshot") if isinstance(brief.get("source_snapshot"), list) else []
    quality_by_article = {
        row["article_id"]: row.get("extraction_quality")
        for row in snapshot
        if isinstance(row, dict) and isinstance(row.get("article_id"), str)
    }

    for ref in refs:
        article_id = ref.get("article_id")
        outlet = ref.get("outlet")
        if isinstance(article_id, str) and article_id:
            article_counts[article_id] += 1
        if isinstance(outlet, str) and outlet:
            outlet_counts[outlet] += 1

    dominant_outlet = outlet_counts.most_common(1)[0] if outlet_counts else None
    article_body_support_count = len(
        {
            article_id
            for article_id in article_counts
            if quality_by_article.get(article_id) == "article_body"
        }
    )
    return {
        "total_refs": sum(outlet_counts.values()),
        "article_counts": dict(article_counts),
        "outlet_counts": dict(outlet_counts),
        "supporting_article_count": len(article_counts),
        "supporting_outlet_count": len(outlet_counts),
        "article_body_support_count": article_body_support_count,
        "dominant_outlet": dominant_outlet[0] if dominant_outlet else None,
        "dominant_outlet_share": round((dominant_outlet[1] / sum(outlet_counts.values())), 3)
        if dominant_outlet and outlet_counts
        else 0.0,
    }


def current_source_metrics(cluster: dict[str, Any], article_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_metrics = cluster_brief_source_metrics(cluster)
    open_outlets = {row["outlet"] for row in article_rows if row["access_tier"] == "open"}
    paywalled_outlets = {row["outlet"] for row in article_rows if row["access_tier"] == "likely_paywalled"}
    blocked_outlets = {row["outlet"] for row in article_rows if row["fetch_blocked"]}

    return {
        "article_count": len(article_rows),
        "outlet_count": len({row["outlet"] for row in article_rows}),
        "substantive_source_count": source_metrics["substantive_source_count"],
        "substantive_outlet_count": source_metrics["substantive_outlet_count"],
        "article_body_outlet_count": source_metrics["article_body_outlet_count"],
        "comparison_ready_outlet_count": source_metrics.get("comparison_ready_outlet_count", 0),
        "title_only_shell_outlet_count": source_metrics.get("title_only_shell_outlet_count", 0),
        "contextual_outlet_count": source_metrics.get("contextual_outlet_count", 0),
        "open_outlet_count": len(open_outlets),
        "likely_paywalled_outlet_count": len(paywalled_outlets),
        "blocked_outlet_count": len(blocked_outlets),
        "full_brief_ready": source_metrics["full_brief_ready"],
        "open_alternate_expected": False,
    }


def snapshot_metrics(brief: dict[str, Any]) -> dict[str, Any]:
    snapshot = brief.get("source_snapshot") if isinstance(brief.get("source_snapshot"), list) else []
    outlets = {row.get("outlet") for row in snapshot if isinstance(row, dict) and isinstance(row.get("outlet"), str)}
    article_body_outlets = {
        row.get("outlet")
        for row in snapshot
        if isinstance(row, dict) and row.get("extraction_quality") == "article_body" and isinstance(row.get("outlet"), str)
    }
    return {
        "snapshot_source_count": len(snapshot),
        "snapshot_outlet_count": len(outlets),
        "snapshot_article_body_outlet_count": len(article_body_outlets),
        "snapshot_comparison_ready_source_count": len(
            [row for row in snapshot if isinstance(row, dict) and row.get("comparison_ready") is True]
        ),
        "snapshot_title_only_source_count": len(
            [row for row in snapshot if isinstance(row, dict) and row.get("title_only_stub") is True]
        ),
        "snapshot_contextual_source_count": len(
            [row for row in snapshot if isinstance(row, dict) and int(row.get("context_score") or 0) >= 2]
        ),
    }


def evaluate_story_quality(cluster: dict[str, Any], brief: dict[str, Any] | None) -> dict[str, Any]:
    article_rows = build_cluster_article_rows(cluster)
    current_metrics = current_source_metrics(cluster, article_rows)

    evaluation = {
        "cluster_id": cluster.get("id"),
        "slug": cluster.get("slug"),
        "story_path": f"/stories/{cluster.get('slug')}" if cluster.get("slug") else None,
        "title": cluster.get("canonical_headline"),
        "latest_event_at": cluster.get("latest_event_at"),
        "review_priority": "pass",
        "risk_score": 0,
        "flags": [],
        "metrics": {
            **current_metrics,
            "grounding_ratio": None,
            "unsupported_section_count": 0,
            "weak_section_count": 0,
            "support_ref_count": 0,
            "supporting_article_count": 0,
            "supporting_outlet_count": 0,
            "article_body_support_count": 0,
            "dominant_support_outlet": None,
            "dominant_support_outlet_share": 0.0,
            "snapshot_source_count": 0,
            "snapshot_outlet_count": 0,
            "snapshot_article_body_outlet_count": 0,
            "snapshot_comparison_ready_source_count": 0,
            "snapshot_title_only_source_count": 0,
            "snapshot_contextual_source_count": 0,
        },
        "brief_status": None,
        "revision_tag": None,
        "unsupported_sections": [],
        "weak_sections": [],
        "duplicate_paragraph_pairs": [],
        "unbalanced_quote_sections": [],
        "brief_preview": None,
        "source_snapshot": [],
    }

    if brief is None:
        evaluation["flags"].append(
            make_flag(
                "missing_current_brief",
                "critical",
                "No current stored brief revision exists for this active story.",
            )
        )
        return finalize_evaluation(evaluation)

    brief_metadata = brief.get("metadata") or {}
    section_grounding_mode = brief_metadata.get("section_grounding_mode") if isinstance(brief_metadata, dict) else {}
    if not isinstance(section_grounding_mode, dict):
        section_grounding_mode = {}
    evaluation["brief_status"] = brief.get("status")
    evaluation["revision_tag"] = brief.get("revision_tag")
    evaluation["brief_preview"] = {
        "title": brief.get("title"),
        "paragraphs": [paragraph for paragraph in brief.get("paragraphs") or [] if isinstance(paragraph, str)],
        "why_it_matters": brief.get("why_it_matters"),
        "where_sources_agree": brief.get("where_sources_agree"),
        "where_coverage_differs": brief.get("where_coverage_differs"),
        "what_to_watch": brief.get("what_to_watch"),
    }
    evaluation["source_snapshot"] = [row for row in brief.get("source_snapshot") or [] if isinstance(row, dict)]
    evaluation["metrics"].update(snapshot_metrics(brief))

    stored_ready = brief_metadata.get("full_brief_ready") if isinstance(brief_metadata, dict) else None
    stored_open_alternate = bool(isinstance(brief_metadata, dict) and brief_metadata.get("open_alternate_available"))
    snapshot_article_ids = {
        row.get("article_id")
        for row in evaluation["source_snapshot"]
        if isinstance(row.get("article_id"), str)
    }
    expected_open_alternate = bool(
        cluster_open_alternate_source(
            cluster,
            exclude_article_ids=snapshot_article_ids,
        )
    )
    evaluation["metrics"]["open_alternate_expected"] = expected_open_alternate

    if brief.get("status") == "full" and not current_metrics["full_brief_ready"]:
        evaluation["flags"].append(
            make_flag(
                "full_brief_without_current_source_breadth",
                "critical",
                "The stored brief is marked full even though the current story does not have two substantive outlets.",
                substantive_outlet_count=current_metrics["substantive_outlet_count"],
            )
        )
    elif brief.get("status") != "full" and current_metrics["full_brief_ready"]:
        evaluation["flags"].append(
            make_flag(
                "ready_story_still_early",
                "warning",
                "The current story appears ready for a full brief but still serves an early brief.",
                substantive_outlet_count=current_metrics["substantive_outlet_count"],
            )
        )

    if isinstance(stored_ready, bool) and stored_ready != current_metrics["full_brief_ready"]:
        evaluation["flags"].append(
            make_flag(
                "brief_readiness_stale",
                "warning",
                "The stored brief readiness metadata no longer matches the current linked source mix.",
                stored_full_brief_ready=stored_ready,
                current_full_brief_ready=current_metrics["full_brief_ready"],
            )
        )

    if expected_open_alternate and not stored_open_alternate:
        evaluation["flags"].append(
            make_flag(
                "missing_open_alternate",
                "warning",
                "The current source mix suggests an open alternate should be recorded, but the stored brief metadata does not mark one.",
            )
        )

    if (
        section_grounding_mode.get("where_sources_agree") != "scaffold"
        and current_metrics.get("comparison_ready_outlet_count", 0) == 0
        and (
            current_metrics.get("title_only_shell_outlet_count", 0) >= 1
            or evaluation["metrics"].get("snapshot_title_only_source_count", 0) >= 1
        )
    ):
        evaluation["flags"].append(
            make_flag(
                "title_only_shell_driving_brief",
                "critical",
                "The brief is still grounding substantive comparison copy on a title-like liveblog or other thin shell source.",
                comparison_ready_outlet_count=current_metrics.get("comparison_ready_outlet_count", 0),
                title_only_shell_outlet_count=current_metrics.get("title_only_shell_outlet_count", 0),
                snapshot_title_only_source_count=evaluation["metrics"].get("snapshot_title_only_source_count", 0),
            )
        )
    elif (
        section_grounding_mode.get("where_sources_agree") != "scaffold"
        and current_metrics.get("comparison_ready_outlet_count", 0) == 0
        and current_metrics.get("contextual_outlet_count", 0) >= 1
    ):
        evaluation["flags"].append(
            make_flag(
                "contextual_source_driving_brief",
                "warning",
                "The brief is still grounding substantive comparison copy on contextual or explainer coverage instead of an event-aligned report.",
                comparison_ready_outlet_count=current_metrics.get("comparison_ready_outlet_count", 0),
                contextual_outlet_count=current_metrics.get("contextual_outlet_count", 0),
            )
        )

    section_results = evaluate_grounding_sections(brief)
    reviewable_sections = [item for item in section_results if item["status"] != "scaffold"]
    unsupported_sections = [item["name"] for item in reviewable_sections if item["status"] in {"unsupported", "missing"}]
    weak_sections = [item["name"] for item in reviewable_sections if item["status"] == "weak"]
    grounded_sections = sum(1 for item in reviewable_sections if item["status"] in {"grounded", "event_based"})
    grounding_ratio = round(grounded_sections / max(1, len(reviewable_sections)), 3) if reviewable_sections else 1.0

    evaluation["metrics"]["grounding_ratio"] = grounding_ratio
    evaluation["metrics"]["unsupported_section_count"] = len(unsupported_sections)
    evaluation["metrics"]["weak_section_count"] = len(weak_sections)
    evaluation["unsupported_sections"] = unsupported_sections
    evaluation["weak_sections"] = weak_sections

    if not flatten_support_refs(brief):
        evaluation["flags"].append(
            make_flag(
                "missing_section_support",
                "critical",
                "The stored brief does not contain section-support references for review.",
            )
        )
    elif grounding_ratio < 0.5 or len(unsupported_sections) >= 2:
        evaluation["flags"].append(
            make_flag(
                "grounding_failures",
                "critical",
                "The brief has major grounding gaps across its stored sections.",
                grounding_ratio=grounding_ratio,
                unsupported_sections=unsupported_sections,
            )
        )
    elif unsupported_sections or len(weak_sections) >= 2:
        evaluation["flags"].append(
            make_flag(
                "grounding_warnings",
                "warning",
                "The brief has weak or unsupported sections that need review.",
                grounding_ratio=grounding_ratio,
                unsupported_sections=unsupported_sections,
                weak_sections=weak_sections,
            )
        )

    support = summarize_support(brief)
    evaluation["metrics"]["support_ref_count"] = support["total_refs"]
    evaluation["metrics"]["supporting_article_count"] = support["supporting_article_count"]
    evaluation["metrics"]["supporting_outlet_count"] = support["supporting_outlet_count"]
    evaluation["metrics"]["article_body_support_count"] = support["article_body_support_count"]
    evaluation["metrics"]["dominant_support_outlet"] = support["dominant_outlet"]
    evaluation["metrics"]["dominant_support_outlet_share"] = support["dominant_outlet_share"]

    if brief.get("status") == "full" and support["supporting_outlet_count"] < 2:
        evaluation["flags"].append(
            make_flag(
                "full_brief_single_outlet_support",
                "critical",
                "The stored full brief is still supported by fewer than two outlets.",
                supporting_outlet_count=support["supporting_outlet_count"],
            )
        )
    elif brief.get("status") == "full" and support["dominant_outlet_share"] >= 0.8:
        evaluation["flags"].append(
            make_flag(
                "full_brief_dominant_support_outlet",
                "warning",
                "One outlet still dominates the support references behind this full brief.",
                dominant_outlet=support["dominant_outlet"],
                dominant_outlet_share=support["dominant_outlet_share"],
            )
        )

    if brief.get("status") == "full" and support["supporting_article_count"] < 2:
        evaluation["flags"].append(
            make_flag(
                "full_brief_single_article_support",
                "warning",
                "The stored full brief is effectively grounded on one article.",
                supporting_article_count=support["supporting_article_count"],
            )
        )

    if brief.get("status") == "full" and support["article_body_support_count"] < 2:
        evaluation["flags"].append(
            make_flag(
                "full_brief_limited_article_body_support",
                "warning",
                "The stored full brief does not have two article-body support sources.",
                article_body_support_count=support["article_body_support_count"],
            )
        )

    paragraphs = evaluation["brief_preview"]["paragraphs"] if isinstance(evaluation["brief_preview"], dict) else []
    duplicates = duplicate_paragraph_pairs(paragraphs)
    evaluation["duplicate_paragraph_pairs"] = duplicates
    if duplicates:
        evaluation["flags"].append(
            make_flag(
                "duplicate_paragraphs",
                "warning",
                "Two brief paragraphs substantially repeat the same content.",
                pairs=duplicates,
            )
        )

    unbalanced_quote_sections = [name for name, text in brief_sections(brief).items() if isinstance(text, str) and quote_balance_issue(text)]
    evaluation["unbalanced_quote_sections"] = unbalanced_quote_sections
    if unbalanced_quote_sections:
        evaluation["flags"].append(
            make_flag(
                "unbalanced_quotes",
                "warning",
                "One or more brief sections contain unbalanced quote punctuation.",
                sections=unbalanced_quote_sections,
            )
        )

    if brief.get("status") == "full" and any(
        isinstance(paragraph, str) and ONE_SOURCE_SENTINEL in paragraph.lower() for paragraph in paragraphs
    ):
        evaluation["flags"].append(
            make_flag(
                "full_brief_contains_one_source_disclaimer",
                "critical",
                "The stored full brief still contains one-source early-brief language.",
            )
        )

    where_differs = str(brief.get("where_coverage_differs") or "")
    if brief.get("status") == "full" and normalize_whitespace(where_differs).startswith(EARLY_SPLIT_SENTINEL):
        evaluation["flags"].append(
            make_flag(
                "full_brief_uses_early_split_boilerplate",
                "warning",
                "The stored full brief still uses early-brief split language in the coverage-differences section.",
            )
        )

    if brief.get("status") == "full" and any(
        isinstance(paragraph, str) and normalize_whitespace(paragraph).startswith(FOLLOW_ON_SENTINEL) for paragraph in paragraphs
    ):
        evaluation["flags"].append(
            make_flag(
                "full_brief_follow_on_boilerplate",
                "warning",
                "The stored full brief still contains generic follow-on boilerplate in its body paragraphs.",
            )
        )

    return finalize_evaluation(evaluation)


def finalize_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    severity_rank = {"critical": 0, "warning": 1}
    evaluation["flags"] = sorted(
        evaluation["flags"],
        key=lambda flag: (severity_rank.get(flag["severity"], 99), flag["code"]),
    )
    if any(flag["severity"] == "critical" for flag in evaluation["flags"]):
        evaluation["review_priority"] = "critical"
    elif any(flag["severity"] == "warning" for flag in evaluation["flags"]):
        evaluation["review_priority"] = "warning"
    else:
        evaluation["review_priority"] = "pass"
    evaluation["risk_score"] = min(100, sum(SEVERITY_WEIGHT.get(flag["severity"], 0) for flag in evaluation["flags"]))
    return evaluation


def sort_story_key(story: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(story.get("risk_score") or 0),
        story.get("latest_event_at") or "",
        str(story.get("slug") or ""),
    )


def build_review_sample(
    evaluations: list[dict[str, Any]],
    *,
    limit: int,
    control_count: int,
) -> list[dict[str, Any]]:
    critical = sorted(
        (story for story in evaluations if story["review_priority"] == "critical"),
        key=sort_story_key,
        reverse=True,
    )
    warning = sorted(
        (story for story in evaluations if story["review_priority"] == "warning"),
        key=sort_story_key,
        reverse=True,
    )
    passing = sorted(
        (story for story in evaluations if story["review_priority"] == "pass"),
        key=lambda story: (story.get("latest_event_at") or "", str(story.get("slug") or "")),
        reverse=True,
    )

    if not critical and not warning:
        sample = [deepcopy(story) for story in passing[:limit]]
        for story in sample[:control_count]:
            story["review_priority"] = "control"
        return sample

    sample = [deepcopy(story) for story in critical]
    non_control_target = max(limit - control_count, 0)
    if len(sample) < non_control_target:
        sample.extend(deepcopy(story) for story in warning[: non_control_target - len(sample)])

    controls = [deepcopy(story) for story in passing[:control_count]]
    for story in controls:
        story["review_priority"] = "control"
    sample.extend(controls)
    return sample


def build_quality_report(
    evaluations: list[dict[str, Any]],
    *,
    limit: int,
    control_count: int,
) -> dict[str, Any]:
    sample = build_review_sample(evaluations, limit=limit, control_count=control_count)
    grounding_values = [
        float(story["metrics"]["grounding_ratio"])
        for story in evaluations
        if isinstance(story["metrics"].get("grounding_ratio"), (int, float))
    ]

    return {
        "generated_at": isoformat_utc(),
        "summary": {
            "stories_scanned": len(evaluations),
            "sampled_stories": len(sample),
            "critical_stories": sum(1 for story in evaluations if story["review_priority"] == "critical"),
            "warning_stories": sum(1 for story in evaluations if story["review_priority"] == "warning"),
            "passing_stories": sum(1 for story in evaluations if story["review_priority"] == "pass"),
            "missing_current_briefs": sum(
                1 for story in evaluations if any(flag["code"] == "missing_current_brief" for flag in story["flags"])
            ),
            "full_brief_ready_stories": sum(1 for story in evaluations if story["metrics"]["full_brief_ready"]),
            "average_grounding_ratio": round(sum(grounding_values) / len(grounding_values), 3) if grounding_values else None,
            "requested_sample_limit": limit,
            "requested_control_count": control_count,
        },
        "stories": sample,
    }


def truncate(value: str, length: int = 180) -> str:
    cleaned = normalize_whitespace(value)
    if len(cleaned) <= length:
        return cleaned
    return f"{cleaned[: length - 3].rstrip()}..."


def format_flag_codes(flags: list[dict[str, Any]]) -> str:
    return ", ".join(f"`{flag.get('code')}`" for flag in flags if isinstance(flag, dict))


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Brief Quality Review",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Stories scanned: `{summary.get('stories_scanned')}`",
        f"- Stories sampled: `{summary.get('sampled_stories')}`",
        f"- Critical stories: `{summary.get('critical_stories')}`",
        f"- Warning stories: `{summary.get('warning_stories')}`",
        f"- Passing stories: `{summary.get('passing_stories')}`",
        f"- Missing current briefs: `{summary.get('missing_current_briefs')}`",
        f"- Full-brief-ready stories: `{summary.get('full_brief_ready_stories')}`",
    ]

    if summary.get("average_grounding_ratio") is not None:
        lines.append(f"- Average grounding ratio: `{summary.get('average_grounding_ratio')}`")

    lines.extend(["", "## Review Sample", ""])

    for story in report.get("stories") or []:
        metrics = story.get("metrics") or {}
        flags = story.get("flags") or []
        lines.extend(
            [
                f"### {story.get('review_priority', 'pass').title()}: {story.get('title') or 'Untitled story'}",
                "",
                f"- Story path: `{story.get('story_path') or 'n/a'}`",
                f"- Revision: `{story.get('revision_tag') or 'missing'}`",
                f"- Brief status: `{story.get('brief_status') or 'missing'}`",
                f"- Risk score: `{story.get('risk_score')}`",
                f"- Flags: {format_flag_codes(flags)}" if flags else "- Flags: none",
                (
                    "- Metrics: "
                    f"grounding `{metrics.get('grounding_ratio')}`, "
                    f"substantive outlets `{metrics.get('substantive_outlet_count')}`, "
                    f"support outlets `{metrics.get('supporting_outlet_count')}`, "
                    f"dominant support `{metrics.get('dominant_support_outlet') or 'n/a'}` "
                    f"(`{metrics.get('dominant_support_outlet_share')}`)"
                ),
            ]
        )
        if story.get("unsupported_sections"):
            lines.append(
                f"- Unsupported sections: {', '.join(f'`{name}`' for name in story['unsupported_sections'])}"
            )
        if story.get("weak_sections"):
            lines.append(f"- Weak sections: {', '.join(f'`{name}`' for name in story['weak_sections'])}")
        if story.get("duplicate_paragraph_pairs"):
            duplicate_text = ", ".join(
                f"`{pair['left']}-{pair['right']}` ({pair['overlap']})" for pair in story["duplicate_paragraph_pairs"]
            )
            lines.append(f"- Duplicate paragraphs: {duplicate_text}")
        if story.get("unbalanced_quote_sections"):
            lines.append(
                f"- Unbalanced quote sections: {', '.join(f'`{name}`' for name in story['unbalanced_quote_sections'])}"
            )

        preview = story.get("brief_preview") or {}
        lines.extend(["", "**Brief**", ""])
        for index, paragraph in enumerate(preview.get("paragraphs") or [], start=1):
            lines.append(f"{index}. {paragraph}")
        for name in SECTION_SUPPORT_NAMES:
            value = preview.get(name)
            if isinstance(value, str) and value.strip():
                lines.append(f"- `{name}`: {value}")

        snapshot = story.get("source_snapshot") or []
        lines.extend(["", "**Source Snapshot**", ""])
        for source in snapshot:
            outlet = source.get("outlet") or "Unknown outlet"
            extraction_quality = source.get("extraction_quality") or "unknown"
            access_tier = source.get("access_tier") or "unknown"
            headline = source.get("headline") or ""
            snippet = source.get("used_snippet") or source.get("focus") or ""
            lines.append(
                f"- {outlet} (`{extraction_quality}`, `{access_tier}`): {truncate(headline, 140)}"
            )
            if snippet:
                lines.append(f"  - {truncate(str(snippet), 220)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")
    if args.control_count < 0:
        raise SystemExit("--control-count must be 0 or greater")
    if args.scan_limit <= 0:
        raise SystemExit("--scan-limit must be greater than 0")

    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    clusters = fetch_active_clusters(client, scan_limit=args.scan_limit)
    briefs_by_cluster = fetch_current_briefs(client)
    evaluations = [evaluate_story_quality(cluster, briefs_by_cluster.get(cluster.get("id"))) for cluster in clusters]
    report = build_quality_report(evaluations, limit=args.limit, control_count=args.control_count)

    if args.format == "markdown":
        print(render_markdown_report(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
