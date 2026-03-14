#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import subprocess
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
    from tooling.source_fetch_strategies import (
        SourceFetchStrategy,
        resolve_source_fetch_strategy,
        should_attempt_browser_fallback,
        should_attempt_source_api_fallback,
    )
    from tooling.url_normalization import normalize_canonical_url
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from semantic_story_candidates import build_similarity_lookup
    from source_fetch_strategies import (
        SourceFetchStrategy,
        resolve_source_fetch_strategy,
        should_attempt_browser_fallback,
        should_attempt_source_api_fallback,
    )
    from url_normalization import normalize_canonical_url

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATHS = [
    ROOT / "data" / "temporary-live-feed.json",
    ROOT / "src" / "web" / "public" / "data" / "temporary-live-feed.json",
]
BROWSER_FETCH_SCRIPT_PATH = ROOT / "tooling" / "browser_fetch_article.mjs"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
ARTICLE_ENRICHMENT_LIMIT_PER_FEED = 2
ARTICLE_ENRICHMENT_TIMEOUT_SECONDS = 6
BROWSER_FETCH_TIMEOUT_SECONDS = 15
PAYWALL_HINT_PATTERNS = (
    r"subscribe to continue",
    r"subscription required",
    r"sign in to continue",
    r"already a subscriber",
    r"this article is for subscribers",
    r"meteredcontent",
    r"gateway-content",
    r"paywall",
)
FETCH_BLOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    ("perimeterx", r"px-captcha"),
    ("perimeterx", r"_pxAppId"),
    ("perimeterx", r"captcha\.px-cloud\.net"),
    ("perimeterx", r"Access to this page has been denied"),
    ("perimeterx", r"Press\s*&\s*Hold to confirm you are"),
    ("cloudflare", r"Attention Required!"),
    ("cloudflare", r"__cf_chl"),
    ("cloudflare", r"challenge-platform"),
    ("generic", r"verify you are human"),
    ("generic", r"enable javascript and cookies to continue"),
)

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
    "country",
    "countries",
    "trump",
    "iran",
    "war",
    "attack",
    "attacks",
    "bomb",
    "bombing",
    "china",
    "drone",
    "fire",
    "fires",
    "price",
    "prices",
    "us",
    "u",
    "world",
    "news",
    "global",
}

LOW_SIGNAL_CLUSTER_TOKENS = {
    "attack",
    "attacks",
    "bomb",
    "bombing",
    "country",
    "countries",
    "drone",
    "fire",
    "fires",
    "hub",
    "hubs",
    "key",
    "keys",
    "live",
    "oil",
    "shipping",
    "story",
    "strike",
    "strikes",
    "update",
    "updates",
}
GENERIC_EVENT_TAGS = {"iran_shipping_attacks"}
LOW_SIGNAL_ENTITY_NAMES = {
    "donald trump",
    "iran",
    "israel",
    "middle east",
    "president donald trump",
    "president trump",
    "strait of hormuz",
    "tehran",
    "trump",
    "u s",
    "united states",
    "us",
}
CONTEXTUAL_CLUSTER_TOKENS = {
    "analysis",
    "context",
    "explain",
    "explainer",
    "here",
    "know",
    "latest",
    "live",
    "matter",
    "photo",
    "photos",
    "podcast",
    "question",
    "takeaway",
    "timeline",
    "update",
    "updates",
    "video",
    "watch",
    "what",
    "why",
}
CONTEXT_HEADLINE_PATTERN = re.compile(
    r"\b(?:analysis|column|explainer|fact check|five things|how to|live updates?|liveblog|minute-by-minute|opinion|photos|podcast|q&a|questions answered|takeaways?|timeline|video|what to know|what we know|why it matters)\b",
    re.IGNORECASE,
)
CONTEXT_URL_PATTERN = re.compile(
    r"/(?:analysis|explainer|fact-check|live|live-updates|opinion|photos|podcast|timeline|video)/",
    re.IGNORECASE,
)
EVENT_HEADLINE_PATTERN = re.compile(
    r"\b(?:announces?|bombs?|deploys?|fires?|grills?|halts?|launches?|moves?|orders?|rejects?|restarts?|resumes?|says?|sends?|strikes?|suspends?|threatens?|vows?|warns?)\b",
    re.IGNORECASE,
)

PHRASE_NORMALIZATIONS: list[tuple[str, str]] = [
    (r"\bstrait of hormuz\b", "straithormuz"),
    (r"\bkharg island\b", "khargisland"),
    (r"\bnuclear stockpile\b", "nuclearstockpile"),
    (r"\bmiddle east\b", "middleeast"),
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
CONTEXTUAL_SEMANTIC_JOIN_THRESHOLD = float(os.getenv("PRISM_CONTEXTUAL_JOIN_THRESHOLD", "0.66"))
LIKELY_PAYWALLED_DOMAINS = {"ft.com", "bloomberg.com", "nytimes.com", "wsj.com"}
OPEN_ACCESS_DOMAINS = {
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
}

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
    access_signal: str
    image: str | None
    tokens: set[str]
    event_tags: set[str]


def fetch_text(url: str, timeout: int = 20) -> str:
    header_profiles = (
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
        {
            "User-Agent": "PrismWirePrototype/0.1 (+local preview)",
            "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        },
    )

    last_error: Exception | None = None
    for headers in header_profiles:
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to fetch {url}")


def fetch_json(url: str, timeout: int = 20) -> object:
    header_profiles = (
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
        {
            "User-Agent": "PrismWirePrototype/0.1 (+local preview)",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        },
    )

    last_error: Exception | None = None
    for headers in header_profiles:
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to fetch JSON from {url}")


def strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


PHOTO_CREDIT_FRAGMENT_PATTERN = re.compile(
    r"(?:\|\s*[^|]{0,120}?/(?:AP|Reuters|Getty|AFP|EPA)\b|\([^)]{0,120}?(?:via AP|via Reuters|Getty Images|AP Photo|Reuters|AFP|EPA|ISNA)[^)]*\))",
    re.IGNORECASE,
)
LEADING_WIRE_CREDIT_FRAGMENT_PATTERN = re.compile(
    r"^(?:[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}/(?:AP|Reuters|Getty|AFP|EPA)\s+)+",
    re.IGNORECASE,
)
LEADING_OUTLET_CREDIT_FRAGMENT_PATTERN = re.compile(
    r"^(?:[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}\s+for\s+[A-Z][A-Za-z'’.-]+"
    r"(?:/[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,4}\s+for\s+[A-Z][A-Za-z'’.-]+)*)\s+",
    re.IGNORECASE,
)
NOTE_FRAGMENT_PATTERN = re.compile(
    r"^(?:notes?:|notice:\s*transcripts?\s+are\s+machine\s+and\s+human\s+generated|they may contain errors\.?$|data delayed at least|data shows future contract prices|chart:|graphic:|read more:)",
    re.IGNORECASE,
)
PROMO_FRAGMENT_PATTERN = re.compile(r"^(?:watch|listen|read more|see also):\s*", re.IGNORECASE)
SCRIPT_ARTIFACT_PATTERN = re.compile(
    r"(?:\bfunction\s*\(|\bvar\s+[a-z_$]+\s*=|\bwindow\.[A-Za-z_$]+|\bdocument\.[A-Za-z_$]+|\be\.exports\b|\bt\[\d+\]|\b__INITIAL_STATE__\b|Ajax/DataUrl/Excluded|NREUM|&&|\|\|)",
    re.IGNORECASE,
)
BYLINE_FRAGMENT_PATTERN = re.compile(
    r"(?:^|[\s.])-?[A-Z][A-Za-z]+ News['’]?\s+[A-Z][A-Za-z'’.-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’.-]+){0,3}",
    re.IGNORECASE,
)
TRAILING_BYLINE_FRAGMENT_PATTERN = re.compile(
    r"([.?!])\s+(?:[A-Z][A-Za-z'’.-]+(?:,\s*)?)(?:\s+(?:and\s+)?[A-Z][A-Za-z'’.-]+){0,5}$"
)
CAPTION_PARAGRAPH_PATTERN = re.compile(
    r"^(?:a man|a woman|firefighters?|people|residents|supporters|children|protesters|smoke|flames|vehicles|ships|boats)\b",
    re.IGNORECASE,
)
CAPTION_SCENE_FRAGMENT_PATTERN = re.compile(
    r"\b(?:shore|street|road|rubble|ruins|square|market|port|harbor|dock|coast|coastline|border|outside|inside|near|amid|tankers?|boats?|ships?)\b",
    re.IGNORECASE,
)
REPORTING_VERB_FRAGMENT_PATTERN = re.compile(
    r"\b(?:said|says|told|warned|announced|reported|according|officials|authorities|police)\b",
    re.IGNORECASE,
)
REPORTER_BIO_FRAGMENT_PATTERN = re.compile(
    r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2}(?:\s+and\s+[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2})?\s+have reported\b",
    re.IGNORECASE,
)
REPORTER_TRAVEL_FRAGMENT_PATTERN = re.compile(
    r"^(?:they|he|she)\s+travel(?:s)?\s+with\s+the\s+u\.s\.\s+secretary\s+of\s+state\b",
    re.IGNORECASE,
)
DATE_OR_DAY_FRAGMENT_PATTERN = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)


