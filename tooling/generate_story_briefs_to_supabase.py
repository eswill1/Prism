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
LEADING_SOURCE_ATTRIBUTION_PATTERN = re.compile(
    r"^(?:"
    + "|".join(re.escape(outlet) for outlet in sorted(OPEN_OUTLETS | PAYWALLED_OUTLETS, key=len, reverse=True))
    + r")\s+(?:also\s+)?(?:described|focused|keeps?|kept|noted|reported|said|spends?|spent|wrote)\s+(?:that|more time on|on)?\s*",
    re.IGNORECASE,
)
LEADING_SPEAKER_ATTRIBUTION_PATTERN = re.compile(
    r"^(?:(?:[A-Z][A-Za-z'’.-]+|[Pp]resident|[Ff]ormer|[Ee]xiled|[Uu]\.S\.)\s+){1,4}"
    r"(?:added|announced|argued|called|declared|described|focused|keeps?|kept|noted|reported|said|says|spends?|spent|warned|wrote)\s+"
    r"(?:that|more time on|on)?\s*",
    re.IGNORECASE,
)
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
VAGUE_FOCUS_TOKENS = {
    "administration",
    "donald",
    "government",
    "iran",
    "israel",
    "judge",
    "lawmakers",
    "official",
    "officials",
    "president",
    "state",
    "trump",
    "white",
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
    "attack",
    "attacks",
    "donald",
    "friday",
    "government",
    "governments",
    "iran",
    "mark",
    "marks",
    "middle",
    "monday",
    "night",
    "oil",
    "official",
    "officials",
    "president",
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
    "strike",
    "strikes",
    "struck",
    "sunday",
    "thursday",
    "trump",
    "tuesday",
    "vowed",
    "vows",
    "wednesday",
    "week",
    "weeks",
    "war",
    "yesterday",
}

ABBREVIATION_PATTERNS = (
    r"\bU\.S\.",
    r"\bU\.S\b",
    r"\bU\.K\.",
    r"\bU\.K\b",
    r"\bE\.U\.",
    r"\bE\.U\b",
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
LEADING_WIRE_CREDIT_PATTERN = re.compile(
    r"^(?:[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}/(?:AP|Reuters|Getty|AFP|EPA)\s+)+",
    re.IGNORECASE,
)
LEADING_OUTLET_CREDIT_PATTERN = re.compile(
    r"^(?:[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}\s+for\s+[A-Z][A-Za-z'’.-]+"
    r"(?:/[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}\s+for\s+[A-Z][A-Za-z'’.-]+)*)\s+",
    re.IGNORECASE,
)
NOTE_BOILERPLATE_PATTERN = re.compile(
    r"^(?:notes?:|notice:\s*transcripts?\s+are\s+machine\s+and\s+human\s+generated|they may contain errors\.?$|data delayed at least|data shows future contract prices|chart:|graphic:|read more:)",
    re.IGNORECASE,
)
PROMO_PREFIX_PATTERN = re.compile(r"^(?:watch|listen|read more|see also):\s*", re.IGNORECASE)
CAPTION_START_PATTERN = re.compile(
    r"^(?:a man|a woman|firefighters?|people|residents|supporters|children|protesters|smoke|flames|vehicles|ships|boats)\b",
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
REPORTER_BIO_PATTERN = re.compile(
    r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2}(?:\s+and\s+[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2})?\s+have reported\b",
    re.IGNORECASE,
)
REPORTER_TRAVEL_PATTERN = re.compile(
    r"^(?:they|he|she)\s+travel(?:s)?\s+with\s+the\s+u\.s\.\s+secretary\s+of\s+state\b",
    re.IGNORECASE,
)
REPORTER_SIGNOFF_PATTERN = re.compile(
    r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2}\s+reports\.?$",
    re.IGNORECASE,
)
CONTEXT_HEADLINE_PATTERN = re.compile(
    r"\b(?:analysis|column|explainer|fact check|five things|how to|jokes?\b|live updates?|liveblog|minute-by-minute|mock(?:s|ed)?|opinion|photos|podcast|q&a|questions answered|slams?\b|swipes?\s+at|takeaways?|timeline|video|what to know|what we know|why it matters)\b",
    re.IGNORECASE,
)
CONTEXT_URL_PATTERN = re.compile(
    r"/(?:analysis|blogs?|explainer|fact-check|live|live-updates|media|opinion|photos|podcast|timeline|video)/",
    re.IGNORECASE,
)
COMMENTARY_SOURCE_PATTERN = re.compile(
    r"\b(?:blog|comedian|commentary|former\s+[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}\s+(?:aide|director|official)|host|panelists?|pundit|ret\.\)|swipes?\s+at)\b",
    re.IGNORECASE,
)
BRIEF_SCOPE_NOTE_PATTERN = re.compile(
    r"^Prism (?:could not retrieve|currently sees|found an open alternate read from|has also linked|has linked|is grounding|is holding back|is still treating|is still working with|only has|still needs)\b",
    re.IGNORECASE,
)
FOCUS_CONNECTOR_PATTERN = re.compile(
    r"\b(?:about|after|amid|as|before|during|for|into|over|under|while|with)\b",
    re.IGNORECASE,
)
FOCUS_VERB_OBJECT_PATTERN = re.compile(
    r"\b(?:blocks?|blocked|calls?|called|calms?|calmed|deploys?|deployed|exits?|exited|grills?|grilled|keeps?|kept|launches?|launched|leads?|led|moves?|moved|pushes?|pushed|releases?|released|says?|said|sends?|sent|steadies?|steadied|suspends?|suspended|uses?|used|vows?|vowed|warns?|warned|wants?)\s+(.+)$",
    re.IGNORECASE,
)
DATE_OR_DAY_PATTERN = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_credit_prefixes(value: str) -> str:
    cleaned = normalize_whitespace(value)
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = PHOTO_CREDIT_PATTERN.sub(". ", cleaned)
        cleaned = LEADING_WIRE_CREDIT_PATTERN.sub("", cleaned)
        cleaned = LEADING_OUTLET_CREDIT_PATTERN.sub("", cleaned)
        cleaned = PROMO_PREFIX_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"^(?:hide caption|toggle caption)\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = normalize_whitespace(cleaned)
    return cleaned


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


def raw_focus_phrase(value: str | None) -> str:
    cleaned = strip_ending_punctuation(value or "")
    cleaned = normalize_whitespace(cleaned.strip(' "\''))
    if not cleaned:
        return ""

    cleaned = LEADING_SOURCE_ATTRIBUTION_PATTERN.sub("", cleaned)
    cleaned = LEADING_SPEAKER_ATTRIBUTION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^(?:focus(?:es)?\s+on|questions?\s+about|the\s+question\s+of|the\s+debate\s+over|coverage\s+of)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:about|after|amid|as|before|during|for|into|over|under|while|with)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:according to|officials said|reporters said)\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_whitespace(cleaned.strip(' "\''))
    if not cleaned:
        return ""

    words = cleaned.split()
    if len(words) > 8:
        cleaned = " ".join(words[:8])
    return cleaned


