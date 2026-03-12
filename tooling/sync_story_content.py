#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
LIVE_FEED_PATH = ROOT / "src" / "web" / "public" / "data" / "temporary-live-feed.json"

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ENABLE_SNAPSHOT_SYNC = os.environ.get("PRISM_ENABLE_SNAPSHOT_SYNC", "").lower() == "true"

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    sys.exit("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

REST_BASE = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
NOW = datetime.now(timezone.utc)

LENS_TO_DB = {
    "Balanced Framing": "balanced_framing",
    "Evidence-First": "evidence_first",
    "Local Impact": "local_impact",
    "International Comparison": "international_comparison",
}

EVENT_TYPE_BY_KIND = {
    "summary": "summary_update",
    "coverage": "article_remap",
    "evidence": "evidence_update",
    "correction": "manual_correction",
}

FRAMING_BY_SOURCE = {
    "BBC": "center",
    "BBC News": "center",
    "NPR": "left",
    "PBS NewsHour": "center",
    "WSJ World": "right",
    "Wall Street Journal": "right",
    "Associated Press": "center",
    "Reuters": "center",
    "Bloomberg": "center",
    "The Hill": "center",
    "NBC News": "center",
    "ABC News": "center",
    "CBS News": "center",
    "New York Times": "center",
    "CNN": "center",
    "MSNBC": "left",
    "Fox News": "right",
    "Politico": "center",
    "Financial Times": "center",
}

OUTLET_CATALOG: dict[str, dict[str, str]] = {
    "npr.org": {
        "canonical_name": "NPR",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "public_media",
    },
    "bbc.com": {
        "canonical_name": "BBC News",
        "country_code": "GB",
        "language_code": "en",
        "outlet_type": "public_media",
    },
    "pbs.org": {
        "canonical_name": "PBS NewsHour",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "public_media",
    },
    "wsj.com": {
        "canonical_name": "Wall Street Journal",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "apnews.com": {
        "canonical_name": "Associated Press",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "wire",
    },
    "reuters.com": {
        "canonical_name": "Reuters",
        "country_code": "GB",
        "language_code": "en",
        "outlet_type": "wire",
    },
    "bloomberg.com": {
        "canonical_name": "Bloomberg",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "ft.com": {
        "canonical_name": "Financial Times",
        "country_code": "GB",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "politico.com": {
        "canonical_name": "Politico",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "thehill.com": {
        "canonical_name": "The Hill",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "nbcnews.com": {
        "canonical_name": "NBC News",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "abcnews.com": {
        "canonical_name": "ABC News",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "abcnews.go.com": {
        "canonical_name": "ABC News",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "cbsnews.com": {
        "canonical_name": "CBS News",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "nytimes.com": {
        "canonical_name": "New York Times",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
    },
    "cnn.com": {
        "canonical_name": "CNN",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "edition.cnn.com": {
        "canonical_name": "CNN",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "msnbc.com": {
        "canonical_name": "MSNBC",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
    "foxnews.com": {
        "canonical_name": "Fox News",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
    },
}


def minutes_ago_iso(minutes: int) -> str:
    return (NOW - timedelta(minutes=minutes)).isoformat()


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""

    domain = value.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    domain = re.sub(r"^www\.", "", domain)

    aliases = {
        "abcnews.go.com": "abcnews.com",
        "edition.cnn.com": "cnn.com",
        "rss.cnn.com": "cnn.com",
        "international.reuters.com": "reuters.com",
        "today.com": "nbcnews.com",
    }
    return aliases.get(domain, domain)


def slugify(value: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def outlet_domain(outlet: str) -> str:
    mapping = {
        "NPR": "npr.org",
        "BBC": "bbc.com",
        "BBC News": "bbc.com",
        "PBS NewsHour": "pbs.org",
        "WSJ World": "wsj.com",
        "Wall Street Journal": "wsj.com",
        "Associated Press": "apnews.com",
        "Reuters": "reuters.com",
        "Bloomberg": "bloomberg.com",
        "Financial Times": "ft.com",
        "Politico": "politico.com",
        "The Hill": "thehill.com",
        "NBC News": "nbcnews.com",
        "ABC News": "abcnews.com",
        "CBS News": "cbsnews.com",
        "New York Times": "nytimes.com",
        "CNN": "cnn.com",
        "MSNBC": "msnbc.com",
        "Fox News": "foxnews.com",
    }
    return mapping[outlet]


def outlet_label_for_domain(domain: str) -> str:
    catalog = OUTLET_CATALOG.get(domain)
    return catalog["canonical_name"] if catalog else domain


def synthetic_url(slug: str, outlet: str, title: str) -> str:
    return f"https://seed.prism.local/{slug}/{slugify(outlet)}/{slugify(title)}"


def infer_desk_label(title: str, dek: str) -> str:
    haystack = f"{title} {dek}".lower()
    section_scores = {
        "World": 0,
        "US Politics": 0,
        "Business": 0,
        "Climate and Infrastructure": 0,
        "Technology": 0,
    }

    signal_map = {
        "World": [
            (r"\b(iran|ukraine|gaza|israel|europe|european|foreign|war|missile|refugee|china|chinese|beijing)\b", 4),
            (r"\b(britain|british|uk|u\.k\.|parliament|london)\b|house of lords", 4),
            (r"\b(international|global|diplomacy)\b|strait of hormuz", 3),
        ],
        "US Politics": [
            (r"\b(congress|senate|house|election|campaign|governor|policy|lawmakers|administration)\b|white house", 4),
            (r"\b(trump|biden|federal|court|budget)\b|supreme court|title ix", 3),
        ],
        "Business": [
            (r"\b(market|markets|economy|economic|jobs|trade|business|inflation|consumer|fed)\b", 5),
            (r"\b(oil|reserve|bank|banks|prices|shipping|tariff|sanction|sanctions)\b", 4),
        ],
        "Climate and Infrastructure": [
            (r"\b(storm|grid|climate|energy|weather|wildfire|flood|hurricane|disaster)\b", 4),
            (r"\b(outage|recovery|infrastructure|utility|utilities)\b", 3),
        ],
        "Technology": [
            (r"\b(ai|technology|tech|software|platform|chip|cyber)\b|artificial intelligence", 4),
            (r"\b(regulation|antitrust|semiconductor)\b|data center", 3),
        ],
    }

    for section, patterns in signal_map.items():
        for pattern, points in patterns:
            if re.search(pattern, haystack):
                section_scores[section] += points

    best_section = max(section_scores, key=section_scores.get)
    if section_scores[best_section] == 0:
        return "General News"

    return best_section


def join_sources(values: list[str]) -> str:
    unique = list(dict.fromkeys(values))
    if len(unique) <= 2:
        return " and ".join(unique)
    return f"{', '.join(unique[:2])}, and {len(unique) - 2} more"


def framing_for_outlet(outlet: str) -> str:
    return FRAMING_BY_SOURCE.get(outlet, "center")


def build_live_context_packs(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    left = [item for item in articles if item["framing"] == "left"]
    center = [item for item in articles if item["framing"] == "center"]
    right = [item for item in articles if item["framing"] == "right"]

    balanced = []
    for bucket in (left, center, right, articles):
        for article in bucket:
            if article not in balanced:
                balanced.append(article)
            if len(balanced) >= min(3, len(articles)):
                break
        if len(balanced) >= min(3, len(articles)):
            break

    evidence_first = sorted(articles, key=lambda item: len(item["summary"]), reverse=True)[:3]
    local_impact = [
        item
        for item in articles
        if re.search(
            r"(local|state|city|school|community|jobs|families|residents|agency|operations|market)",
            f"{item['title']} {item['summary']}",
            re.I,
        )
    ] or articles[:1]
    international = [item for item in articles if item["outlet"] == "BBC News"] or articles[1:3]

    def as_context(article: dict[str, Any], why: str) -> dict[str, Any]:
        return {"outlet": article["outlet"], "title": article["title"], "why": why}

    return {
        "Balanced Framing": [
            as_context(article, "Included because it changes the reader's frame without flattening disagreement.")
            for article in balanced
        ],
        "Evidence-First": [
            as_context(article, "Selected because the reporting is dense with direct detail, named sourcing, or concrete sequence.")
            for article in evidence_first
        ],
        "Local Impact": [
            as_context(article, "Useful for understanding operational or civic consequences if the story keeps moving.")
            for article in local_impact[:2]
        ],
        "International Comparison": [
            as_context(article, "Shows how the story looks when framed outside the most immediate domestic source context.")
            for article in international[:2]
        ],
    }


def editorial_seed_stories() -> list[dict[str, Any]]:
    return [
        {
            "slug": "federal-budget-deadline",
            "topic": "US Policy",
            "title": "Federal budget talks enter a new deadline cycle",
            "dek": "Lawmakers moved toward a short-term funding patch while both parties hardened their messaging around spending cuts, border provisions, and shutdown risk.",
            "updated_at": minutes_ago_iso(12),
            "display_status": "Developing",
            "db_status": "developing",
            "hero_image": "https://picsum.photos/seed/prism-capitol/1600/900",
            "hero_alt": "Government building used as a stand-in editorial image for a budget story.",
            "hero_credit": "Prototype editorial image",
            "hero_rights_class": "first_party",
            "outlet_count": 18,
            "reliability_range": "Established to high",
            "coverage_counts": {"left": 3, "center": 4, "right": 2},
            "key_facts": [
                "Leaders are signaling support for a short-term funding extension rather than a full agreement.",
                "Border and discretionary spending caps remain the main points of dispute.",
                "Coverage diverges most on political blame and the likely economic fallout of delay.",
            ],
            "change_timeline": [
                {
                    "timestamp": minutes_ago_iso(12),
                    "kind": "summary",
                    "label": "Story summary recast around the stopgap path",
                    "detail": "Prism updated the core summary after leadership clarified that negotiators were converging on a short-term extension rather than a larger package.",
                },
                {
                    "timestamp": minutes_ago_iso(37),
                    "kind": "coverage",
                    "label": "Two additional national outlets entered the comparison set",
                    "detail": "The coverage stack widened after late-morning leadership comments pulled more process-heavy reporting into the story.",
                },
                {
                    "timestamp": minutes_ago_iso(51),
                    "kind": "correction",
                    "label": "Syndicated duplicate merged into the canonical AP item",
                    "detail": "A duplicate pickup was removed so the comparison stack reflects distinct reporting rather than repeated wire copy.",
                },
                {
                    "timestamp": minutes_ago_iso(68),
                    "kind": "evidence",
                    "label": "Committee memo added to the evidence ledger",
                    "detail": "The latest stopgap language memo now anchors the procedural claims surfaced in the story summary and article stack.",
                },
            ],
            "articles": [
                {
                    "outlet": "Associated Press",
                    "title": "Congress moves closer to short-term spending patch as deadline looms",
                    "summary": "AP frames the latest step as a tactical extension, emphasizing legislative process and immediate timing.",
                    "published_at": minutes_ago_iso(14),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/ap-capitol/640/420",
                    "reason": "Most direct process-focused reporting in the story",
                },
                {
                    "outlet": "The Hill",
                    "title": "Border fight keeps budget deal out of reach even as shutdown clock ticks",
                    "summary": "Focuses on the policy tradeoffs that continue to block a larger agreement and highlights faction pressure.",
                    "published_at": minutes_ago_iso(21),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/hill-hearing/640/420",
                    "reason": "Strong synthesis of congressional dynamics",
                },
                {
                    "outlet": "Bloomberg",
                    "title": "Stopgap momentum builds as markets look past shutdown theatrics",
                    "summary": "Frames the event through investor expectations and the practical implications of another temporary fix.",
                    "published_at": minutes_ago_iso(29),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/bloomberg-market/640/420",
                    "reason": "Best market and macroeconomic angle",
                },
                {
                    "outlet": "MSNBC",
                    "title": "Democrats argue hardline demands are driving the latest budget standoff",
                    "summary": "Emphasizes party messaging and accountability narratives more than legislative mechanics.",
                    "published_at": minutes_ago_iso(33),
                    "framing": "left",
                    "image": "https://picsum.photos/seed/msnbc-press/640/420",
                    "reason": "Useful for partisan blame framing comparison",
                },
                {
                    "outlet": "Fox News",
                    "title": "Spending fight sharpens as conservatives demand deeper cuts before deal",
                    "summary": "Centers fiscal leverage and conservative negotiating goals as the key explanatory frame.",
                    "published_at": minutes_ago_iso(41),
                    "framing": "right",
                    "image": "https://picsum.photos/seed/fox-podium/640/420",
                    "reason": "Useful for right-leaning leverage framing",
                },
                {
                    "outlet": "Reuters",
                    "title": "How international readers are seeing the U.S. budget drama",
                    "summary": "A straighter international framing on the budget deadline that minimizes party-message packaging.",
                    "published_at": minutes_ago_iso(46),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/reuters-capitol/640/420",
                    "reason": "External framing that broadens the context pack",
                    "context_only": True,
                },
            ],
            "evidence": [
                {"label": "Latest committee memo on stopgap language", "source": "House Appropriations", "type": "memo"},
                {"label": "Leadership briefing transcript", "source": "Congressional leadership press conference", "type": "transcript"},
                {"label": "Treasury warning on timing and agency operations", "source": "US Treasury", "type": "official_statement"},
            ],
            "context_packs": {
                "Balanced Framing": [
                    {"outlet": "Associated Press", "title": "Congress moves closer to short-term spending patch as deadline looms", "why": "Baseline account of the legislative move without strong blame framing."},
                    {"outlet": "MSNBC", "title": "Democrats argue hardline demands are driving the latest budget standoff", "why": "Shows how the conflict is being cast as a negotiating failure by the right."},
                    {"outlet": "Fox News", "title": "Spending fight sharpens as conservatives demand deeper cuts before deal", "why": "Shows the counter-frame that centers spending cuts and negotiation pressure."},
                ],
                "Evidence-First": [
                    {"outlet": "Associated Press", "title": "Congress moves closer to short-term spending patch as deadline looms", "why": "Highest ratio of direct sourcing to commentary."},
                    {"outlet": "The Hill", "title": "Border fight keeps budget deal out of reach even as shutdown clock ticks", "why": "Strong use of direct congressional sourcing and process detail."},
                ],
                "Local Impact": [
                    {"outlet": "Bloomberg", "title": "Stopgap momentum builds as markets look past shutdown theatrics", "why": "Best immediate explanation of downstream effects."},
                ],
                "International Comparison": [
                    {"outlet": "Reuters", "title": "How international readers are seeing the U.S. budget drama", "why": "Clean external framing with less domestic partisan packaging."},
                ],
            },
        },
        {
            "slug": "europe-tech-regulation-push",
            "topic": "Global Tech",
            "title": "European regulators tighten pressure on major AI platforms",
            "dek": "A new round of European scrutiny focused on disclosure, training-data transparency, and the pace of compliance for large model providers.",
            "updated_at": minutes_ago_iso(26),
            "display_status": "New",
            "db_status": "active",
            "hero_image": "https://picsum.photos/seed/prism-europe/1600/900",
            "hero_alt": "Conference hall image used as a stand-in editorial visual for a technology regulation story.",
            "hero_credit": "Prototype editorial image",
            "hero_rights_class": "first_party",
            "outlet_count": 11,
            "reliability_range": "Established to high",
            "coverage_counts": {"left": 2, "center": 3, "right": 1},
            "key_facts": [
                "The regulatory push centers on transparency and compliance timelines rather than an outright usage ban.",
                "Business coverage emphasizes cost and pace while policy coverage emphasizes oversight and accountability.",
                "International outlets are framing the move as a precedent-setting step for AI governance.",
            ],
            "change_timeline": [
                {
                    "timestamp": minutes_ago_iso(26),
                    "kind": "coverage",
                    "label": "Business and policy coverage converged into a single Europe-wide story",
                    "detail": "Prism merged scattered compliance reporting into one story shell once regulators, platforms, and investors were all in play.",
                },
                {
                    "timestamp": minutes_ago_iso(44),
                    "kind": "evidence",
                    "label": "Draft disclosure language added to the evidence ledger",
                    "detail": "The reader now has a direct reference point for the transparency obligations driving the latest coverage cycle.",
                },
            ],
            "articles": [
                {
                    "outlet": "Reuters",
                    "title": "EU officials press AI firms on disclosures and training data records",
                    "summary": "A straightforward regulatory framing focused on what authorities want documented and when.",
                    "published_at": minutes_ago_iso(31),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/reuters-eu-ai/640/420",
                    "reason": "Best baseline read on the regulatory move itself",
                },
                {
                    "outlet": "Financial Times",
                    "title": "European AI scrutiny shifts from headlines to compliance cost",
                    "summary": "Frames the story through corporate burden, timing, and likely implementation friction.",
                    "published_at": minutes_ago_iso(38),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/ft-ai-panel/640/420",
                    "reason": "Best business and market consequences angle",
                },
                {
                    "outlet": "Politico",
                    "title": "Brussels hardens tone as AI rulemakers test enforcement credibility",
                    "summary": "Centers political intent, regulatory signaling, and the power dynamics around compliance.",
                    "published_at": minutes_ago_iso(43),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/politico-brussels/640/420",
                    "reason": "Strong policy-process framing",
                },
                {
                    "outlet": "Bloomberg",
                    "title": "Tech giants face a tighter European timetable for AI transparency",
                    "summary": "Useful alternate read on investor expectations and the pace of operational response.",
                    "published_at": minutes_ago_iso(47),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/bloomberg-ai-eu/640/420",
                    "reason": "Helpful for fast executive and market context",
                    "context_only": True,
                },
            ],
            "evidence": [
                {"label": "Draft EU disclosure language", "source": "European Commission", "type": "document"},
                {"label": "Regulator briefing remarks", "source": "European Commission press briefing", "type": "transcript"},
                {"label": "Platform compliance response", "source": "Major AI provider statement", "type": "official_statement"},
            ],
            "context_packs": {
                "Balanced Framing": [
                    {"outlet": "Reuters", "title": "EU officials press AI firms on disclosures and training data records", "why": "Baseline reporting on the practical terms of the regulatory move."},
                    {"outlet": "Financial Times", "title": "European AI scrutiny shifts from headlines to compliance cost", "why": "Adds the business burden and implementation frame."},
                    {"outlet": "Politico", "title": "Brussels hardens tone as AI rulemakers test enforcement credibility", "why": "Adds the policy-intent frame that may not be obvious from business coverage alone."},
                ],
                "Evidence-First": [
                    {"outlet": "Reuters", "title": "EU officials press AI firms on disclosures and training data records", "why": "Most direct description of the disclosure demands."},
                ],
                "Local Impact": [
                    {"outlet": "Financial Times", "title": "European AI scrutiny shifts from headlines to compliance cost", "why": "Best explanation of who will feel the compliance pressure first."},
                ],
                "International Comparison": [
                    {"outlet": "Bloomberg", "title": "Tech giants face a tighter European timetable for AI transparency", "why": "Shows how the same regulatory story is framed through a transatlantic business lens."},
                ],
            },
        },
        {
            "slug": "storm-recovery-energy-grid",
            "topic": "Climate and Infrastructure",
            "title": "Storm recovery raises new questions about grid resilience",
            "dek": "Regional coverage is diverging between utility accountability, climate resilience planning, and immediate local recovery timelines.",
            "updated_at": minutes_ago_iso(44),
            "display_status": "Watch",
            "db_status": "watch",
            "hero_image": "https://picsum.photos/seed/prism-grid/1600/900",
            "hero_alt": "Storm recovery infrastructure image used as a stand-in editorial visual.",
            "hero_credit": "Prototype editorial image",
            "hero_rights_class": "first_party",
            "outlet_count": 9,
            "reliability_range": "Generally reliable",
            "coverage_counts": {"left": 2, "center": 2, "right": 1},
            "key_facts": [
                "Local coverage is more operational and recovery-focused than national commentary.",
                "The strongest divergence is over accountability versus infrastructure planning.",
                "Grid resilience is now being discussed as a multi-season policy problem rather than a one-storm outage story.",
            ],
            "change_timeline": [
                {
                    "timestamp": minutes_ago_iso(44),
                    "kind": "evidence",
                    "label": "Regional outage maps entered the story file",
                    "detail": "Utility and local-government operational data now support the recovery and resilience framing on the story page.",
                },
                {
                    "timestamp": minutes_ago_iso(61),
                    "kind": "coverage",
                    "label": "Regional accountability framing started to split from national policy framing",
                    "detail": "Local and national outlets are now emphasizing different questions even when citing the same outages and repair estimates.",
                },
            ],
            "articles": [
                {
                    "outlet": "Associated Press",
                    "title": "Storm recovery efforts expose new pressure points on the regional grid",
                    "summary": "A broad utility-and-governance account of what failed, what is being restored, and what comes next.",
                    "published_at": minutes_ago_iso(49),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/ap-grid/640/420",
                    "reason": "Best general recovery overview",
                },
                {
                    "outlet": "Reuters",
                    "title": "Power companies face renewed scrutiny as resilience spending comes under review",
                    "summary": "Frames the story through system fragility, investor scrutiny, and public-utility oversight.",
                    "published_at": minutes_ago_iso(57),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/reuters-grid/640/420",
                    "reason": "Useful for accountability and financial framing",
                },
                {
                    "outlet": "PBS NewsHour",
                    "title": "What prolonged outages reveal about climate resilience and local recovery capacity",
                    "summary": "Brings the story closer to households, municipalities, and public-service continuity.",
                    "published_at": minutes_ago_iso(65),
                    "framing": "center",
                    "image": "https://picsum.photos/seed/pbs-grid/640/420",
                    "reason": "Best civic-impact read",
                },
            ],
            "evidence": [
                {"label": "Regional utility outage maps", "source": "Utility dashboards", "type": "dataset"},
                {"label": "State emergency operations briefing", "source": "State emergency management office", "type": "official_statement"},
                {"label": "Grid resilience spending filing", "source": "Regional utility regulator filing", "type": "report"},
            ],
            "context_packs": {
                "Balanced Framing": [
                    {"outlet": "Associated Press", "title": "Storm recovery efforts expose new pressure points on the regional grid", "why": "Balanced operational view of the recovery and repair cycle."},
                    {"outlet": "Reuters", "title": "Power companies face renewed scrutiny as resilience spending comes under review", "why": "Adds the accountability and investment frame."},
                    {"outlet": "PBS NewsHour", "title": "What prolonged outages reveal about climate resilience and local recovery capacity", "why": "Adds the civic and household impact frame."},
                ],
                "Evidence-First": [
                    {"outlet": "Associated Press", "title": "Storm recovery efforts expose new pressure points on the regional grid", "why": "Most directly grounded in outage figures and recovery sequencing."},
                ],
                "Local Impact": [
                    {"outlet": "PBS NewsHour", "title": "What prolonged outages reveal about climate resilience and local recovery capacity", "why": "Best explanation of how local systems and residents are affected."},
                ],
                "International Comparison": [
                    {"outlet": "Reuters", "title": "Power companies face renewed scrutiny as resilience spending comes under review", "why": "The frame travels well beyond the immediate local story and helps compare utility governance approaches."},
                ],
            },
        },
    ]


def live_snapshot_stories() -> list[dict[str, Any]]:
    if not LIVE_FEED_PATH.exists():
        return []

    payload = json.loads(LIVE_FEED_PATH.read_text())
    stories = []

    for cluster in payload.get("clusters", []):
        articles = []
        unique_sources = []

        for article in cluster.get("articles", []):
            domain = normalize_domain(article.get("domain") or parse.urlparse(article.get("url", "")).netloc)
            source_name = article.get("source", outlet_label_for_domain(domain))
            display_outlet = outlet_label_for_domain(domain) if domain else source_name
            unique_sources.append(display_outlet)
            articles.append(
                {
                    "outlet": display_outlet,
                    "site_name": source_name,
                    "title": article["title"],
                    "summary": article.get("summary") or domain,
                    "feed_summary": article.get("feed_summary") or article.get("summary") or domain,
                    "body_text": article.get("body_preview") or "",
                    "named_entities": article.get("named_entities") or [],
                    "extraction_quality": article.get("extraction_quality") or "rss_only",
                    "published_at": article["published_at"],
                    "framing": framing_for_outlet(display_outlet),
                    "image": article.get("image") or cluster.get("hero_image") or f"https://picsum.photos/seed/{cluster['slug']}-article/640/420",
                    "reason": f"{display_outlet} adds a visible live reporting angle to the story stack.",
                    "url": article["url"],
                    "domain": domain,
                }
            )

        coverage_counts = {"left": 0, "center": 0, "right": 0}
        for source in dict.fromkeys(unique_sources):
            coverage_counts[framing_for_outlet(source)] += 1

        unique_sources = list(dict.fromkeys(unique_sources))
        latest_article = max(articles, key=lambda item: item["published_at"], default=None)
        timeline = [
            {
                "timestamp": cluster["latest_at"],
                "kind": "summary",
                "label": f"Story shell refreshed from {len(unique_sources)} publisher signals",
                "detail": f"Prism regenerated this live story using {cluster['article_count']} linked inputs across {join_sources(unique_sources)}.",
            }
        ]

        if latest_article:
            timeline.append(
                {
                    "timestamp": latest_article["published_at"],
                    "kind": "coverage",
                    "label": f"{latest_article['outlet']} added the latest visible turn",
                    "detail": latest_article["title"],
                }
            )

        if cluster.get("hero_image"):
            timeline.append(
                {
                    "timestamp": cluster["latest_at"],
                    "kind": "evidence",
                    "label": "Representative publisher media attached to the story shell",
                    "detail": "The current hero image comes from linked publisher metadata and is shown as a preview rather than a definitive visual claim.",
                }
            )

        stories.append(
            {
                "slug": cluster["slug"],
                "topic": infer_desk_label(cluster["title"], cluster["dek"]),
                "title": cluster["title"],
                "dek": cluster["dek"],
                "updated_at": cluster["latest_at"],
                "display_status": "Live intake",
                "db_status": "developing",
                "hero_image": cluster.get("hero_image") or f"https://picsum.photos/seed/{cluster['slug']}/1600/900",
                "hero_alt": f"{cluster['title']} preview image from linked publisher metadata.",
                "hero_credit": cluster.get("hero_credit") or "Publisher preview image",
                "hero_rights_class": "pointer_metadata",
                "outlet_count": len(unique_sources),
                "reliability_range": "Mixed source set" if len(unique_sources) >= 3 else "Early source set",
                "coverage_counts": coverage_counts,
                "key_facts": [
                    f"Prism currently sees {cluster['article_count']} linked pieces across {len(unique_sources)} publishers in this story.",
                    (
                        f"The newest linked coverage came from {latest_article['outlet']}."
                        if latest_article
                        else "The story shell is waiting for the first linked article payload."
                    ),
                    (
                        f"The comparison set is already broad enough to inspect framing differences across {join_sources(unique_sources)}."
                        if len(unique_sources) >= 2
                        else "The comparison set is still thin, so this story may move quickly as additional publishers enter the frame."
                    ),
                ],
                "change_timeline": timeline,
                "articles": articles,
                "evidence": [
                    {"label": "Primary linked reporting set", "source": join_sources(unique_sources), "type": "report"},
                    {"label": "Latest refresh in the live intake queue", "source": cluster["latest_at"], "type": "dataset"},
                    {
                        "label": "Current source breadth",
                        "source": f"{cluster['article_count']} linked articles across {len(unique_sources)} publishers",
                        "type": "report",
                    },
                ],
                "context_packs": build_live_context_packs(articles),
                "metadata": {
                    "story_origin": "live_snapshot",
                    "source_count": len(unique_sources),
                    "snapshot_generated_at": payload.get("generated_at"),
                },
            }
        )

    return stories


def ensure_context_articles(story: dict[str, Any]) -> None:
    seen = {(item["outlet"], item["title"]) for item in story["articles"]}
    for items in story["context_packs"].values():
        for item in items:
            key = (item["outlet"], item["title"])
            if key in seen:
                continue
            story["articles"].append(
                {
                    "outlet": item["outlet"],
                    "title": item["title"],
                    "summary": item["why"],
                    "published_at": story["updated_at"],
                    "framing": framing_for_outlet(item["outlet"]),
                    "image": story["hero_image"],
                    "reason": "Context-pack supporting article",
                    "context_only": True,
                }
            )
            seen.add(key)


def build_story_payloads() -> list[dict[str, Any]]:
    stories = live_snapshot_stories() if ENABLE_SNAPSHOT_SYNC else []
    for story in stories:
        story.setdefault("metadata", {})
        story["metadata"].update(
            {
                "display_status": story["display_status"],
                "story_origin": story["metadata"].get("story_origin", "live_snapshot"),
                "sync_source": "tooling/sync_story_content.py",
            }
        )
        ensure_context_articles(story)
        for article in story["articles"]:
            article.setdefault("site_name", article["outlet"])
            article.setdefault("domain", outlet_domain(article["outlet"]))
    return stories


class SupabaseRestClient:
    def __init__(self, base_url: str, service_role_key: str):
        self.base_url = base_url.rstrip("/")
        self.service_role_key = service_role_key

    def _request(self, method: str, path: str, body: Any | None = None, prefer: str | None = None) -> Any:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }

        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode()

        if prefer:
            headers["Prefer"] = prefer

        req = request.Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method.upper())
        try:
            with request.urlopen(req) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw)
        except error.HTTPError as exc:
            detail = exc.read().decode()
            raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: Any, prefer: str | None = None) -> Any:
        return self._request("POST", path, body=body, prefer=prefer)

    def patch(self, path: str, body: Any, prefer: str | None = None) -> Any:
        return self._request("PATCH", path, body=body, prefer=prefer)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


def upsert_rows(client: SupabaseRestClient, table: str, rows: list[dict[str, Any]], on_conflict: str, select: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    path = f"/{table}?on_conflict={parse.quote(on_conflict)}&select={parse.quote(select, safe=',')}"
    return client.post(path, rows, prefer="resolution=merge-duplicates,return=representation") or []


def delete_where(client: SupabaseRestClient, table: str, field: str, value: str) -> None:
    client.delete(f"/{table}?{field}=eq.{parse.quote(value)}")


def fetch_source_registry(client: SupabaseRestClient) -> dict[str, str]:
    rows = client.get("/source_registry?select=id,primary_domain&limit=500") or []
    return {normalize_domain(row["primary_domain"]): row["id"] for row in rows}


def fetch_story_cluster_count(client: SupabaseRestClient) -> int:
    rows = client.get("/story_clusters?select=id") or []
    return len(rows)


def purge_editorial_seed_content(client: SupabaseRestClient) -> int:
    cluster_rows = client.get("/story_clusters?select=id,slug,metadata&limit=500") or []
    editorial_seed_slugs = []

    for row in cluster_rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") == "editorial_seed":
            editorial_seed_slugs.append(row["slug"])
            delete_where(client, "story_clusters", "id", row["id"])

    if not editorial_seed_slugs:
        return 0

    article_rows = client.get("/articles?select=id,canonical_url,metadata&limit=2000") or []
    for row in article_rows:
        canonical_url = row.get("canonical_url") or ""
        metadata = row.get("metadata") or {}
        story_slug = metadata.get("story_slug") if isinstance(metadata, dict) else None
        if canonical_url.startswith("https://seed.prism.local/") or story_slug in editorial_seed_slugs:
            delete_where(client, "articles", "id", row["id"])

    return len(editorial_seed_slugs)


def seed_outlets(client: SupabaseRestClient, stories: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    domains = sorted({normalize_domain(article["domain"]) for story in stories for article in story["articles"]})
    rows = []
    for domain in domains:
        catalog = OUTLET_CATALOG.get(domain)
        if not catalog:
            raise RuntimeError(f"Missing outlet catalog entry for domain {domain}")
        rows.append(
            {
                "canonical_name": catalog["canonical_name"],
                "domain": domain,
                "country_code": catalog["country_code"],
                "language_code": catalog["language_code"],
                "outlet_type": catalog["outlet_type"],
                "status": "active",
            }
        )

    results = upsert_rows(client, "outlets", rows, "domain", "id,domain,canonical_name")
    return {normalize_domain(row["domain"]): row for row in results}


def article_payloads(story: dict[str, Any], outlet_rows: dict[str, dict[str, Any]], source_registry: dict[str, str]) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    rows = []
    lookup = {}
    for article in story["articles"]:
        domain = normalize_domain(article["domain"])
        outlet_row = outlet_rows[domain]
        url = article.get("url")
        canonical_url = url or synthetic_url(story["slug"], article["outlet"], article["title"])
        row = {
            "outlet_id": outlet_row["id"],
            "source_registry_id": source_registry.get(domain),
            "canonical_url": canonical_url,
            "original_url": url,
            "headline": article["title"],
            "dek": article.get("feed_summary") or article["summary"],
            "summary": article["summary"],
            "body_text": article.get("body_text") or None,
            "authors": [],
            "site_name": article["site_name"],
            "language_code": "en",
            "published_at": article["published_at"],
            "rights_class": "pointer_metadata" if url else "first_party",
            "preview_image_url": article["image"],
            "preview_image_status": "unknown" if url else "fallback_only",
            "metadata": {
                "story_slug": story["slug"],
                "context_only": bool(article.get("context_only")),
                "feed_summary": article.get("feed_summary") or article["summary"],
                "named_entities": article.get("named_entities") or [],
                "extraction_quality": article.get("extraction_quality") or "rss_only",
                "sync_source": "tooling/sync_story_content.py",
            },
        }
        rows.append(row)
        lookup[(article["outlet"], article["title"])] = row
    return rows, lookup


def to_story_cluster_row(story: dict[str, Any], hero_article_id: str | None) -> dict[str, Any]:
    return {
        "slug": story["slug"],
        "topic_label": story["topic"],
        "canonical_headline": story["title"],
        "summary": story["dek"],
        "status": story["db_status"],
        "cluster_version": "0.1.0",
        "perspective_version": "0.1.0",
        "latest_event_at": story["updated_at"],
        "hero_article_id": hero_article_id,
        "hero_media_url": story["hero_image"],
        "hero_media_alt": story["hero_alt"],
        "hero_media_credit": story["hero_credit"],
        "hero_media_rights_class": story["hero_rights_class"],
        "reliability_range": story["reliability_range"],
        "outlet_count": story["outlet_count"],
        "coverage_counts": story["coverage_counts"],
        "metadata": story["metadata"],
    }


def sync_story(client: SupabaseRestClient, story: dict[str, Any], outlet_rows: dict[str, dict[str, Any]], source_registry: dict[str, str]) -> None:
    article_rows, article_lookup = article_payloads(story, outlet_rows, source_registry)
    upserted_articles = upsert_rows(
        client,
        "articles",
        article_rows,
        "canonical_url",
        "id,canonical_url,headline,original_url",
    )
    article_id_by_url = {row["canonical_url"]: row["id"] for row in upserted_articles}
    article_id_by_key = {
        key: article_id_by_url[row["canonical_url"]]
        for key, row in article_lookup.items()
    }

    visible_articles = [article for article in story["articles"] if not article.get("context_only")]
    hero_article_id = None
    if visible_articles:
        first_article = article_lookup[(visible_articles[0]["outlet"], visible_articles[0]["title"])]
        hero_article_id = article_id_by_url[first_article["canonical_url"]]

    cluster_row = to_story_cluster_row(story, hero_article_id)
    cluster_result = upsert_rows(client, "story_clusters", [cluster_row], "slug", "id,slug")
    cluster_id = cluster_result[0]["id"]

    for table in ("cluster_articles", "cluster_key_facts", "context_pack_items", "evidence_items", "correction_events"):
        delete_where(client, table, "cluster_id", cluster_id)

    if story["key_facts"]:
        client.post(
            "/cluster_key_facts",
            [
                {"cluster_id": cluster_id, "fact_text": fact, "sort_order": index}
                for index, fact in enumerate(story["key_facts"])
            ],
            prefer="return=minimal",
        )

    if visible_articles:
        cluster_article_rows = []
        for index, article in enumerate(visible_articles, start=1):
            article_id = article_id_by_key[(article["outlet"], article["title"])]
            cluster_article_rows.append(
                {
                    "cluster_id": cluster_id,
                    "article_id": article_id,
                    "relation_type": "lead" if index == 1 else "member",
                    "rank_in_cluster": index,
                    "is_primary": index == 1,
                    "framing_group": article["framing"],
                    "selection_reason": article["reason"],
                }
            )
        client.post("/cluster_articles", cluster_article_rows, prefer="return=minimal")

    context_rows = []
    for lens, items in story["context_packs"].items():
        for index, item in enumerate(items, start=1):
            article_id = article_id_by_key.get((item["outlet"], item["title"]))
            if not article_id:
                continue
            context_rows.append(
                {
                    "cluster_id": cluster_id,
                    "lens": LENS_TO_DB[lens],
                    "article_id": article_id,
                    "rank": index,
                    "title_override": None,
                    "why_included": item["why"],
                    "reason_codes": [],
                    "rule_version": "0.1.0",
                }
            )
    if context_rows:
        client.post("/context_pack_items", context_rows, prefer="return=minimal")

    if story["evidence"]:
        client.post(
            "/evidence_items",
            [
                {
                    "cluster_id": cluster_id,
                    "label": item["label"],
                    "source_name": item["source"],
                    "source_type": item["type"],
                    "sort_order": index,
                }
                for index, item in enumerate(story["evidence"])
            ],
            prefer="return=minimal",
        )

    if story["change_timeline"]:
        client.post(
            "/correction_events",
            [
                {
                    "cluster_id": cluster_id,
                    "event_type": EVENT_TYPE_BY_KIND[item["kind"]],
                    "display_summary": item["label"],
                    "notes": item["detail"],
                    "version_before": None,
                    "version_after": "0.1.0",
                    "created_at": item["timestamp"],
                }
                for item in story["change_timeline"]
            ],
            prefer="return=minimal",
        )


def main() -> int:
    stories = build_story_payloads()
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    purged_editorial_seeds = purge_editorial_seed_content(client)
    outlet_rows = seed_outlets(client, stories)
    source_registry = fetch_source_registry(client)

    for story in stories:
        sync_story(client, story, outlet_rows, source_registry)

    print(
        json.dumps(
            {
                "editorial_seed_clusters_purged": purged_editorial_seeds,
                "snapshot_sync_enabled": ENABLE_SNAPSHOT_SYNC,
                "stories_synced": len(stories),
                "live_snapshot_stories": len([story for story in stories if story["metadata"]["story_origin"] == "live_snapshot"]),
                "story_cluster_count": fetch_story_cluster_count(client),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