def sanitize_extracted_text(text: str) -> str:
    cleaned = strip_html(text)
    if not cleaned:
        return ""
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = PHOTO_CREDIT_FRAGMENT_PATTERN.sub(". ", cleaned)
        cleaned = LEADING_WIRE_CREDIT_FRAGMENT_PATTERN.sub("", cleaned)
        cleaned = LEADING_OUTLET_CREDIT_FRAGMENT_PATTERN.sub("", cleaned)
        cleaned = PROMO_FRAGMENT_PATTERN.sub("", cleaned)
        cleaned = BYLINE_FRAGMENT_PATTERN.sub(" ", cleaned)
        cleaned = TRAILING_BYLINE_FRAGMENT_PATTERN.sub(r"\1", cleaned)
    cleaned = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extracted_text_alignment_score(reference: str, candidate: str) -> float:
    reference_tokens = {
        token
        for token in re.findall(r"[a-z0-9]{4,}", sanitize_extracted_text(reference).lower().replace("u.s.", "us").replace("u.s", "us"))
        if token not in {
            "that",
            "with",
            "from",
            "this",
            "have",
            "said",
            "says",
            "into",
            "after",
            "about",
            "their",
            "they",
            "were",
            "will",
            "would",
        }
    }
    candidate_tokens = {
        token
        for token in re.findall(r"[a-z0-9]{4,}", sanitize_extracted_text(candidate).lower().replace("u.s.", "us").replace("u.s", "us"))
        if token not in {
            "that",
            "with",
            "from",
            "this",
            "have",
            "said",
            "says",
            "into",
            "after",
            "about",
            "their",
            "they",
            "were",
            "will",
            "would",
        }
    }
    if len(reference_tokens) < 4 or len(candidate_tokens) < 4:
        return 0.0
    overlap = reference_tokens & candidate_tokens
    return len(overlap) / max(1, min(len(reference_tokens), len(candidate_tokens)))


def extracted_text_looks_non_narrative(text: str) -> bool:
    normalized = sanitize_extracted_text(text)
    lowered = normalized.lower()
    if len(normalized) < 60:
        return True
    if SCRIPT_ARTIFACT_PATTERN.search(normalized):
        return True
    if NOTE_FRAGMENT_PATTERN.search(normalized):
        return True
    if PHOTO_CREDIT_FRAGMENT_PATTERN.search(text):
        return True
    if LEADING_WIRE_CREDIT_FRAGMENT_PATTERN.search(normalized) or LEADING_OUTLET_CREDIT_FRAGMENT_PATTERN.search(normalized):
        return True
    if PROMO_FRAGMENT_PATTERN.search(normalized):
        return True
    if re.match(r"^[A-Z]\.\s+[a-z]", normalized):
        return True
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", normalized):
        return True
    if REPORTER_BIO_FRAGMENT_PATTERN.search(normalized):
        return True
    if REPORTER_TRAVEL_FRAGMENT_PATTERN.search(normalized):
        return True
    if CAPTION_PARAGRAPH_PATTERN.match(normalized):
        if DATE_OR_DAY_FRAGMENT_PATTERN.search(normalized):
            return True
        if CAPTION_SCENE_FRAGMENT_PATTERN.search(normalized) and not REPORTING_VERB_FRAGMENT_PATTERN.search(normalized):
            return True
    return False


