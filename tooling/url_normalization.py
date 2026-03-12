#!/usr/bin/env python3

from __future__ import annotations

import re
from urllib import parse


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""

    domain = value.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    domain = re.sub(r"^www\.", "", domain)

    aliases = {
        "abcnews.go.com": "abcnews.com",
        "amp.cnn.com": "cnn.com",
        "edition.cnn.com": "cnn.com",
        "feeds.bbci.co.uk": "bbc.com",
        "international.reuters.com": "reuters.com",
        "m.nbcnews.com": "nbcnews.com",
        "mobile.reuters.com": "reuters.com",
        "rss.cnn.com": "cnn.com",
        "today.com": "nbcnews.com",
    }
    return aliases.get(domain, domain)


def normalize_canonical_url(value: str | None) -> str:
    if not value:
        return ""

    raw = value.strip()
    if not raw:
        return ""

    if raw.startswith("//"):
        raw = f"https:{raw}"
    elif not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = f"https://{raw.lstrip('/')}"

    parsed_url = parse.urlsplit(raw)
    scheme = (parsed_url.scheme or "https").lower()
    domain = normalize_domain(parsed_url.netloc)
    path = re.sub(r"/{2,}", "/", parsed_url.path or "/")
    path = re.sub(r"/index(?:\.[a-z0-9]+)?$", "/", path, flags=re.IGNORECASE)
    if path != "/":
        path = path.rstrip("/")

    tracking_prefixes = ("utm_", "ga_", "mc_", "oly_")
    tracking_params = {
        "fbclid",
        "gclid",
        "igshid",
        "ocid",
        "cmpid",
        "cmp",
        "ref",
        "ref_src",
        "smid",
        "src",
        "sref",
        "intcmp",
        "taid",
        "mbid",
        "share",
        "output",
    }
    keep_query_pairs = []
    for key, query_value in parse.parse_qsl(parsed_url.query, keep_blank_values=False):
        lowered = key.lower()
        if lowered in tracking_params or any(lowered.startswith(prefix) for prefix in tracking_prefixes):
            continue
        if lowered.endswith("id") or lowered in {"id", "p", "story", "article", "post"}:
            keep_query_pairs.append((key, query_value))

    query = parse.urlencode(keep_query_pairs, doseq=True)
    return parse.urlunsplit((scheme, domain, path or "/", query, ""))
