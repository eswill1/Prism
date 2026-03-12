#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

try:
    from tooling.semantic_story_candidates import build_similarity_lookup
    from tooling.url_normalization import normalize_canonical_url
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from semantic_story_candidates import build_similarity_lookup
    from url_normalization import normalize_canonical_url

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATHS = [
    ROOT / "data" / "temporary-live-feed.json",
    ROOT / "src" / "web" / "public" / "data" / "temporary-live-feed.json",
]
USER_AGENT = "PrismWirePrototype/0.1 (+local preview)"
ARTICLE_ENRICHMENT_LIMIT_PER_FEED = 2
ARTICLE_ENRICHMENT_TIMEOUT_SECONDS = 6

FEEDS = [
    {"source": "NPR", "feed_url": "https://feeds.npr.org/1001/rss.xml"},
    {"source": "BBC", "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"source": "PBS NewsHour", "feed_url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
    {"source": "WSJ World", "feed_url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
]
SITEMAP_CHILD_LIMIT = 6
SITEMAP_URL_LIMIT = 20

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "to",
    "with",
    "after",
    "amid",
    "before",
    "over",
    "under",
    "new",
    "says",
    "say",
    "how",
    "why",
    "what",
    "who",
    "will",
    "into",
    "through",
    "about",
    "after",
    "amid",
    "says",
}

BROAD_MATCH_TOKENS = {
    "trump",
    "iran",
    "war",
    "china",
    "price",
    "prices",
    "us",
    "u",
    "world",
    "news",
    "global",
}

PHRASE_NORMALIZATIONS: list[tuple[str, str]] = [
    (r"\bstrategic petroleum reserve\b", "oil reserve"),
    (r"\boil reserves\b", "oil reserve"),
    (r"\bemergency oil reserves\b", "oil reserve"),
    (r"\bgas prices\b", "fuel price"),
    (r"\bnational people's congress\b", "npc"),
    (r"\bpolitical meeting\b", "npc meeting"),
    (r"\btwo sessions\b", "npc"),
    (r"\btrade wars?\b", "tariff investigation"),
]

EVENT_TAG_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("oil_reserve_release", (r"\boil\b", r"\breserves?\b", r"\b(release|tap|strategic|petroleum|barrel|fuel price)\b")),
    ("iran_war_cost", (r"\biran\b", r"\bwar\b", r"\b(cost|billion|pentagon|congress|days?)\b")),
    ("iran_shipping_attacks", (r"\biran\b", r"\b(ships?|shipping|strait of hormuz|persian gulf|hormuz)\b")),
    ("china_npc", (r"\bchina\b", r"\b(npc|national people's congress|political meeting|two sessions)\b")),
    ("trade_investigation", (r"\btrump\b", r"\b(trade|tariff)\b", r"\b(investigation|investigations)\b")),
    ("iran_school_strike", (r"\biran\b", r"\bschool\b", r"\b(strike|missile)\b")),
]

ENTITY_STOPWORDS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
}

ARTICLE_FETCH_CACHE: dict[str, dict[str, object]] = {}
SEMANTIC_SIMILARITY_JOIN_THRESHOLD = float(os.getenv("PRISM_SEMANTIC_JOIN_THRESHOLD", "0.42"))
SEMANTIC_SIMILARITY_SUPPORT_THRESHOLD = float(os.getenv("PRISM_SEMANTIC_SUPPORT_THRESHOLD", "0.32"))

SITEMAP_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "Associated Press": {
        "deny_url_patterns": (
            r"/article/(winning-numbers|lottery|hotwins|pick-\d)",
            r"/article/.*(?:nfl|nba|mlb|nhl|golf|tennis|soccer|sports?|basketball|football|baseball|hockey|champions)",
            r"/photo-gallery/",
        ),
        "deny_title_patterns": (
            r"\bwinning numbers\b",
            r"\blottery\b",
            r"\b(score|scores|beats|defeats|rallies past|career-high|tournament)\b",
            r"\b(world cup|season ends|coach|goalkeeper|odi|triplete|big ten|sec play|concacaf)\b",
        ),
    },
    "Reuters": {
        "deny_url_patterns": (
            r"/sports/",
            r"/es/",
            r"/commentary/",
        ),
        "deny_title_patterns": (
            r"\b(score|scores|beats|rallies past|career-high|tournament)\b",
        ),
    },
    "Politico": {
        "allow_url_patterns": (
            r"/news/",
            r"/story/",
        ),
        "deny_url_patterns": (
            r"/newsletters/",
            r"/blogs/",
            r"/politico-press/",
            r"/podcasts?/",
        ),
        "deny_title_patterns": (
            r"\bplaybook\b",
            r"\bpodcast\b",
        ),
    },
}