def looks_clipped(text: str) -> bool:
    trimmed = text.strip()
    if len(trimmed) < 80:
        return bool(re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", trimmed))
    if trimmed.endswith("...") or trimmed.endswith("…"):
        return True
    if trimmed.count("“") > trimmed.count("”") or trimmed.count('"') % 2 == 1:
        return True
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.$", trimmed):
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


def strong_named_entities(entities: Iterable[str]) -> set[str]:
    return {
        normalized
        for entity in entities
        if (normalized := normalize_entity(entity)) and normalized not in LOW_SIGNAL_ENTITY_NAMES
    }


def story_item_value(item: FeedItem | dict[str, object], *fields: str) -> str:
    for field in fields:
        value = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def story_item_tokens(item: FeedItem | dict[str, object]) -> set[str]:
    raw_tokens = item.get("tokens") if isinstance(item, dict) else getattr(item, "tokens", None)
    if isinstance(raw_tokens, set):
        return set(raw_tokens)
    if isinstance(raw_tokens, list):
        return {str(token) for token in raw_tokens if str(token)}
    text = " ".join(
        filter(
            None,
            [
                story_item_value(item, "title", "headline"),
                story_item_value(item, "summary", "feed_summary", "lede"),
            ],
        )
    )
    return tokenize(text)


def story_item_entities(item: FeedItem | dict[str, object]) -> set[str]:
    raw_entities = item.get("named_entities") if isinstance(item, dict) else getattr(item, "named_entities", None)
    if isinstance(raw_entities, list):
        return strong_named_entities(raw_entities)
    return set()


def story_item_event_tags(item: FeedItem | dict[str, object]) -> set[str]:
    raw_tags = item.get("event_tags") if isinstance(item, dict) else getattr(item, "event_tags", None)
    if isinstance(raw_tags, set):
        return set(raw_tags)
    if isinstance(raw_tags, list):
        return {str(tag) for tag in raw_tags if str(tag)}
    return extract_event_tags(
        story_item_value(item, "title", "headline"),
        story_item_value(item, "summary", "feed_summary", "lede"),
        story_item_value(item, "body_preview", "body_text"),
    )


def event_anchor_tokens(tokens: set[str]) -> set[str]:
    return {
        token
        for token in anchored_cluster_overlap(tokens)
        if token not in CONTEXTUAL_CLUSTER_TOKENS
    }


def story_item_context_score(item: FeedItem | dict[str, object]) -> int:
    title = normalize_whitespace(story_item_value(item, "title", "headline"))
    url = story_item_value(item, "url", "canonical_url", "original_url")
    summary = normalize_whitespace(story_item_value(item, "summary", "feed_summary", "lede"))
    extraction_quality = story_item_value(item, "extraction_quality")
    score = 0
    if CONTEXT_HEADLINE_PATTERN.search(title):
        score += 3
    if CONTEXT_URL_PATTERN.search(url):
        score += 2
    if "?" in title:
        score += 1
    if len(story_item_tokens(item) & CONTEXTUAL_CLUSTER_TOKENS) >= 2:
        score += 1
    if any(phrase in normalize_matching_text(f"{title} {summary}") for phrase in ("what to know", "what we know", "why it matters")):
        score += 1
    if EVENT_HEADLINE_PATTERN.search(title):
        score -= 1
    if extraction_quality == "article_body" and score > 0 and not CONTEXT_HEADLINE_PATTERN.search(title):
        score -= 1
    return max(score, 0)


def story_item_is_contextual(item: FeedItem | dict[str, object]) -> bool:
    return story_item_context_score(item) >= 2


def story_item_event_signal(item: FeedItem | dict[str, object]) -> int:
    title = story_item_value(item, "title", "headline")
    extraction_quality = story_item_value(item, "extraction_quality")
    score = 0
    if EVENT_HEADLINE_PATTERN.search(title):
        score += 3
    if extraction_quality == "article_body":
        score += 2
    if story_item_value(item, "access_signal") == "open":
        score += 1
    score += min(len(story_item_event_tags(item)), 2) * 2
    score += min(len(event_anchor_tokens(story_item_tokens(item))), 2)
    score += min(len(story_item_entities(item)), 2)
    score -= story_item_context_score(item) * 2
    return score


def story_item_is_event_driven(item: FeedItem | dict[str, object]) -> bool:
    return story_item_event_signal(item) >= 3


def preferred_story_items(items: list[FeedItem] | list[dict[str, object]]) -> list[FeedItem] | list[dict[str, object]]:
    event_items = [item for item in items if story_item_is_event_driven(item)]
    if event_items:
        return event_items
    reporting_items = [item for item in items if not story_item_is_contextual(item)]
    return reporting_items or items


def contextual_join_requires_stronger_match(
    item: FeedItem,
    cluster: list[FeedItem],
    *,
    event_overlap: set[str],
    entity_overlap: set[str],
    semantic_similarity: float,
) -> bool:
    cluster_contextual = [entry for entry in cluster if story_item_is_contextual(entry)]
    cluster_reporting = [entry for entry in cluster if not story_item_is_contextual(entry)]
    item_contextual = story_item_is_contextual(item)
    strong_overlap = len(event_overlap) >= 2 or len(entity_overlap) >= 2
    if item_contextual and cluster_reporting and not strong_overlap:
        return semantic_similarity < CONTEXTUAL_SEMANTIC_JOIN_THRESHOLD
    if not item_contextual and cluster_contextual and not cluster_reporting and not strong_overlap:
        return semantic_similarity < CONTEXTUAL_SEMANTIC_JOIN_THRESHOLD
    return False


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


def infer_source_domain(url: str) -> str:
    return urlparse(url).hostname.replace("www.", "").lower() if urlparse(url).hostname else ""


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
                    if cleaned and not extracted_text_looks_non_narrative(cleaned):
                        texts.append(cleaned)

            graph = current.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)

    return texts


def extract_abc_liveblog_paragraphs(markup: str) -> list[str]:
    def append_candidate(paragraphs: list[str], seen: set[str], text: str) -> bool:
        normalized = text.lower()
        if len(text) < 80 or normalized in seen or extracted_text_looks_non_narrative(text):
            return False
        seen.add(normalized)
        paragraphs.append(text)
        return len(paragraphs) >= 2

    paragraphs: list[str] = []
    seen: set[str] = set()
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

            article_type = str(current.get("@type") or "")
            if article_type == "LiveBlogPosting":
                anchor_text = " ".join(
                    str(current.get(key) or "").strip()
                    for key in ("headline", "name", "description", "alternateName")
                ).strip()
                updates = current.get("liveBlogUpdate")
                if isinstance(updates, list):
                    candidates: list[tuple[float, int, str]] = []
                    for update in updates:
                        if not isinstance(update, dict):
                            continue
                        body = update.get("articleBody")
                        if not isinstance(body, str):
                            continue
                        cleaned = sanitize_extracted_text(body)
                        if not cleaned or extracted_text_looks_non_narrative(cleaned):
                            continue
                        update_anchor = " ".join(
                            str(update.get(key) or "").strip()
                            for key in ("headline", "name", "articleSection")
                        ).strip()
                        body_score = extracted_text_alignment_score(anchor_text, cleaned) if anchor_text else 0.0
                        headline_score = extracted_text_alignment_score(anchor_text, update_anchor) if anchor_text and update_anchor else 0.0
                        score = body_score + (headline_score * 0.6)
                        candidates.append((score, len(candidates), cleaned))
                    if candidates:
                        best_score = max(score for score, _index, _text in candidates)
                        if best_score < 0.12:
                            for _score, _index, cleaned in sorted(
                                candidates,
                                key=lambda item: (item[0], -item[1]),
                                reverse=True,
                            )[:1]:
                                if append_candidate(paragraphs, seen, cleaned):
                                    return paragraphs
                            if paragraphs:
                                return paragraphs

                        threshold = max(0.12, best_score * 0.45)
                        selected_indexes = {
                            index
                            for _score, index, _cleaned in sorted(
                                candidates,
                                key=lambda item: (item[0], -item[1]),
                                reverse=True,
                            )[:2]
                            if _score >= threshold
                        }
                        for score, _index, cleaned in candidates:
                            if best_score >= 0.12 and score < threshold:
                                continue
                            if _index not in selected_indexes:
                                continue
                            if append_candidate(paragraphs, seen, cleaned):
                                return paragraphs
                        if not paragraphs:
                            for _score, _index, cleaned in candidates[:2]:
                                if append_candidate(paragraphs, seen, cleaned):
                                    return paragraphs
            body = current.get("articleBody")
            if article_type in {"BlogPosting", "LiveBlogPosting"} and isinstance(body, str):
                cleaned = sanitize_extracted_text(body)
                if append_candidate(paragraphs, seen, cleaned):
                    return paragraphs

            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)

    return paragraphs


