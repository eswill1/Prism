#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib import parse

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_STORIES = 24
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
PAYWALLED_OUTLETS = {"Bloomberg", "Financial Times", "New York Times", "Wall Street Journal"}
PLACEHOLDER_KEY_FACT = re.compile(
    r"^Prism has |^Prism only has |^The latest linked reporting came from |^The comparison set ",
    re.IGNORECASE,
)
GENERIC_FOCUS_TOKENS = {
    "another",
    "around",
    "current",
    "currently",
    "detailed",
    "development",
    "first",
    "general",
    "headline",
    "holding",
    "linked",
    "main",
    "potentially",
    "prism",
    "report",
    "reported",
    "reporting",
    "source",
    "sources",
    "story",
    "strong",
    "take",
    "this",
    "hold",
    "driving",
    "drive",
    "driven",
    "set",
    "likely",
    "emerge",
    "persist",
    "through",
    "today",
    "update",
    "updates",
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def ensure_period(value: str) -> str:
    trimmed = normalize_whitespace(value)
    if not trimmed:
        return ""
    return trimmed if re.search(r"[.!?]$", trimmed) else f"{trimmed}."


def strip_ending_punctuation(value: str) -> str:
    return normalize_whitespace(value).rstrip(".!?")


def focus_fallback_for_family(family: str) -> str:
    return {
        "politics": "policy and political consequences",
        "business": "prices and economic fallout",
        "technology": "technology policy and platform rules",
        "weather": "weather and temperature impacts",
        "world": "international fallout",
    }.get(family, "the main reported development")


def clean_focus_phrase(value: str | None, family: str) -> str:
    cleaned = strip_ending_punctuation(value or "")
    if not cleaned:
        return focus_fallback_for_family(family)

    tokens: list[str] = []
    for token in re.findall(r"[A-Za-zÀ-ÿ]{4,}", cleaned.lower()):
        if token in GENERIC_FOCUS_TOKENS or token in tokens:
            continue
        tokens.append(token)

    if not tokens:
        return focus_fallback_for_family(family)
    if len(tokens) == 1:
        return tokens[0]
    return f"{tokens[0]} and {tokens[1]}"


def sentence_similarity(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9]{4,}", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]{4,}", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens))


def first_narrative_sentences(text: str, sentence_count: int) -> str:
    cleaned = normalize_whitespace(text)
    sentences = [segment.strip() for segment in re.findall(r"[^.!?]+[.!?]+", cleaned) if segment.strip()]
    if not sentences:
        return cleaned
    return " ".join(sentences[:sentence_count]).strip()


def topic_family_for_story(topic: str) -> str:
    normalized = topic.lower()
    if re.search(r"(policy|politic|government|congress|senate|election|white house|u\.s\.|us )", normalized):
        return "politics"
    if re.search(r"(business|economy|economic|market|trade|finance)", normalized):
        return "business"
    if re.search(r"(technology|tech|ai|innovation)", normalized):
        return "technology"
    if re.search(r"(climate|weather|storm|wildfire|flood|energy|infrastructure|disaster)", normalized):
        return "weather"
    if re.search(r"(world|global|international)", normalized):
        return "world"
    return "general"


def infer_access_tier(outlet: str, signal: str | None = None) -> str:
    if signal in {"open", "likely_paywalled"}:
        return signal
    if outlet in OPEN_OUTLETS:
        return "open"
    if outlet in PAYWALLED_OUTLETS:
        return "likely_paywalled"
    return "unknown"


def substantive_text_for_article(article: dict[str, Any]) -> str:
    body_text = str(article.get("body_text") or "").strip()
    if body_text:
        body_candidate = first_narrative_sentences(body_text, 3)
        if len(body_candidate) >= 120:
            return body_candidate

    summary = str(article.get("summary") or "").strip()
    if summary:
        return normalize_whitespace(summary)

    feed_summary = str((article.get("metadata") or {}).get("feed_summary") or "").strip()
    if feed_summary:
        return normalize_whitespace(feed_summary)

    return ""