@dataclass
class FeedItem:
    source: str
    feed_url: str
    title: str
    url: str
    published_at: str
    summary: str
    feed_summary: str
    lede: str
    body_preview: str
    named_entities: list[str]
    extraction_quality: str
    image: str | None
    tokens: set[str]
    event_tags: set[str]


def fetch_text(url: str, timeout: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def looks_clipped(text: str) -> bool:
    trimmed = text.strip()
    if len(trimmed) < 80:
        return False
    if trimmed.endswith("...") or trimmed.endswith("…"):
        return True
    if not re.search(r"[.!?]$", trimmed):
        return True

    words = re.findall(r"[A-Za-z']+", trimmed)
    if len(words) < 2:
        return False

    last_word = words[-1]
    previous_word = words[-2].lower()
    if len(last_word) <= 2 and previous_word in {"a", "an", "the", "to", "of", "in", "on", "for", "with", "from", "at"}:
        return True

    return False


def clamp_to_word_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    sentence_matches = list(re.finditer(r".+?[.!?](?:\s|$)", text))
    for match in reversed(sentence_matches):
        if match.end() <= max_chars and match.end() >= int(max_chars * 0.55):
            return text[: match.end()].strip()

    truncated = text[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{truncated}..." if truncated else text[:max_chars].strip()


def clean_summary_snippet(text: str | None, max_chars: int) -> str:
    if not text:
        return ""

    trimmed = re.sub(r"\s+", " ", text).strip()
    if not trimmed:
        return ""

    clamped = clamp_to_word_boundary(trimmed, max_chars)
    if looks_clipped(clamped):
        sentence_match = re.search(r"^(.+?[.!?])(?:\s|$)", trimmed)
        if sentence_match and len(sentence_match.group(1).strip()) >= 60:
            return sentence_match.group(1).strip()
        return ""

    return clamped


def normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def tokenize(title: str) -> set[str]:
    normalized = normalize_matching_text(title)
    words = re.findall(r"[A-Za-z]{3,}", normalized.lower())
    return {stem_token(word) for word in words if stem_token(word) and stem_token(word) not in STOPWORDS}


def normalize_matching_text(text: str) -> str:
    normalized = text.lower()
    for pattern, replacement in PHRASE_NORMALIZATIONS:
        normalized = re.sub(pattern, replacement, normalized)
    normalized = normalized.replace("u.s.", "us").replace("u.s", "us")
    return normalized


def stem_token(word: str) -> str:
    token = word.lower()
    if len(token) <= 3:
        return token

    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"

    if token.endswith("ing") and len(token) > 5:
        root = token[:-3]
        if len(root) >= 2 and root[-1] == root[-2]:
            root = root[:-1]
        if root.endswith(("as", "iz", "at", "leas")):
            return f"{root}e"
        return root

    if token.endswith("ed") and len(token) > 4:
        root = token[:-2]
        if root.endswith(("as", "iz", "at", "leas")):
            return f"{root}e"
        return root

    if token.endswith("es") and len(token) > 4 and not token.endswith(("ses", "xes")):
        return token[:-2]

    if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
        return token[:-1]

    return token


def extract_event_tags(*parts: str) -> set[str]:
    haystack = normalize_matching_text(" ".join(part for part in parts if part))
    tags = set()
    for tag, patterns in EVENT_TAG_PATTERNS:
        if all(re.search(pattern, haystack) for pattern in patterns):
            tags.add(tag)
    return tags


def normalize_entity(entity: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", entity.lower()).strip()


def image_from_description(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r'<img[^>]+src="([^"]+)"', raw, re.IGNORECASE)
    return html.unescape(match.group(1)) if match else None


def find_meta_content(markup: str, field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        patterns = [
            rf'<meta[^>]+property=["\']{re.escape(field_name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(field_name)}["\']',
            rf'<meta[^>]+name=["\']{re.escape(field_name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(field_name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, markup, re.IGNORECASE)
            if match:
                return html.unescape(match.group(1)).strip()
    return ""


def extract_json_ld_text(markup: str) -> list[str]:
    texts: list[str] = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        markup,
        re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        stack: list[object] = payload if isinstance(payload, list) else [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, list):
                stack.extend(current)
                continue
            if not isinstance(current, dict):
                continue

            for key in ("description", "articleBody"):
                value = current.get(key)
                if isinstance(value, str):
                    cleaned = strip_html(value)
                    if cleaned:
                        texts.append(cleaned)

            graph = current.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)

    return texts


def extract_article_paragraphs(markup: str) -> list[str]:
    article_match = re.search(r"<article[^>]*>(.*?)</article>", markup, re.IGNORECASE | re.DOTALL)
    candidate_markup = article_match.group(1) if article_match else markup
    raw_paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", candidate_markup, re.IGNORECASE | re.DOTALL)

    paragraphs: list[str] = []
    seen: set[str] = set()
    for raw in raw_paragraphs:
        cleaned = strip_html(raw)
        normalized = cleaned.lower()
        if len(cleaned) < 60:
            continue
        if normalized in seen:
            continue
        if any(
            phrase in normalized
            for phrase in (
                "all rights reserved",
                "sign up for",
                "newsletter",
                "click here",
                "watch:",
                "read more:",
                "advertisement",
            )
        ):
            continue
        seen.add(normalized)
        paragraphs.append(cleaned)
        if len(paragraphs) >= 5:
            break

    return paragraphs


def extract_named_entities(text: str) -> list[str]:
    seen: set[str] = set()
    entities: list[str] = []
    for match in re.finditer(
        r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){0,3}\b",
        text,
    ):
        entity = match.group(0).strip()
        if entity in ENTITY_STOPWORDS or len(entity) < 4:
            continue
        if entity in seen:
            continue
        seen.add(entity)
        entities.append(entity)
        if len(entities) >= 8:
            break
    return entities


def default_enrichment(summary: str = "") -> dict[str, object]:
    return {
        "image": None,
        "lede": clean_summary_snippet(summary, 320),
        "body_preview": "",
        "named_entities": [],
        "extraction_quality": "rss_only",
    }


def derive_title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    segment = path.split("/")[-1]
    segment = re.sub(r"\.[a-z0-9]+$", "", segment, flags=re.IGNORECASE)
    segment = re.sub(r"[-_]+", " ", segment).strip()
    if not segment or len(segment) < 8:
        return ""
    words = [word for word in segment.split() if not re.fullmatch(r"\d+", word)]
    if not words:
        return ""
    return " ".join(words).strip().capitalize()


def normalize_feed_fetch_url(value: str | None) -> str:
    raw = strip_html(value)
    if not raw:
        return ""
    if raw.startswith("//"):
        return f"https:{raw}"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        return f"https://{raw.lstrip('/')}"
    return raw


def should_use_sitemap_keywords(keywords: str, title: str) -> bool:
    normalized_keywords = strip_html(keywords)
    if not normalized_keywords:
        return False
    if normalize_matching_text(normalized_keywords) == normalize_matching_text(title):
        return False
    if len(normalized_keywords) < 40:
        return False
    if any(marker in normalized_keywords.lower() for marker in ("guid:", "vguid:", "usn:", "newsml_")):
        return False
    if normalized_keywords.count(",") >= 5 and len(re.findall(r"[A-Za-z]{4,}", normalized_keywords)) <= 8:
        return False
    if re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}", normalized_keywords):
        return False
    return True


def should_keep_sitemap_item(feed: dict[str, str], url: str, title: str) -> bool:
    rules = SITEMAP_RULES.get(feed.get("source", ""))
    if not rules:
        return True

    allow_patterns = rules.get("allow_url_patterns", ())
    if allow_patterns and not any(re.search(pattern, url, re.IGNORECASE) for pattern in allow_patterns):
        return False

    deny_url_patterns = rules.get("deny_url_patterns", ())
    if any(re.search(pattern, url, re.IGNORECASE) for pattern in deny_url_patterns):
        return False

    deny_title_patterns = rules.get("deny_title_patterns", ())
    if any(re.search(pattern, title, re.IGNORECASE) for pattern in deny_title_patterns):
        return False

    return True


def summary_looks_title_like(title: str, summary: str) -> bool:
    normalized_title = normalize_matching_text(title)
    normalized_summary = normalize_matching_text(summary)
    if not normalized_summary:
        return True
    if normalized_summary == normalized_title:
        return True
    if normalized_summary in normalized_title or normalized_title in normalized_summary:
        return True

    title_tokens = set(re.findall(r"[a-z0-9]{4,}", normalized_title))
    summary_tokens = set(re.findall(r"[a-z0-9]{4,}", normalized_summary))
    if not summary_tokens:
        return True

    overlap = title_tokens & summary_tokens
    overlap_ratio = len(overlap) / max(1, len(summary_tokens))
    return overlap_ratio >= 0.85 and len(summary_tokens) <= len(title_tokens) + 2


def first_narrative_sentences(text: str, sentence_count: int = 2) -> str:
    sentences = re.findall(r"[^.!?]+[.!?]+", normalize_whitespace(text))
    cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
    if not cleaned:
        return normalize_whitespace(text)
    return " ".join(cleaned[:sentence_count]).strip()


def summary_quality_score(
    title: str,
    summary: str,
    *,
    extraction_quality: str = "rss_only",
    body_text: str = "",
) -> int:
    cleaned_summary = clean_summary_snippet(summary, 320)
    cleaned_body = normalize_whitespace(body_text)
    words = re.findall(r"[A-Za-z0-9']+", cleaned_summary)

    score = 0
    if extraction_quality == "article_body":
        score += 6
    elif extraction_quality == "metadata_description":
        score += 3

    if len(words) >= 18:
        score += 5
    elif len(words) >= 12:
        score += 3
    elif len(words) >= 8:
        score += 1
    else:
        score -= 5

    if len(cleaned_summary) >= 180:
        score += 4
    elif len(cleaned_summary) >= 110:
        score += 2
    elif len(cleaned_summary) >= 80:
        score += 1
    else:
        score -= 3

    if re.search(r"[.!?]$", cleaned_summary):
        score += 1
    if cleaned_body and len(cleaned_body) >= 240:
        score += 2
    if looks_clipped(cleaned_summary):
        score -= 4
    if summary_looks_title_like(title, cleaned_summary):
        score -= 8

    return score


def summary_is_substantive(
    title: str,
    summary: str,
    *,
    extraction_quality: str = "rss_only",
    body_text: str = "",
    minimum_score: int = 6,
) -> bool:
    return (
        summary_quality_score(
            title,
            summary,
            extraction_quality=extraction_quality,
            body_text=body_text,
        )
        >= minimum_score
    )


def choose_story_summary(
    articles: list[object],
    title: str,
    sources: list[str],
) -> tuple[str, int, int]:
    best_summary = ""
    best_score = -999
    substantive_sources: set[str] = set()

    for article in articles:
        article_title = getattr(article, "title", None) or (article.get("title") if isinstance(article, dict) else "") or title
        source_name = (
            getattr(article, "source", None)
            or (article.get("source") if isinstance(article, dict) else None)
            or (article.get("site_name") if isinstance(article, dict) else None)
            or (article.get("outlet") if isinstance(article, dict) else None)
            or article_title
        )
        extraction_quality = (
            getattr(article, "extraction_quality", None)
            or (article.get("extraction_quality") if isinstance(article, dict) else None)
            or "rss_only"
        )
        body_text = (
            getattr(article, "body_preview", None)
            or (article.get("body_preview") if isinstance(article, dict) else None)
            or (article.get("body_text") if isinstance(article, dict) else None)
            or ""
        )
        summary_candidate = (
            getattr(article, "lede", None)
            or (article.get("lede") if isinstance(article, dict) else None)
            or (article.get("summary") if isinstance(article, dict) else None)
            or (article.get("feed_summary") if isinstance(article, dict) else None)
            or getattr(article, "summary", None)
            or ""
        )
        if extraction_quality == "article_body" and body_text:
            summary_candidate = first_narrative_sentences(body_text, sentence_count=2) or summary_candidate

        cleaned_candidate = clean_summary_snippet(summary_candidate, 320)
        score = summary_quality_score(
            article_title,
            cleaned_candidate,
            extraction_quality=extraction_quality,
            body_text=body_text,
        )
        if score >= 6:
            substantive_sources.add(str(source_name))
        if cleaned_candidate and score > best_score:
            best_summary = cleaned_candidate
            best_score = score

    if best_summary and best_score >= 6:
        return best_summary, best_score, len(substantive_sources)

    fallback_sources = ", ".join(list(dict.fromkeys(sources))[:3]) if sources else "linked publishers"
    fallback = (
        f"{title.rstrip('?!.')} is drawing early coverage from {fallback_sources} as Prism waits for fuller reporting."
    )
    return fallback, max(best_score, 0), len(substantive_sources)


def fetch_article_enrichment(url: str, fallback_summary: str = "") -> dict[str, object]:
    cached = ARTICLE_FETCH_CACHE.get(url)
    if cached is not None:
        return cached

    default_payload: dict[str, object] = {
        "image": None,
        "lede": clean_summary_snippet(fallback_summary, 320),
        "body_preview": "",
        "named_entities": [],
        "extraction_quality": "rss_only",
    }

    try:
        markup = fetch_text(url, timeout=ARTICLE_ENRICHMENT_TIMEOUT_SECONDS)
    except (HTTPError, URLError, TimeoutError, ValueError):
        ARTICLE_FETCH_CACHE[url] = default_payload
        return default_payload

    match = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        markup,
        re.IGNORECASE,
    )
    image = html.unescape(match.group(1)) if match else None
    image = image or find_meta_content(markup, ("twitter:image",))

    meta_description = find_meta_content(markup, ("og:description", "description", "twitter:description"))
    json_ld_text = extract_json_ld_text(markup)
    paragraphs = extract_article_paragraphs(markup)

    lede_candidates = [paragraphs[0] if paragraphs else "", meta_description, *(json_ld_text[:2]), fallback_summary]
    lede = ""
    for candidate in lede_candidates:
        lede = clean_summary_snippet(candidate, 320)
        if lede:
            break

    body_preview = ""
    if paragraphs:
        body_preview = clamp_to_word_boundary(" ".join(paragraphs[:3]), 1200)
    elif json_ld_text:
        body_preview = clamp_to_word_boundary(" ".join(json_ld_text[:2]), 1200)

    extraction_quality = "rss_only"
    if paragraphs:
        extraction_quality = "article_body"
    elif meta_description or json_ld_text:
        extraction_quality = "metadata_description"

    payload = {
        "image": image,
        "lede": lede,
        "body_preview": body_preview,
        "named_entities": extract_named_entities(" ".join(part for part in (lede, body_preview) if part)),
        "extraction_quality": extraction_quality,
    }
    ARTICLE_FETCH_CACHE[url] = payload
    return payload


def parse_rss_feed(feed: dict[str, str], *, enrich_articles: bool = False) -> list[FeedItem]:
    xml = fetch_text(feed["feed_url"])
    root = ET.fromstring(xml)
    namespace_map = {"media": "http://search.yahoo.com/mrss/"}

    items: list[FeedItem] = []
    for item in root.findall(".//item")[:10]:
        title = strip_html(item.findtext("title"))
        url = normalize_canonical_url(strip_html(item.findtext("link")))
        if not title or not url:
            continue

        description_raw = item.findtext("description") or item.findtext(
            "{http://purl.org/rss/1.0/modules/content/}encoded"
        )
        summary = strip_html(description_raw)

        media_image = None
        media_content = item.find("media:content", namespace_map)
        media_thumbnail = item.find("media:thumbnail", namespace_map)
        enclosure = item.find("enclosure")
        if media_content is not None:
          media_image = media_content.attrib.get("url")
        elif media_thumbnail is not None:
          media_image = media_thumbnail.attrib.get("url")
        elif enclosure is not None and enclosure.attrib.get("type", "").startswith("image/"):
          media_image = enclosure.attrib.get("url")

        should_enrich = enrich_articles and len(items) < ARTICLE_ENRICHMENT_LIMIT_PER_FEED
        enrichment = (
            fetch_article_enrichment(url, summary)
            if should_enrich
            else default_enrichment(summary)
        )
        feed_summary = clean_summary_snippet(summary, 220)
        lede = clean_summary_snippet(str(enrichment.get("lede", "")) or summary, 320) or feed_summary
        body_preview = clamp_to_word_boundary(str(enrichment.get("body_preview", "")), 1200) if enrichment.get("body_preview") else ""

        items.append(
            FeedItem(
                source=feed["source"],
                feed_url=feed["feed_url"],
                title=title,
                url=url,
                published_at=parse_datetime(
                    item.findtext("pubDate") or item.findtext("published")
                ).isoformat(),
                summary=lede or feed_summary,
                feed_summary=feed_summary,
                lede=lede or feed_summary,
                body_preview=body_preview,
                named_entities=list(enrichment.get("named_entities", [])),
                extraction_quality=str(enrichment.get("extraction_quality", "rss_only")),
                image=media_image or image_from_description(description_raw) or enrichment.get("image"),
                tokens=tokenize(" ".join(filter(None, [title, " ".join(list(enrichment.get("named_entities", []))[:4])]))),
                event_tags=extract_event_tags(title, summary, str(enrichment.get("lede", ""))),
            )
        )

    return items


def parse_news_sitemap(feed: dict[str, str], *, enrich_articles: bool = False) -> list[FeedItem]:
    def parse_sitemap_url(target_url: str, *, depth: int, remaining: int) -> list[FeedItem]:
        if remaining <= 0:
            return []

        try:
            xml = fetch_text(target_url)
            root = ET.fromstring(xml)
        except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError):
            return []
        root_tag = root.tag.rsplit("}", 1)[-1].lower()

        if root_tag == "sitemapindex":
            child_urls = []
            for sitemap in root.findall(".//{*}sitemap"):
                child_url = normalize_feed_fetch_url(sitemap.findtext("{*}loc"))
                if child_url:
                    child_urls.append(child_url)
            prioritized = sorted(
                dict.fromkeys(child_urls),
                key=lambda value: (
                    0 if re.search(r"(news|latest)", value, re.IGNORECASE) else 1,
                    value,
                ),
            )
            nested_items: list[FeedItem] = []
            for child_url in prioritized[:SITEMAP_CHILD_LIMIT]:
                budget = remaining - len(nested_items)
                if budget <= 0:
                    break
                nested_items.extend(parse_sitemap_url(child_url, depth=depth + 1, remaining=budget))
            return nested_items

        if root_tag != "urlset":
            return []

        items: list[FeedItem] = []
        for url_node in root.findall(".//{*}url"):
            if len(items) >= remaining:
                break

            url = normalize_canonical_url(strip_html(url_node.findtext("{*}loc")))
            if not url:
                continue

            news_node = next((child for child in url_node if child.tag.rsplit("}", 1)[-1].lower() == "news"), None)
            title = strip_html(news_node.findtext("{*}title")) if news_node is not None else ""
            publication_date = (
                news_node.findtext("{*}publication_date") if news_node is not None else ""
            ) or url_node.findtext("{*}lastmod")
            publication_node = news_node.find("{*}publication") if news_node is not None else None
            news_language = (
                (publication_node.findtext("{*}language") if publication_node is not None else "")
                or (news_node.findtext("{*}language") if news_node is not None else "")
                or ""
            )
            keywords = strip_html(news_node.findtext("{*}keywords")) if news_node is not None else ""
            image = strip_html(url_node.findtext("{*}image/{*}loc")) or None

            if news_language and news_language.lower() not in {"en", "eng"}:
                continue

            if not title:
                title = derive_title_from_url(url)
            if not title:
                continue
            if not should_keep_sitemap_item(feed, url, title):
                continue

            keyword_summary = keywords if should_use_sitemap_keywords(keywords, title) else ""
            summary = keyword_summary or title
            should_enrich = enrich_articles and len(items) < ARTICLE_ENRICHMENT_LIMIT_PER_FEED and depth == 0
            enrichment = fetch_article_enrichment(url, summary) if should_enrich else default_enrichment(summary)
            feed_summary = clean_summary_snippet(keyword_summary or title, 220) or title
            lede = clean_summary_snippet(str(enrichment.get("lede", "")) or keyword_summary or title, 320) or feed_summary
            body_preview = clamp_to_word_boundary(str(enrichment.get("body_preview", "")), 1200) if enrichment.get("body_preview") else ""
            named_entities = list(enrichment.get("named_entities", [])) or extract_named_entities(" ".join(filter(None, [title, keywords])))

            items.append(
                FeedItem(
                    source=feed["source"],
                    feed_url=feed["feed_url"],
                    title=title,
                    url=url,
                    published_at=parse_datetime(publication_date).isoformat(),
                    summary=lede or feed_summary,
                    feed_summary=feed_summary,
                    lede=lede or feed_summary,
                    body_preview=body_preview,
                    named_entities=named_entities,
                    extraction_quality=str(enrichment.get("extraction_quality", "rss_only")),
                    image=image or enrichment.get("image"),
                    tokens=tokenize(" ".join(filter(None, [title, keyword_summary, " ".join(named_entities[:4])]))),
                    event_tags=extract_event_tags(title, keyword_summary, str(enrichment.get("lede", ""))),
                )
            )

        return items

    return parse_sitemap_url(feed["feed_url"], depth=0, remaining=SITEMAP_URL_LIMIT)


