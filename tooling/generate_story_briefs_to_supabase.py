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
    r"^Prism has |^Prism only has |^The latest linked reporting came from |^The comparison set |^The strongest available source read is already open\.?$|^Prism found an open alternate read from |^Some linked reporting may be gated|^Linked source reads are still thin",
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
FOCUS_ENTITY_STOPWORDS = {
    "around",
    "more",
    "president",
    "state",
    "their",
}
FOCUS_TITLE_TOKENS = {
    "president",
    "sen",
    "senator",
    "gov",
    "governor",
    "rep",
    "representative",
    "minister",
    "prime",
    "crown",
    "prince",
}

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
LOW_SIGNAL_ALIGNMENT_TOKENS = STOPWORD_TOKENS | {
    "administration",
    "friday",
    "government",
    "governments",
    "mark",
    "marks",
    "monday",
    "night",
    "official",
    "officials",
    "president",
    "presidential",
    "reached",
    "reaches",
    "reach",
    "said",
    "saturday",
    "spokesperson",
    "state",
    "states",
    "sunday",
    "thursday",
    "tuesday",
    "wednesday",
    "week",
    "weeks",
    "yesterday",
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
    r"\b[A-Z](?=\.\s+[A-Z][a-z])\.",
)

PHOTO_CREDIT_PATTERN = re.compile(
    r"(?:\|\s*[^|]{0,120}?/(?:AP|Reuters|Getty|AFP|EPA)\b|\([^)]{0,120}?(?:via AP|via Reuters|Getty Images|AP Photo|Reuters|AFP|EPA|ISNA)[^)]*\))",
    re.IGNORECASE,
)
NOTE_BOILERPLATE_PATTERN = re.compile(
    r"^(?:notes?:|notice:\s*transcripts?\s+are\s+machine\s+and\s+human\s+generated|they may contain errors\.?$|data delayed at least|data shows future contract prices|chart:|graphic:|read more:)",
    re.IGNORECASE,
)
CAPTION_START_PATTERN = re.compile(
    r"^(?:a man|a woman|people|residents|supporters|children|protesters|smoke|flames|vehicles|ships|boats)\b",
    re.IGNORECASE,
)
CAPTION_SCENE_PATTERN = re.compile(
    r"\b(?:shore|street|road|rubble|ruins|square|market|port|harbor|dock|coast|coastline|border|outside|inside|near|amid|tankers?|boats?|ships?)\b",
    re.IGNORECASE,
)
REPORTING_VERB_PATTERN = re.compile(
    r"\b(?:said|says|told|warned|announced|reported|according|officials|authorities|police)\b",
    re.IGNORECASE,
)
DATE_OR_DAY_PATTERN = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def ensure_period(value: str) -> str:
    trimmed = normalize_whitespace(value)
    if not trimmed:
        return ""
    return trimmed if re.search(r'[.!?](?:["\u2019\u201d)\]]+)?$', trimmed) else f"{trimmed}."


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

    entity_chunks: list[str] = []
    for chunk in re.split(r"\band\b", cleaned, flags=re.IGNORECASE):
        normalized = normalize_whitespace(chunk)
        if not normalized:
            continue
        words = [word for word in re.findall(r"[A-Za-zÀ-ÿ']+", normalized) if len(word) >= 2]
        while words and words[0].lower() in FOCUS_TITLE_TOKENS:
            words.pop(0)
        candidate = normalize_whitespace(" ".join(words))
        if not candidate or candidate.lower() in FOCUS_ENTITY_STOPWORDS:
            continue
        if candidate not in entity_chunks:
            entity_chunks.append(candidate)
    if len(entity_chunks) >= 2:
        return f"{entity_chunks[0]} and {entity_chunks[1]}"
    if len(entity_chunks) == 1:
        return entity_chunks[0]

    tokens: list[str] = []
    for token in re.findall(r"[A-Za-zÀ-ÿ]{4,}", cleaned.lower()):
        if token in GENERIC_FOCUS_TOKENS or token in FOCUS_ENTITY_STOPWORDS or token in tokens:
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


def comparable_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", normalize_whitespace(value).lower().replace("u.s.", "us").replace("u.s", "us"))
        if token not in STOPWORD_TOKENS
    }


def alignment_score(reference: str, candidate: str) -> float:
    reference_tokens = comparable_tokens(reference)
    candidate_tokens = comparable_tokens(candidate)
    if len(reference_tokens) < 4 or len(candidate_tokens) < 4:
        return 1.0
    overlap = reference_tokens & candidate_tokens
    return len(overlap) / max(1, min(len(reference_tokens), len(candidate_tokens)))


def focused_alignment_score(reference: str, candidate: str) -> float:
    reference_tokens = comparable_tokens(reference) - LOW_SIGNAL_ALIGNMENT_TOKENS
    candidate_tokens = comparable_tokens(candidate) - LOW_SIGNAL_ALIGNMENT_TOKENS
    if len(reference_tokens) < 2 or len(candidate_tokens) < 2:
        return 0.0
    overlap = reference_tokens & candidate_tokens
    return len(overlap) / max(1, min(len(reference_tokens), len(candidate_tokens)))


def text_looks_title_like(headline: str, text: str) -> bool:
    normalized_headline = normalize_whitespace(headline).lower()
    normalized_text = normalize_whitespace(text).lower()
    if not normalized_headline or not normalized_text:
        return False
    if normalized_headline == normalized_text:
        return True
    if normalized_text in normalized_headline or normalized_headline in normalized_text:
        return True

    headline_tokens = comparable_tokens(normalized_headline)
    text_tokens = comparable_tokens(normalized_text)
    if not headline_tokens or not text_tokens:
        return False
    overlap = headline_tokens & text_tokens
    overlap_ratio = len(overlap) / max(1, len(text_tokens))
    return overlap_ratio >= 0.85 and len(text_tokens) <= len(headline_tokens) + 2