def focus_phrase_is_specific(value: str) -> bool:
    cleaned = raw_focus_phrase(value)
    if not cleaned:
        return False

    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9']{3,}", cleaned)
    content_tokens = [
        token
        for token in tokens
        if token.lower() not in GENERIC_FOCUS_TOKENS
        and token.lower() not in FOCUS_ENTITY_STOPWORDS
        and token.lower() not in STOPWORD_TOKENS
    ]
    if len(content_tokens) >= 3:
        return True
    if len(content_tokens) >= 2 and not all(token.lower() in VAGUE_FOCUS_TOKENS for token in content_tokens):
        return True
    if len(content_tokens) == 1 and content_tokens[0].lower() not in VAGUE_FOCUS_TOKENS and len(content_tokens[0]) >= 8:
        return True
    return False


def focus_candidate_score(value: str) -> float:
    cleaned = raw_focus_phrase(value)
    if not cleaned:
        return -1.0

    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9']{3,}", cleaned)
    content_tokens = [
        token
        for token in tokens
        if token.lower() not in GENERIC_FOCUS_TOKENS
        and token.lower() not in FOCUS_ENTITY_STOPWORDS
        and token.lower() not in STOPWORD_TOKENS
    ]
    score = float(len(content_tokens))
    if 2 <= len(cleaned.split()) <= 6:
        score += 2.0
    if not FOCUS_CONNECTOR_PATTERN.search(cleaned):
        score += 1.0
    if not re.match(r"^(?:the|a|an)\b", cleaned, re.IGNORECASE):
        score += 0.5
    if cleaned.lower().startswith(tuple(VAGUE_FOCUS_TOKENS)):
        score -= 1.0
    return score


def clean_focus_phrase(value: str | None, family: str) -> str:
    cleaned = raw_focus_phrase(value)
    if focus_phrase_is_specific(cleaned):
        return cleaned

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

    if not tokens or all(token in VAGUE_FOCUS_TOKENS for token in tokens):
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


def focused_overlap_count(reference: str, candidate: str) -> int:
    reference_tokens = comparable_tokens(reference) - LOW_SIGNAL_ALIGNMENT_TOKENS
    candidate_tokens = comparable_tokens(candidate) - LOW_SIGNAL_ALIGNMENT_TOKENS
    return len(reference_tokens & candidate_tokens)


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


def source_context_score(*, headline: str, summary: str, url: str) -> int:
    score = 0
    combined_text = normalize_whitespace(f"{headline} {summary}")
    if CONTEXT_HEADLINE_PATTERN.search(combined_text):
        score += 2
    if CONTEXT_URL_PATTERN.search(url):
        score += 2
    if COMMENTARY_SOURCE_PATTERN.search(combined_text):
        score += 3
    if re.match(r"^\d+\s+(?:things|reasons|takeaways)\b", headline, re.IGNORECASE):
        score += 2
    if "?" in headline:
        score += 1
    return score


def source_is_story_aligned(source: dict[str, Any]) -> bool:
    return bool(
        (
            float(source.get("story_alignment") or 0.0) >= 0.28
            and int(source.get("story_overlap_count") or 0) >= 2
        )
        or (
            float(source.get("detail_alignment") or 0.0) >= 0.24
            and int(source.get("detail_overlap_count") or 0) >= 2
        )
        or (
            float(source.get("followup_alignment") or 0.0) >= 0.24
            and int(source.get("followup_overlap_count") or 0) >= 2
        )
    )


def source_is_shell_aligned(source: dict[str, Any]) -> bool:
    return bool(
        (
            float(source.get("headline_alignment") or 0.0) >= 0.24
            and int(source.get("headline_overlap_count") or 0) >= 2
        )
        or (
            float(source.get("detail_headline_alignment") or 0.0) >= 0.22
            and int(source.get("detail_headline_overlap_count") or 0) >= 2
        )
        or (
            float(source.get("followup_headline_alignment") or 0.0) >= 0.22
            and int(source.get("followup_headline_overlap_count") or 0) >= 2
        )
    )


def source_is_contextual(source: dict[str, Any]) -> bool:
    return int(source.get("context_score") or 0) >= 2


def source_has_distinct_narrative_text(source: dict[str, Any]) -> bool:
    headline = str(source.get("headline") or "")
    for field_name in ("detail", "followup", "snippet"):
        candidate = ensure_period(str(source.get(field_name) or "").strip())
        if not candidate:
            continue
        if sentence_looks_non_narrative(candidate) or text_looks_clipped(candidate):
            continue
        if not text_looks_title_like(headline, candidate):
            return True
    return False


def source_is_title_only_stub(source: dict[str, Any]) -> bool:
    if source_has_distinct_narrative_text(source):
        return False
    if source.get("title_like_snippet"):
        return True
    return bool(
        source_is_contextual(source)
        and source.get("extraction_quality") != "article_body"
        and not str(source.get("detail") or "").strip()
        and not str(source.get("followup") or "").strip()
    )


def source_is_comparison_ready(source: dict[str, Any]) -> bool:
    if not source_is_story_aligned(source):
        return False
    if not source_is_shell_aligned(source):
        return False
    if source_is_contextual(source):
        return False
    if source.get("fetch_blocked"):
        return False
    if source_is_title_only_stub(source):
        return False
    return True


def source_is_core_story_source(source: dict[str, Any]) -> bool:
    return source_is_comparison_ready(source)


def source_priority_score(source: dict[str, Any]) -> float:
    return (
        float(source.get("story_alignment") or 0.0) * 3.0
        + float(source.get("headline_alignment") or 0.0) * 1.8
        + float(source.get("detail_alignment") or 0.0) * 1.4
        + float(source.get("followup_alignment") or 0.0)
        + (0.4 if source_is_core_story_source(source) else 0.0)
        + (0.18 if source_has_distinct_narrative_text(source) else 0.0)
        + (0.18 if source_is_shell_aligned(source) else -0.28)
        + (0.24 if source.get("extraction_quality") == "article_body" else 0.0)
        + (0.06 if source.get("access_tier") == "open" else 0.0)
        - (0.34 * int(source.get("context_score") or 0))
        - (0.16 if source.get("fetch_blocked") else 0.0)
        - (0.48 if source_is_title_only_stub(source) else 0.0)
        - (0.12 if source.get("title_like_snippet") else 0.0)
        - (0.01 * int(source.get("rank_in_cluster") or 999))
    )


def normalize_sentence_closing_punctuation(text: str) -> str:
    text = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r'([.!?])\s+([)"\]\'\u2019\u201d]+)', r"\1\2", text)