def extract_embedded_json_text(markup: str) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()

    for key in ("articleBody", "description", "summary", "excerpt", "seoDescription", "subHeadline"):
        pattern = rf'"{key}"\s*:\s*"((?:\\.|[^"\\]){{80,4000}})"'
        for match in re.finditer(pattern, markup, re.IGNORECASE | re.DOTALL):
            raw = match.group(1)
            try:
                decoded = json.loads(f'"{raw}"')
            except json.JSONDecodeError:
                decoded = raw.encode("utf-8").decode("unicode_escape", errors="ignore")
            cleaned = sanitize_extracted_text(decoded)
            normalized = cleaned.lower()
            if len(cleaned) < 80 or normalized in seen or extracted_text_looks_non_narrative(cleaned):
                continue
            seen.add(normalized)
            texts.append(cleaned)
            if len(texts) >= 8:
                return texts

    return texts


def extract_paragraphs_from_marker_windows(markup: str, markers: tuple[str, ...]) -> list[str]:
    paragraphs: list[str] = []
    seen: set[str] = set()
    for marker in markers:
        for match in re.finditer(marker, markup, re.IGNORECASE):
            window = markup[match.start() : min(len(markup), match.start() + 18000)]
            for raw in re.findall(r"<p\b[^>]*>(.*?)</p>", window, re.IGNORECASE | re.DOTALL):
                cleaned = sanitize_extracted_text(raw)
                cleaned = re.sub(r"\s+hide caption$", "", cleaned, flags=re.IGNORECASE).strip()
                cleaned = re.sub(r"\s+toggle caption$", "", cleaned, flags=re.IGNORECASE).strip()
                normalized = cleaned.lower()
                if len(cleaned) < 60 or normalized in seen:
                    continue
                if extracted_text_looks_non_narrative(cleaned):
                    continue
                if any(
                    phrase in normalized
                    for phrase in (
                        "all rights reserved",
                        "sign up for",
                        "newsletter",
                        "click here",
                        "read more:",
                        "advertisement",
                        "hide caption",
                        "toggle caption",
                        "getty images",
                        "ap photo",
                    )
                ):
                    continue
                seen.add(normalized)
                paragraphs.append(cleaned)
                if len(paragraphs) >= 5:
                    return paragraphs
    return paragraphs


def extract_article_paragraphs(markup: str) -> list[str]:
    article_match = re.search(r"<article[^>]*>(.*?)</article>", markup, re.IGNORECASE | re.DOTALL)
    candidate_markup = article_match.group(1) if article_match else markup
    raw_paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", candidate_markup, re.IGNORECASE | re.DOTALL)

    paragraphs: list[str] = []
    seen: set[str] = set()
    for raw in raw_paragraphs:
        cleaned = sanitize_extracted_text(raw)
        cleaned = re.sub(r"\s+hide caption$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+toggle caption$", "", cleaned, flags=re.IGNORECASE).strip()
        normalized = cleaned.lower()
        if len(cleaned) < 60:
            continue
        if normalized in seen:
            continue
        if extracted_text_looks_non_narrative(cleaned):
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
                "hide caption",
                "toggle caption",
                "getty images",
                "ap photo",
            )
        ):
            continue
        seen.add(normalized)
        paragraphs.append(cleaned)
        if len(paragraphs) >= 5:
            break

    return paragraphs


def source_text_looks_boilerplate(text: str, *, url: str) -> bool:
    normalized = normalize_whitespace(text).lower()
    if not normalized:
        return False

    domain = infer_source_domain(url)
    if domain == "thehill.com" or domain.endswith(".thehill.com"):
        if re.search(r"ultimate hub for polls,\s*predictions,\s*and election results", normalized):
            return True
        if normalized == "sponsored content":
            return True
        if normalized.startswith("results forecasting polls projects sponsored content"):
            return True

    return False


def filter_source_boilerplate_texts(texts: list[str], *, url: str) -> list[str]:
    return [text for text in texts if not source_text_looks_boilerplate(text, url=url)]


def extract_source_specific_paragraphs(markup: str, url: str) -> list[str]:
    domain = infer_source_domain(url)
    if domain == "abcnews.com" or domain.endswith(".abcnews.com"):
        paragraphs = extract_abc_liveblog_paragraphs(markup)
        if paragraphs:
            return paragraphs

    marker_map: dict[str, tuple[str, ...]] = {
        "reuters.com": (
            r'data-testid=["\']paragraph',
            r'class=["\'][^"\']*(article-body|articleBody|body__content|paywall-article)[^"\']*["\']',
        ),
        "pbs.org": (
            r'itemprop=["\']articleBody["\']',
            r'class=["\'][^"\']*body-text[^"\']*["\']',
        ),
        "ft.com": (
            r'class=["\'][^"\']*(article-body|story-body|n-content-body|o-teaser__content)[^"\']*["\']',
            r'data-trackable=["\']story-body["\']',
        ),
        "bloomberg.com": (
            r'class=["\'][^"\']*(body-content|body-copy|story-body|article-body)[^"\']*["\']',
            r'data-component=["\']article-body["\']',
        ),
        "nytimes.com": (
            r'id=["\']story["\']',
            r'class=["\'][^"\']*(StoryBodyCompanionColumn|story-body|g-body|meteredContent)[^"\']*["\']',
        ),
        "wsj.com": (
            r'class=["\'][^"\']*(article-content|story-body|wsj-snippet-body)[^"\']*["\']',
        ),
    }

    for candidate_domain, markers in marker_map.items():
        if domain == candidate_domain or domain.endswith(f".{candidate_domain}"):
            paragraphs = extract_paragraphs_from_marker_windows(markup, markers)
            if paragraphs:
                return paragraphs
    return []


def detect_access_signal(markup: str, url: str) -> str:
    domain = infer_source_domain(url)
    if domain in LIKELY_PAYWALLED_DOMAINS:
        return "likely_paywalled"
    if any(re.search(pattern, markup, re.IGNORECASE) for pattern in PAYWALL_HINT_PATTERNS):
        return "likely_paywalled"
    return "open"