def parse_feed(feed: dict[str, str], *, enrich_articles: bool = False) -> list[FeedItem]:
    feed_type = feed.get("feed_type", "rss").lower()
    if feed_type in {"news_sitemap", "sitemap"}:
        return parse_news_sitemap(feed, enrich_articles=enrich_articles)
    return parse_rss_feed(feed, enrich_articles=enrich_articles)


def cluster_match_score(
    item: FeedItem,
    cluster: list[FeedItem],
    *,
    similarity_lookup: dict[tuple[str, str], float] | None = None,
) -> float:
    if not item.tokens:
        return 0.0

    cluster_tokens = set().union(*(entry.tokens for entry in cluster))
    cluster_tags = set().union(*(entry.event_tags for entry in cluster))
    if not cluster_tokens and not cluster_tags:
        return 0.0

    overlap = item.tokens & cluster_tokens
    if not overlap and not (item.event_tags & cluster_tags):
        return 0.0

    specific_overlap = {token for token in overlap if token not in BROAD_MATCH_TOKENS}
    union = item.tokens | cluster_tokens
    smaller = min(len(item.tokens), len(cluster_tokens)) if cluster_tokens else 0
    token_ratio = len(overlap) / len(union) if union else 0.0
    specific_ratio = len(specific_overlap) / smaller if smaller else 0.0
    tag_overlap = item.event_tags & cluster_tags
    cluster_entities = {
        normalize_entity(entity)
        for entry in cluster
        for entity in entry.named_entities
        if normalize_entity(entity)
    }
    item_entities = {normalize_entity(entity) for entity in item.named_entities if normalize_entity(entity)}
    entity_overlap = item_entities & cluster_entities
    semantic_similarity = 0.0
    if similarity_lookup:
        semantic_similarity = max(similarity_lookup.get((item.url, entry.url), 0.0) for entry in cluster)

    score = len(tag_overlap) * 8.0
    score += len(specific_overlap) * 2.5
    score += len(overlap) * 1.25
    score += token_ratio * 4.0
    score += specific_ratio * 5.0
    score += len(entity_overlap) * 2.0
    score += semantic_similarity * 12.0

    if tag_overlap and len(specific_overlap) >= 1:
        score += 3.0
    if semantic_similarity >= SEMANTIC_SIMILARITY_JOIN_THRESHOLD and (tag_overlap or specific_overlap or entity_overlap):
        score += 3.0

    return score