def prepare_narrative_text(text: str) -> str:
    cleaned = strip_credit_prefixes(text)
    if not cleaned:
        return ""
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
    if LEADING_WIRE_CREDIT_PATTERN.search(cleaned) or LEADING_OUTLET_CREDIT_PATTERN.search(cleaned):
        return True
    if PROMO_PREFIX_PATTERN.search(cleaned):
        return True
    if "|" in cleaned and re.search(r"/(?:ap|reuters|getty|afp|epa)\b", lowered):
        return True
    if re.match(r"^[A-Z]\.\s+[a-z]", cleaned):
        return True
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", cleaned):
        return True
    if REPORTER_BIO_PATTERN.search(cleaned):
        return True
    if REPORTER_TRAVEL_PATTERN.search(cleaned):
        return True
    if REPORTER_SIGNOFF_PATTERN.search(cleaned):
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
        return bool(re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", cleaned))
    if cleaned.endswith("...") or cleaned.endswith("…"):
        return True
    if cleaned.count("“") > cleaned.count("”") or cleaned.count('"') % 2 == 1:
        return True
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", cleaned):
        return True
    return not re.search(r"[.!?](?:[\"'\u2019\u201d)\]]+)?$", cleaned)


def has_spaced_abbreviation(text: str) -> bool:
    return bool(re.search(r"\b[A-Z]\.\s+[A-Z](?:\b|\.)", normalize_whitespace(text)))


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
    filtered = [
        sentence
        for sentence in split_narrative_sentences(text)
        if sentence and not sentence_looks_non_narrative(sentence) and not text_looks_clipped(sentence)
    ]
    deduped: list[str] = []
    for sentence in filtered:
        if any(
            sentence_similarity(sentence, existing) >= 0.72
            or narrative_token_overlap(sentence, existing) >= 0.66
            or normalize_whitespace(sentence).lower() == normalize_whitespace(existing).lower()
            for existing in deduped
        ):
            continue
        deduped.append(sentence)
    return deduped


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
        if reference_text.strip():
            if focused_overlap_count(reference_text, sentence) < 2:
                continue
            if focused_alignment_score(reference_text, sentence) < minimum_alignment:
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
        if (
            len(sentence) >= 50
            and focused_overlap_count(reference_text, sentence) >= 2
            and focused_alignment_score(reference_text, sentence) >= minimum_alignment
        )
    ]
    return " ".join(aligned[:sentence_count]).strip()


def short_body_followup_sentences(
    article: dict[str, Any],
    *,
    sentence_count: int,
    minimum_alignment: float = 0.08,
) -> str:
    body_text = str(article.get("body_text") or "").strip()
    if not body_text:
        return ""

    sentences = filtered_narrative_sentences(body_text)
    if len(sentences) <= 1:
        return ""

    reference_text = source_reference_text(article)
    opening = sentences[0]
    short_body = len(sentences) <= 2
    selected: list[str] = []
    for sentence in sentences[1:]:
        if len(selected) >= sentence_count:
            break
        if len(sentence) < 40:
            continue
        if (
            sentence_similarity(sentence, opening) >= 0.72
            or narrative_token_overlap(sentence, opening) >= 0.66
        ):
            continue
        if reference_text.strip() and not short_body:
            if (
                focused_alignment_score(reference_text, sentence) < minimum_alignment
                and focused_overlap_count(reference_text, sentence) < 2
            ):
                continue
        selected.append(sentence)

    return " ".join(selected).strip()


def sentence_has_detail_signal(sentence: str) -> bool:
    cleaned = normalize_whitespace(sentence)
    if len(cleaned) < 45:
        return False
    if re.search(r"\b\d[\d,]*(?:\.\d+)?\b", cleaned):
        return True
    if re.search(r"\b(?:Pentagon|White House|Congress|Senate|House|Navy|Marines|military|officials|analysts|police|court|judge|prosecutors?)\b", cleaned):
        return True
    if REPORTING_VERB_PATTERN.search(cleaned):
        return True
    return bool(re.search(r"\b[A-Z]{2,}\b", cleaned))


def sentence_starts_with_new_proper_noun(reference_text: str, sentence: str) -> bool:
    match = re.match(
        r"^(?:[A-Z][A-Za-z'’.-]+|Gov\.|Sen\.|Rep\.|President|Prime|Minister)(?:\s+(?:[A-Z][A-Za-z'’.-]+|Gov\.|Sen\.|Rep\.|President|Prime|Minister)){1,4}",
        normalize_whitespace(sentence),
    )
    if not match:
        return False

    reference_lower = normalize_whitespace(reference_text).lower()
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z'’.-]{3,}", match.group(0))
        if token.lower() not in {"gov", "sen", "rep", "prime", "minister", "president"}
    ]
    return len(tokens) >= 2 and all(token not in reference_lower for token in tokens)


def contiguous_body_detail_sentences(
    article: dict[str, Any],
    *,
    skip_count: int,
    sentence_count: int,
) -> str:
    body_text = str(article.get("body_text") or "").strip()
    if not body_text:
        return ""

    sentences = filtered_narrative_sentences(body_text)
    if len(sentences) <= skip_count:
        return ""

    reference_text = source_reference_text(article)
    prior_sentences = sentences[:skip_count]
    selected: list[str] = []
    for sentence in sentences[skip_count:]:
        if len(selected) >= sentence_count:
            break
        if len(sentence) < 35:
            continue
        if any(
            sentence_similarity(sentence, existing) >= 0.72
            or narrative_token_overlap(sentence, existing) >= 0.66
            for existing in prior_sentences + selected
        ):
            continue
        if reference_text.strip():
            overlap = focused_overlap_count(reference_text, sentence)
            alignment = focused_alignment_score(reference_text, sentence)
            if overlap >= 2 and alignment >= 0.16:
                selected.append(sentence)
                continue
            if overlap >= 1 and alignment >= 0.08 and sentence_has_detail_signal(sentence):
                selected.append(sentence)
                continue
        if sentence_has_detail_signal(sentence):
            selected.append(sentence)
            continue

    return " ".join(selected).strip()


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
            if (
                raw_later
                and focused_overlap_count(reference_text, raw_later) >= 2
                and focused_alignment_score(reference_text, raw_later) >= 0.16
            ):
                return raw_later

        aligned = aligned_later_body_sentences(article, skip_count=2, sentence_count=2)
        if aligned:
            return ensure_period(aligned)

        contiguous_detail = ensure_period(contiguous_body_detail_sentences(article, skip_count=2, sentence_count=2))
        if contiguous_detail:
            return contiguous_detail

        short_followup = ensure_period(short_body_followup_sentences(article, sentence_count=2))
        if short_followup:
            return short_followup

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
            if (
                raw_later
                and focused_overlap_count(reference_text, raw_later) >= 2
                and focused_alignment_score(reference_text, raw_later) >= 0.16
            ):
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