def cluster_story_alignment(cluster: dict[str, Any], candidate: str) -> float:
    references = [str(cluster.get("canonical_headline") or ""), str(cluster.get("summary") or "")]
    scores = [alignment_score(reference, candidate) for reference in references if reference and candidate]
    return max(scores) if scores else 0.0


def normalize_sentence_closing_punctuation(text: str) -> str:
    text = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r'([.!?])\s+([)"\]\'\u2019\u201d]+)', r"\1\2", text)


def prepare_narrative_text(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    cleaned = PHOTO_CREDIT_PATTERN.sub(". ", cleaned)
    cleaned = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return normalize_whitespace(cleaned)


def sentence_looks_non_narrative(text: str) -> bool:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return True

    if re.match(r"^[,;:)\]]", cleaned):
        return True
    if re.match(r"^\d{1,2},\b", cleaned):
        return True

    lowered = cleaned.lower()
    if NOTE_BOILERPLATE_PATTERN.search(cleaned):
        return True
    if PHOTO_CREDIT_PATTERN.search(cleaned):
        return True
    if "|" in cleaned and re.search(r"/(?:ap|reuters|getty|afp|epa)\b", lowered):
        return True
    if CAPTION_START_PATTERN.match(cleaned):
        if DATE_OR_DAY_PATTERN.search(cleaned):
            return True
        if CAPTION_SCENE_PATTERN.search(cleaned) and not REPORTING_VERB_PATTERN.search(cleaned):
            return True
    return False


def text_looks_clipped(text: str) -> bool:
    cleaned = normalize_whitespace(text)
    if len(cleaned) < 80:
        return False
    if cleaned.endswith("...") or cleaned.endswith("…"):
        return True
    if cleaned.count("“") > cleaned.count("”") or cleaned.count('"') % 2 == 1:
        return True
    return not re.search(r"[.!?](?:[\"'\u2019\u201d)\]]+)?$", cleaned)


def sentence_has_unclosed_quote(text: str) -> bool:
    normalized = text
    curly_balance = normalized.count("“") - normalized.count("”")
    straight_unpaired = normalized.count('"') % 2
    return curly_balance > 0 or straight_unpaired == 1


def sentence_continues_quoted_attribution(previous: str, current: str) -> bool:
    if not re.search(r'["\u201d\u2019]$', previous.strip()):
        return False
    return bool(
        re.match(
            r"^(?:(?:[A-Z][A-Za-z'’-]+|[Tt]he|[Hh]e|[Ss]he|[Tt]hey|[Oo]fficials|[Aa]ides|[Rr]eporters)\s+){0,3}"
            r"(said|says|told|asked|wrote|added|warned|argued|noted|announced|replied|stated|called|posted)\b",
            current,
        )
    )


def split_narrative_sentences(text: str) -> list[str]:
    cleaned = prepare_narrative_text(text)
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

    matches = re.findall(r'[^.!?]+[.!?]+(?:[)"\]\'\u2019\u201d]+)?', protected)
    if not matches:
        restored = protected
        for token, original in replacements.items():
            restored = restored.replace(token, original)
        return [restored]

    sentences: list[str] = []
    buffer = ""
    for segment in matches:
        restored = segment
        for token, original in replacements.items():
            restored = restored.replace(token, original)
        restored = normalize_sentence_closing_punctuation(normalize_whitespace(restored))
        if restored:
            if buffer:
                buffer = normalize_whitespace(f"{buffer} {restored}")
            else:
                buffer = restored
            if sentence_has_unclosed_quote(buffer):
                continue
            if sentences and sentence_continues_quoted_attribution(sentences[-1], buffer):
                sentences[-1] = normalize_whitespace(f"{sentences[-1]} {buffer}")
                buffer = ""
                continue
            sentences.append(buffer)
            buffer = ""
    if buffer:
        sentences.append(normalize_sentence_closing_punctuation(buffer))
    return sentences


def filtered_narrative_sentences(text: str) -> list[str]:
    return [
        sentence
        for sentence in split_narrative_sentences(text)
        if sentence and not sentence_looks_non_narrative(sentence)
    ]


def has_body_mismatch(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("body_mismatch_detected") is True:
        return True

    reference_text = " ".join(
        filter(
            None,
            [
                article.get("headline") or "",
                (metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "",
            ],
        )
    )
    candidate_text = first_narrative_sentences(
        str(article.get("body_text") or article.get("summary") or ""),
        2,
    )
    if not reference_text.strip() or not candidate_text.strip():
        return False
    return alignment_score(reference_text, candidate_text) < 0.16


def fetch_blocked(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    return bool(isinstance(metadata, dict) and metadata.get("fetch_blocked") is True)


def source_reference_text(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    return " ".join(
        filter(
            None,
            [
                article.get("headline") or "",
                (metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "",
            ],
        )
    )


def story_aligned_body_excerpt(
    article: dict[str, Any],
    *,
    sentence_count: int,
    minimum_alignment: float = 0.16,
) -> str:
    body_text = str(article.get("body_text") or "").strip()
    if not body_text:
        return ""

    sentences = filtered_narrative_sentences(body_text)
    if not sentences:
        return ""

    excerpt = [sentences[0]]
    reference_text = source_reference_text(article)
    for sentence in sentences[1:]:
        if len(excerpt) >= sentence_count:
            break
        if len(sentence) < 35:
            continue
        if reference_text.strip() and focused_alignment_score(reference_text, sentence) < minimum_alignment:
            continue
        excerpt.append(sentence)
    return " ".join(excerpt).strip()


def article_looks_like_live_updates(article: dict[str, Any]) -> bool:
    headline = normalize_whitespace(str(article.get("headline") or "")).lower()
    url = normalize_whitespace(str(article.get("canonical_url") or article.get("original_url") or "")).lower()
    return bool(
        re.search(r"\blive updates?\b|\bliveblog\b|\blive\b", headline)
        or "live-updates" in url
        or "/live/" in url
    )


def aligned_later_body_sentences(
    article: dict[str, Any],
    *,
    skip_count: int,
    sentence_count: int,
    minimum_alignment: float = 0.16,
) -> str:
    body_text = str(article.get("body_text") or "").strip()
    if not body_text:
        return ""
    reference_text = source_reference_text(article)
    if not reference_text.strip():
        return ""
    sentences = filtered_narrative_sentences(body_text)
    aligned = [
        sentence
        for sentence in sentences[skip_count:]
        if len(sentence) >= 50 and focused_alignment_score(reference_text, sentence) >= minimum_alignment
    ]
    return " ".join(aligned[:sentence_count]).strip()


def detail_text_for_article(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = str(article.get("body_text") or "").strip()
    reference_text = source_reference_text(article)
    if body_text and extraction_quality == "article_body":
        aligned_text = ensure_period(aligned_later_body_sentences(article, skip_count=2, sentence_count=2))
        if aligned_text:
            return aligned_text
        if article_looks_like_live_updates(article):
            return ""

        if not has_body_mismatch(article):
            raw_later = ensure_period(later_narrative_sentences(body_text, skip_count=2, sentence_count=2))
            if raw_later and focused_alignment_score(reference_text, raw_later) >= 0.16:
                return raw_later

        aligned = aligned_later_body_sentences(article, skip_count=2, sentence_count=2)
        if aligned:
            return ensure_period(aligned)

    for fallback_text in (
        str(article.get("summary") or "").strip(),
        str((metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "").strip(),
    ):
        sentences = filtered_narrative_sentences(fallback_text)
        if len(sentences) >= 2:
            return ensure_period(" ".join(sentences[1:3]))
    return ""


def followup_text_for_article(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = str(article.get("body_text") or "").strip()
    reference_text = source_reference_text(article)
    if body_text and extraction_quality == "article_body":
        aligned_text = ensure_period(aligned_later_body_sentences(article, skip_count=4, sentence_count=2))
        if aligned_text:
            return aligned_text
        if article_looks_like_live_updates(article):
            return ""

        if not has_body_mismatch(article):
            raw_later = ensure_period(later_narrative_sentences(body_text, skip_count=4, sentence_count=2))
            if raw_later and focused_alignment_score(reference_text, raw_later) >= 0.16:
                return raw_later

        aligned = aligned_later_body_sentences(article, skip_count=4, sentence_count=2)
        return ensure_period(aligned) if aligned else ""

    for fallback_text in (
        str(article.get("summary") or "").strip(),
        str((metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "").strip(),
    ):
        sentences = filtered_narrative_sentences(fallback_text)
        if len(sentences) >= 3:
            return ensure_period(" ".join(sentences[2:4]))
    return ""


def first_narrative_sentences(text: str, sentence_count: int) -> str:
    sentences = filtered_narrative_sentences(text)
    if not sentences:
        return ""
    return " ".join(sentences[:sentence_count]).strip()


def later_narrative_sentences(text: str, *, skip_count: int, sentence_count: int) -> str:
    sentences = filtered_narrative_sentences(text)
    if len(sentences) <= skip_count:
        return ""
    return " ".join(sentences[skip_count : skip_count + sentence_count]).strip()


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
    metadata = article.get("metadata") or {}
    feed_summary = str((metadata or {}).get("feed_summary") or "").strip()
    mismatch = has_body_mismatch(article)
    body_text = str(article.get("body_text") or "").strip()
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    if body_text and extraction_quality == "article_body" and not mismatch:
        body_candidate = story_aligned_body_excerpt(article, sentence_count=3) or first_narrative_sentences(body_text, 1)
        if len(body_candidate) >= 120:
            return body_candidate

    summary = str(article.get("summary") or "").strip()
    if summary and (not mismatch or not feed_summary):
        cleaned_summary = first_narrative_sentences(summary, 2) or prepare_narrative_text(summary)
        return normalize_whitespace(cleaned_summary)

    if feed_summary:
        cleaned_feed = first_narrative_sentences(feed_summary, 2) or prepare_narrative_text(feed_summary)
        return normalize_whitespace(cleaned_feed)

    return ""


def is_substantive_article(article: dict[str, Any]) -> bool:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = str(article.get("body_text") or "").strip()
    if extraction_quality == "article_body" and len(body_text) >= 180 and not has_body_mismatch(article):
        return True
    return len(substantive_text_for_article(article)) >= 110


def article_focus(article: dict[str, Any]) -> str:
    metadata = article.get("metadata") or {}
    named_entities = metadata.get("named_entities") if isinstance(metadata, dict) else []
    if isinstance(named_entities, list):
        cleaned = []
        for value in named_entities:
            if not isinstance(value, str) or len(value.strip()) < 4:
                continue
            normalized = normalize_whitespace(value)
            if normalized.lower() in FOCUS_ENTITY_STOPWORDS:
                continue
            if normalized not in cleaned:
                cleaned.append(normalized)
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
            if token in GENERIC_FOCUS_TOKENS or token in FOCUS_ENTITY_STOPWORDS or token in {"which", "their", "there", "about", "would", "could", "these"}:
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


def cluster_source_rows(cluster: dict[str, Any], *, substantive_only: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relation in sorted(cluster.get("cluster_articles") or [], key=lambda item: item.get("rank_in_cluster") or 999):
        article = relation.get("articles") if isinstance(relation, dict) else None
        if not isinstance(article, dict):
            continue
        is_substantive = is_substantive_article(article)
        if substantive_only and not is_substantive:
            continue

        snippet = substantive_text_for_article(article)
        if not snippet:
            continue

        metadata = article.get("metadata") or {}
        outlet = ((article.get("outlets") or {}).get("canonical_name") or article.get("site_name") or "Unknown outlet").strip()
        rows.append(
            {
                "article_id": article.get("id"),
                "outlet": outlet,
                "headline": article.get("headline") or cluster["canonical_headline"],
                "canonical_url": article.get("canonical_url"),
                "original_url": article.get("original_url"),
                "rank_in_cluster": relation.get("rank_in_cluster") or 999,
                "framing": relation.get("framing_group") or "center",
                "summary": article.get("summary") or "",
                "feed_summary": metadata.get("feed_summary") if isinstance(metadata, dict) else "",
                "snippet": ensure_period(snippet),
                "focus": article_focus(article),
                "detail": detail_text_for_article(article),
                "followup": followup_text_for_article(article),
                "extraction_quality": metadata.get("extraction_quality") if isinstance(metadata, dict) else None,
                "story_alignment": max(
                    cluster_story_alignment(cluster, ensure_period(snippet)),
                    cluster_story_alignment(cluster, str(article.get("headline") or "")),
                ),
                "title_like_snippet": text_looks_title_like(
                    str(article.get("headline") or cluster["canonical_headline"]),
                    ensure_period(snippet),
                ),
                "fetch_blocked": fetch_blocked(article),
                "is_substantive": is_substantive,
                "access_tier": infer_access_tier(
                    outlet,
                    metadata.get("access_signal") if isinstance(metadata, dict) else None,
                ),
            }
        )

    return rows


def cluster_substantive_source_rows(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    return cluster_source_rows(cluster, substantive_only=True)


def cluster_available_source_rows(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    return cluster_source_rows(cluster, substantive_only=False)


def dedupe_source_rows(
    rows: list[dict[str, Any]],
    *,
    title_anchors: list[str],
    drop_title_matches: bool,
) -> list[dict[str, Any]]:
    existing: list[str] = []
    deduped: list[dict[str, Any]] = []
    for source in rows:
        snippet = str(source.get("snippet") or "")
        if drop_title_matches and len(rows) > 1 and any(sentence_similarity(snippet, anchor) >= 0.72 for anchor in title_anchors if anchor):
            continue

        if any(sentence_similarity(snippet, current) >= 0.72 for current in existing):
            continue

        existing.append(snippet)
        deduped.append(source)

    return deduped


def build_brief_sources(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    return dedupe_source_rows(
        cluster_substantive_source_rows(cluster),
        title_anchors=[cluster["canonical_headline"], cluster["summary"]],
        drop_title_matches=True,
    )


def build_review_sources(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    return dedupe_source_rows(
        cluster_available_source_rows(cluster),
        title_anchors=[cluster["canonical_headline"], cluster["summary"]],
        drop_title_matches=False,
    )


def best_story_aligned_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not sources:
        return None
    return sorted(
        sources,
        key=lambda source: (
            float(source.get("story_alignment") or 0.0),
            0 if not source.get("title_like_snippet") else -1,
            1 if source.get("extraction_quality") == "article_body" else 0,
            1 if source.get("access_tier") == "open" else 0,
            -(int(source.get("rank_in_cluster") or 999)),
        ),
        reverse=True,
    )[0]


def cluster_brief_source_metrics(cluster: dict[str, Any]) -> dict[str, Any]:
    rows = cluster_substantive_source_rows(cluster)
    substantive_outlets = {row["outlet"] for row in rows}
    article_body_outlets = {row["outlet"] for row in rows if row.get("extraction_quality") == "article_body"}
    open_outlets = {row["outlet"] for row in rows if row.get("access_tier") == "open"}
    paywalled_outlets = {row["outlet"] for row in rows if row.get("access_tier") == "likely_paywalled"}
    return {
        "substantive_source_count": len(rows),
        "substantive_outlet_count": len(substantive_outlets),
        "article_body_outlet_count": len(article_body_outlets),
        "open_outlet_count": len(open_outlets),
        "likely_paywalled_outlet_count": len(paywalled_outlets),
        "full_brief_ready": len(substantive_outlets) >= 2 and len(article_body_outlets) >= 2,
    }


def blocked_cluster_article(cluster: dict[str, Any]) -> dict[str, Any] | None:
    for relation in sorted(cluster.get("cluster_articles") or [], key=lambda item: item.get("rank_in_cluster") or 999):
        article = relation.get("articles") if isinstance(relation, dict) else None
        if isinstance(article, dict) and fetch_blocked(article):
            metadata = article.get("metadata") or {}
            outlet = ((article.get("outlets") or {}).get("canonical_name") or article.get("site_name") or "Unknown outlet").strip()
            return {
                "outlet": outlet,
                "fetch_blocked": True,
                "access_tier": infer_access_tier(
                    outlet,
                    metadata.get("access_signal") if isinstance(metadata, dict) else None,
                ),
            }
    return None


def cluster_open_alternate_source(
    cluster: dict[str, Any],
    *,
    exclude_outlet: str | None = None,
    exclude_article_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    exclude_article_ids = exclude_article_ids or set()
    candidates = sorted(
        cluster_substantive_source_rows(cluster),
        key=lambda source: (
            0 if source.get("access_tier") == "open" else 1,
            0 if source.get("extraction_quality") == "article_body" else 1,
            int(source.get("rank_in_cluster") or 999),
        ),
    )
    for source in candidates:
        if source.get("access_tier") != "open":
            continue
        article_id = source.get("article_id")
        if isinstance(article_id, str) and article_id in exclude_article_ids:
            continue
        if exclude_outlet and source.get("outlet") == exclude_outlet:
            continue
        return source
    return None


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


def narrative_token_overlap(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9]{4,}", normalize_whitespace(left).lower()))
    right_tokens = set(re.findall(r"[a-z0-9]{4,}", normalize_whitespace(right).lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def source_support_excerpt(source: dict[str, Any]) -> str:
    segments: list[str] = []
    for value in (source.get("snippet"), source.get("detail"), source.get("followup")):
        for sentence in split_narrative_sentences(str(value or "").strip()):
            cleaned = ensure_period(sentence)
            if not cleaned or sentence_looks_non_narrative(cleaned):
                continue
            if any(
                cleaned.lower() in existing.lower()
                or sentence_similarity(cleaned, existing) >= 0.72
                or narrative_token_overlap(cleaned, existing) >= 0.72
                for existing in segments
            ):
                continue
            segments.append(cleaned)
    return " ".join(segments).strip()


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


def why_it_matters_copy(cluster: dict[str, Any], family: str, sources: list[dict[str, Any]], *, full_brief: bool) -> tuple[str, str]:
    facts = visible_key_facts(cluster)
    if len(facts) >= 2:
        return facts[1], "required"
    if full_brief and len(sources) >= 2:
        return (
            f"This matters because the reporting is already pointing beyond the immediate headline and toward {clean_focus_phrase(sources[1]['focus'], family)}.",
            "required",
        )
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
    return default_copy, "required" if full_brief else "scaffold"


def watch_next_copy(cluster: dict[str, Any], family: str, *, full_brief: bool) -> tuple[str, str]:
    correction_events = sorted(
        cluster.get("correction_events") or [],
        key=lambda row: row.get("created_at") or "",
        reverse=True,
    )
    if correction_events:
        label = str(correction_events[0].get("display_summary") or "").strip()
        if label and not re.match(r"^Story shell refreshed from \d+ publisher signals$", label, re.IGNORECASE):
            return f"Watch for the next turn: {ensure_period(label)}", "required"

    return ({
        "politics": "Watch for new votes, official statements, or negotiation details that change the practical stakes instead of just the rhetoric.",
        "business": "Watch for any move in prices, official economic action, or company response that makes the downstream effects easier to measure.",
        "technology": "Watch for regulatory details, product changes, or company statements that turn the broad argument into concrete action.",
        "weather": "Watch for damage figures, recovery updates, and official assessments that show whether this is a short disruption or a longer resilience problem.",
        "world": "Watch for international responses, official confirmations, and any change that broadens the story beyond the first wave of headlines.",
    }.get(
        family,
        "Watch for new reporting or official updates that widen the source mix and sharpen where the coverage starts to split.",
    ), "scaffold")


def early_brief_opening(cluster: dict[str, Any], central: dict[str, Any] | None) -> str:
    summary = ensure_period(cluster["summary"])
    if not central:
        return summary

    snippet = ensure_period(first_narrative_sentences(str(central.get("snippet") or "").strip(), 1))
    summary_score = alignment_score(str(cluster.get("canonical_headline") or ""), summary)
    snippet_score = alignment_score(str(cluster.get("canonical_headline") or ""), snippet)
    if snippet and (
        not summary
        or text_looks_clipped(summary)
        or snippet_score >= summary_score + 0.08
        or (
            sentence_similarity(summary, snippet) < 0.45
            and narrative_token_overlap(summary, snippet) < 0.45
            and snippet_score >= summary_score
        )
    ):
        return snippet

    snippet_sentences = split_narrative_sentences(str(central.get("snippet") or "").strip())
    snippet = ensure_period(snippet_sentences[0] if snippet_sentences else "")
    normalized_summary = normalize_whitespace(summary).lower()
    normalized_snippet = normalize_whitespace(snippet).lower()
    summary_anchor = re.sub(r"[.!?]+$", "", normalized_summary)
    if (
        snippet
        and not normalized_snippet.startswith(summary_anchor)
        and normalized_snippet not in normalized_summary
        and normalized_summary not in normalized_snippet
        and sentence_similarity(snippet, cluster["summary"]) < 0.72
        and narrative_token_overlap(snippet, summary) < 0.6
    ):
        return f"{summary} {snippet}".strip()
    return summary


def snippet_extension_after_opening(opening: str, snippet: str) -> str:
    opening_sentences = split_narrative_sentences(opening)
    snippet_sentences = split_narrative_sentences(snippet)
    if not opening_sentences or len(snippet_sentences) <= 1:
        return ""

    normalized_opening = normalize_whitespace(opening_sentences[0]).lower()
    normalized_snippet_first = normalize_whitespace(snippet_sentences[0]).lower()
    opening_anchor = re.sub(r"[.!?]+$", "", normalized_opening)
    if (
        sentence_similarity(opening_sentences[0], snippet_sentences[0]) < 0.72
        and not normalized_snippet_first.startswith(opening_anchor)
    ):
        return ""

    remaining = [
        sentence
        for sentence in snippet_sentences[1:]
        if not any(
            sentence_similarity(sentence, existing) >= 0.72
            or narrative_token_overlap(sentence, existing) >= 0.66
            for existing in opening_sentences
        )
    ]
    return " ".join(remaining).strip()


def early_brief_detail_followup(
    cluster: dict[str, Any],
    central: dict[str, Any] | None,
    opening: str,
) -> str:
    if not central:
        return ""

    snippet = ensure_period(str(central.get("snippet") or "").strip())
    snippet_extension = ensure_period(snippet_extension_after_opening(opening, snippet))
    if (
        snippet_extension
        and normalize_whitespace(snippet_extension).lower() not in normalize_whitespace(opening).lower()
        and sentence_similarity(snippet_extension, opening) < 0.72
    ):
        return snippet_extension

    detail = ensure_period(str(central.get("detail") or "").strip())
    if detail and normalize_whitespace(detail).lower() not in normalize_whitespace(opening).lower() and sentence_similarity(detail, opening) < 0.72:
        return detail

    for fallback_text in (
        str(central.get("summary") or "").strip(),
        str(central.get("feed_summary") or "").strip(),
    ):
        extra_sentences = split_narrative_sentences(fallback_text)
        candidate = ensure_period(" ".join(extra_sentences[1:3])) if len(extra_sentences) >= 2 else ""
        if (
            candidate
            and normalize_whitespace(candidate).lower() not in normalize_whitespace(opening).lower()
            and sentence_similarity(candidate, opening) < 0.72
            and narrative_token_overlap(candidate, opening) < 0.6
        ):
            return candidate

    summary = ensure_period(cluster["summary"])
    if (
        snippet
        and normalize_whitespace(snippet).lower() not in normalize_whitespace(opening).lower()
        and len(split_narrative_sentences(snippet)) >= 2
        and sentence_similarity(snippet, summary) < 0.72
        and sentence_similarity(snippet, opening) < 0.72
        and narrative_token_overlap(snippet, opening) < 0.6
    ):
        return snippet

    return ""


def first_distinct_paragraph(candidates: list[str], existing: list[str]) -> str:
    for candidate in candidates:
        cleaned = ensure_period(candidate)
        if not cleaned:
            continue
        normalized_cleaned = normalize_whitespace(cleaned).lower()
        duplicate = False
        for prior in existing:
            normalized_prior = normalize_whitespace(prior).lower()
            if (
                normalized_cleaned in normalized_prior
                or sentence_similarity(cleaned, prior) >= 0.72
                or narrative_token_overlap(cleaned, prior) >= 0.66
            ):
                duplicate = True
                break
        if not duplicate:
            return cleaned
    return ""


def build_grounded_brief(cluster: dict[str, Any]) -> dict[str, Any]:
    family = topic_family_for_story(cluster["topic_label"])
    sources = build_brief_sources(cluster)
    review_sources = build_review_sources(cluster)
    source_metrics = cluster_brief_source_metrics(cluster)
    visible_facts = visible_key_facts(cluster)
    central = central_source(sources)
    divergent = divergent_source(sources, central)
    anchor_source = central or central_source(review_sources)
    review_anchor = best_story_aligned_source(review_sources)
    if review_anchor and (
        not anchor_source
        or float(anchor_source.get("story_alignment") or 0.0) < 0.18
        or float(review_anchor.get("story_alignment") or 0.0) >= float(anchor_source.get("story_alignment") or 0.0) + 0.12
    ):
        anchor_source = review_anchor
    outlet_count = len({source["outlet"] for source in sources})
    full_brief = bool(source_metrics["full_brief_ready"] and len(sources) >= 2 and outlet_count >= 2)
    blocked_article = blocked_cluster_article(cluster)
    secondary_sources = [source for source in sources if source["outlet"] != (central or {}).get("outlet")][:3]
    corroborating_outlets = outlet_list_text([source["outlet"] for source in secondary_sources])
    if sources:
        open_alternate = cluster_open_alternate_source(
            cluster,
            exclude_outlet=(central or {}).get("outlet"),
            exclude_article_ids={
                source["article_id"] for source in sources if isinstance(source.get("article_id"), str)
            },
        )
        open_alternate_available = cluster_open_alternate_source(
            cluster,
            exclude_outlet=(central or {}).get("outlet"),
        )
    else:
        open_alternate = open_alternate_source(
            review_sources,
            exclude_outlet=(anchor_source or {}).get("outlet"),
        )
        open_alternate_available = open_alternate

    paragraph_entries: list[dict[str, Any]] = []

    def add_paragraph(
        text: str,
        *supporting_sources: dict[str, Any],
        role: str = "body",
        grounding_mode: str = "required",
    ) -> None:
        cleaned = normalize_whitespace(text)
        if not cleaned:
            return
        if any(
            sentence_similarity(cleaned, existing["text"]) >= 0.82
            or narrative_token_overlap(cleaned, existing["text"]) >= 0.82
            for existing in paragraph_entries
        ):
            return
        paragraph_entries.append(
            {
                "text": cleaned,
                "support": support_payload(*supporting_sources),
                "role": role,
                "grounding_mode": grounding_mode,
            }
        )

    if full_brief:
        baseline_source = secondary_sources[0] if secondary_sources else central
        baseline_extension = (
            ensure_period(snippet_extension_after_opening(cluster["summary"], str(baseline_source.get("snippet") or "")))
            if baseline_source
            else ""
        )
        add_paragraph(
            ensure_period(cluster["summary"]),
            *(sources[:2] or ([central] if central else [])),
            role="opening",
        )
        baseline_paragraph = first_distinct_paragraph(
            [
                (
                    f"Across {outlet_text(cluster)}, the baseline is consistent. {baseline_extension}"
                    if baseline_source and baseline_extension
                    else ""
                ),
                (
                    f"Across {outlet_text(cluster)}, the baseline is consistent. {baseline_source['detail']}"
                    if baseline_source and baseline_source.get("detail")
                    else ""
                ),
                (
                    f"Across {outlet_text(cluster)}, the baseline is consistent. {baseline_source['snippet']}"
                    if baseline_source
                    else ensure_period(cluster["summary"])
                ),
                f"Across {outlet_text(cluster)}, the baseline is consistent. {central['snippet']}" if central else "",
            ],
            [entry["text"] for entry in paragraph_entries],
        )
        if baseline_paragraph:
            add_paragraph(
                baseline_paragraph,
                *(support_payload(central, secondary_sources[0]) if central and secondary_sources else support_payload(central) if central else []),
                role="baseline",
            )

        extra_detail = first_distinct_paragraph(
            [
                str(source.get("detail") or "")
                for source in secondary_sources
            ]
            + [
                str(source.get("followup") or "")
                for source in secondary_sources
            ]
            + [
                str(source.get("snippet") or "")
                for source in secondary_sources
            ],
            [entry["text"] for entry in paragraph_entries],
        )
        if extra_detail:
            detail_source = next(
                (
                    source
                    for source in secondary_sources
                    if extra_detail in {
                        ensure_period(str(source.get("detail") or "")),
                        ensure_period(str(source.get("followup") or "")),
                        ensure_period(str(source.get("snippet") or "")),
                    }
                ),
                secondary_sources[0] if secondary_sources else None,
            )
            add_paragraph(
                extra_detail,
                *(support_payload(detail_source) if detail_source else []),
                role="detail",
            )

        add_paragraph(
            (
                f"The main difference in coverage is emphasis. {divergent['outlet']} spends more time on "
                f"{clean_focus_phrase(divergent['focus'], family)}, while {(central or divergent)['outlet']} stays closer to the straight sequence of events."
                if divergent and central
                else "The outlets are still more aligned than divided on the event itself, with most of the variation showing up in what each one treats as the bigger downstream stake."
            ),
            *(support_payload(central, divergent) if central and divergent else support_payload(*(secondary_sources[:2] or ([central] if central else [])))),
            role="difference",
        )
    else:
        opening_sources = [anchor_source] if anchor_source else (sources[:2] or [])
        opening = early_brief_opening(cluster, anchor_source)
        add_paragraph(
            opening,
            *opening_sources,
            role="opening",
            grounding_mode="required" if opening_sources else "scaffold",
        )
        detail_followup = early_brief_detail_followup(cluster, anchor_source, opening)
        if detail_followup:
            detail_sources = support_payload(anchor_source) if anchor_source else []
            add_paragraph(
                detail_followup,
                *detail_sources,
                role="detail",
                grounding_mode="required" if detail_sources else "scaffold",
            )

        grounded_followup_candidates = [
            {
                "text": str((anchor_source or {}).get("followup") or ""),
                "role": "followup",
                "grounding_mode": "required" if anchor_source else "scaffold",
                "sources": [anchor_source] if anchor_source else [],
            },
            {
                "text": visible_facts[0] if visible_facts else "",
                "role": "fact",
                "grounding_mode": "required" if anchor_source else "scaffold",
                "sources": [anchor_source] if anchor_source else [],
            },
            {
                "text": (
                    f"Prism could not retrieve the full article text from {anchor_source['outlet']} because the site served an automated access challenge to the enrichment worker. "
                    "This early brief is limited to feed-level material until Prism can verify the full body text or another independent report arrives."
                )
                if anchor_source and anchor_source.get("fetch_blocked")
                else "",
                "role": "blocked_notice",
                "grounding_mode": "scaffold",
                "sources": [anchor_source] if anchor_source else [],
            },
            {
                "text": (
                    f"Prism could not retrieve the full article text from {blocked_article['outlet']} because the site served an automated access challenge to the enrichment worker. "
                    "This early brief is limited to feed-level material until Prism can verify the full body text or another independent report arrives."
                )
                if not central and blocked_article
                else "",
                "role": "blocked_notice",
                "grounding_mode": "scaffold",
                "sources": [],
            },
        ]
        grounded_followup = next(
            (
                candidate
                for candidate in grounded_followup_candidates
                if first_distinct_paragraph(
                    [candidate["text"]],
                    [opening, detail_followup],
                )
            ),
            None,
        )
        if grounded_followup:
            add_paragraph(
                str(grounded_followup["text"]),
                *grounded_followup["sources"],
                role=str(grounded_followup["role"]),
                grounding_mode=str(grounded_followup["grounding_mode"]),
            )
        if anchor_source:
            if open_alternate:
                add_paragraph(
                    (
                        f"Prism has also linked an open follow-on read from {open_alternate['outlet']}. "
                        "The source mix is still too thin to treat differences in emphasis as a meaningful split in coverage, but this early brief is meant to give readers a fuller working summary before that wider comparison arrives."
                    ),
                    anchor_source or open_alternate,
                    open_alternate,
                    role="scope_note",
                    grounding_mode="scaffold",
                )
            elif anchor_source.get("fetch_blocked"):
                add_paragraph(
                    (
                        f"Prism is still treating this as a one-source early brief grounded primarily in {anchor_source['outlet']}'s feed-level reporting because the site blocked automated full-text retrieval. "
                        "Prism still needs either verified body text or another independent detailed report before coverage differences become useful to compare."
                    ),
                    *(support_payload(anchor_source) if anchor_source else []),
                    role="scope_note",
                    grounding_mode="scaffold",
                )
            else:
                add_paragraph(
                    (
                        f"Prism is still treating this as a one-source early brief grounded primarily in {anchor_source['outlet']}'s reporting. "
                        "It should already give readers the core story and immediate stakes, but Prism still needs another independent detailed report before coverage differences become useful to compare."
                    ),
                    *(support_payload(anchor_source) if anchor_source else []),
                    role="scope_note",
                    grounding_mode="scaffold",
                )
        elif blocked_article:
            add_paragraph(
                (
                    f"Prism is still treating this as a one-source early brief grounded primarily in {blocked_article['outlet']}'s feed-level reporting because the site blocked automated full-text retrieval. "
                    "Prism still needs either verified body text or another independent detailed report before coverage differences become useful to compare."
                ),
                role="scope_note",
                grounding_mode="scaffold",
            )
        elif open_alternate:
            add_paragraph(
                (
                    f"Prism has also linked an open follow-on read from {open_alternate['outlet']}. "
                    "The source mix is still too thin to treat differences in emphasis as a meaningful split in coverage, but this early brief is meant to give readers a fuller working summary before that wider comparison arrives."
                ),
                open_alternate,
                role="scope_note",
                grounding_mode="scaffold",
            )
        else:
            add_paragraph(
                (
                    "Prism is still working with a thin source set here. "
                    "This early brief is meant to give readers a usable first summary now, then widen into a fuller comparison once another detailed report arrives."
                ),
                *(support_payload(central) if central else []),
                role="scope_note",
                grounding_mode="scaffold",
            )

    filtered_paragraphs = [entry["text"] for entry in paragraph_entries]
    paragraph_support = [
        {
            "index": index,
            "support": entry["support"],
            "role": entry["role"],
            "grounding_mode": entry["grounding_mode"],
        }
        for index, entry in enumerate(paragraph_entries)
    ]

    supporting_points = visible_facts
    why_text, why_mode = why_it_matters_copy(cluster, family, sources, full_brief=full_brief)
    watch_text, watch_mode = watch_next_copy(cluster, family, full_brief=full_brief)
    why_support = support_payload(*(secondary_sources[:2] or ([central] if central else []))) if why_mode == "required" else []
    agree_anchor = anchor_source or central
    agree_support = (
        support_payload(central, secondary_sources[0])
        if central and secondary_sources
        else support_payload(*(sources[:2] or ([agree_anchor] if agree_anchor else [])))
    )
    agree_mode = "required" if agree_support else "scaffold"
    differs_support = (
        support_payload(central, divergent)
        if central and divergent
        else support_payload(*(secondary_sources[:2] or ([central] if central else [])))
    ) if full_brief else []
    watch_support = (
        []
        if watch_mode != "required" or cluster.get("correction_events")
        else support_payload(*(secondary_sources[:1] or ([central] if central else [])))
    )

    where_sources_agree = (
        (
                f"Across {outlet_text(cluster)}, the shared baseline is clear: {(central or {}).get('snippet') or ensure_period(cluster['summary'])}"
                if full_brief
                else f"The best-supported baseline right now comes from {(agree_anchor or {}).get('outlet') or 'the first linked report'}: {(agree_anchor or {}).get('snippet') or ensure_period(cluster['summary'])}"
        )
    )
    where_coverage_differs = (
        (
            f"The split so far is more about emphasis than the event itself. {(central or {}).get('outlet') or 'One outlet'} stays closest to the core sequence, while {divergent['outlet']} spends more time on {clean_focus_phrase(divergent['focus'], family)}."
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

    snapshot_sources: list[dict[str, Any]] = []
    if anchor_source:
        snapshot_sources.append(anchor_source)
    for source in (sources if sources else review_sources[:3]):
        article_id = source.get("article_id")
        if any(existing.get("article_id") == article_id and article_id for existing in snapshot_sources):
            continue
        snapshot_sources.append(source)
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
            "used_snippet": source_support_excerpt(source) or source["snippet"],
        }
        for source in snapshot_sources
    ]

    brief_payload = {
        "status": "full" if full_brief else "early",
        "label": "Prism brief" if full_brief else "Early brief",
        "title": "The story so far" if full_brief else "What the reporting says so far",
        "paragraphs": filtered_paragraphs,
        "why_it_matters": why_text,
        "where_sources_agree": where_sources_agree,
        "where_coverage_differs": where_coverage_differs,
        "what_to_watch": watch_text,
        "supporting_points": supporting_points,
        "metadata": {
            "substantive_source_count": source_metrics["substantive_outlet_count"],
            "article_body_source_count": source_metrics["article_body_outlet_count"],
            "paragraph_count": len(filtered_paragraphs),
            "family": family,
            "full_brief_ready": full_brief,
            "open_source_count": source_metrics["open_outlet_count"],
            "likely_paywalled_source_count": source_metrics["likely_paywalled_outlet_count"],
            "open_alternate_available": bool(open_alternate_available),
            "support_strategy_version": "grounded_sections_v2",
            "section_grounding_mode": {
                "why_it_matters": why_mode,
                "where_sources_agree": agree_mode,
                "where_coverage_differs": "required" if full_brief else "scaffold",
                "what_to_watch": watch_mode,
            },
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
            "generator_version": "deterministic_grounded_v2",
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
                "section_grounding_mode": brief_payload["metadata"]["section_grounding_mode"],
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


def fetch_revision_by_signature(
    client: SupabaseRestClient,
    cluster_id: str,
    input_signature: str,
) -> dict[str, Any] | None:
    rows = client.get(
        f"/story_brief_revisions?select=id,cluster_id,revision_tag,input_signature,status,metadata,is_current"
        f"&cluster_id=eq.{cluster_id}&input_signature=eq.{input_signature}&limit=1"
    ) or []
    return rows[0] if rows else None


def current_revision_row_id(current_revision: dict[str, Any] | None) -> str | None:
    if not isinstance(current_revision, dict):
        return None
    revision_id = current_revision.get("id")
    return revision_id if isinstance(revision_id, str) else None


def patch_revision_current_state(client: SupabaseRestClient, revision_id: str, *, is_current: bool) -> None:
    client.patch(
        f"/story_brief_revisions?id=eq.{revision_id}",
        {"is_current": is_current},
        prefer="return=minimal",
    )


def insert_brief_revision_draft(
    client: SupabaseRestClient,
    cluster_id: str,
    revision_tag: str,
    brief_payload: dict[str, Any],
) -> str:
    existing_revision_id = current_revision_row_id(
        fetch_revision_by_signature(client, cluster_id, brief_payload["input_signature"])
    )
    if existing_revision_id:
        return existing_revision_id

    try:
        rows = client.post(
            "/story_brief_revisions?select=id",
            [
                {
                    "cluster_id": cluster_id,
                    "revision_tag": revision_tag,
                    "status": brief_payload["status"],
                    "is_current": False,
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
            prefer="return=representation",
        ) or []
    except RuntimeError as exc:
        if "409" in str(exc) and "cluster_id, input_signature" in str(exc):
            existing_revision_id = current_revision_row_id(
                fetch_revision_by_signature(client, cluster_id, brief_payload["input_signature"])
            )
            if existing_revision_id:
                return existing_revision_id
        raise
    revision_id = rows[0].get("id") if rows else None
    if not isinstance(revision_id, str) or not revision_id:
        raise RuntimeError(f"Brief draft insert for cluster {cluster_id} did not return a revision id")
    return revision_id


def promote_revision_current_state(
    client: SupabaseRestClient,
    current_revision_id: str | None,
    new_revision_id: str,
) -> None:
    if current_revision_id:
        patch_revision_current_state(client, current_revision_id, is_current=False)
    try:
        patch_revision_current_state(client, new_revision_id, is_current=True)
    except Exception as exc:
        if current_revision_id:
            try:
                patch_revision_current_state(client, current_revision_id, is_current=True)
            except Exception as restore_exc:  # noqa: BLE001
                raise RuntimeError(
                    f"Failed to promote brief revision {new_revision_id} and failed to restore previous current revision {current_revision_id}: {restore_exc}"
                ) from exc
        raise


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

        revision_tag = f"brief-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        inserted_revision_id = insert_brief_revision_draft(client, cluster["id"], revision_tag, brief_payload)
        promote_revision_current_state(
            client,
            current_revision_row_id(current),
            inserted_revision_id,
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
