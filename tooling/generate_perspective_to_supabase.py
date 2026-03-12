#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient, delete_where


MAX_STORIES = 24
GENERATION_METHOD = "deterministic_perspective_v1"
LENS_TO_DB = {
    "Balanced Framing": "balanced_framing",
    "Evidence-First": "evidence_first",
    "Local Impact": "local_impact",
    "International Comparison": "international_comparison",
}
FRAMING_LABELS = {
    "left": "Left / advocacy-leaning framing",
    "center": "Center / straight-news framing",
    "right": "Right / advocacy-leaning framing",
}
SOURCE_FAMILY_NOTES = {
    "Wire services": "Useful for baseline facts and fast-moving updates.",
    "Public media": "Often adds explanatory framing and civic context.",
    "Broadcast networks": "Adds broad public-facing framing and urgency signals.",
    "Policy publications": "Often emphasizes institutional or strategic implications.",
    "National publications": "Adds deeper narrative framing and enterprise context.",
    "Regional coverage": "More likely to surface practical local consequences.",
    "Specialist coverage": "Useful when the story turns technical or niche.",
}
SCOPE_NOTES = {
    "Local impact": "Highlights practical effects on residents, services, or operations.",
    "National frame": "Centers national politics, institutions, or broad domestic effects.",
    "International frame": "Shows how the story is framed outside the immediate domestic lens.",
}
LOCAL_SCOPE_PATTERN = re.compile(
    r"\b(local|state|city|county|community|residents|families|district|school|utility|utilities|outage|operations|jobs|workers|customers|commuters)\b",
    re.IGNORECASE,
)
INTERNATIONAL_SCOPE_PATTERN = re.compile(
    r"\b(global|international|foreign|europe|european|china|iran|ukraine|gaza|israel|britain|british|london|beijing|tehran|parliament|strait of hormuz)\b",
    re.IGNORECASE,
)


def normalize_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def ensure_period(value: str | None) -> str:
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return ""
    return cleaned if re.search(r"[.!?]$", cleaned) else f"{cleaned}."


def sentence_split(value: str | None) -> list[str]:
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return []
    matches = re.findall(r"[^.!?]+[.!?]+", cleaned)
    if matches:
        return [segment.strip() for segment in matches if segment.strip()]
    return [cleaned]


def first_sentences(value: str | None, count: int) -> str:
    sentences = sentence_split(value)
    return " ".join(sentences[:count]).strip()


def substantive_text(article: dict[str, Any]) -> str:
    body_text = normalize_whitespace(article.get("body_text"))
    if len(body_text) >= 220:
        return first_sentences(body_text, 3)

    summary = normalize_whitespace(article.get("summary"))
    if summary:
        return summary

    metadata = article.get("metadata") or {}
    if isinstance(metadata, dict):
        feed_summary = normalize_whitespace(metadata.get("feed_summary"))
        if feed_summary:
            return feed_summary

    return ""