def infer_access_signal_from_url(url: str | None) -> str:
    domain = infer_source_domain(url or "")
    if domain in LIKELY_PAYWALLED_DOMAINS or any(domain.endswith(f".{candidate}") for candidate in LIKELY_PAYWALLED_DOMAINS):
        return "likely_paywalled"
    if domain in OPEN_ACCESS_DOMAINS or any(domain.endswith(f".{candidate}") for candidate in OPEN_ACCESS_DOMAINS):
        return "open"
    return "unknown"


def detect_fetch_block(markup: str) -> dict[str, str] | None:
    for vendor, pattern in FETCH_BLOCK_PATTERNS:
        if re.search(pattern, markup, re.IGNORECASE):
            return {
                "reason": "anti_bot_challenge",
                "vendor": vendor,
            }
    return None


def classify_fetch_block(markup: str, status_code: int | None = None) -> dict[str, str] | None:
    detected = detect_fetch_block(markup)
    if detected:
        return detected
    if status_code in (401, 403, 429):
        return {
            "reason": "http_access_denied",
            "vendor": "generic",
        }
    return None


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


def default_enrichment(summary: str = "", url: str = "", *, fetch_strategy: str = "http_fetch") -> dict[str, object]:
    return {
        "image": None,
        "lede": clean_summary_snippet(summary, 320),
        "body_preview": "",
        "named_entities": [],
        "extraction_quality": "rss_only",
        "access_signal": infer_access_signal_from_url(url),
        "fetch_blocked": False,
        "fetch_strategy": fetch_strategy,
        "browser_attempted": False,
        "browser_rendered": False,
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


def normalize_sentence_closing_punctuation(text: str) -> str:
    return re.sub(r'([.!?])\s+([)"\]\'\u2019\u201d]+)', r"\1\2", text)


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
    cleaned = normalize_whitespace(text)
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


def summary_title_alignment_score(title: str, summary: str) -> float:
    normalized_title = normalize_matching_text(title)
    normalized_summary = normalize_matching_text(summary)
    title_tokens = set(re.findall(r"[a-z0-9]{4,}", normalized_title))
    summary_tokens = set(re.findall(r"[a-z0-9]{4,}", normalized_summary))
    if not title_tokens or not summary_tokens:
        return 0.0
    overlap = title_tokens & summary_tokens
    return len(overlap) / max(1, min(len(title_tokens), len(summary_tokens)))


def first_narrative_sentences(text: str, sentence_count: int = 2) -> str:
    cleaned = split_narrative_sentences(text)
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
    best_selection_score = -999.0
    best_access_signal = "unknown"
    best_is_open = False
    best_open_summary = ""
    best_open_score = -999
    best_open_selection_score = -999.0
    best_alignment = 0.0
    best_aligned_summary = ""
    best_aligned_score = -999
    best_aligned_selection_score = -999.0
    best_aligned_alignment = 0.0
    lead_summary = ""
    lead_score = -999
    lead_selection_score = -999.0
    lead_alignment = 0.0
    substantive_sources: set[str] = set()
    normalized_title = normalize_matching_text(title)

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
        access_signal = (
            getattr(article, "access_signal", None)
            or (article.get("access_signal") if isinstance(article, dict) else None)
            or "unknown"
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
            body_excerpt = first_narrative_sentences(body_text, sentence_count=2)
            body_reference = " ".join(filter(None, [article_title, summary_candidate]))
            if (
                body_excerpt
                and not extracted_text_looks_non_narrative(body_excerpt)
                and extracted_text_alignment_score(body_reference, body_excerpt) >= 0.18
            ):
                summary_candidate = body_excerpt

        cleaned_candidate = clean_summary_snippet(summary_candidate, 320)
        score = summary_quality_score(
            article_title,
            cleaned_candidate,
            extraction_quality=extraction_quality,
            body_text=body_text,
        )
        alignment = summary_title_alignment_score(title, cleaned_candidate)
        context_penalty = story_item_context_score(article) * 4.0
        event_bonus = max(story_item_event_signal(article), 0) * 1.5
        selection_score = score + event_bonus + (alignment * 5.0) - context_penalty
        if score >= 6:
            substantive_sources.add(str(source_name))
        if cleaned_candidate and selection_score > best_selection_score:
            best_summary = cleaned_candidate
            best_score = score
            best_selection_score = selection_score
            best_access_signal = str(access_signal)
            best_is_open = str(access_signal) == "open"
            best_alignment = alignment
        if cleaned_candidate and alignment >= 0.28 and (
            alignment > best_aligned_alignment
            or (
                abs(alignment - best_aligned_alignment) < 1e-9
                and selection_score > best_aligned_selection_score
            )
        ):
            best_aligned_summary = cleaned_candidate
            best_aligned_score = score
            best_aligned_selection_score = selection_score
            best_aligned_alignment = alignment
        if cleaned_candidate and str(access_signal) == "open" and selection_score > best_open_selection_score:
            best_open_summary = cleaned_candidate
            best_open_score = score
            best_open_selection_score = selection_score
        if normalize_matching_text(article_title) == normalized_title and cleaned_candidate and selection_score > lead_selection_score:
            lead_summary = cleaned_candidate
            lead_score = score
            lead_selection_score = selection_score
            lead_alignment = alignment

    if (
        best_aligned_summary
        and best_aligned_score >= 6
        and (
            not best_summary
            or best_alignment < best_aligned_alignment - 0.12
            or best_aligned_score >= best_score - 3
        )
    ):
        return best_aligned_summary, best_aligned_score, len(substantive_sources)

    if (
        lead_summary
        and lead_score >= 6
        and lead_alignment >= 0.28
        and (
            not best_summary
            or best_alignment < lead_alignment
            or lead_score >= best_score - 2
        )
    ):
        return lead_summary, lead_score, len(substantive_sources)

    if best_is_open and best_summary and best_score >= 6:
        return best_summary, best_score, len(substantive_sources)
    if best_summary and best_score >= 6:
        if best_access_signal == "likely_paywalled" and best_open_summary and best_open_score >= max(6, best_score - 3):
            return best_open_summary, best_open_score, len(substantive_sources)
        return best_summary, best_score, len(substantive_sources)
    if best_open_summary and best_open_score >= 4:
        return best_open_summary, best_open_score, len(substantive_sources)

    fallback_sources = ", ".join(list(dict.fromkeys(sources))[:3]) if sources else "linked publishers"
    fallback = (
        f"{title.rstrip('?!.')} is drawing early coverage from {fallback_sources} as Prism waits for fuller reporting."
    )
    return fallback, max(best_score, 0), len(substantive_sources)


def build_enrichment_from_markup(
    markup: str,
    *,
    url: str,
    fallback_summary: str,
    default_payload: dict[str, object],
    browser_rendered: bool = False,
) -> dict[str, object]:
    fetch_block = classify_fetch_block(markup)
    if fetch_block:
        return {
            **default_payload,
            "fetch_blocked": True,
            "fetch_block_reason": fetch_block["reason"],
            "fetch_block_vendor": fetch_block["vendor"],
            "browser_rendered": browser_rendered,
        }

    match = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        markup,
        re.IGNORECASE,
    )
    image = html.unescape(match.group(1)) if match else None
    image = image or find_meta_content(markup, ("twitter:image",))

    meta_description = find_meta_content(markup, ("og:description", "description", "twitter:description"))
    if source_text_looks_boilerplate(meta_description, url=url):
        meta_description = ""
    domain = infer_source_domain(url)
    json_ld_text = extract_json_ld_text(markup)
    embedded_json_text = extract_embedded_json_text(markup)
    paragraphs = filter_source_boilerplate_texts(extract_article_paragraphs(markup), url=url)
    source_specific_paragraphs = filter_source_boilerplate_texts(extract_source_specific_paragraphs(markup, url), url=url)
    if source_specific_paragraphs and (domain == "abcnews.com" or domain.endswith(".abcnews.com")):
        paragraphs = source_specific_paragraphs
    elif source_specific_paragraphs and len(" ".join(source_specific_paragraphs)) > len(" ".join(paragraphs)):
        paragraphs = source_specific_paragraphs

    lede_candidates = [
        paragraphs[0] if paragraphs else "",
        meta_description,
        *(embedded_json_text[:2]),
        *(json_ld_text[:2]),
        fallback_summary,
    ]
    lede = ""
    for candidate in lede_candidates:
        lede = clean_summary_snippet(candidate, 320)
        if lede:
            break

    body_preview = ""
    if paragraphs:
        body_preview = clamp_to_word_boundary(" ".join(paragraphs[:3]), 1200)
    elif embedded_json_text:
        body_preview = clamp_to_word_boundary(" ".join(embedded_json_text[:2]), 1200)
    elif json_ld_text:
        body_preview = clamp_to_word_boundary(" ".join(json_ld_text[:2]), 1200)

    extraction_quality = "rss_only"
    if paragraphs:
        extraction_quality = "article_body"
    elif meta_description or embedded_json_text or json_ld_text:
        extraction_quality = "metadata_description"

    return {
        **default_payload,
        "image": image,
        "lede": lede,
        "body_preview": body_preview,
        "named_entities": extract_named_entities(" ".join(part for part in (lede, body_preview) if part)),
        "extraction_quality": extraction_quality,
        "access_signal": detect_access_signal(markup, url),
        "fetch_blocked": False,
        "browser_rendered": browser_rendered,
    }


def build_source_api_markup(
    *,
    title: str,
    article_html: str,
    description: str = "",
    image_url: str = "",
) -> str:
    head_parts = [f"<title>{html.escape(strip_html(title))}</title>"] if title else []
    if description:
        escaped_description = html.escape(strip_html(description), quote=True)
        head_parts.append(f'<meta property="og:description" content="{escaped_description}" />')
        head_parts.append(f'<meta name="description" content="{escaped_description}" />')
    if image_url:
        escaped_image_url = html.escape(image_url, quote=True)
        head_parts.append(f'<meta property="og:image" content="{escaped_image_url}" />')

    return f"<html><head>{''.join(head_parts)}</head><body><article>{article_html}</article></body></html>"


def infer_thehill_post_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    segment = path.split("/")[-1]
    match = re.match(r"(?P<post_id>\d+)(?:-|$)", segment)
    return match.group("post_id") if match else ""


def fetch_thehill_wp_json_markup(url: str) -> dict[str, str] | None:
    post_id = infer_thehill_post_id(url)
    if not post_id:
        return None

    endpoint = f"https://thehill.com/wp-json/wp/v2/posts/{post_id}"
    try:
        payload = fetch_json(endpoint, timeout=ARTICLE_ENRICHMENT_TIMEOUT_SECONDS)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    content = payload.get("content")
    title = payload.get("title")
    excerpt = payload.get("excerpt")
    article_html = content.get("rendered") if isinstance(content, dict) else ""
    title_text = title.get("rendered") if isinstance(title, dict) else ""
    description = excerpt.get("rendered") if isinstance(excerpt, dict) else ""
    image_url = ""

    if not isinstance(article_html, str) or not article_html.strip():
        return None

    return {
        "html": build_source_api_markup(
            title=title_text if isinstance(title_text, str) else "",
            article_html=article_html,
            description=description if isinstance(description, str) else "",
            image_url=image_url,
        ),
        "source_api": "thehill_wp_json",
        "source_api_endpoint": endpoint,
    }


def fetch_source_api_markup(url: str, strategy: SourceFetchStrategy) -> dict[str, str] | None:
    if strategy.source_api_fallback == "thehill_wp_json":
        return fetch_thehill_wp_json_markup(url)
    return None


def fetch_browser_rendered_markup(url: str) -> dict[str, object] | None:
    if not BROWSER_FETCH_SCRIPT_PATH.exists():
        return None

    try:
        completed = subprocess.run(
            ["node", str(BROWSER_FETCH_SCRIPT_PATH), url],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=BROWSER_FETCH_TIMEOUT_SECONDS + 5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("html"), str) or not payload["html"].strip():
        return None
    return payload


def fetch_article_enrichment(url: str, fallback_summary: str = "") -> dict[str, object]:
    cached = ARTICLE_FETCH_CACHE.get(url)
    if cached is not None:
        return cached

    fetch_strategy = resolve_source_fetch_strategy(url)
    default_payload = default_enrichment(
        fallback_summary,
        url,
        fetch_strategy=fetch_strategy.name,
    )

    def fallback_succeeded(payload: dict[str, object] | None) -> bool:
        return bool(
            payload
            and payload.get("fetch_blocked") is not True
            and payload.get("extraction_quality") != "rss_only"
        )

    def try_source_api_fallback(reason: str) -> dict[str, object] | None:
        if not should_attempt_source_api_fallback(fetch_strategy, reason=reason):
            return None

        source_markup = fetch_source_api_markup(url, fetch_strategy)
        if not source_markup:
            return {
                **default_payload,
                "source_api_attempted": True,
                "source_api_fallback_error": "source_api_fetch_unavailable",
            }

        source_payload = build_enrichment_from_markup(
            str(source_markup.get("html") or ""),
            url=url,
            fallback_summary=fallback_summary,
            default_payload={
                **default_payload,
                "source_api_attempted": True,
            },
        )
        if source_markup.get("source_api"):
            source_payload["source_api_used"] = source_markup["source_api"]
        if source_markup.get("source_api_endpoint"):
            source_payload["source_api_endpoint"] = source_markup["source_api_endpoint"]
        return source_payload

    def try_browser_fallback(reason: str) -> dict[str, object] | None:
        if not should_attempt_browser_fallback(fetch_strategy, reason=reason):
            return None

        browser_markup = fetch_browser_rendered_markup(url)
        if not browser_markup:
            return {
                **default_payload,
                "browser_attempted": True,
                "browser_fallback_error": "browser_fetch_unavailable",
            }

        browser_payload = build_enrichment_from_markup(
            str(browser_markup.get("html") or ""),
            url=url,
            fallback_summary=fallback_summary,
            default_payload={
                **default_payload,
                "browser_attempted": True,
            },
            browser_rendered=True,
        )
        if browser_markup.get("executablePath"):
            browser_payload["browser_executable"] = browser_markup["executablePath"]
        if browser_markup.get("finalUrl"):
            browser_payload["browser_final_url"] = browser_markup["finalUrl"]
        return browser_payload

    status_code: int | None = None
    try:
        markup = fetch_text(url, timeout=ARTICLE_ENRICHMENT_TIMEOUT_SECONDS)
    except HTTPError as exc:
        status_code = exc.code
        markup = exc.read().decode("utf-8", errors="replace")
        fetch_block = classify_fetch_block(markup, status_code=status_code)
        if fetch_block:
            source_retry = try_source_api_fallback("fetch_blocked")
            if fallback_succeeded(source_retry):
                ARTICLE_FETCH_CACHE[url] = source_retry
                return source_retry

            browser_retry = try_browser_fallback("fetch_blocked")
            if fallback_succeeded(browser_retry):
                ARTICLE_FETCH_CACHE[url] = browser_retry
                return browser_retry

            payload = {
                **default_payload,
                "fetch_blocked": True,
                "fetch_block_reason": fetch_block["reason"],
                "fetch_block_vendor": fetch_block["vendor"],
            }
            if source_retry:
                payload["source_api_attempted"] = source_retry.get("source_api_attempted", False)
                if source_retry.get("source_api_fallback_error"):
                    payload["source_api_fallback_error"] = source_retry["source_api_fallback_error"]
            if browser_retry:
                payload["browser_attempted"] = browser_retry.get("browser_attempted", False)
                if browser_retry.get("browser_fallback_error"):
                    payload["browser_fallback_error"] = browser_retry["browser_fallback_error"]
                if browser_retry.get("browser_rendered") is True:
                    payload["browser_rendered"] = True
            ARTICLE_FETCH_CACHE[url] = payload
            return payload
        ARTICLE_FETCH_CACHE[url] = default_payload
        return default_payload
    except (URLError, TimeoutError, ValueError):
        ARTICLE_FETCH_CACHE[url] = default_payload
        return default_payload

    payload = build_enrichment_from_markup(
        markup,
        url=url,
        fallback_summary=fallback_summary,
        default_payload=default_payload,
    )
    if payload.get("fetch_blocked"):
        source_retry = try_source_api_fallback("fetch_blocked")
        if fallback_succeeded(source_retry):
            ARTICLE_FETCH_CACHE[url] = source_retry
            return source_retry

        browser_retry = try_browser_fallback("fetch_blocked")
        if fallback_succeeded(browser_retry):
            ARTICLE_FETCH_CACHE[url] = browser_retry
            return browser_retry
        if source_retry:
            payload["source_api_attempted"] = source_retry.get("source_api_attempted", False)
            if source_retry.get("source_api_fallback_error"):
                payload["source_api_fallback_error"] = source_retry["source_api_fallback_error"]
        if browser_retry:
            payload["browser_attempted"] = browser_retry.get("browser_attempted", False)
            if browser_retry.get("browser_fallback_error"):
                payload["browser_fallback_error"] = browser_retry["browser_fallback_error"]
            if browser_retry.get("browser_rendered") is True:
                payload["browser_rendered"] = True
        ARTICLE_FETCH_CACHE[url] = payload
        return payload

    if payload.get("extraction_quality") == "rss_only":
        source_retry = try_source_api_fallback("rss_only")
        if fallback_succeeded(source_retry):
            ARTICLE_FETCH_CACHE[url] = source_retry
            return source_retry

        browser_retry = try_browser_fallback("rss_only")
        if fallback_succeeded(browser_retry):
            ARTICLE_FETCH_CACHE[url] = browser_retry
            return browser_retry
        if source_retry:
            payload["source_api_attempted"] = source_retry.get("source_api_attempted", False)
            if source_retry.get("source_api_fallback_error"):
                payload["source_api_fallback_error"] = source_retry["source_api_fallback_error"]
        if browser_retry:
            payload["browser_attempted"] = browser_retry.get("browser_attempted", False)
            if browser_retry.get("browser_fallback_error"):
                payload["browser_fallback_error"] = browser_retry["browser_fallback_error"]

    ARTICLE_FETCH_CACHE[url] = payload
    return payload


def parse_rss_feed(feed: dict[str, str], *, enrich_articles: bool = False, item_limit: int = 10) -> list[FeedItem]:
    xml = fetch_text(feed["feed_url"])
    root = ET.fromstring(xml)
    namespace_map = {"media": "http://search.yahoo.com/mrss/"}

    items: list[FeedItem] = []
    for item in root.findall(".//item")[:item_limit]:
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
            else default_enrichment(summary, url)
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
                access_signal=str(enrichment.get("access_signal", "unknown")),
                image=media_image or image_from_description(description_raw) or enrichment.get("image"),
                tokens=tokenize(" ".join(filter(None, [title, " ".join(list(enrichment.get("named_entities", []))[:4])]))),
                event_tags=extract_event_tags(title, summary, str(enrichment.get("lede", ""))),
            )
        )

    return items