def should_join_cluster(
    item: FeedItem,
    cluster: list[FeedItem],
    *,
    similarity_lookup: dict[tuple[str, str], float] | None = None,
) -> bool:
    score = cluster_match_score(item, cluster, similarity_lookup=similarity_lookup)
    if score >= 12.0:
        return True

    cluster_tokens = set().union(*(entry.tokens for entry in cluster))
    cluster_tags = set().union(*(entry.event_tags for entry in cluster))
    overlap = item.tokens & cluster_tokens
    specific_overlap = {token for token in overlap if token not in BROAD_MATCH_TOKENS}
    cluster_entities = {
        normalize_entity(entity)
        for entry in cluster
        for entity in entry.named_entities
        if normalize_entity(entity)
    }
    item_entities = {normalize_entity(entity) for entity in item.named_entities if normalize_entity(entity)}
    entity_overlap = item_entities & cluster_entities
    semantic_similarity = 0.0
    if similarity_lookup:
        semantic_similarity = max(similarity_lookup.get((item.url, entry.url), 0.0) for entry in cluster)

    if semantic_similarity >= SEMANTIC_SIMILARITY_JOIN_THRESHOLD and (
        len(specific_overlap) >= 1 or entity_overlap or item.event_tags & cluster_tags
    ):
        return True
    if semantic_similarity >= SEMANTIC_SIMILARITY_SUPPORT_THRESHOLD and (
        len(specific_overlap) >= 2 or len(entity_overlap) >= 1
    ):
        return True

    if item.event_tags & cluster_tags and len(specific_overlap) >= 2:
        return True
    if len(specific_overlap) >= 4:
        return True
    return len(specific_overlap) >= 3 and len(overlap) >= 4


