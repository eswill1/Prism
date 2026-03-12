#!/usr/bin/env python3
from __future__ import annotations

import html
import json
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
}

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


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def tokenize(title: str) -> set[str]:
    words = re.findall(r"[A-Za-z]{3,}", title.lower())
    return {word.rstrip("s") for word in words if word not in STOPWORDS}


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


def parse_feed(feed: dict[str, str], *, enrich_articles: bool = False) -> list[FeedItem]:
    xml = fetch_text(feed["feed_url"])
    root = ET.fromstring(xml)
    namespace_map = {"media": "http://search.yahoo.com/mrss/"}

    items: list[FeedItem] = []
    for item in root.findall(".//item")[:10]:
        title = strip_html(item.findtext("title"))
        url = strip_html(item.findtext("link"))
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
            else {
                "image": None,
                "lede": clean_summary_snippet(summary, 320),
                "body_preview": "",
                "named_entities": [],
                "extraction_quality": "rss_only",
            }
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
                tokens=tokenize(title),
            )
        )

    return items


def should_join_cluster(item: FeedItem, cluster: list[FeedItem]) -> bool:
    if not item.tokens:
        return False

    def titles_match(left: set[str], right: set[str]) -> bool:
        if not left or not right:
            return False

        overlap = len(left & right)
        union = len(left | right)
        smaller = min(len(left), len(right))

        if overlap >= 4:
            return True
        if overlap >= 3 and union > 0 and overlap / union >= 0.34:
            return True
        return smaller > 0 and overlap >= 3 and overlap / smaller >= 0.6

    return any(titles_match(item.tokens, entry.tokens) for entry in cluster[:3])


def cluster_items(items: Iterable[FeedItem]) -> list[list[FeedItem]]:
    clusters: list[list[FeedItem]] = []
    for item in sorted(items, key=lambda entry: entry.published_at, reverse=True):
        target = None
        for cluster in clusters:
            if should_join_cluster(item, cluster):
                target = cluster
                break
        if target is None:
            clusters.append([item])
        else:
            target.append(item)
    return clusters


def pick_cluster_label(items: list[FeedItem]) -> str:
    tokens = Counter(token for item in items for token in item.tokens)
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
    cleaned_dek = clean_summary_snippet(lead.lede or lead.summary, 280)
    dek = cleaned_dek or (
        f"{lead.title.rstrip('?')} is drawing live coverage from {', '.join(sources)} as Prism tracks what changes next."
    )

    return {
        "slug": f"live-{index}-{slugify(lead.title)}",
        "topic_label": pick_cluster_label(ordered),
        "title": lead.title,
        "dek": dek,
        "latest_at": lead.published_at,
        "article_count": len(ordered),
        "sources": sources,
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
            for item in ordered[:5]
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