def is_substantive_article(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = normalize_whitespace(article.get("body_text"))
    if extraction_quality == "article_body" and len(body_text) >= 220:
        return True
    return len(substantive_text(article)) >= 120


def source_family(article: dict[str, Any]) -> str:
    outlet = ((article.get("outlets") or {}).get("canonical_name") or "").strip()
    outlet_type = ((article.get("outlets") or {}).get("outlet_type") or "").strip()
    if outlet_type == "wire":
        return "Wire services"
    if outlet_type == "public_media":
        return "Public media"
    if outlet_type == "broadcaster":
        return "Broadcast networks"
    if outlet_type == "regional":
        return "Regional coverage"
    if outlet_type == "specialist":
        return "Specialist coverage"
    if outlet in {"Politico", "The Hill"}:
        return "Policy publications"
    return "National publications"


def story_scope(article: dict[str, Any]) -> str:
    outlet = ((article.get("outlets") or {}).get("canonical_name") or "").strip()
    haystack = " ".join(
        filter(
            None,
            [
                article.get("headline"),
                article.get("summary"),
                article.get("body_text"),
            ],
        )
    )
    if LOCAL_SCOPE_PATTERN.search(haystack):
        return "Local impact"
    if outlet in {"BBC News", "Reuters", "Financial Times", "Bloomberg"} or INTERNATIONAL_SCOPE_PATTERN.search(haystack):
        return "International frame"
    return "National frame"


def access_signal(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    signal = metadata.get("access_signal") if isinstance(metadata, dict) else None
    if signal in {"open", "likely_paywalled"}:
        return str(signal)
    return "unknown"


def extraction_quality(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    value = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    return str(value or "rss_only")


def body_length(article: dict[str, Any]) -> int:
    return len(normalize_whitespace(article.get("body_text")))


def topic_family(cluster: dict[str, Any]) -> str:
    haystack = f"{cluster.get('topic_label', '')} {cluster.get('canonical_headline', '')} {cluster.get('summary', '')}".lower()
    if re.search(r"\b(storm|weather|grid|energy|heat|summer|wildfire|flood|climate|infrastructure)\b", haystack):
        return "weather"
    if re.search(r"\b(policy|politic|congress|senate|white house|administration|election|court|parliament)\b", haystack):
        return "politics"
    if re.search(r"\b(oil|reserve|trade|market|economy|tariff|shipping|prices|business)\b", haystack):
        return "business"
    if re.search(r"\b(technology|ai|chip|platform|software|cyber)\b", haystack):
        return "technology"
    return "general"


def short_focus(cluster: dict[str, Any], articles: list[dict[str, Any]]) -> str:
    key_facts = cluster.get("cluster_key_facts") or []
    if key_facts:
        first_fact = normalize_whitespace(key_facts[0].get("fact_text"))
        if first_fact:
            lowered = first_fact[0].lower() + first_fact[1:] if len(first_fact) > 1 else first_fact.lower()
            return lowered.rstrip(".")

    for article in articles:
        snippet = substantive_text(article)
        if snippet:
            first_sentence = first_sentences(snippet, 1)
            lowered = first_sentence[0].lower() + first_sentence[1:] if len(first_sentence) > 1 else first_sentence.lower()
            return lowered.rstrip(".")

    family = topic_family(cluster)
    fallback = {
        "weather": "weather and infrastructure effects",
        "politics": "policy and political consequences",
        "business": "prices and economic fallout",
        "technology": "technology policy and platform effects",
        "general": "the main reported development",
    }
    return fallback[family]


def top_labels(counter: Counter[str], limit: int = 2) -> list[str]:
    return [label for label, count in counter.most_common(limit) if count > 0]


def join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def build_presence_items(counter: Counter[str], notes: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for label, count in counter.most_common():
        if count <= 0:
            continue
        rows.append(
            {
                "label": label,
                "count": count,
                "note": notes.get(label, ""),
            }
        )
    return rows


def build_source_snapshot(article_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot = []
    for article in article_rows:
        snapshot.append(
            {
                "article_id": article["article_id"],
                "outlet": article["outlet"],
                "headline": article["headline"],
                "framing_group": article["framing_group"],
                "source_family": article["source_family"],
                "scope": article["scope"],
                "access_signal": article["access_signal"],
                "extraction_quality": article["extraction_quality"],
                "substantive": article["substantive"],
            }
        )
    return snapshot


def select_lens_items(lens: str, article_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not article_rows:
        return []

    framing_counter = Counter(article["framing_group"] for article in article_rows)
    family_counter = Counter(article["source_family"] for article in article_rows)
    selected: list[dict[str, Any]] = []
    used_article_ids: set[str] = set()

    def score(article: dict[str, Any]) -> float:
        value = 0.0
        if article["substantive"]:
            value += 14
        if article["access_signal"] == "open":
            value += 4
        elif article["access_signal"] == "likely_paywalled":
            value -= 2
        if article["extraction_quality"] == "article_body":
            value += 8
        elif article["extraction_quality"] == "metadata_description":
            value += 3
        value += min(body_length(article["raw"]), 800) / 200

        if lens == "Balanced Framing":
            value += 10 / max(1, framing_counter[article["framing_group"]])
            value += 8 / max(1, family_counter[article["source_family"]])
        elif lens == "Evidence-First":
            value += 10 if article["substantive"] else 0
            value += 6 if article["source_family"] in {"Wire services", "Public media"} else 0
        elif lens == "Local Impact":
            value += 14 if article["scope"] == "Local impact" else -4
            if LOCAL_SCOPE_PATTERN.search(article["text_blob"]):
                value += 8
        elif lens == "International Comparison":
            value += 14 if article["scope"] == "International frame" else -4
            if article["source_family"] in {"Wire services", "National publications"}:
                value += 2

        return value

    ranked = sorted(article_rows, key=score, reverse=True)
    limit = 3 if lens in {"Balanced Framing", "Evidence-First"} else 2

    for article in ranked:
        if article["article_id"] in used_article_ids:
            continue
        if lens == "Balanced Framing" and selected:
            if all(entry["framing_group"] == article["framing_group"] for entry in selected) and len(framing_counter) > 1:
                continue
        selected.append(article)
        used_article_ids.add(article["article_id"])
        if len(selected) >= limit:
            break

    def reason_for(article: dict[str, Any]) -> tuple[str, list[str]]:
        if lens == "Balanced Framing":
            return (
                f"Adds a {FRAMING_LABELS.get(article['framing_group'], 'different')} view through {article['source_family'].lower()}.",
                ["framing_diversity", "source_family_diversity"],
            )
        if lens == "Evidence-First":
            return (
                "Selected because it carries the strongest concrete reporting detail in the current mix.",
                ["direct_detail", "source_density"],
            )
        if lens == "Local Impact":
            return (
                "Useful for understanding practical effects on residents, services, or operations.",
                ["local_consequences", "operational_impact"],
            )
        return (
            "Shows how the story looks when framed through a more international or less domestic lens.",
            ["international_frame", "outside_domestic_center"],
        )

    return [
        {
            "article_id": article["article_id"],
            "title": article["headline"],
            "why": reason_for(article)[0],
            "reason_codes": reason_for(article)[1],
        }
        for article in selected
    ]


def build_perspective(cluster: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    relation_rows = sorted(cluster.get("cluster_articles") or [], key=lambda item: item.get("rank_in_cluster") or 999)
    article_rows: list[dict[str, Any]] = []

    for relation in relation_rows:
        article = relation.get("articles") or {}
        outlet = article.get("outlets") or {}
        article_rows.append(
            {
                "article_id": relation.get("article_id"),
                "headline": normalize_whitespace(article.get("headline")) or "Untitled article",
                "summary": normalize_whitespace(article.get("summary")),
                "body_text": normalize_whitespace(article.get("body_text")),
                "framing_group": relation.get("framing_group") or "center",
                "outlet": normalize_whitespace(outlet.get("canonical_name")) or "Unknown outlet",
                "source_family": source_family(article),
                "scope": story_scope(article),
                "access_signal": access_signal(article),
                "extraction_quality": extraction_quality(article),
                "substantive": is_substantive_article(article),
                "text_blob": " ".join(
                    filter(None, [article.get("headline"), article.get("summary"), article.get("body_text")])
                ),
                "raw": article,
            }
        )

    substantive_articles = [article for article in article_rows if article["substantive"]]
    comparison_count = len(substantive_articles) if substantive_articles else len(article_rows)
    status = "ready" if len(substantive_articles) >= 2 else "early"

    framing_counter = Counter(article["framing_group"] for article in article_rows)
    family_counter = Counter(article["source_family"] for article in article_rows)
    scope_counter = Counter(article["scope"] for article in article_rows)

    dominant_framing = FRAMING_LABELS.get(framing_counter.most_common(1)[0][0], "mixed framing") if framing_counter else "mixed framing"
    family_phrase = join_labels(top_labels(family_counter))
    scope_phrase = join_labels(top_labels(scope_counter))
    focus = short_focus(cluster, substantive_articles or article_rows)

    if status == "early":
        summary = ensure_period(
            f"Prism is still building a wider comparison set for this story. So far the linked reporting is mostly coming from {family_phrase or 'a narrow set of outlets'}, and the clearest visible frame is {dominant_framing.lower()} around {focus}."
        )
        takeaways = [
            ensure_period(
                f"Most of the current reporting is anchored by {family_phrase or 'a narrow outlet mix'}, so this Perspective view is still early."
            ),
            ensure_period(
                f"The visible frame right now is {dominant_framing.lower()}, with limited evidence yet of a broader ideological split."
            ),
            ensure_period(
                f"What Prism still needs most is another substantive source that adds a different family or scope of reporting."
            ),
        ]
    else:
        summary = ensure_period(
            f"Prism is seeing a broader comparison set here. Coverage is led by {dominant_framing.lower()}, source families are strongest in {family_phrase or 'a mixed outlet set'}, and the reporting focus is converging on {focus}."
        )
        takeaways = [
            ensure_period(
                f"Shared baseline: multiple outlets are circling the same core development around {focus}."
            ),
            ensure_period(
                f"Main visible split: the mix now spans {join_labels([item['label'] for item in build_presence_items(Counter({FRAMING_LABELS[key]: value for key, value in framing_counter.items()}), {})][:2]) or 'a narrow framing range'}."
            ),
            ensure_period(
                f"Scope check: the current story is being seen through {scope_phrase.lower() or 'one dominant scope'}, which shapes what consequences readers see first."
            ),
        ]

    framing_presence = build_presence_items(
        Counter({FRAMING_LABELS.get(key, key): value for key, value in framing_counter.items()}),
        {
            FRAMING_LABELS["left"]: "Present in the linked reporting, not treated as a verdict.",
            FRAMING_LABELS["center"]: "Baseline straight-news framing present in the current mix.",
            FRAMING_LABELS["right"]: "Present in the linked reporting, not treated as a verdict.",
        },
    )
    source_family_presence = build_presence_items(family_counter, SOURCE_FAMILY_NOTES)
    scope_presence = build_presence_items(scope_counter, SCOPE_NOTES)

    context_packs = {
        lens: select_lens_items(lens, substantive_articles or article_rows)
        for lens in LENS_TO_DB
    }

    metadata = {
        "substantive_source_count": len(substantive_articles),
        "article_count": len(article_rows),
        "lens_counts": {lens: len(items) for lens, items in context_packs.items()},
        "framing_diversity": len([count for count in framing_counter.values() if count > 0]),
        "source_family_diversity": len([count for count in family_counter.values() if count > 0]),
        "scope_diversity": len([count for count in scope_counter.values() if count > 0]),
    }

    payload = {
        "status": status,
        "summary": summary,
        "takeaways": takeaways,
        "framing_presence": framing_presence,
        "source_family_presence": source_family_presence,
        "scope_presence": scope_presence,
        "methodology_note": "Perspective shows what kinds of coverage are present in the linked reporting. It does not decide who is right or reduce the story to a single score.",
        "metadata": metadata,
        "source_snapshot": build_source_snapshot(article_rows),
    }

    signature_input = json.dumps(
        {
            "generator_version": GENERATION_METHOD,
            "summary": cluster.get("summary"),
            "topic_label": cluster.get("topic_label"),
            "source_snapshot": payload["source_snapshot"],
            "payload": {
                "status": status,
                "summary": summary,
                "takeaways": takeaways,
                "framing_presence": framing_presence,
                "source_family_presence": source_family_presence,
                "scope_presence": scope_presence,
                "methodology_note": payload["methodology_note"],
                "lens_counts": metadata["lens_counts"],
            },
        },
        sort_keys=True,
    )
    payload["input_signature"] = hashlib.sha256(signature_input.encode("utf-8")).hexdigest()
    return payload, context_packs


def fetch_clusters(client: SupabaseRestClient) -> list[dict[str, Any]]:
    return client.get(
        "/story_clusters?select=id,slug,topic_label,canonical_headline,summary,metadata,cluster_key_facts(fact_text,sort_order),cluster_articles(article_id,rank_in_cluster,framing_group,selection_reason,articles!inner(headline,summary,body_text,metadata,outlets!inner(canonical_name,outlet_type)))&order=latest_event_at.desc&limit="
        + str(MAX_STORIES)
    ) or []


def fetch_current_revisions(client: SupabaseRestClient) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/story_perspective_revisions?select=id,cluster_id,revision_tag,input_signature,status,metadata&is_current=eq.true&limit=200"
    ) or []
    return {row["cluster_id"]: row for row in rows if row.get("cluster_id")}


def patch_current_revisions_off(client: SupabaseRestClient, cluster_id: str) -> None:
    client.patch(
        f"/story_perspective_revisions?cluster_id=eq.{cluster_id}&is_current=eq.true",
        {"is_current": False},
        prefer="return=minimal",
    )


def patch_cluster_metadata(client: SupabaseRestClient, cluster: dict[str, Any], revision_tag: str, payload: dict[str, Any]) -> None:
    metadata = dict(cluster.get("metadata") or {})
    metadata["perspective_revision_tag"] = revision_tag
    metadata["perspective_status"] = payload["status"]
    metadata["perspective_generated_at"] = datetime.now(timezone.utc).isoformat()
    metadata["perspective_generation_method"] = GENERATION_METHOD
    metadata["context_pack_counts"] = payload["metadata"]["lens_counts"]
    client.patch(
        f"/story_clusters?id=eq.{cluster['id']}",
        {"metadata": metadata},
        prefer="return=minimal",
    )


def replace_context_pack_items(
    client: SupabaseRestClient,
    cluster_id: str,
    context_packs: dict[str, list[dict[str, Any]]],
) -> None:
    delete_where(client, "context_pack_items", "cluster_id", cluster_id)
    rows: list[dict[str, Any]] = []
    for lens, items in context_packs.items():
        for index, item in enumerate(items, start=1):
            if not item.get("article_id"):
                continue
            rows.append(
                {
                    "cluster_id": cluster_id,
                    "lens": LENS_TO_DB[lens],
                    "article_id": item["article_id"],
                    "rank": index,
                    "title_override": None,
                    "why_included": item["why"],
                    "reason_codes": item["reason_codes"],
                    "rule_version": "0.2.0",
                }
            )
    if rows:
        client.post("/context_pack_items", rows, prefer="return=minimal")


def insert_version_event(
    client: SupabaseRestClient,
    cluster_id: str,
    revision_tag: str,
    payload: dict[str, Any],
    change_kind: str,
) -> None:
    client.post(
        "/version_registry",
        [
            {
                "scope": "perspective",
                "scope_id": cluster_id,
                "version_tag": revision_tag,
                "change_kind": change_kind,
                "metadata": {
                    "status": payload["status"],
                    "generation_method": GENERATION_METHOD,
                    "substantive_source_count": payload["metadata"]["substantive_source_count"],
                    "lens_counts": payload["metadata"]["lens_counts"],
                },
            }
        ],
        prefer="return=minimal",
    )


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    clusters = [
        cluster
        for cluster in fetch_clusters(client)
        if isinstance(cluster.get("metadata"), dict)
        and cluster["metadata"].get("story_origin") in ("automated_feed_ingestion", "live_snapshot")
    ]
    current_revisions = fetch_current_revisions(client)

    created = 0
    updated = 0
    unchanged = 0

    for cluster in clusters:
        payload, context_packs = build_perspective(cluster)
        current = current_revisions.get(cluster["id"])
        if current and current.get("input_signature") == payload["input_signature"]:
            unchanged += 1
            continue

        patch_current_revisions_off(client, cluster["id"])
        replace_context_pack_items(client, cluster["id"], context_packs)

        revision_tag = f"perspective-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        client.post(
            "/story_perspective_revisions",
            [
                {
                    "cluster_id": cluster["id"],
                    "revision_tag": revision_tag,
                    "status": payload["status"],
                    "is_current": True,
                    "generation_method": GENERATION_METHOD,
                    "input_signature": payload["input_signature"],
                    "source_snapshot": payload["source_snapshot"],
                    "summary": payload["summary"],
                    "takeaways": payload["takeaways"],
                    "framing_presence": payload["framing_presence"],
                    "source_family_presence": payload["source_family_presence"],
                    "scope_presence": payload["scope_presence"],
                    "methodology_note": payload["methodology_note"],
                    "metadata": payload["metadata"],
                }
            ],
            prefer="return=minimal",
        )
        patch_cluster_metadata(client, cluster, revision_tag, payload)
        insert_version_event(client, cluster["id"], revision_tag, payload, "update" if current else "create")
        if current:
            updated += 1
        else:
            created += 1

    print(
        json.dumps(
            {
                "stories_considered": len(clusters),
                "perspective_revisions_created": created,
                "perspective_revisions_updated": updated,
                "perspective_revisions_unchanged": unchanged,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