def parse_news_sitemap(feed: dict[str, str], *, enrich_articles: bool = False, item_limit: int = SITEMAP_URL_LIMIT) -> list[FeedItem]:
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
            enrichment = fetch_article_enrichment(url, summary) if should_enrich else default_enrichment(summary, url)
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
                    access_signal=str(enrichment.get("access_signal", "unknown")),
                    image=image or enrichment.get("image"),
                    tokens=tokenize(" ".join(filter(None, [title, keyword_summary, " ".join(named_entities[:4])]))),
                    event_tags=extract_event_tags(title, keyword_summary, str(enrichment.get("lede", ""))),
                )
            )

        return items

    return parse_sitemap_url(feed["feed_url"], depth=0, remaining=item_limit)


def parse_feed(feed: dict[str, str], *, enrich_articles: bool = False, item_limit: int | None = None) -> list[FeedItem]:
    feed_type = feed.get("feed_type", "rss").lower()
    if feed_type in {"news_sitemap", "sitemap"}:
        return parse_news_sitemap(feed, enrich_articles=enrich_articles, item_limit=item_limit or SITEMAP_URL_LIMIT)
    return parse_rss_feed(feed, enrich_articles=enrich_articles, item_limit=item_limit or 10)


def anchored_cluster_overlap(tokens: set[str]) -> set[str]:
    return {token for token in tokens if token not in LOW_SIGNAL_CLUSTER_TOKENS}


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
    strong_tag_overlap = {tag for tag in tag_overlap if tag not in GENERIC_EVENT_TAGS}
    generic_tag_overlap = tag_overlap & GENERIC_EVENT_TAGS
    cluster_entities = {entity for entry in cluster for entity in strong_named_entities(entry.named_entities)}
    item_entities = strong_named_entities(item.named_entities)
    entity_overlap = item_entities & cluster_entities
    semantic_similarity = 0.0
    if similarity_lookup:
        semantic_similarity = max(similarity_lookup.get((item.url, entry.url), 0.0) for entry in cluster)

    anchored_specific_overlap = anchored_cluster_overlap(specific_overlap)
    event_overlap = event_anchor_tokens(specific_overlap)
    if generic_tag_overlap and not strong_tag_overlap and not entity_overlap and len(anchored_specific_overlap) < 2:
        return 0.0
    if contextual_join_requires_stronger_match(
        item,
        cluster,
        event_overlap=event_overlap,
        entity_overlap=entity_overlap,
        semantic_similarity=semantic_similarity,
    ):
        return 0.0
    if not tag_overlap and not entity_overlap and not anchored_specific_overlap and semantic_similarity < SEMANTIC_SIMILARITY_JOIN_THRESHOLD:
        return 0.0

    score = len(strong_tag_overlap) * 8.0
    score += len(generic_tag_overlap) * 3.0
    score += len(specific_overlap) * 2.5
    score += len(anchored_specific_overlap) * 3.0
    score += len(event_overlap) * 3.5
    score += len(overlap) * 1.25
    score += token_ratio * 4.0
    score += specific_ratio * 5.0
    score += len(entity_overlap) * 2.0
    score += semantic_similarity * 12.0

    if strong_tag_overlap and len(specific_overlap) >= 1:
        score += 3.0
    if generic_tag_overlap and len(anchored_specific_overlap) >= 2:
        score += 1.5
    if semantic_similarity >= SEMANTIC_SIMILARITY_JOIN_THRESHOLD and (strong_tag_overlap or anchored_specific_overlap or entity_overlap):
        score += 3.0
    if story_item_is_contextual(item):
        score -= 4.5
    if any(not story_item_is_contextual(entry) for entry in cluster) and story_item_is_contextual(item):
        score -= 3.5

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
    tag_overlap = item.event_tags & cluster_tags
    strong_tag_overlap = {tag for tag in tag_overlap if tag not in GENERIC_EVENT_TAGS}
    generic_tag_overlap = tag_overlap & GENERIC_EVENT_TAGS
    cluster_entities = {entity for entry in cluster for entity in strong_named_entities(entry.named_entities)}
    item_entities = strong_named_entities(item.named_entities)
    entity_overlap = item_entities & cluster_entities
    semantic_similarity = 0.0
    if similarity_lookup:
        semantic_similarity = max(similarity_lookup.get((item.url, entry.url), 0.0) for entry in cluster)

    anchored_specific_overlap = anchored_cluster_overlap(specific_overlap)
    event_overlap = event_anchor_tokens(specific_overlap)
    if generic_tag_overlap and not strong_tag_overlap and not entity_overlap and len(anchored_specific_overlap) < 2:
        return False
    if contextual_join_requires_stronger_match(
        item,
        cluster,
        event_overlap=event_overlap,
        entity_overlap=entity_overlap,
        semantic_similarity=semantic_similarity,
    ):
        return False
    if not tag_overlap and not entity_overlap and not anchored_specific_overlap:
        return semantic_similarity >= SEMANTIC_SIMILARITY_JOIN_THRESHOLD

    if semantic_similarity >= SEMANTIC_SIMILARITY_JOIN_THRESHOLD and (
        anchored_specific_overlap or entity_overlap or strong_tag_overlap
    ):
        return True
    if semantic_similarity >= SEMANTIC_SIMILARITY_SUPPORT_THRESHOLD and (
        len(anchored_specific_overlap) >= 2 or len(entity_overlap) >= 1
    ):
        return True

    if strong_tag_overlap and len(anchored_specific_overlap) >= 1:
        return True
    if generic_tag_overlap and len(anchored_specific_overlap) >= 2:
        return True
    if len(event_overlap) >= 2:
        return True
    if len(anchored_specific_overlap) >= 4:
        return True
    return len(anchored_specific_overlap) >= 3 and len(overlap) >= 4


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
    label_items = preferred_story_items(items)
    tokens = Counter(
        token for item in label_items for token in item.tokens if token not in BROAD_MATCH_TOKENS
    )
    common = [token for token, _count in tokens.most_common(3)]
    return " / ".join(token.title() for token in common) if common else "Live story"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "story"