def cluster_items(items: Iterable[FeedItem]) -> list[list[FeedItem]]:
    ordered_items = sorted(items, key=lambda entry: entry.published_at, reverse=True)
    candidate_strategy = os.getenv("PRISM_CLUSTERING_CANDIDATE_STRATEGY", "semantic").strip().lower()
    neighbor_lookup: dict[str, list[str]] = {}
    similarity_lookup: dict[tuple[str, str], float] = {}
    if candidate_strategy == "semantic" and len(ordered_items) > 1:
        neighbor_lookup, similarity_lookup = build_similarity_lookup(ordered_items)

    clusters: list[list[FeedItem]] = []
    for item in ordered_items:
        target = None
        best_score = 0.0
        candidate_urls = set(neighbor_lookup.get(item.url, []))
        candidate_clusters = (
            [
                cluster
                for cluster in clusters
                if any(entry.url in candidate_urls for entry in cluster)
            ]
            if candidate_urls
            else clusters
        )
        for cluster in candidate_clusters or clusters:
            score = cluster_match_score(item, cluster, similarity_lookup=similarity_lookup)
            if score > best_score and should_join_cluster(item, cluster, similarity_lookup=similarity_lookup):
                target = cluster
                best_score = score
        if target is None:
            clusters.append([item])
        else:
            target.append(item)
    return clusters