def is_substantive_article(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = str(article.get("body_text") or "").strip()
    if extraction_quality == "article_body" and len(body_text) >= 180:
        return True
    return len(substantive_text_for_article(article)) >= 110


def article_focus(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    named_entities = metadata.get("named_entities") if isinstance(metadata, dict) else []
    if isinstance(named_entities, list):
        cleaned = [str(value).strip() for value in named_entities if isinstance(value, str) and len(value.strip()) >= 4]
        if len(cleaned) >= 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        if len(cleaned) == 1:
            return cleaned[0]

    for text in (
        article.get("headline") or "",
        article.get("summary") or "",
        (metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "",
    ):
        tokens: list[str] = []
        for token in re.findall(r"[A-Za-zÀ-ÿ]{4,}", text.lower()):
            if token in GENERIC_FOCUS_TOKENS or token in {"which", "their", "there", "about", "would", "could", "these"}:
                continue
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= 2:
                break
        if len(tokens) >= 2:
            return f"{tokens[0]} and {tokens[1]}"
        if len(tokens) == 1:
            return tokens[0]

    return "the practical stakes"


def build_brief_sources(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    existing: list[str] = []
    title_anchors = [cluster["canonical_headline"], cluster["summary"]]
    rows: list[dict[str, Any]] = []
    for relation in sorted(cluster.get("cluster_articles") or [], key=lambda item: item.get("rank_in_cluster") or 999):
        article = relation.get("articles") if isinstance(relation, dict) else None
        if not isinstance(article, dict):
            continue
        if not is_substantive_article(article):
            continue

        snippet = substantive_text_for_article(article)
        if not snippet:
            continue

        if any(sentence_similarity(snippet, anchor) >= 0.72 for anchor in title_anchors if anchor):
            if len(cluster.get("cluster_articles") or []) > 1:
                continue

        if any(sentence_similarity(snippet, current) >= 0.72 for current in existing):
            continue

        metadata = article.get("metadata") or {}
        outlet = ((article.get("outlets") or {}).get("canonical_name") or article.get("site_name") or "Unknown outlet").strip()
        existing.append(snippet)
        rows.append(
            {
                "article_id": article.get("id"),
                "outlet": outlet,
                "headline": article.get("headline") or cluster["canonical_headline"],
                "canonical_url": article.get("canonical_url"),
                "original_url": article.get("original_url"),
                "framing": relation.get("framing_group") or "center",
                "snippet": ensure_period(snippet),
                "focus": article_focus(article),
                "extraction_quality": metadata.get("extraction_quality") if isinstance(metadata, dict) else None,
                "access_tier": infer_access_tier(
                    outlet,
                    metadata.get("access_signal") if isinstance(metadata, dict) else None,
                ),
            }
        )

    return rows


def source_reference(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": source.get("article_id"),
        "outlet": source.get("outlet"),
        "headline": source.get("headline"),
        "canonical_url": source.get("canonical_url"),
        "original_url": source.get("original_url"),
        "access_tier": source.get("access_tier"),
    }


def unique_source_references(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_article_ids: set[str] = set()
    refs: list[dict[str, Any]] = []
    for source in sources:
        article_id = source.get("article_id")
        if isinstance(article_id, str) and article_id in seen_article_ids:
            continue
        if isinstance(article_id, str):
            seen_article_ids.add(article_id)
        refs.append(source_reference(source))
    return refs


def support_payload(*sources: dict[str, Any]) -> list[dict[str, Any]]:
    return unique_source_references([source for source in sources if source])


def open_alternate_source(sources: list[dict[str, Any]], exclude_outlet: str | None = None) -> dict[str, Any] | None:
    for source in sources:
        if source.get("access_tier") != "open":
            continue
        if exclude_outlet and source.get("outlet") == exclude_outlet:
            continue
        return source
    return None


def outlet_text(cluster: dict[str, Any]) -> str:
    outlets = []
    for relation in cluster.get("cluster_articles") or []:
        article = relation.get("articles") if isinstance(relation, dict) else None
        outlet = ((article or {}).get("outlets") or {}).get("canonical_name") if isinstance(article, dict) else None
        if isinstance(outlet, str) and outlet and outlet not in outlets:
            outlets.append(outlet)
        if len(outlets) >= 3:
            break

    if not outlets:
        return f"{int(cluster.get('outlet_count') or 0)} outlets"
    if len(outlets) == 1:
        return outlets[0]
    return f"{', '.join(outlets[:-1])} and {outlets[-1]}"


def outlet_list_text(outlets: list[str]) -> str:
    unique = []
    for outlet in outlets:
        if outlet and outlet not in unique:
            unique.append(outlet)
    if not unique:
        return "multiple outlets"
    if len(unique) == 1:
        return unique[0]
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    return f"{', '.join(unique[:-1])}, and {unique[-1]}"


def central_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not sources:
        return None

    best = None
    best_score = -1.0
    for source in sources:
        score = sum(sentence_similarity(source["snippet"], other["snippet"]) for other in sources)
        if score > best_score:
            best = source
            best_score = score
    return best


def divergent_source(sources: list[dict[str, Any]], central: dict[str, Any] | None) -> dict[str, Any] | None:
    if not central:
        return sources[1] if len(sources) > 1 else None

    def source_score(source: dict[str, Any]) -> float:
        framing_bonus = -0.25 if source.get("framing") != central.get("framing") else 0.0
        return sentence_similarity(source["snippet"], central["snippet"]) + framing_bonus

    others = [source for source in sources if source["outlet"] != central["outlet"]]
    if not others:
        return None
    return sorted(others, key=source_score)[0]


def visible_key_facts(cluster: dict[str, Any]) -> list[str]:
    facts = []
    for item in sorted(cluster.get("cluster_key_facts") or [], key=lambda row: row.get("sort_order") or 0):
        fact = ensure_period(str(item.get("fact_text") or ""))
        if not fact or PLACEHOLDER_KEY_FACT.search(fact):
            continue
        if any(sentence_similarity(fact, existing) >= 0.8 for existing in facts):
            continue
        facts.append(fact)
        if len(facts) >= 3:
            break
    return facts


def why_it_matters_copy(cluster: dict[str, Any], family: str, sources: list[dict[str, Any]]) -> str:
    facts = visible_key_facts(cluster)
    if len(facts) >= 2:
        return facts[1]
    if len(sources) >= 2:
        return f"This matters because the reporting is already pointing beyond the immediate headline and toward {clean_focus_phrase(sources[1]['focus'], family)}."
    default_copy = {
        "politics": "This matters because the next move here could affect public policy, negotiations, or the balance of political leverage in a visible way.",
        "business": "This matters because the practical effects are likely to show up in prices, markets, or business decisions faster than in many political stories.",
        "technology": "This matters because the story is really about who sets the rules for platforms, infrastructure, or emerging technology before those rules harden.",
        "weather": "This matters because the real consequences are operational: safety, infrastructure, recovery, and the public systems people rely on every day.",
        "world": "This matters because the story is already affecting how other governments, markets, or institutions are responding beyond the immediate event itself.",
    }.get(
        family,
        "This matters because the story is broad enough that reading one outlet alone is already likely to miss part of the picture.",
    )

    if sources:
        return default_copy

    return default_copy


def watch_next_copy(cluster: dict[str, Any], family: str) -> str:
    correction_events = sorted(
        cluster.get("correction_events") or [],
        key=lambda row: row.get("created_at") or "",
        reverse=True,
    )
    if correction_events:
        label = str(correction_events[0].get("display_summary") or "").strip()
        if label and not re.match(r"^Story shell refreshed from \d+ publisher signals$", label, re.IGNORECASE):
            return f"Watch for the next turn: {ensure_period(label)}"

    return {
        "politics": "Watch for new votes, official statements, or negotiation details that change the practical stakes instead of just the rhetoric.",
        "business": "Watch for any move in prices, official economic action, or company response that makes the downstream effects easier to measure.",
        "technology": "Watch for regulatory details, product changes, or company statements that turn the broad argument into concrete action.",
        "weather": "Watch for damage figures, recovery updates, and official assessments that show whether this is a short disruption or a longer resilience problem.",
        "world": "Watch for international responses, official confirmations, and any change that broadens the story beyond the first wave of headlines.",
    }.get(
        family,
        "Watch for new reporting or official updates that widen the source mix and sharpen where the coverage starts to split.",
    )


def build_grounded_brief(cluster: dict[str, Any]) -> dict[str, Any]:
    family = topic_family_for_story(cluster["topic_label"])
    sources = build_brief_sources(cluster)
    central = central_source(sources)
    divergent = divergent_source(sources, central)
    outlet_count = len({source["outlet"] for source in sources})
    full_brief = len(sources) >= 2 and outlet_count >= 2
    secondary_sources = [source for source in sources if source["outlet"] != (central or {}).get("outlet")][:3]
    corroborating_outlets = outlet_list_text([source["outlet"] for source in secondary_sources])
    open_alternate = open_alternate_source(
        secondary_sources if secondary_sources else sources,
        exclude_outlet=(central or {}).get("outlet"),
    )

    paragraph_entries: list[dict[str, Any]] = []

    def add_paragraph(text: str, *supporting_sources: dict[str, Any]) -> None:
        cleaned = normalize_whitespace(text)
        if not cleaned:
            return
        if any(sentence_similarity(cleaned, existing["text"]) >= 0.82 for existing in paragraph_entries):
            return
        paragraph_entries.append(
            {
                "text": cleaned,
                "support": support_payload(*supporting_sources),
            }
        )

    add_paragraph(ensure_period(cluster["summary"]), *(sources[:2] or ([central] if central else [])))

    if full_brief:
        add_paragraph(
            (
                f"Across {outlet_text(cluster)}, the baseline is consistent. {central['snippet']}"
                if central
                else ensure_period(cluster["summary"])
            ),
            *(support_payload(central, secondary_sources[0]) if central and secondary_sources else support_payload(central) if central else []),
        )
        if len(secondary_sources) >= 2:
            add_paragraph(
                (
                    f"The reporting expands in two directions once you get past the headline. "
                    f"{secondary_sources[0]['outlet']} adds more around {strip_ending_punctuation(secondary_sources[0]['focus'])}, "
                    f"while {secondary_sources[1]['outlet']} spends more time on {strip_ending_punctuation(secondary_sources[1]['focus'])}."
                ),
                secondary_sources[0],
                secondary_sources[1],
            )
        elif secondary_sources:
            add_paragraph(
                (
                    f"{secondary_sources[0]['outlet']} adds more around {strip_ending_punctuation(secondary_sources[0]['focus'])}, "
                    "which helps turn the first-wave headline into a fuller working picture."
                ),
                secondary_sources[0],
            )

        add_paragraph(
            (
                f"The main difference in coverage is emphasis. {divergent['outlet']} leans harder on "
                f"{strip_ending_punctuation(divergent['focus'])}, while {(central or divergent)['outlet']} stays closer to the straight sequence of events."
                if divergent and central
                else "The outlets are still more aligned than divided on the event itself, with most of the variation showing up in what each one treats as the bigger downstream stake."
            ),
            *(support_payload(central, divergent) if central and divergent else support_payload(*(secondary_sources[:2] or ([central] if central else [])))),
        )
    else:
        if central:
            central_focus = clean_focus_phrase(central["focus"], family)
            if sentence_similarity(central["snippet"], cluster["summary"]) < 0.72:
                add_paragraph(
                    f"The clearest detailed reporting so far comes from {central['outlet']}. {central['snippet']}",
                    central,
                )
            else:
                add_paragraph(
                    (
                        f"The clearest detailed reporting so far comes from {central['outlet']}, "
                        "and it supports the same overall picture while adding detail beyond the first headline."
                    ),
                    central,
                )

        if open_alternate:
            add_paragraph(
                (
                    f"Prism has also linked an open follow-on read from {open_alternate['outlet']}. "
                    "It broadly tracks the same story, but the source mix is still too thin to treat differences in emphasis as a meaningful split in coverage."
                ),
                central or open_alternate,
                open_alternate,
            )
        else:
            add_paragraph(
                (
                    "Prism is still working with a thin source set here. "
                    "This early brief will become more useful once another detailed report arrives and the comparison layer has more than one substantive account to work with."
                ),
                *(support_payload(central) if central else []),
            )

    filtered_paragraphs = [entry["text"] for entry in paragraph_entries]
    paragraph_support = [
        {
            "index": index,
            "support": entry["support"],
        }
        for index, entry in enumerate(paragraph_entries)
    ]

    supporting_points = visible_key_facts(cluster)
    why_support = support_payload(*(secondary_sources[:2] or ([central] if central else [])))
    agree_support = support_payload(central, secondary_sources[0]) if central and secondary_sources else support_payload(*(sources[:2]))
    differs_support = (
        support_payload(central, divergent)
        if central and divergent
        else support_payload(*(secondary_sources[:2] or ([central] if central else [])))
    )
    watch_support = (
        []
        if cluster.get("correction_events")
        else support_payload(*(secondary_sources[:1] or ([central] if central else [])))
    )

    where_sources_agree = (
        (
                f"Across {outlet_text(cluster)}, the shared baseline is clear: {(central or {}).get('snippet') or ensure_period(cluster['summary'])}"
                if full_brief
                else f"The best-supported baseline right now comes from {(central or {}).get('outlet') or 'the first linked report'}: {(central or {}).get('snippet') or ensure_period(cluster['summary'])}"
        )
    )
    where_coverage_differs = (
        (
            f"The split so far is more about emphasis than the event itself. {(central or {}).get('outlet') or 'One outlet'} stays closest to the core sequence, while {divergent['outlet']} gives more weight to {divergent['focus']}."
            if full_brief and divergent
            else "The reporting is still fairly aligned on the core sequence, but outlets are beginning to diverge in what they emphasize most."
        )
        if full_brief
        else (
            (
                "It is too early to call a real split in coverage. "
                "Prism needs at least one more detailed independent report before differences in framing become useful to compare."
            )
        )
    )

    source_snapshot = [
        {
            "article_id": source.get("article_id"),
            "outlet": source["outlet"],
            "headline": source["headline"],
            "canonical_url": source.get("canonical_url"),
            "original_url": source.get("original_url"),
            "extraction_quality": source.get("extraction_quality"),
            "access_tier": source.get("access_tier"),
            "focus": source["focus"],
            "used_snippet": source["snippet"],
        }
        for source in sources
    ]

    brief_payload = {
        "status": "full" if full_brief else "early",
        "label": "Prism brief" if full_brief else "Early brief",
        "title": "The story so far" if full_brief else "What the reporting says so far",
        "paragraphs": filtered_paragraphs,
        "why_it_matters": why_it_matters_copy(cluster, family, sources),
        "where_sources_agree": where_sources_agree,
        "where_coverage_differs": where_coverage_differs,
        "what_to_watch": watch_next_copy(cluster, family),
        "supporting_points": supporting_points,
        "metadata": {
            "substantive_source_count": len(sources),
            "paragraph_count": len(filtered_paragraphs),
            "family": family,
            "full_brief_ready": full_brief,
            "open_source_count": sum(1 for source in sources if source.get("access_tier") == "open"),
            "likely_paywalled_source_count": sum(1 for source in sources if source.get("access_tier") == "likely_paywalled"),
            "open_alternate_available": bool(open_alternate),
            "support_strategy_version": "grounded_sections_v1",
            "section_support": {
                "paragraphs": paragraph_support,
                "why_it_matters": why_support,
                "where_sources_agree": agree_support,
                "where_coverage_differs": differs_support,
                "what_to_watch": watch_support,
            },
        },
        "source_snapshot": source_snapshot,
    }

    signature_input = json.dumps(
        {
            "generator_version": "deterministic_grounded_v1",
            "summary": cluster["summary"],
            "topic_label": cluster["topic_label"],
            "key_facts": supporting_points,
            "sources": source_snapshot,
            "payload": {
                "paragraphs": filtered_paragraphs,
                "why_it_matters": brief_payload["why_it_matters"],
                "where_sources_agree": where_sources_agree,
                "where_coverage_differs": where_coverage_differs,
                "what_to_watch": brief_payload["what_to_watch"],
                "section_support": brief_payload["metadata"]["section_support"],
            },
        },
        sort_keys=True,
    )
    brief_payload["input_signature"] = hashlib.sha256(signature_input.encode("utf-8")).hexdigest()
    return brief_payload


def fetch_clusters(client: SupabaseRestClient) -> list[dict[str, Any]]:
    return client.get(
        "/story_clusters?select=id,slug,topic_label,canonical_headline,summary,latest_event_at,metadata,cluster_key_facts(fact_text,sort_order),correction_events(display_summary,created_at),cluster_articles(rank_in_cluster,framing_group,articles!inner(id,headline,summary,body_text,canonical_url,original_url,site_name,metadata,outlets!inner(canonical_name)))&order=latest_event_at.desc&limit="
        + str(MAX_STORIES)
    ) or []


def fetch_current_revisions(client: SupabaseRestClient) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/story_brief_revisions?select=id,cluster_id,revision_tag,input_signature,status,metadata&is_current=eq.true&limit=200"
    ) or []
    return {row["cluster_id"]: row for row in rows if row.get("cluster_id")}


def patch_current_revisions_off(client: SupabaseRestClient, cluster_id: str) -> None:
    client.patch(
        f"/story_brief_revisions?cluster_id=eq.{cluster_id}&is_current=eq.true",
        {"is_current": False},
        prefer="return=minimal",
    )


def patch_cluster_metadata(client: SupabaseRestClient, cluster: dict[str, Any], revision_tag: str, brief_payload: dict[str, Any]) -> None:
    metadata = dict(cluster.get("metadata") or {})
    metadata["brief_revision_tag"] = revision_tag
    metadata["brief_status"] = brief_payload["status"]
    metadata["brief_generated_at"] = datetime.now(timezone.utc).isoformat()
    metadata["brief_generation_method"] = "deterministic_grounded_v1"
    metadata["brief_substantive_source_count"] = brief_payload["metadata"]["substantive_source_count"]
    client.patch(
        f"/story_clusters?id=eq.{cluster['id']}",
        {"metadata": metadata},
        prefer="return=minimal",
    )


def insert_version_event(client: SupabaseRestClient, cluster_id: str, revision_tag: str, brief_payload: dict[str, Any], change_kind: str) -> None:
    client.post(
        "/version_registry",
        [
            {
                "scope": "story_brief",
                "scope_id": cluster_id,
                "version_tag": revision_tag,
                "change_kind": change_kind,
                "metadata": {
                    "status": brief_payload["status"],
                    "paragraph_count": brief_payload["metadata"]["paragraph_count"],
                    "substantive_source_count": brief_payload["metadata"]["substantive_source_count"],
                    "generation_method": "deterministic_grounded_v1",
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
        brief_payload = build_grounded_brief(cluster)
        current = current_revisions.get(cluster["id"])
        if current and current.get("input_signature") == brief_payload["input_signature"]:
            unchanged += 1
            continue

        patch_current_revisions_off(client, cluster["id"])
        revision_tag = f"brief-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        client.post(
            "/story_brief_revisions",
            [
                {
                    "cluster_id": cluster["id"],
                    "revision_tag": revision_tag,
                    "status": brief_payload["status"],
                    "is_current": True,
                    "label": brief_payload["label"],
                    "title": brief_payload["title"],
                    "generation_method": "deterministic_grounded_v1",
                    "input_signature": brief_payload["input_signature"],
                    "source_snapshot": brief_payload["source_snapshot"],
                    "paragraphs": brief_payload["paragraphs"],
                    "why_it_matters": brief_payload["why_it_matters"],
                    "where_sources_agree": brief_payload["where_sources_agree"],
                    "where_coverage_differs": brief_payload["where_coverage_differs"],
                    "what_to_watch": brief_payload["what_to_watch"],
                    "supporting_points": brief_payload["supporting_points"],
                    "metadata": brief_payload["metadata"],
                }
            ],
            prefer="return=minimal",
        )
        patch_cluster_metadata(client, cluster, revision_tag, brief_payload)
        insert_version_event(
            client,
            cluster["id"],
            revision_tag,
            brief_payload,
            "update" if current else "create",
        )
        if current:
            updated += 1
        else:
            created += 1

    print(
        json.dumps(
            {
                "stories_considered": len(clusters),
                "brief_revisions_created": created,
                "brief_revisions_updated": updated,
                "brief_revisions_unchanged": unchanged,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