def body_story_paragraph_candidates(
    article: dict[str, Any],
    *,
    max_paragraphs: int = 4,
    max_sentences_per_paragraph: int = 2,
) -> list[str]:
    metadata = article.get("metadata") or {}
    extraction_quality = metadata.get("extraction_quality") if isinstance(metadata, dict) else None
    body_text = str(article.get("body_text") or "").strip()
    if not body_text or extraction_quality != "article_body" or has_body_mismatch(article):
        return []

    paragraphs: list[str] = []
    current_sentences: list[str] = []
    reference_text = source_reference_text(article)
    for sentence in filtered_narrative_sentences(body_text):
        if len(sentence) < 35:
            continue
        if (
            reference_text
            and focused_overlap_count(reference_text, sentence) == 0
            and focused_alignment_score(reference_text, sentence) < 0.05
            and sentence_starts_with_new_proper_noun(reference_text, sentence)
        ):
            continue
        current_sentences.append(sentence)
        if len(current_sentences) >= max_sentences_per_paragraph or len(" ".join(current_sentences)) >= 240:
            paragraph = ensure_period(" ".join(current_sentences))
            if paragraph and not any(
                sentence_similarity(paragraph, existing) >= 0.72
                or narrative_token_overlap(paragraph, existing) >= 0.66
                for existing in paragraphs
            ):
                paragraphs.append(paragraph)
            current_sentences = []
        if len(paragraphs) >= max_paragraphs:
            break

    if current_sentences and len(paragraphs) < max_paragraphs:
        paragraph = ensure_period(" ".join(current_sentences))
        if paragraph and not any(
            sentence_similarity(paragraph, existing) >= 0.72
            or narrative_token_overlap(paragraph, existing) >= 0.66
            for existing in paragraphs
        ):
            paragraphs.append(paragraph)

    return paragraphs


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