def pick_cluster_label(items: list[FeedItem]) -> str:
    tokens = Counter(
        token for item in items for token in item.tokens if token not in BROAD_MATCH_TOKENS
    )
    common = [token for token, _count in tokens.most_common(3)]
    return " / ".join(token.title() for token in common) if common else "Live story"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "story"


def build_cluster_payload(
    index: int,
    items: list[FeedItem],
    *,
    allow_article_image_fetch: bool = False,
) -> dict[str, object]:
    ordered = sorted(items, key=lambda item: item.published_at, reverse=True)
    lead = ordered[0]
    hero_image = lead.image or (
        fetch_article_enrichment(lead.url, lead.summary).get("image") if allow_article_image_fetch else None
    )
    sources = sorted({item.source for item in ordered})
    dek, summary_score, substantive_source_count = choose_story_summary(ordered, lead.title, sources)

    primary_articles: list[FeedItem] = []
    seen_sources: set[str] = set()
    for item in ordered:
        if item.source in seen_sources:
            continue
        seen_sources.add(item.source)
        primary_articles.append(item)
        if len(primary_articles) >= 5:
            break

    if len(primary_articles) < min(5, len(ordered)):
        for item in ordered:
            if item in primary_articles:
                continue
            primary_articles.append(item)
            if len(primary_articles) >= 5:
                break

    return {
        "slug": f"live-{index}-{slugify(lead.title)}",
        "topic_label": pick_cluster_label(ordered),
        "title": lead.title,
        "dek": dek,
        "latest_at": lead.published_at,
        "article_count": len(ordered),
        "sources": sources,
        "summary_quality_score": summary_score,
        "substantive_source_count": substantive_source_count,
        "hero_image": hero_image,
        "hero_credit": "Publisher preview image" if hero_image else "No image available",
        "articles": [
            {
                "source": item.source,
                "title": item.title,
                "url": item.url,
                "published_at": item.published_at,
                "summary": clean_summary_snippet(item.lede or item.summary, 220)
                or f"{item.source} is covering this development from its own reporting angle.",
                "feed_summary": item.feed_summary,
                "body_preview": item.body_preview,
                "named_entities": item.named_entities,
                "extraction_quality": item.extraction_quality,
                "image": item.image,
                "domain": urlparse(item.url).netloc,
            }
            for item in primary_articles
        ],
    }


def main() -> int:
    all_items: list[FeedItem] = []
    source_errors: list[dict[str, str]] = []

    for feed in FEEDS:
        try:
            all_items.extend(parse_feed(feed, enrich_articles=True))
            time.sleep(0.25)
        except Exception as exc:  # noqa: BLE001
            source_errors.append(
                {
                    "source": feed["source"],
                    "feed_url": feed["feed_url"],
                    "error": str(exc),
                }
            )

    deduped = {item.url: item for item in all_items}
    clustered = cluster_items(deduped.values())
    ordered_clusters = sorted(
        clustered,
        key=lambda group: (len(group), max(item.published_at for item in group)),
        reverse=True,
    )[:10]

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_count": len(FEEDS),
        "article_count": len(deduped),
        "sources": FEEDS,
        "errors": source_errors,
        "clusters": [
            build_cluster_payload(index, cluster)
            for index, cluster in enumerate(ordered_clusters, start=1)
        ],
    }

    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {output_path}")

    print(f"Clusters: {len(payload['clusters'])}, articles: {payload['article_count']}")
    if source_errors:
        print(f"Feed errors: {len(source_errors)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
