#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceFetchStrategy:
    name: str = "http_fetch"
    source_api_fallback: str | None = None
    source_api_fallback_on_block: bool = False
    source_api_fallback_on_rss_only: bool = False
    browser_fallback: bool = False
    browser_fallback_on_block: bool = False
    browser_fallback_on_rss_only: bool = False


DEFAULT_SOURCE_FETCH_STRATEGY = SourceFetchStrategy()

DOMAIN_SOURCE_FETCH_STRATEGIES: dict[str, SourceFetchStrategy] = {
    "thehill.com": SourceFetchStrategy(
        name="http_fetch_with_source_api_and_browser_fallback",
        source_api_fallback="thehill_wp_json",
        source_api_fallback_on_block=True,
        source_api_fallback_on_rss_only=True,
        browser_fallback=True,
        browser_fallback_on_block=True,
        browser_fallback_on_rss_only=True,
    ),
}


def infer_source_domain(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlparse(raw).netloc.lower()
    return raw.removeprefix("www.")


def resolve_source_fetch_strategy(value: str | None) -> SourceFetchStrategy:
    domain = infer_source_domain(value)
    for candidate, strategy in DOMAIN_SOURCE_FETCH_STRATEGIES.items():
        if domain == candidate or domain.endswith(f".{candidate}"):
            return strategy
    return DEFAULT_SOURCE_FETCH_STRATEGY


def should_attempt_browser_fallback(strategy: SourceFetchStrategy, *, reason: str) -> bool:
    if not strategy.browser_fallback:
        return False
    if reason == "fetch_blocked":
        return strategy.browser_fallback_on_block
    if reason == "rss_only":
        return strategy.browser_fallback_on_rss_only
    return False


def should_attempt_source_api_fallback(strategy: SourceFetchStrategy, *, reason: str) -> bool:
    if not strategy.source_api_fallback:
        return False
    if reason == "fetch_blocked":
        return strategy.source_api_fallback_on_block
    if reason == "rss_only":
        return strategy.source_api_fallback_on_rss_only
    return False