def representative_cluster_item(items: list[FeedItem]) -> FeedItem:
    if not items:
        raise ValueError("representative_cluster_item requires at least one item")
    if len(items) == 1:
        return items[0]

    candidate_items = preferred_story_items(items)
    freshest = max(parse_datetime(item.published_at) for item in items)

    def representative_score(item: FeedItem) -> tuple[float, float]:
        content_score = summary_quality_score(
            item.title,
            item.summary,
            extraction_quality=item.extraction_quality,
            body_text=item.body_preview,
        )
        centrality = sum(cluster_match_score(item, [other]) for other in items if other.url != item.url)
        extraction_bonus = 6 if item.extraction_quality == "article_body" else 2 if item.extraction_quality == "metadata_description" else 0
        event_bonus = max(story_item_event_signal(item), 0) * 1.5
        context_penalty = story_item_context_score(item) * 6.0
        recency_penalty_hours = max(0.0, (freshest - parse_datetime(item.published_at)).total_seconds() / 3600.0)
        return (
            (content_score * 2.0) + centrality + extraction_bonus + event_bonus - context_penalty - min(recency_penalty_hours, 12.0),
            parse_datetime(item.published_at).timestamp(),
        )

    return max(candidate_items, key=representative_score)


def build_cluster_payload(
    index: int,
    items: list[FeedItem],
    *,
    allow_article_image_fetch: bool = False,
) -> dict[str, object]:
    ordered = sorted(items, key=lambda item: item.published_at, reverse=True)
    latest_item = ordered[0]
    lead = representative_cluster_item(ordered)
    hero_image = lead.image or latest_item.image or (
        fetch_article_enrichment(lead.url, lead.summary).get("image") if allow_article_image_fetch else None
    )
    sources = sorted({item.source for item in ordered})
    dek, summary_score, substantive_source_count = choose_story_summary(ordered, lead.title, sources)

    primary_articles: list[FeedItem] = []
    seen_sources: set[str] = set()
    prioritized_articles = sorted(
        ordered,
        key=lambda item: (
            0 if not story_item_is_contextual(item) else 1,
            -story_item_event_signal(item),
            -summary_quality_score(
                item.title,
                item.summary,
                extraction_quality=item.extraction_quality,
                body_text=item.body_preview,
            ),
            -parse_datetime(item.published_at).timestamp(),
        ),
    )
    for item in prioritized_articles:
        if item.source in seen_sources:
            continue
        seen_sources.add(item.source)
        primary_articles.append(item)
        if len(primary_articles) >= 5:
            break

    if len(primary_articles) < min(5, len(ordered)):
        for item in prioritized_articles:
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
        "latest_at": latest_item.published_at,
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
                "access_signal": item.access_signal,
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
