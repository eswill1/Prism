#!/usr/bin/env python3

from __future__ import annotations

import json

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient, upsert_rows


SOURCE_DEFINITIONS = [
    {
        "canonical_name": "Associated Press",
        "domain": "apnews.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "wire",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "news_sitemap",
        "poll_interval_seconds": 600,
        "notes": "AP news sitemap activated with source-specific filtering to exclude lottery, sports, and non-English items.",
        "feeds": [
            {
                "feed_type": "news_sitemap",
                "feed_url": "https://apnews.com/news-sitemap-content.xml",
                "poll_interval_seconds": 600,
            }
        ],
    },
    {
        "canonical_name": "Reuters",
        "domain": "reuters.com",
        "country_code": "GB",
        "language_code": "en",
        "outlet_type": "wire",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "news_sitemap",
        "poll_interval_seconds": 600,
        "notes": "Reuters news sitemap index activated with source-specific keyword cleanup to avoid GUID-only summaries.",
        "feeds": [
            {
                "feed_type": "news_sitemap",
                "feed_url": "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml",
                "poll_interval_seconds": 600,
            }
        ],
    },
    {
        "canonical_name": "Politico",
        "domain": "politico.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "news_sitemap",
        "poll_interval_seconds": 900,
        "notes": "Politico news sitemap activated behind strict URL filtering to avoid newsletters, blogs, and press releases.",
        "feeds": [
            {
                "feed_type": "news_sitemap",
                "feed_url": "https://www.politico.com/news-sitemap.xml",
                "poll_interval_seconds": 900,
            }
        ],
    },
    {
        "canonical_name": "Bloomberg",
        "domain": "bloomberg.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "news_sitemap",
        "poll_interval_seconds": 600,
        "notes": "Verified Bloomberg latest news sitemap used to improve business and markets overlap.",
        "feeds": [
            {
                "feed_type": "news_sitemap",
                "feed_url": "https://www.bloomberg.com/sitemaps/news/latest.xml",
                "poll_interval_seconds": 600,
            }
        ],
    },
    {
        "canonical_name": "Financial Times",
        "domain": "ft.com",
        "country_code": "GB",
        "language_code": "en",
        "outlet_type": "publication",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "sitemap",
        "poll_interval_seconds": 900,
        "notes": "Verified FT sitemap index used to widen international business and geopolitical coverage.",
        "feeds": [
            {
                "feed_type": "sitemap",
                "feed_url": "https://www.ft.com/sitemaps/index.xml",
                "poll_interval_seconds": 900,
            }
        ],
    },
    {
        "canonical_name": "NBC News",
        "domain": "nbcnews.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "General news feed used for live-story overlap in early Prism testing.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://feeds.nbcnews.com/nbcnews/public/news",
                "poll_interval_seconds": 300,
            }
        ],
    },
    {
        "canonical_name": "ABC News",
        "domain": "abcnews.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "Top stories feed used to increase multi-outlet story overlap.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://abcnews.go.com/abcnews/topstories",
                "poll_interval_seconds": 300,
            }
        ],
    },
    {
        "canonical_name": "CBS News",
        "domain": "cbsnews.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "Latest news feed used to deepen fast-moving national coverage.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://www.cbsnews.com/latest/rss/main",
                "poll_interval_seconds": 300,
            }
        ],
    },
    {
        "canonical_name": "New York Times",
        "domain": "nytimes.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "Homepage feed used to increase overlap on national and international stories.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
                "poll_interval_seconds": 300,
            }
        ],
    },
    {
        "canonical_name": "Fox News",
        "domain": "foxnews.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "broadcaster",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "Latest feed used to improve ideological spread in live comparison sets.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://moxie.foxnews.com/google-publisher/latest.xml",
                "poll_interval_seconds": 300,
            }
        ],
    },
    {
        "canonical_name": "The Hill",
        "domain": "thehill.com",
        "country_code": "US",
        "language_code": "en",
        "outlet_type": "publication",
        "launch_tier": "launch_core",
        "ingestion_status": "active",
        "preferred_discovery_method": "rss",
        "poll_interval_seconds": 300,
        "notes": "General feed activated to improve overlap on political and policy stories.",
        "feeds": [
            {
                "feed_type": "rss",
                "feed_url": "https://thehill.com/feed/",
                "poll_interval_seconds": 300,
            }
        ],
    },
]


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)

    outlet_rows = upsert_rows(
        client,
        "outlets",
        [
            {
                "canonical_name": source["canonical_name"],
                "domain": source["domain"],
                "country_code": source["country_code"],
                "language_code": source["language_code"],
                "outlet_type": source["outlet_type"],
                "status": "active",
            }
            for source in SOURCE_DEFINITIONS
        ],
        "domain",
        "id,domain,canonical_name",
    )
    outlet_ids = {row["domain"]: row["id"] for row in outlet_rows}

    registry_rows = upsert_rows(
        client,
        "source_registry",
        [
            {
                "outlet_id": outlet_ids[source["domain"]],
                "source_name": source["canonical_name"],
                "primary_domain": source["domain"],
                "launch_tier": source["launch_tier"],
                "ingestion_status": source["ingestion_status"],
                "preferred_discovery_method": source["preferred_discovery_method"],
                "poll_interval_seconds": source["poll_interval_seconds"],
                "is_active": True,
                "notes": source["notes"],
            }
            for source in SOURCE_DEFINITIONS
        ],
        "primary_domain",
        "id,primary_domain,source_name",
    )
    registry_ids = {row["primary_domain"]: row["id"] for row in registry_rows}

    upsert_rows(
        client,
        "source_policies",
        [
            {
                "source_registry_id": registry_ids[source["domain"]],
                "rights_class_default": "pointer_metadata",
                "allow_preview_image": False,
                "allow_cached_preview_image": False,
                "allow_body_parse": True,
                "robots_reviewed": False,
                "notes": "Default launch posture: pointer metadata only until rights posture is reviewed.",
            }
            for source in SOURCE_DEFINITIONS
        ],
        "source_registry_id",
        "source_registry_id",
    )

    feed_rows = []
    for source in SOURCE_DEFINITIONS:
      for feed in source["feeds"]:
        feed_rows.append(
            {
                "source_registry_id": registry_ids[source["domain"]],
                "feed_type": feed["feed_type"],
                "feed_url": feed["feed_url"],
                "poll_interval_seconds": feed["poll_interval_seconds"],
                "is_active": True,
            }
        )

    upsert_rows(
        client,
        "source_feeds",
        feed_rows,
        "source_registry_id,feed_url",
        "id,source_registry_id,feed_url",
    )

    print(
        json.dumps(
            {
                "sources_upserted": len(SOURCE_DEFINITIONS),
                "feeds_upserted": len(feed_rows),
                "domains": [source["domain"] for source in SOURCE_DEFINITIONS],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