def focus_candidate_fragments(text: str) -> list[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []

    candidates: list[str] = []
    segments = [segment for segment in re.split(r"\s*(?::|;|,|[–—])\s*", cleaned) if segment]
    for segment in segments:
        normalized_segment = normalize_whitespace(segment)
        if not normalized_segment:
            continue

        for match in FOCUS_CONNECTOR_PATTERN.finditer(normalized_segment):
            fragment = raw_focus_phrase(normalized_segment[match.end() :])
            if fragment and fragment not in candidates:
                candidates.append(fragment)

        verb_match = FOCUS_VERB_OBJECT_PATTERN.search(normalized_segment)
        if verb_match:
            fragment = raw_focus_phrase(verb_match.group(1))
            if fragment and fragment not in candidates:
                candidates.append(fragment)

        leading_fragment = raw_focus_phrase(normalized_segment)
        if leading_fragment and leading_fragment not in candidates:
            candidates.append(leading_fragment)

    return candidates


def article_focus(article: dict[str, Any], family: str) -> str:
    metadata = article.get("metadata") or {}
    focus_texts = [
        article.get("headline") or "",
        article.get("summary") or "",
        (metadata.get("feed_summary") if isinstance(metadata, dict) else "") or "",
    ]
    focus_texts.extend(split_narrative_sentences(str(article.get("body_text") or ""))[:3])
    candidate_fragments: list[str] = []
    for text in focus_texts:
        for fragment in focus_candidate_fragments(str(text or "")):
            cleaned_fragment = clean_focus_phrase(fragment, family)
            if focus_phrase_is_specific(cleaned_fragment) and cleaned_fragment not in candidate_fragments:
                candidate_fragments.append(cleaned_fragment)
    if candidate_fragments:
        return sorted(candidate_fragments, key=focus_candidate_score, reverse=True)[0]

    named_entities = metadata.get("named_entities") if isinstance(metadata, dict) else []
    if isinstance(named_entities, list):
        cleaned_entities = []
        for value in named_entities:
            if not isinstance(value, str) or len(value.strip()) < 4:
                continue
            normalized = raw_focus_phrase(value)
            if not normalized:
                continue
            tokens = re.findall(r"[A-Za-zÀ-ÿ0-9']{3,}", normalized)
            if not tokens or all(token.lower() in FOCUS_ENTITY_STOPWORDS or token.lower() in VAGUE_FOCUS_TOKENS for token in tokens):
                continue
            if normalized not in cleaned_entities:
                cleaned_entities.append(normalized)
        if cleaned_entities:
            preferred = clean_focus_phrase(cleaned_entities[0], family)
            if focus_phrase_is_specific(preferred):
                return preferred

    for text in focus_texts:
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

    return focus_fallback_for_family(family)


def cluster_source_rows(cluster: dict[str, Any], *, substantive_only: bool) -> list[dict[str, Any]]:
    family = topic_family_for_story(str(cluster.get("topic_label") or cluster.get("topic") or "general"))
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
        headline = article.get("headline") or cluster["canonical_headline"]
        canonical_url = article.get("canonical_url")
        original_url = article.get("original_url")
        snippet_text = ensure_period(snippet)
        detail = detail_text_for_article(article)
        followup = followup_text_for_article(article)
        context_score = source_context_score(
            headline=str(headline),
            summary=str(article.get("summary") or metadata.get("feed_summary") or ""),
            url=normalize_whitespace(str(canonical_url or original_url or "")),
        )
        summary_reference = str(cluster.get("summary") or "")
        headline_reference = str(cluster.get("canonical_headline") or "")
        story_alignment = max(
            cluster_story_alignment(cluster, snippet_text),
            cluster_story_alignment(cluster, str(headline or "")),
        )
        headline_alignment = max(
            alignment_score(headline_reference, snippet_text),
            alignment_score(headline_reference, str(headline or "")),
        )
        detail_alignment = cluster_story_alignment(cluster, detail) if detail else 0.0
        followup_alignment = cluster_story_alignment(cluster, followup) if followup else 0.0
        detail_headline_alignment = alignment_score(headline_reference, detail) if detail else 0.0
        followup_headline_alignment = alignment_score(headline_reference, followup) if followup else 0.0
        story_overlap_count = max(
            focused_overlap_count(summary_reference, snippet_text),
            focused_overlap_count(headline_reference, snippet_text),
            focused_overlap_count(summary_reference, str(headline or "")),
            focused_overlap_count(headline_reference, str(headline or "")),
        )
        headline_overlap_count = max(
            focused_overlap_count(headline_reference, snippet_text),
            focused_overlap_count(headline_reference, str(headline or "")),
        )
        detail_overlap_count = max(
            focused_overlap_count(summary_reference, detail),
            focused_overlap_count(headline_reference, detail),
        ) if detail else 0
        detail_headline_overlap_count = focused_overlap_count(headline_reference, detail) if detail else 0
        followup_overlap_count = max(
            focused_overlap_count(summary_reference, followup),
            focused_overlap_count(headline_reference, followup),
        ) if followup else 0
        followup_headline_overlap_count = focused_overlap_count(headline_reference, followup) if followup else 0
        rows.append(
            {
                "article_id": article.get("id"),
                "outlet": outlet,
                "headline": headline,
                "canonical_url": canonical_url,
                "original_url": original_url,
                "rank_in_cluster": relation.get("rank_in_cluster") or 999,
                "framing": relation.get("framing_group") or "center",
                "summary": article.get("summary") or "",
                "feed_summary": metadata.get("feed_summary") if isinstance(metadata, dict) else "",
                "snippet": snippet_text,
                "focus": article_focus(article, family),
                "detail": detail,
                "followup": followup,
                "body_paragraphs": body_story_paragraph_candidates(article),
                "extraction_quality": metadata.get("extraction_quality") if isinstance(metadata, dict) else None,
                "story_alignment": story_alignment,
                "headline_alignment": headline_alignment,
                "detail_alignment": detail_alignment,
                "followup_alignment": followup_alignment,
                "story_overlap_count": story_overlap_count,
                "headline_overlap_count": headline_overlap_count,
                "detail_overlap_count": detail_overlap_count,
                "detail_headline_alignment": detail_headline_alignment,
                "detail_headline_overlap_count": detail_headline_overlap_count,
                "followup_overlap_count": followup_overlap_count,
                "followup_headline_alignment": followup_headline_alignment,
                "followup_headline_overlap_count": followup_headline_overlap_count,
                "title_like_snippet": text_looks_title_like(
                    str(headline or cluster["canonical_headline"]),
                    snippet_text,
                ),
                "context_score": context_score,
                "fetch_blocked": fetch_blocked(article),
                "is_substantive": is_substantive,
                "access_tier": infer_access_tier(
                    outlet,
                    metadata.get("access_signal") if isinstance(metadata, dict) else None,
                ),
            }
        )

    for source in rows:
        source["is_story_aligned"] = source_is_story_aligned(source)
        source["is_core_story_source"] = source_is_core_story_source(source)
        source["priority_score"] = source_priority_score(source)

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


def ranked_story_sources(sources: list[dict[str, Any]], *, core_only: bool = False) -> list[dict[str, Any]]:
    filtered = [source for source in sources if source_is_core_story_source(source)] if core_only else list(sources)
    return sorted(
        filtered,
        key=lambda source: (
            float(source.get("priority_score") or source_priority_score(source)),
            float(source.get("story_alignment") or 0.0),
            float(source.get("detail_alignment") or 0.0),
            1 if source.get("extraction_quality") == "article_body" else 0,
            1 if source.get("access_tier") == "open" else 0,
            -(int(source.get("rank_in_cluster") or 999)),
        ),
        reverse=True,
    )


def best_story_aligned_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = ranked_story_sources(sources)
    preferred = [source for source in ranked if source_is_story_aligned(source) and not source_is_title_only_stub(source)]
    if preferred:
        return preferred[0]
    aligned = [source for source in ranked if source_is_story_aligned(source)]
    return aligned[0] if aligned else (ranked[0] if ranked else None)


def best_shell_aligned_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    shell_aligned = [source for source in ranked_story_sources(sources) if source_is_shell_aligned(source)]
    preferred = [source for source in shell_aligned if not source_is_title_only_stub(source)]
    return preferred[0] if preferred else (shell_aligned[0] if shell_aligned else None)


def best_comparison_ready_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [source for source in ranked_story_sources(sources) if source_is_comparison_ready(source)]
    return candidates[0] if candidates else None


def source_distinct_candidate_text(source: dict[str, Any], existing: list[str]) -> str:
    return first_distinct_paragraph(
        [
            str(source.get("detail") or ""),
            str(source.get("followup") or ""),
            str(source.get("snippet") or ""),
        ],
        existing,
    )


def source_followon_candidate_text(source: dict[str, Any], existing: list[str]) -> str:
    return first_distinct_paragraph(
        [
            str(source.get("detail") or ""),
            str(source.get("followup") or ""),
        ],
        existing,
    )


def divergent_source(sources: list[dict[str, Any]], lead: dict[str, Any] | None, family: str) -> dict[str, Any] | None:
    if not lead:
        return None

    candidates = [
        source
        for source in ranked_story_sources(sources, core_only=True)
        if source.get("article_id") != lead.get("article_id") and source.get("outlet") != lead.get("outlet")
    ]
    if not candidates:
        return None

    lead_focus = clean_focus_phrase(str(lead.get("focus") or ""), family)
    lead_texts = [
        ensure_period(str(value or ""))
        for value in (lead.get("snippet"), lead.get("detail"), lead.get("followup"))
        if str(value or "").strip()
    ]

    best_candidate: dict[str, Any] | None = None
    best_score = -1.0
    for source in candidates:
        candidate_text = source_distinct_candidate_text(source, lead_texts)
        if not candidate_text:
            continue

        source_focus = clean_focus_phrase(str(source.get("focus") or ""), family)
        focus_shift = 1.0 if source_focus and source_focus != lead_focus else 0.0
        distinctness = 1.0 - max(
            sentence_similarity(str(source.get("snippet") or ""), str(lead.get("snippet") or "")),
            narrative_token_overlap(str(source.get("snippet") or ""), str(lead.get("snippet") or "")),
        )
        score = (
            float(source.get("priority_score") or 0.0)
            + focus_shift * 0.3
            + distinctness * 0.4
            + (0.15 if source.get("framing") != lead.get("framing") else 0.0)
        )
        if score > best_score:
            best_candidate = source
            best_score = score

    return best_candidate


def substantive_alignment_pair(cluster: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    family = topic_family_for_story(str(cluster.get("topic_label") or cluster.get("topic") or "general"))
    ranked_core = ranked_story_sources(rows, core_only=True)
    lead = ranked_core[0] if ranked_core else (ranked_story_sources(rows)[0] if rows else None)
    return lead, divergent_source(rows, lead, family) if lead else None


def cluster_brief_source_metrics(cluster: dict[str, Any]) -> dict[str, Any]:
    rows = cluster_substantive_source_rows(cluster)
    substantive_outlets = {row["outlet"] for row in rows}
    article_body_outlets = {row["outlet"] for row in rows if row.get("extraction_quality") == "article_body"}
    aligned_outlets = {row["outlet"] for row in rows if source_is_story_aligned(row)}
    aligned_article_body_outlets = {
        row["outlet"] for row in rows if source_is_story_aligned(row) and row.get("extraction_quality") == "article_body"
    }
    shell_aligned_outlets = {row["outlet"] for row in rows if source_is_shell_aligned(row)}
    shell_aligned_article_body_outlets = {
        row["outlet"] for row in rows if source_is_shell_aligned(row) and row.get("extraction_quality") == "article_body"
    }
    core_story_outlets = {row["outlet"] for row in rows if source_is_core_story_source(row)}
    comparison_ready_outlets = {row["outlet"] for row in rows if source_is_comparison_ready(row)}
    title_only_shell_outlets = {
        row["outlet"] for row in rows if source_is_shell_aligned(row) and source_is_title_only_stub(row)
    }
    contextual_outlets = {row["outlet"] for row in rows if source_is_contextual(row)}
    open_outlets = {row["outlet"] for row in rows if row.get("access_tier") == "open"}
    paywalled_outlets = {row["outlet"] for row in rows if row.get("access_tier") == "likely_paywalled"}
    lead_source, divergence_source = substantive_alignment_pair(cluster, rows)
    return {
        "substantive_source_count": len(rows),
        "substantive_outlet_count": len(substantive_outlets),
        "article_body_outlet_count": len(article_body_outlets),
        "aligned_outlet_count": len(aligned_outlets),
        "aligned_article_body_outlet_count": len(aligned_article_body_outlets),
        "shell_aligned_outlet_count": len(shell_aligned_outlets),
        "shell_aligned_article_body_outlet_count": len(shell_aligned_article_body_outlets),
        "core_story_outlet_count": len(core_story_outlets),
        "comparison_ready_outlet_count": len(comparison_ready_outlets),
        "title_only_shell_outlet_count": len(title_only_shell_outlets),
        "contextual_outlet_count": len(contextual_outlets),
        "open_outlet_count": len(open_outlets),
        "likely_paywalled_outlet_count": len(paywalled_outlets),
        "full_brief_ready": bool(
            len(substantive_outlets) >= 2
            and len(comparison_ready_outlets) >= 2
            and len(shell_aligned_article_body_outlets) >= 1
            and len(core_story_outlets) >= 2
            and lead_source
            and divergence_source
        ),
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
    candidates = ranked_story_sources(cluster_substantive_source_rows(cluster))
    preferred = [source for source in candidates if source_is_comparison_ready(source)]
    fallback = [
        source
        for source in candidates
        if source_is_story_aligned(source) and source_is_shell_aligned(source) and not source_is_title_only_stub(source)
    ]
    ordered_candidates = preferred or fallback
    for source in ordered_candidates:
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
    for source in ranked_story_sources(sources):
        if source.get("access_tier") != "open":
            continue
        if exclude_outlet and source.get("outlet") == exclude_outlet:
            continue
        if source_is_title_only_stub(source):
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
    values = [*(source.get("body_paragraphs") or []), source.get("snippet"), source.get("detail"), source.get("followup")]
    for value in values:
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
    return best_story_aligned_source(sources)


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
    summary_is_title_like_shell = text_looks_title_like(str(cluster.get("canonical_headline") or ""), summary) or bool(
        CONTEXT_HEADLINE_PATTERN.search(summary)
    )
    if snippet and (
        not summary
        or sentence_looks_non_narrative(summary)
        or text_looks_clipped(summary)
        or (source_is_comparison_ready(central) and summary_is_title_like_shell)
        or (has_spaced_abbreviation(summary) and not has_spaced_abbreviation(snippet))
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
        and not (source_is_comparison_ready(central) and summary_is_title_like_shell)
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


def remove_overlapping_sentences(candidate: str, existing: list[str]) -> str:
    candidate_sentences = split_narrative_sentences(candidate)
    if not candidate_sentences:
        return ""

    existing_sentences = [
        sentence
        for paragraph in existing
        for sentence in split_narrative_sentences(paragraph)
    ]
    if not existing_sentences:
        return candidate.strip()

    remaining = [
        sentence
        for sentence in candidate_sentences
        if not any(
            sentence_similarity(sentence, prior) >= 0.72
            or narrative_token_overlap(sentence, prior) >= 0.66
            or normalize_whitespace(sentence).lower() in normalize_whitespace(prior).lower()
            for prior in existing_sentences
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

    detail = ensure_period(remove_overlapping_sentences(str(central.get("detail") or "").strip(), [opening]))
    if detail and normalize_whitespace(detail).lower() not in normalize_whitespace(opening).lower() and sentence_similarity(detail, opening) < 0.72:
        return detail

    for fallback_text in (
        str(central.get("summary") or "").strip(),
        str(central.get("feed_summary") or "").strip(),
    ):
        extra_sentences = split_narrative_sentences(fallback_text)
        candidate = ensure_period(remove_overlapping_sentences(" ".join(extra_sentences[1:3]), [opening])) if len(extra_sentences) >= 2 else ""
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


def source_story_followon_paragraphs(
    source: dict[str, Any] | None,
    *,
    opening: str,
    limit: int,
) -> list[str]:
    if not source:
        return []

    existing = [opening]
    paragraphs: list[str] = []
    candidate_pool: list[str] = []

    snippet_extension = ensure_period(snippet_extension_after_opening(opening, str(source.get("snippet") or "")))
    candidate_pool.extend(str(value or "") for value in source.get("body_paragraphs") or [])
    if snippet_extension:
        candidate_pool.append(snippet_extension)
    candidate_pool.extend(
        [
            str(source.get("detail") or ""),
            str(source.get("followup") or ""),
        ]
    )

    for raw_candidate in candidate_pool:
        candidate = ensure_period(remove_overlapping_sentences(str(raw_candidate or ""), existing))
        paragraph = first_distinct_paragraph([candidate], existing)
        if not paragraph:
            continue
        paragraphs.append(paragraph)
        existing.append(paragraph)
        if len(paragraphs) >= limit:
            break

    return paragraphs


def paragraph_materially_distinct(text: str, anchors: list[str]) -> bool:
    cleaned = ensure_period(text)
    if not cleaned:
        return False
    for anchor in anchors:
        normalized_anchor = normalize_whitespace(anchor)
        if not normalized_anchor:
            continue
        if (
            sentence_similarity(cleaned, normalized_anchor) >= 0.72
            or narrative_token_overlap(cleaned, normalized_anchor) >= 0.66
            or normalize_whitespace(cleaned).lower() in normalize_whitespace(normalized_anchor).lower()
            or normalize_whitespace(normalized_anchor).lower() in normalize_whitespace(cleaned).lower()
        ):
            return False
    return True


def paragraph_entry_adds_reader_value(
    cluster: dict[str, Any],
    entry: dict[str, Any],
    *,
    opening: str,
) -> bool:
    text = str(entry.get("text") or "")
    if entry.get("grounding_mode") != "required":
        return False
    if entry.get("role") in {"opening", "scope_note", "blocked_notice"}:
        return False
    if BRIEF_SCOPE_NOTE_PATTERN.search(text):
        return False
    if sentence_looks_non_narrative(text) or text_looks_clipped(text):
        return False
    anchors = [
        opening,
        str(cluster.get("summary") or ""),
        str(cluster.get("canonical_headline") or ""),
        str(cluster.get("dek") or ""),
    ]
    return paragraph_materially_distinct(text, anchors)


def brief_display_state(
    cluster: dict[str, Any],
    paragraph_entries: list[dict[str, Any]],
    *,
    full_brief: bool,
) -> tuple[bool, str | None]:
    if not paragraph_entries:
        return False, "no_paragraphs"

    opening = str(paragraph_entries[0].get("text") or "")
    value_entries = [
        entry
        for entry in paragraph_entries[1:]
        if paragraph_entry_adds_reader_value(cluster, entry, opening=opening)
    ]
    if full_brief:
        if len(value_entries) >= 1:
            return True, None
        return False, "no_distinct_grounded_followup"
    if value_entries:
        return True, None
    return False, "no_distinct_grounded_followup"


def early_scope_note_text(
    *,
    anchor_source: dict[str, Any] | None,
    blocked_article: dict[str, Any] | None,
    open_alternate: dict[str, Any] | None,
    source_metrics: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    aligned_count = int(source_metrics.get("aligned_outlet_count") or 0)
    substantive_count = int(source_metrics.get("substantive_outlet_count") or 0)
    multi_source_but_thin = aligned_count >= 2 or substantive_count >= 2

    if anchor_source:
        if open_alternate:
            return (
                (
                    f"Prism has also linked an open follow-on read from {open_alternate['outlet']}. "
                    "The source mix is still too thin to treat differences in emphasis as a meaningful split in coverage, but this early brief is meant to give readers a fuller working summary before that wider comparison arrives."
                ),
                support_payload(anchor_source, open_alternate),
            )
        if anchor_source.get("fetch_blocked"):
            if multi_source_but_thin:
                return (
                    (
                        f"Prism is grounding this early brief primarily in {anchor_source['outlet']}'s feed-level reporting because the site blocked automated full-text retrieval. "
                        "Prism has linked other related reporting, but it still needs either verified body text or a second strong event-aligned report before coverage differences become useful to compare."
                    ),
                    support_payload(anchor_source),
                )
            return (
                (
                    f"Prism is still treating this as a one-source early brief grounded primarily in {anchor_source['outlet']}'s feed-level reporting because the site blocked automated full-text retrieval. "
                    "Prism still needs either verified body text or another independent detailed report before coverage differences become useful to compare."
                ),
                support_payload(anchor_source),
            )
        if multi_source_but_thin:
            return (
                (
                    f"Prism is grounding this early brief primarily in {anchor_source['outlet']} while the other linked reports are still too thin or too contextual to support a meaningful comparison. "
                    "It should already give readers the core story and immediate stakes, but Prism still needs a second strong event-aligned report before coverage differences become useful to compare."
                ),
                support_payload(anchor_source),
            )
        return (
            (
                f"Prism is still treating this as a one-source early brief grounded primarily in {anchor_source['outlet']}'s reporting. "
                "It should already give readers the core story and immediate stakes, but Prism still needs another independent detailed report before coverage differences become useful to compare."
            ),
            support_payload(anchor_source),
        )

    if blocked_article:
        return (
            (
                f"Prism is still treating this as a one-source early brief grounded primarily in {blocked_article['outlet']}'s feed-level reporting because the site blocked automated full-text retrieval. "
                "Prism still needs either verified body text or another independent detailed report before coverage differences become useful to compare."
            ),
            [],
        )

    if open_alternate:
        return (
            (
                f"Prism has also linked an open follow-on read from {open_alternate['outlet']}. "
                "The source mix is still too thin to treat differences in emphasis as a meaningful split in coverage, but this early brief is meant to give readers a fuller working summary before that wider comparison arrives."
            ),
            [open_alternate],
        )

    return (
        (
            "Prism is still working with a thin source set here. "
            "This early brief is meant to give readers a usable first summary now, then widen into a fuller comparison once another detailed report arrives."
        ),
        support_payload(anchor_source) if anchor_source else [],
    )


def full_brief_opening(cluster: dict[str, Any], lead: dict[str, Any] | None) -> str:
    summary = ensure_period(cluster["summary"])
    if not lead:
        return summary

    lead_snippet = ensure_period(first_narrative_sentences(str(lead.get("snippet") or "").strip(), 1))
    if not lead_snippet:
        return summary

    summary_alignment = cluster_story_alignment(cluster, summary)
    lead_alignment = max(float(lead.get("story_alignment") or 0.0), cluster_story_alignment(cluster, lead_snippet))
    if (
        not summary
        or sentence_looks_non_narrative(summary)
        or text_looks_clipped(summary)
        or (
            lead_alignment >= summary_alignment + 0.08
            and sentence_similarity(summary, lead_snippet) < 0.72
            and narrative_token_overlap(summary, lead_snippet) < 0.66
        )
    ):
        return lead_snippet
    return summary


def build_grounded_brief(cluster: dict[str, Any]) -> dict[str, Any]:
    family = topic_family_for_story(cluster["topic_label"])
    all_sources = cluster_substantive_source_rows(cluster)
    sources = build_brief_sources(cluster)
    review_sources = build_review_sources(cluster)
    source_metrics = cluster_brief_source_metrics(cluster)
    visible_facts = visible_key_facts(cluster)
    ranked_sources = ranked_story_sources(all_sources)
    ranked_core_sources = ranked_story_sources(all_sources, core_only=True)
    central = ranked_core_sources[0] if ranked_core_sources else (ranked_sources[0] if ranked_sources else None)
    divergent = divergent_source(all_sources, central, family) if central else None
    comparison_anchor = best_comparison_ready_source(ranked_sources) or best_comparison_ready_source(review_sources)
    anchor_source = central or best_shell_aligned_source(review_sources) or best_story_aligned_source(review_sources)
    review_anchor = comparison_anchor or best_shell_aligned_source(review_sources) or best_story_aligned_source(review_sources)
    if review_anchor and (
        not anchor_source
        or float(review_anchor.get("priority_score") or 0.0) >= float(anchor_source.get("priority_score") or 0.0) + 0.2
    ):
        anchor_source = review_anchor
    if comparison_anchor and (not anchor_source or source_is_title_only_stub(anchor_source)):
        anchor_source = comparison_anchor
    outlet_count = len({source["outlet"] for source in ranked_sources})
    full_brief = bool(source_metrics["full_brief_ready"] and central and divergent and outlet_count >= 2)
    blocked_article = blocked_cluster_article(cluster)
    secondary_sources = [
        source
        for source in (ranked_core_sources or ranked_sources)
        if source.get("article_id") != (central or {}).get("article_id")
    ][:3]
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
        opening = full_brief_opening(cluster, central)
        baseline_extension = source_distinct_candidate_text(baseline_source, [opening]) if baseline_source else ""
        add_paragraph(
            opening,
            *(ranked_sources[:2] or ([central] if central else [])),
            role="opening",
        )
        baseline_paragraph = first_distinct_paragraph(
            [
                (
                    f"Across {outlet_text(cluster)}, the shared baseline is clear. {baseline_extension}"
                    if baseline_source and baseline_extension
                    else ""
                ),
                (
                    f"Across {outlet_text(cluster)}, the shared baseline is clear. {baseline_source['detail']}"
                    if baseline_source and baseline_source.get("detail")
                    else ""
                ),
                (
                    f"Across {outlet_text(cluster)}, the shared baseline is clear. {baseline_source['snippet']}"
                    if baseline_source
                    else opening
                ),
                f"Across {outlet_text(cluster)}, the shared baseline is clear. {central['snippet']}" if central else "",
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

        divergent_detail = source_followon_candidate_text(divergent, [entry["text"] for entry in paragraph_entries]) if divergent else ""
        difference_focus = clean_focus_phrase(str((divergent or {}).get("focus") or ""), family)
        difference_paragraph = first_distinct_paragraph(
            [
                (
                    f"The clearest difference is what comes after the initial event. {divergent['outlet']} adds this follow-on angle: {divergent_detail}"
                    if divergent and divergent_detail
                    else ""
                ),
                (
                    f"The clearest difference is what happens after the shared baseline. {divergent['outlet']} pushes further into {difference_focus}, while {(central or divergent)['outlet']} stays tighter on the immediate sequence."
                    if divergent and central and difference_focus != focus_fallback_for_family(family)
                    else ""
                ),
                "The outlets are still more aligned than divided on the event itself, with most of the variation showing up in what each one extends beyond the immediate headline.",
            ],
            [entry["text"] for entry in paragraph_entries],
        )
        if difference_paragraph:
            add_paragraph(
                difference_paragraph,
                *(support_payload(central, divergent) if central and divergent else support_payload(*(secondary_sources[:2] or ([central] if central else [])))),
                role="difference",
            )
    else:
        brief_anchor = comparison_anchor or anchor_source
        opening_sources = [brief_anchor] if brief_anchor else (ranked_sources[:2] or [])
        opening = early_brief_opening(cluster, brief_anchor)
        add_paragraph(
            opening,
            *opening_sources,
            role="opening",
            grounding_mode="required" if opening_sources else "scaffold",
        )
        detail_followups = source_story_followon_paragraphs(
            brief_anchor,
            opening=opening,
            limit=3,
        )
        for index, detail_followup in enumerate(detail_followups):
            detail_sources = support_payload(brief_anchor) if brief_anchor else []
            add_paragraph(
                detail_followup,
                *detail_sources,
                role="detail" if index == 0 else "body",
                grounding_mode="required" if detail_sources else "scaffold",
            )
        if (
            open_alternate
            and brief_anchor
            and (
                brief_anchor.get("title_like_snippet")
                or brief_anchor.get("extraction_quality") != "article_body"
            )
            and not source_is_contextual(open_alternate)
        ):
            alternate_detail = first_distinct_paragraph(
                [
                    str(open_alternate.get("snippet") or ""),
                    str(open_alternate.get("detail") or ""),
                    str(open_alternate.get("followup") or ""),
                ],
                [opening],
            )
            if alternate_detail:
                add_paragraph(
                    alternate_detail,
                    *support_payload(open_alternate),
                    role="detail",
                    grounding_mode="required",
                )

    filtered_paragraphs = [entry["text"] for entry in paragraph_entries]
    display_visible, display_hide_reason = brief_display_state(
        cluster,
        paragraph_entries,
        full_brief=full_brief,
    )
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
    why_text, why_mode = why_it_matters_copy(
        cluster,
        family,
        ([central] if central else []) + secondary_sources,
        full_brief=full_brief,
    )
    watch_text, watch_mode = watch_next_copy(cluster, family, full_brief=full_brief)
    why_support = support_payload(*(secondary_sources[:2] or ([central] if central else []))) if why_mode == "required" else []
    agree_anchor = comparison_anchor or anchor_source or central
    agree_support = (
        support_payload(central, secondary_sources[0])
        if full_brief and central and secondary_sources
        else support_payload(agree_anchor) if agree_anchor and not source_is_title_only_stub(agree_anchor) else []
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
    divergent_detail = source_followon_candidate_text(divergent, [ensure_period(str((central or {}).get("snippet") or ""))]) if divergent else ""
    difference_focus = clean_focus_phrase(str((divergent or {}).get("focus") or ""), family) if divergent else ""
    difference_reference = (
        strip_ending_punctuation(first_narrative_sentences(divergent_detail, 1))
        if divergent_detail
        else difference_focus
    )

    if full_brief:
        where_sources_agree = (
            f"Across {outlet_text(cluster)}, the shared baseline is clear: {(central or {}).get('snippet') or full_brief_opening(cluster, central)}"
        )
    elif agree_anchor and not source_is_title_only_stub(agree_anchor) and (comparison_anchor or not source_is_contextual(agree_anchor)):
        where_sources_agree = (
            f"The best-supported baseline right now comes from {(agree_anchor or {}).get('outlet') or 'the first linked report'}: "
            f"{(agree_anchor or {}).get('snippet') or ensure_period(cluster['summary'])}"
        )
    else:
        where_sources_agree = (
            "Prism is holding back from calling a shared baseline because the lead shell-aligned source is still just a live-update style headline or other thin stub. "
            "It needs a fuller event-aligned report before an outlet-to-outlet comparison is useful."
        )
        agree_mode = "scaffold"
        agree_support = []
    where_coverage_differs = (
        (
            f"The split so far is mostly about the next angle, not the underlying event. {divergent['outlet']} pushes further into {difference_reference}, while {(central or {}).get('outlet') or 'the lead outlet'} stays tighter on the immediate sequence."
            if full_brief and divergent and difference_reference and difference_reference != focus_fallback_for_family(family)
            else "The outlets are still mostly aligned on the event itself, with differences showing up mainly in what each one extends beyond the headline."
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
    snapshot_candidates = [
        source
        for source in (ranked_sources if all_sources else review_sources[:3])
        if source_is_comparison_ready(source)
        or source_is_core_story_source(source)
        or source_is_shell_aligned(source)
        or source.get("article_id") == (anchor_source or {}).get("article_id")
    ]
    if not snapshot_candidates:
        snapshot_candidates = ranked_sources[:3] if all_sources else review_sources[:3]
    for source in snapshot_candidates:
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
            "context_score": int(source.get("context_score") or 0),
            "story_aligned": source_is_story_aligned(source),
            "shell_aligned": source_is_shell_aligned(source),
            "comparison_ready": source_is_comparison_ready(source),
            "title_only_stub": source_is_title_only_stub(source),
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
            "display_visible": display_visible,
            "display_hide_reason": display_hide_reason,
            "aligned_source_count": source_metrics["aligned_outlet_count"],
            "aligned_article_body_source_count": source_metrics["aligned_article_body_outlet_count"],
            "comparison_ready_source_count": source_metrics["comparison_ready_outlet_count"],
            "title_only_shell_source_count": source_metrics["title_only_shell_outlet_count"],
            "contextual_source_count": source_metrics["contextual_outlet_count"],
            "open_source_count": source_metrics["open_outlet_count"],
            "likely_paywalled_source_count": source_metrics["likely_paywalled_outlet_count"],
            "open_alternate_available": bool(open_alternate_available),
            "support_strategy_version": "grounded_sections_v4",
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
            "generator_version": "deterministic_grounded_v3",
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
