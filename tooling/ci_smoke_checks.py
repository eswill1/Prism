#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any


os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

try:
    from tooling.generate_perspective_to_supabase import (
        build_perspective,
        current_revision_row_id,
        insert_perspective_revision_draft,
        promote_revision_current_state as promote_perspective_revision_current_state,
    )
    from tooling.generate_story_briefs_to_supabase import (
        build_grounded_brief,
        insert_brief_revision_draft,
        promote_revision_current_state as promote_brief_revision_current_state,
        split_narrative_sentences as split_brief_sentences,
    )
    from tooling.evaluate_brief_quality import build_quality_report, evaluate_story_quality, render_markdown_report
    from tooling.enrich_articles_to_supabase import merge_article_metadata
    from tooling.generate_temporary_live_feed import (
        FeedItem,
        build_cluster_payload,
        build_enrichment_from_markup,
        build_source_api_markup,
        classify_fetch_block,
        choose_story_summary,
        cluster_items,
        detect_fetch_block,
        infer_thehill_post_id,
        normalize_feed_fetch_url,
        representative_cluster_item,
        summary_quality_score,
    )
    from tooling.ingest_live_feeds_to_supabase import select_story_augmentation_candidates, story_query_from_cluster
    from tooling.local_ingest_runtime import build_launchd_plist, choose_due_job
    from tooling.semantic_story_candidates import build_similarity_lookup
    from tooling.source_fetch_strategies import (
        resolve_source_fetch_strategy,
        should_attempt_browser_fallback,
        should_attempt_source_api_fallback,
    )
    from tooling.url_normalization import normalize_canonical_url
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from generate_perspective_to_supabase import build_perspective, current_revision_row_id, insert_perspective_revision_draft, promote_revision_current_state as promote_perspective_revision_current_state
    from generate_story_briefs_to_supabase import build_grounded_brief, insert_brief_revision_draft, promote_revision_current_state as promote_brief_revision_current_state, split_narrative_sentences as split_brief_sentences
    from evaluate_brief_quality import build_quality_report, evaluate_story_quality, render_markdown_report
    from enrich_articles_to_supabase import merge_article_metadata
    from generate_temporary_live_feed import FeedItem, build_cluster_payload, build_enrichment_from_markup, build_source_api_markup, classify_fetch_block, choose_story_summary, cluster_items, detect_fetch_block, infer_thehill_post_id, normalize_feed_fetch_url, representative_cluster_item, summary_quality_score
    from ingest_live_feeds_to_supabase import select_story_augmentation_candidates, story_query_from_cluster
    from local_ingest_runtime import build_launchd_plist, choose_due_job
    from semantic_story_candidates import build_similarity_lookup
    from source_fetch_strategies import resolve_source_fetch_strategy, should_attempt_browser_fallback, should_attempt_source_api_fallback
    from url_normalization import normalize_canonical_url


FIXTURES_PATH = Path(__file__).with_name("clustering_regression_fixtures.json")
REPO_ROOT = Path(__file__).resolve().parent.parent
TSX_BIN = REPO_ROOT / "node_modules" / ".bin" / "tsx"


def build_item(
    *,
    source: str,
    title: str,
    url: str,
    summary: str,
    tokens: set[str],
    event_tags: set[str],
) -> FeedItem:
    return FeedItem(
        source=source,
        feed_url=f"https://example.com/{source.lower()}",
        title=title,
        url=url,
        published_at="2026-03-11T12:00:00+00:00",
        summary=summary,
        feed_summary=summary,
        lede=summary,
        body_preview="",
        named_entities=[],
        extraction_quality="rss_only",
        access_signal="open",
        image=None,
        tokens=tokens,
        event_tags=event_tags,
    )


class PromotionClient:
    def __init__(self):
        self.patches: list[tuple[str, bool]] = []

    def patch(self, path: str, body: dict[str, bool], prefer: str | None = None) -> None:  # noqa: ARG002
        self.patches.append((path, bool(body.get("is_current"))))
        if "id=eq.new-revision" in path and body.get("is_current") is True:
            raise RuntimeError("simulated promotion failure")


class ExistingPerspectiveDraftClient:
    def get(self, path: str) -> list[dict[str, str]]:
        if "input_signature=eq.signature-123" in path:
            return [{"id": "existing-perspective-draft"}]
        return []

    def post(self, path: str, body: list[dict[str, object]], prefer: str | None = None) -> None:  # noqa: ARG002
        raise AssertionError(f"unexpected draft insert call for {path} with {body}")


class ExistingBriefDraftClient:
    def get(self, path: str) -> list[dict[str, str]]:
        if "input_signature=eq.brief-signature-123" in path:
            return [{"id": "existing-brief-draft"}]
        return []

    def post(self, path: str, body: list[dict[str, object]], prefer: str | None = None) -> None:  # noqa: ARG002
        raise AssertionError(f"unexpected brief draft insert call for {path} with {body}")


def quality_article(
    *,
    article_id: str,
    outlet: str,
    headline: str,
    summary: str,
    body_text: str,
) -> dict[str, Any]:
    return {
        "id": article_id,
        "headline": headline,
        "summary": summary,
        "body_text": body_text,
        "metadata": {
            "feed_summary": summary,
            "extraction_quality": "article_body",
            "access_signal": "open",
        },
        "original_url": f"https://example.com/{article_id}",
        "canonical_url": f"https://example.com/{article_id}",
        "outlets": {
            "canonical_name": outlet,
        },
    }


def quality_snapshot(
    *,
    article_id: str,
    outlet: str,
    headline: str,
    snippet: str,
    focus: str,
) -> dict[str, str]:
    return {
        "article_id": article_id,
        "outlet": outlet,
        "headline": headline,
        "canonical_url": f"https://example.com/{article_id}",
        "original_url": f"https://example.com/{article_id}",
        "extraction_quality": "article_body",
        "access_tier": "open",
        "focus": focus,
        "used_snippet": snippet,
    }


def quality_ref(*, article_id: str, outlet: str, headline: str, snippet: str, focus: str) -> dict[str, str]:
    return {
        "article_id": article_id,
        "outlet": outlet,
        "headline": headline,
        "focus": focus,
        "used_snippet": snippet,
    }


def run_web_regression_tests() -> None:
    if not TSX_BIN.exists():
        raise SystemExit(f"expected tsx test runner at {TSX_BIN}")

    try:
        subprocess.run(
            [
                str(TSX_BIN),
                "--test",
                "src/web/src/lib/perspective-versioning.test.ts",
                "src/web/src/lib/cluster-ranking.test.ts",
                "src/web/src/lib/reader-persistence.test.ts",
                "src/web/src/lib/story-brief-versioning.test.ts",
                "src/web/src/lib/story-briefs.test.ts",
                "src/web/src/lib/tracked-story-history.test.ts",
            ],
            cwd=REPO_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"web regression tests failed with exit code {error.returncode}") from error


def main() -> int:
    run_web_regression_tests()

    now = datetime.now(UTC)
    if choose_due_job(
        now=now,
        next_raw_due_at=now - timedelta(seconds=30),
        next_full_due_at=now - timedelta(seconds=5),
    ) != "full":
        raise SystemExit("expected full ingest to win when both raw and full are due")
    if choose_due_job(
        now=now,
        next_raw_due_at=now - timedelta(seconds=5),
        next_full_due_at=now + timedelta(seconds=120),
    ) != "raw":
        raise SystemExit("expected raw ingest to run when only the raw cadence is due")

    plist_payload = build_launchd_plist(
        raw_interval_seconds=300,
        full_interval_seconds=1800,
        startup_delay_seconds=30,
        retry_delay_seconds=60,
    ).decode("utf-8")
    if "com.prismwire.local-ingest" not in plist_payload or "tooling/run_local_ingest_scheduler.py" not in plist_payload:
        raise SystemExit("expected launchd plist to include the local ingest scheduler label and command")

    for command in (
        ["python3", "tooling/run_local_ingest_job.py", "--help"],
        ["python3", "tooling/run_local_ingest_scheduler.py", "status", "--json"],
    ):
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise SystemExit(f"expected {' '.join(command)} to succeed, got {completed.returncode}: {completed.stderr}")

    oil_one = build_item(
        source="NPR",
        title="US to release emergency oil reserves as prices rise",
        url="https://example.com/oil-1",
        summary="Oil reserve release as prices rise.",
        tokens={"oil", "reserve", "release", "price"},
        event_tags={"oil_reserve_release"},
    )
    oil_two = build_item(
        source="BBC",
        title="Emergency oil reserve release announced amid fuel price fears",
        url="https://example.com/oil-2",
        summary="Oil reserve release amid fuel price fears.",
        tokens={"oil", "reserve", "release", "fuel", "price"},
        event_tags={"oil_reserve_release"},
    )
    unrelated = build_item(
        source="BBC",
        title="West Bank settlers face sanctions review",
        url="https://example.com/west-bank",
        summary="West Bank settlers story.",
        tokens={"west", "bank", "settlers", "sanctions", "review"},
        event_tags=set(),
    )

    items = [oil_one, oil_two, unrelated]
    clusters = cluster_items(items)
    cluster_sizes = sorted(len(cluster) for cluster in clusters)
    if cluster_sizes != [1, 2]:
        raise SystemExit(f"unexpected cluster sizes: {cluster_sizes}")

    neighbors, _similarities = build_similarity_lookup(items)
    if neighbors.get(oil_one.url) != [oil_two.url]:
        raise SystemExit(f"unexpected semantic candidates for oil_one: {neighbors.get(oil_one.url)}")
    if neighbors.get(unrelated.url):
        raise SystemExit(f"unexpected semantic candidates for unrelated story: {neighbors.get(unrelated.url)}")

    normalized = normalize_canonical_url("https://example.com/story?utm_source=test&id=42#top")
    if normalized != "https://example.com/story?id=42":
        raise SystemExit(f"unexpected canonical URL normalization result: {normalized}")

    fetch_block = detect_fetch_block(
        """
        <html>
          <head>
            <meta name="description" content="px-captcha" />
            <title>Access to this page has been denied</title>
          </head>
          <body>Before we continue... Press & Hold to confirm you are a human.</body>
        </html>
        """
    )
    if fetch_block != {"reason": "anti_bot_challenge", "vendor": "perimeterx"}:
        raise SystemExit(f"expected perimeterx fetch block detection, got {fetch_block}")

    status_only_block = classify_fetch_block("", status_code=403)
    if status_only_block != {"reason": "http_access_denied", "vendor": "generic"}:
        raise SystemExit(f"expected generic HTTP access-denied fetch block, got {status_only_block}")

    the_hill_strategy = resolve_source_fetch_strategy("https://thehill.com/homenews/example")
    if the_hill_strategy.name != "http_fetch_with_source_api_and_browser_fallback":
        raise SystemExit(f"expected The Hill API plus browser fallback strategy, got {the_hill_strategy}")
    if not should_attempt_source_api_fallback(the_hill_strategy, reason="fetch_blocked"):
        raise SystemExit("expected The Hill strategy to source-retry on fetch blocks")
    if not should_attempt_source_api_fallback(the_hill_strategy, reason="rss_only"):
        raise SystemExit("expected The Hill strategy to source-retry on rss_only extraction")
    if not should_attempt_browser_fallback(the_hill_strategy, reason="fetch_blocked"):
        raise SystemExit("expected The Hill strategy to browser-retry on fetch blocks")
    if not should_attempt_browser_fallback(the_hill_strategy, reason="rss_only"):
        raise SystemExit("expected The Hill strategy to browser-retry on rss_only extraction")

    source_api_markup = build_source_api_markup(
        title="Trump says he has own idea on how long Iran war will last",
        article_html="""
        <p>President Trump said Friday that he had his own idea of how long the conflict in Iran could last.</p>
        <p>He said the military campaign would continue as long as necessary.</p>
        <p>Officials have offered shifting messages about the likely timeline.</p>
        """,
        description="President Trump said Friday that he had his own idea of how long the conflict in Iran could last.",
    )
    source_api_enrichment = build_enrichment_from_markup(
        source_api_markup,
        url="https://thehill.com/homenews/administration/5783947-trump-iran-conflict-timeline/",
        fallback_summary="Fallback summary.",
        default_payload={
            "fetch_strategy": "http_fetch_with_source_api_and_browser_fallback",
            "source_api_attempted": True,
            "source_api_used": "thehill_wp_json",
        },
    )
    if source_api_enrichment.get("extraction_quality") != "article_body":
        raise SystemExit(f"expected The Hill source API enrichment to extract article text, got {source_api_enrichment}")

    quoted_sentences = split_brief_sentences(
        (
            "President Trump said Friday that he has his own idea of how long the conflict in Iran could last. "
            "“I mean, I have my own idea. But what good does it do?” Trump told reporters at Joint Base Andrews when asked about the duration of the war. "
            "“It’ll be as long as it’s necessary.” Trump and the Pentagon have offered conflicting signals about when the conflict could come to an end."
        )
    )
    if len(quoted_sentences) < 3 or "But what good does it do?” Trump told reporters" not in quoted_sentences[1]:
        raise SystemExit(f"expected quoted narrative sentence to stay intact, got {quoted_sentences}")

    browser_rendered_enrichment = build_enrichment_from_markup(
        """
        <html>
          <head>
            <meta property="og:description" content="The Hill article body is now available." />
          </head>
          <body>
            <article>
              <p>President Trump said he had his own idea of how long the Iran conflict would last.</p>
              <p>The Hill reported that the administration was sending mixed messages about the timeline.</p>
              <p>Officials said the next phase would depend on how regional responses unfolded.</p>
            </article>
          </body>
        </html>
        """,
        url="https://thehill.com/example-story",
        fallback_summary="Fallback summary.",
        default_payload={"fetch_strategy": "http_fetch_with_source_api_and_browser_fallback"},
        browser_rendered=True,
    )
    if (
        browser_rendered_enrichment.get("extraction_quality") != "article_body"
        or browser_rendered_enrichment.get("browser_rendered") is not True
    ):
        raise SystemExit(
            f"expected browser-rendered enrichment to produce article body extraction, got {browser_rendered_enrichment}"
        )
    if browser_rendered_enrichment.get("lede", "").startswith("Decision Desk HQ and The Hill"):
        raise SystemExit(
            f"expected The Hill browser-rendered enrichment to skip election-center boilerplate, got {browser_rendered_enrichment}"
        )

    the_hill_boilerplate_enrichment = build_enrichment_from_markup(
        """
        <html>
          <head>
            <meta property="og:description" content="Decision Desk HQ and The Hill's ultimate hub for polls, predictions, and election results." />
          </head>
          <body>
            <p>Decision Desk HQ and The Hill's ultimate hub for polls, predictions, and election results.</p>
            <p>Sponsored content</p>
            <p>A federal appeals court ruled that Mississippi’s law allowing mail ballots to be received after Election Day is illegal.</p>
            <p>The opinion sends the RNC challenge back to a lower court to determine whether the statute should be blocked.</p>
          </body>
        </html>
        """,
        url="https://thehill.com/example-election-center-story",
        fallback_summary="Fallback summary.",
        default_payload={"fetch_strategy": "http_fetch_with_source_api_and_browser_fallback"},
        browser_rendered=True,
    )
    if not the_hill_boilerplate_enrichment.get("lede", "").startswith("A federal appeals court ruled"):
        raise SystemExit(
            f"expected The Hill boilerplate enrichment to choose the first article sentence, got {the_hill_boilerplate_enrichment}"
        )

    abc_liveblog_enrichment = build_enrichment_from_markup(
        """
        <html>
          <head>
            <meta property="og:description" content="President Donald Trump announced major combat operations against Iran." />
            <script type="application/ld+json">
              {
                "@context": "http://schema.org",
                "@type": "LiveBlogPosting",
                "headline": "Iran live updates: US 'bombing raid' strikes Kharg Island, Trump says",
                "liveBlogUpdate": [
                  {
                    "@type": "BlogPosting",
                    "headline": "Israel congratulates US on Kharg Island strikes",
                    "articleBody": "Israel Defense Minister Israel Katz congratulated President Donald Trump on the severe blow that the U.S. military dealt to Kharg Island. Katz said Israel was continuing a powerful wave of attacks on Tehran and throughout Iran."
                  },
                  {
                    "@type": "BlogPosting",
                    "headline": "Trump says Iran wants a deal",
                    "articleBody": "In an overnight Truth Social post, President Donald Trump said Iran is totally defeated and wants a deal, but not one he would accept. The update said the latest strike was part of a broader escalation around the Strait of Hormuz."
                  },
                  {
                    "@type": "BlogPosting",
                    "headline": "Healthcare workers killed in Lebanon",
                    "articleBody": "Twelve healthcare workers were killed in an Israeli airstrike in southern Lebanon, the Ministry of Health said in a statement. The ministry said the strike hit a medical center far from the Kharg Island operation."
                  }
                ]
              }
            </script>
          </head>
          <body>
            <article>
              <p>window.__INITIAL_STATE__ && t[0].headers && e(t[0].headers,o) || Ajax/DataUrl/Excluded</p>
            </article>
          </body>
        </html>
        """,
        url="https://abcnews.com/International/live-updates/iran-live-updates?id=130893022",
        fallback_summary="Fallback summary.",
        default_payload={"fetch_strategy": "http_fetch"},
    )
    if abc_liveblog_enrichment.get("extraction_quality") != "article_body":
        raise SystemExit(f"expected ABC live-blog enrichment to recover article text, got {abc_liveblog_enrichment}")
    if "Ajax/DataUrl/Excluded" in (abc_liveblog_enrichment.get("body_preview") or ""):
        raise SystemExit(f"expected ABC live-blog enrichment to ignore script garbage, got {abc_liveblog_enrichment}")
    if not str(abc_liveblog_enrichment.get("lede") or "").startswith("Israel Defense Minister Israel Katz congratulated"):
        raise SystemExit(f"expected ABC live-blog enrichment to lead with the first update body, got {abc_liveblog_enrichment}")
    if "healthcare workers" in str(abc_liveblog_enrichment.get("body_preview") or "").lower():
        raise SystemExit(f"expected ABC live-blog enrichment to filter unrelated updates, got {abc_liveblog_enrichment}")

    pbs_article_enrichment = build_enrichment_from_markup(
        """
        <html>
          <head>
            <meta property="og:description" content="State senators on Friday grilled the former special prosecutor who led the Georgia election interference case against President Donald Trump." />
          </head>
          <body>
            <article itemprop="articleBody">
              <div class="body-text">
                <p>State senators on Friday grilled the former special prosecutor who led the Georgia election interference case against President Donald Trump about communications his team had with federal investigators.</p>
                <p><strong>READ MORE:</strong> Prosecutor leaves Georgia election interference case against Trump after relationship with district attorney</p>
                <p>While the committee has met multiple times to hear from witnesses, it has unearthed little that was not already known about the investigation and its political fallout.</p>
                <p>Notice: Transcripts are machine and human generated and lightly edited for accuracy. They may contain errors.</p>
                <p>Mostly, though, lawmakers pressed Nathan Wade about invoices that appeared to show contact with the Jan. 6 House committee and Justice Department officials.</p>
              </div>
            </article>
          </body>
        </html>
        """,
        url="https://pbs.org/newshour/politics/georgia-lawmakers-grill-former-special-prosecutor-nathan-wade-over-trump-election-case",
        fallback_summary="Fallback summary.",
        default_payload={"fetch_strategy": "http_fetch"},
    )
    if pbs_article_enrichment.get("extraction_quality") != "article_body":
        raise SystemExit(f"expected PBS article enrichment to extract body text, got {pbs_article_enrichment}")
    if "READ MORE:" in (pbs_article_enrichment.get("body_preview") or ""):
        raise SystemExit(f"expected PBS extraction to skip read-more boilerplate, got {pbs_article_enrichment}")
    if "machine and human generated" in (pbs_article_enrichment.get("body_preview") or "").lower():
        raise SystemExit(f"expected PBS extraction to skip transcript notices, got {pbs_article_enrichment}")

    bloomberg_oil_hub = FeedItem(
        source="Bloomberg",
        feed_url="https://example.com/bloomberg",
        title="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        url="https://example.com/bloomberg-uae-oil-hub",
        published_at="2026-03-14T15:00:00+00:00",
        summary="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        feed_summary="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        lede="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        body_preview="",
        named_entities=["UAE"],
        extraction_quality="rss_only",
        access_signal="likely_paywalled",
        image=None,
        tokens={"uae", "key", "oil", "hub", "suspend", "loading", "attack", "drone", "fire"},
        event_tags=set(),
    )
    reuters_kharg = FeedItem(
        source="Reuters",
        feed_url="https://example.com/reuters",
        title="Kharg Island, struck by US, is key hub for Iran oil exports",
        url="https://example.com/reuters-kharg",
        published_at="2026-03-14T14:45:00+00:00",
        summary="Kharg Island, struck by US, is key hub for Iran oil exports.",
        feed_summary="Kharg Island, struck by US, is key hub for Iran oil exports.",
        lede="Kharg Island, struck by US, is key hub for Iran oil exports.",
        body_preview="",
        named_entities=["Kharg Island", "Iran"],
        extraction_quality="rss_only",
        access_signal="open",
        image=None,
        tokens={"kharg", "island", "struck", "iran", "oil", "exports", "hub", "key"},
        event_tags=set(),
    )
    abc_kharg = FeedItem(
        source="ABC News",
        feed_url="https://example.com/abc",
        title="Iran live updates: US 'bombing raid' strikes Kharg Island, Trump says",
        url="https://example.com/abc-kharg",
        published_at="2026-03-14T14:40:00+00:00",
        summary="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        feed_summary="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        lede="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        body_preview="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island. The deputy governor of Bushehr Province said export activity was continuing.",
        named_entities=["Kharg Island", "Iran", "President Donald Trump"],
        extraction_quality="article_body",
        access_signal="open",
        image=None,
        tokens={"iran", "live", "updates", "bombing", "raid", "strikes", "kharg", "island", "trump"},
        event_tags=set(),
    )
    split_clusters = cluster_items([bloomberg_oil_hub, reuters_kharg, abc_kharg])
    if len(split_clusters) != 2:
        raise SystemExit(f"expected low-signal overlap cluster to split into 2 stories, got {split_clusters}")
    if sorted(len(cluster) for cluster in split_clusters) != [1, 2]:
        raise SystemExit(f"expected Bloomberg item to stay isolated from Kharg cluster, got {split_clusters}")

    representative = representative_cluster_item([bloomberg_oil_hub, reuters_kharg, abc_kharg])
    if representative.source != "ABC News":
        raise SystemExit(f"expected representative cluster lead to prefer richer Kharg article, got {representative}")
    representative_payload = build_cluster_payload(1, [bloomberg_oil_hub, reuters_kharg, abc_kharg])
    if representative_payload["title"] != abc_kharg.title:
        raise SystemExit(f"expected cluster payload title to use representative article, got {representative_payload}")

    reuters_hormuz = FeedItem(
        source="Reuters",
        feed_url="https://example.com/reuters",
        title="Trump says 'many countries' will send warships to keep Strait of Hormuz open",
        url="https://example.com/reuters-hormuz-warships",
        published_at="2026-03-14T15:43:00+00:00",
        summary="Trump says many countries will send warships to keep the Strait of Hormuz open.",
        feed_summary="Trump says many countries will send warships to keep the Strait of Hormuz open.",
        lede="Trump says many countries will send warships to keep the Strait of Hormuz open.",
        body_preview="",
        named_entities=["Strait of Hormuz", "Donald Trump"],
        extraction_quality="rss_only",
        access_signal="open",
        image=None,
        tokens={"trump", "countries", "send", "warships", "keep", "open", "straithormuz"},
        event_tags={"iran_shipping_attacks"},
    )
    abc_live_hormuz = FeedItem(
        source="ABC News",
        feed_url="https://example.com/abc",
        title="Iran live updates: Trump calls on other countries to assist in Strait of Hormuz",
        url="https://example.com/abc-hormuz-live",
        published_at="2026-03-14T15:42:00+00:00",
        summary="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        feed_summary="President Donald Trump announced major combat operations against Iran on Feb. 28, with massive joint U.S.-Israel strikes.",
        lede="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        body_preview="Israel Defense Minister Israel Katz congratulated President Donald Trump after U.S. strikes on Kharg Island.",
        named_entities=["Kharg Island", "President Donald Trump", "Strait of Hormuz"],
        extraction_quality="article_body",
        access_signal="open",
        image=None,
        tokens={"iran", "live", "updates", "trump", "calls", "countries", "assist", "straithormuz", "khargisland"},
        event_tags={"iran_shipping_attacks"},
    )
    ft_stockpile = FeedItem(
        source="Financial Times",
        feed_url="https://example.com/ft",
        title="Why has Trump left Iran’s nuclear stockpile untouched?",
        url="https://example.com/ft-stockpile",
        published_at="2026-03-14T15:44:00+00:00",
        summary="Why has Trump left Iran’s nuclear stockpile untouched?",
        feed_summary="Why has Trump left Iran’s nuclear stockpile untouched?",
        lede="Why has Trump left Iran’s nuclear stockpile untouched?",
        body_preview="",
        named_entities=["Donald Trump", "Iran"],
        extraction_quality="rss_only",
        access_signal="likely_paywalled",
        image=None,
        tokens={"trump", "iran", "nuclearstockpile", "untouched"},
        event_tags=set(),
    )
    thehill_california = FeedItem(
        source="The Hill",
        feed_url="https://example.com/thehill",
        title="Trump administration orders restart of California offshore oil operations",
        url="https://example.com/thehill-california-oil",
        published_at="2026-03-14T15:41:00+00:00",
        summary="The Trump administration directed Sable Offshore to restart operations as prices surged after Iran’s closure of the Strait of Hormuz.",
        feed_summary="The Trump administration directed Sable Offshore to restart operations as prices surged after Iran’s closure of the Strait of Hormuz.",
        lede="The Trump administration directed Sable Offshore to restart operations as prices surged after Iran’s closure of the Strait of Hormuz.",
        body_preview="",
        named_entities=["Sable Offshore", "California", "Strait of Hormuz"],
        extraction_quality="article_body",
        access_signal="open",
        image=None,
        tokens={"trump", "administration", "restart", "california", "offshore", "oil", "operations", "sable", "straithormuz"},
        event_tags={"iran_shipping_attacks"},
    )
    hormuz_cluster_groups = [set(entry.url for entry in cluster) for cluster in cluster_items([reuters_hormuz, abc_live_hormuz, ft_stockpile, thehill_california])]
    if any({"https://example.com/reuters-hormuz-warships", "https://example.com/ft-stockpile"} <= group for group in hormuz_cluster_groups):
        raise SystemExit(f"expected Hormuz warships story to stay split from FT stockpile analysis, got {hormuz_cluster_groups}")
    if any({"https://example.com/reuters-hormuz-warships", "https://example.com/thehill-california-oil"} <= group for group in hormuz_cluster_groups):
        raise SystemExit(f"expected Hormuz warships story to stay split from California offshore oil item, got {hormuz_cluster_groups}")

    nyt_paywalled = FeedItem(
        source="New York Times",
        feed_url="https://example.com/nyt",
        title="Why Little Was Done to Head Off Oil’s Strait of Hormuz Problem",
        url="https://example.com/nyt-hormuz",
        published_at="2026-03-14T14:00:00+00:00",
        summary="Geography and regional rivalries have prevented Gulf countries from finding a true alternative to the strait.",
        feed_summary="Geography and regional rivalries have prevented Gulf countries from finding a true alternative to the strait.",
        lede="Geography and regional rivalries have prevented Gulf countries from finding a true alternative to the strait.",
        body_preview="Geography and regional rivalries have prevented Gulf countries from finding a true alternative to the strait. The war with Iran has effectively shut it down.",
        named_entities=["Strait of Hormuz", "Iran", "Gulf"],
        extraction_quality="article_body",
        access_signal="likely_paywalled",
        image=None,
        tokens={"straithormuz", "iran", "gulf", "shipping", "regional", "rivalries"},
        event_tags={"iran_shipping_attacks"},
    )
    reuters_alternate = FeedItem(
        source="Reuters",
        feed_url="https://example.com/reuters",
        title="Warships prepare to escort tankers through Strait of Hormuz",
        url="https://example.com/reuters-hormuz",
        published_at="2026-03-14T14:10:00+00:00",
        summary="Warships prepared to escort tankers through the Strait of Hormuz as Iran threatened shipping lanes.",
        feed_summary="Warships prepared to escort tankers through the Strait of Hormuz as Iran threatened shipping lanes.",
        lede="Warships prepared to escort tankers through the Strait of Hormuz as Iran threatened shipping lanes.",
        body_preview="Warships prepared to escort tankers through the Strait of Hormuz as Iran threatened shipping lanes. Officials said energy markets were bracing for disruption.",
        named_entities=["Strait of Hormuz", "Iran"],
        extraction_quality="article_body",
        access_signal="open",
        image=None,
        tokens={"warships", "escort", "tankers", "straithormuz", "iran", "shipping", "lanes"},
        event_tags={"iran_shipping_attacks"},
    )
    unrelated_bloomberg = FeedItem(
        source="Bloomberg",
        feed_url="https://example.com/bloomberg",
        title="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        url="https://example.com/bloomberg-unrelated",
        published_at="2026-03-14T14:05:00+00:00",
        summary="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        feed_summary="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        lede="UAE's Key Oil Hub Suspends Loadings After Drone Attack, Fire",
        body_preview="",
        named_entities=["UAE"],
        extraction_quality="rss_only",
        access_signal="likely_paywalled",
        image=None,
        tokens={"uae", "key", "oil", "hub", "suspend", "loading", "attack", "drone", "fire"},
        event_tags=set(),
    )
    query_tokens, query_entities = story_query_from_cluster([nyt_paywalled])
    if "straithormuz" not in query_tokens or "strait of hormuz" not in query_entities:
        raise SystemExit(f"expected story query to preserve strong Hormuz anchors, got {(query_tokens, query_entities)}")
    augmentation_candidates = select_story_augmentation_candidates(
        [nyt_paywalled],
        [reuters_alternate, unrelated_bloomberg],
        limit=2,
    )
    if [item.source for item in augmentation_candidates] != ["Reuters"]:
        raise SystemExit(f"expected augmentation selector to choose matched open alternate only, got {augmentation_candidates}")

    blocked_metadata = merge_article_metadata(
        {"metadata": {"feed_summary": "Fallback summary."}},
        {
            "named_entities": [],
            "extraction_quality": "rss_only",
            "access_signal": "open",
            "fetch_blocked": True,
            "fetch_block_reason": "anti_bot_challenge",
            "fetch_block_vendor": "perimeterx",
        },
        "2026-03-14T03:43:31Z",
    )
    if blocked_metadata.get("fetch_blocked") is not True or blocked_metadata.get("fetch_block_vendor") != "perimeterx":
        raise SystemExit(f"expected fetch block metadata to be retained, got {blocked_metadata}")

    browser_metadata = merge_article_metadata(
        {"metadata": {"feed_summary": "Fallback summary."}},
        {
            "named_entities": [],
            "extraction_quality": "article_body",
            "access_signal": "open",
            "fetch_strategy": "http_fetch_with_source_api_and_browser_fallback",
            "source_api_attempted": True,
            "source_api_used": "thehill_wp_json",
            "source_api_endpoint": "https://thehill.com/wp-json/wp/v2/posts/5783947",
            "browser_attempted": True,
            "browser_rendered": True,
            "browser_executable": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        },
        "2026-03-14T04:15:00Z",
    )
    if (
        browser_metadata.get("browser_rendered") is not True
        or browser_metadata.get("fetch_strategy") != "http_fetch_with_source_api_and_browser_fallback"
        or browser_metadata.get("source_api_used") != "thehill_wp_json"
    ):
        raise SystemExit(f"expected browser-rendered metadata to be retained, got {browser_metadata}")

    single_source_brief = build_grounded_brief(
        {
            "canonical_headline": "Cuba confirms talks with Trump administration amid fuel shortages",
            "summary": "Cuba confirmed talks with the Trump administration after fuel shortages deepened the country’s economic crisis.",
            "topic_label": "World",
            "outlet_count": 1,
            "cluster_key_facts": [
                {"fact_text": "Officials said the talks are aimed at easing immediate fuel shortages.", "sort_order": 0},
                {"fact_text": "Power generation and freight movement have already been disrupted.", "sort_order": 1},
                {"fact_text": "State media described the contacts as practical crisis management.", "sort_order": 2},
            ],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "article-1",
                        "headline": "Cuba confirms talks with Trump administration amid fuel shortages",
                        "summary": "Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut.",
                        "body_text": (
                            "Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut. "
                            "Officials said the immediate goal was to stabilize domestic supply and keep freight lines moving. "
                            "The government described the contacts as practical rather than a diplomatic reset. "
                            "Power generation has already been reduced in several provinces because fuel stocks are low. "
                            "Freight delays have started to disrupt deliveries and factory schedules across the island. "
                            "State media said any agreement would be judged by whether it eases shortages quickly for households and businesses."
                        ),
                        "metadata": {
                            "feed_summary": "Cuba confirmed talks as fuel shortages worsened.",
                            "extraction_quality": "article_body",
                        },
                        "original_url": "https://example.com/cuba-talks",
                        "canonical_url": "https://example.com/cuba-talks",
                        "outlets": {
                            "canonical_name": "Reuters",
                        },
                    },
                }
            ],
        }
    )
    if single_source_brief["status"] != "early":
        raise SystemExit(f"expected one-source brief to stay early, got {single_source_brief['status']}")
    if len(single_source_brief["paragraphs"]) < 3:
        raise SystemExit(
            f"expected richer one-source early brief paragraphs, got {len(single_source_brief['paragraphs'])}: {single_source_brief['paragraphs']}"
        )

    blocked_single_source_brief = build_grounded_brief(
        {
            "canonical_headline": "Trump says he has own idea on how long Iran war will last",
            "summary": "President Trump said Friday that he has his own idea of how long the conflict in Iran could last.",
            "topic_label": "World",
            "outlet_count": 1,
            "cluster_key_facts": [
                {"fact_text": "The strongest available source read is already open.", "sort_order": 0},
            ],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "article-blocked-1",
                        "headline": "Trump says he has own idea on how long Iran war will last",
                        "summary": "President Trump said Friday that he has his own idea of how long the conflict in Iran could last.",
                        "body_text": "",
                        "metadata": {
                            "feed_summary": "President Trump said Friday that he has his own idea of how long the conflict in Iran could last.",
                            "extraction_quality": "rss_only",
                            "access_signal": "open",
                            "fetch_blocked": True,
                        },
                        "original_url": "https://thehill.com/example-story",
                        "canonical_url": "https://thehill.com/example-story",
                        "outlets": {
                            "canonical_name": "The Hill",
                        },
                    },
                }
            ],
        }
    )
    if not any("blocked automated full-text retrieval" in paragraph for paragraph in blocked_single_source_brief["paragraphs"]):
        raise SystemExit(f"expected blocked-fetch brief to disclose retrieval failure, got {blocked_single_source_brief['paragraphs']}")
    if "The strongest available source read is already open." in blocked_single_source_brief["supporting_points"]:
        raise SystemExit("expected access-status boilerplate to stay out of supporting points")
    source_grounded_single_source_quality = evaluate_story_quality(
        {
            "id": "cluster-single-source-quality",
            "slug": "single-source-quality",
            "canonical_headline": "Cuba confirms talks with Trump administration amid fuel shortages",
            "summary": "Cuba confirmed talks with the Trump administration after fuel shortages deepened the country’s economic crisis.",
            "latest_event_at": "2026-03-14T05:10:00Z",
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "article-1",
                        "headline": "Cuba confirms talks with Trump administration amid fuel shortages",
                        "summary": "Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut.",
                        "body_text": (
                            "Cuba said the talks were focused on fuel shortages, transport disruption and a broader economic crunch after Venezuelan oil shipments were cut. "
                            "Officials said the immediate goal was to stabilize domestic supply and keep freight lines moving. "
                            "The government described the contacts as practical rather than a diplomatic reset. "
                            "Power generation has already been reduced in several provinces because fuel stocks are low. "
                            "Freight delays have started to disrupt deliveries and factory schedules across the island. "
                            "State media said any agreement would be judged by whether it eases shortages quickly for households and businesses."
                        ),
                        "metadata": {
                            "feed_summary": "Cuba confirmed talks as fuel shortages worsened.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/cuba-talks",
                        "canonical_url": "https://example.com/cuba-talks",
                        "outlets": {"canonical_name": "Reuters"},
                    },
                }
            ],
        },
        single_source_brief,
    )
    if source_grounded_single_source_quality["review_priority"] == "critical":
        raise SystemExit(
            f"expected grounded one-source early brief scaffolding not to trigger critical review, got {source_grounded_single_source_quality}"
        )

    mixed_quality_brief = build_grounded_brief(
        {
            "canonical_headline": "Grenell exits Kennedy Center before renovation shutdown",
            "summary": "Richard Grenell is stepping down from the Kennedy Center before the site closes for renovations.",
            "topic_label": "Politics",
            "outlet_count": 2,
            "cluster_key_facts": [],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-mixed-1",
                        "headline": "Grenell exits Kennedy Center before renovation shutdown",
                        "summary": "President Trump announced that Richard Grenell is leaving his role at the Kennedy Center before renovations begin.",
                        "body_text": (
                            "President Trump announced that Richard Grenell is leaving his role at the Kennedy Center before renovations begin. "
                            "NPR reported that the change comes before the arts complex closes for a major scheduled shutdown. "
                            "Trump said a current operations executive would take over the next phase."
                        ),
                        "metadata": {
                            "feed_summary": "President Trump announced that Richard Grenell is leaving his role at the Kennedy Center before renovations begin.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/grenell-npr",
                        "canonical_url": "https://example.com/grenell-npr",
                        "outlets": {"canonical_name": "NPR"},
                    },
                },
                {
                    "rank_in_cluster": 2,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-mixed-2",
                        "headline": "Trump announces Ric Grenell is stepping down as Kennedy Center's president",
                        "summary": "Richard Grenell, an ally of President Donald Trump, will step down as the institution's president.",
                        "body_text": "",
                        "metadata": {
                            "feed_summary": "Richard Grenell, an ally of President Donald Trump, will step down as the institution's president.",
                            "extraction_quality": "metadata_description",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/grenell-pbs",
                        "canonical_url": "https://example.com/grenell-pbs",
                        "outlets": {"canonical_name": "PBS NewsHour"},
                    },
                },
            ],
        }
    )
    if mixed_quality_brief["status"] != "early" or mixed_quality_brief["metadata"]["full_brief_ready"] is not False:
        raise SystemExit(f"expected mixed-quality two-outlet brief to stay early, got {mixed_quality_brief}")

    duplicate_open_alternate_brief = build_grounded_brief(
        {
            "canonical_headline": "Marines and warships move toward the Middle East",
            "summary": "More Marines and warships are expected to move toward the Middle East as the regional crisis widens.",
            "topic_label": "World",
            "outlet_count": 3,
            "cluster_key_facts": [],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-open-1",
                        "headline": "More US Marines and warships to be moved to Middle East, reports say",
                        "summary": "More Marines and warships are expected to be deployed to the Middle East, officials said.",
                        "body_text": (
                            "More Marines and warships are expected to be deployed to the Middle East, officials said. "
                            "The deployment would come from an amphibious ready group and its Marine expeditionary unit. "
                            "Officials said the mission remains under review."
                        ),
                        "metadata": {
                            "feed_summary": "More Marines and warships are expected to be deployed to the Middle East, officials said.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/bbc-marines",
                        "canonical_url": "https://example.com/bbc-marines",
                        "outlets": {"canonical_name": "BBC News"},
                    },
                },
                {
                    "rank_in_cluster": 2,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-open-2",
                        "headline": "More Marines and Warships Being Sent to Middle East, U.S. Officials Say",
                        "summary": "About 2,500 Marines aboard warships are heading to the Middle East, U.S. officials said.",
                        "body_text": (
                            "About 2,500 Marines aboard warships are heading to the Middle East, U.S. officials said. "
                            "New York Times reported that the move reflects concern that the regional response has proved more resilient than expected. "
                            "Officials said the deployment is tied to rising attacks in the Strait of Hormuz."
                        ),
                        "metadata": {
                            "feed_summary": "About 2,500 Marines aboard warships are heading to the Middle East, U.S. officials said.",
                            "extraction_quality": "article_body",
                            "access_signal": "likely_paywalled",
                        },
                        "original_url": "https://example.com/nyt-marines",
                        "canonical_url": "https://example.com/nyt-marines",
                        "outlets": {"canonical_name": "New York Times"},
                    },
                },
                {
                    "rank_in_cluster": 3,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-open-3",
                        "headline": "PBS confirms Marines and warships are moving toward the Middle East",
                        "summary": (
                            "More Marines and warships are expected to be deployed to the Middle East, officials said. "
                            "The deployment would come from an amphibious ready group and its Marine expeditionary unit. "
                            "Officials said the mission remains under review."
                        ),
                        "body_text": "",
                        "metadata": {
                            "feed_summary": (
                                "More Marines and warships are expected to be deployed to the Middle East, officials said. "
                                "The deployment would come from an amphibious ready group and its Marine expeditionary unit. "
                                "Officials said the mission remains under review."
                            ),
                            "extraction_quality": "metadata_description",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/pbs-marines",
                        "canonical_url": "https://example.com/pbs-marines",
                        "outlets": {"canonical_name": "PBS NewsHour"},
                    },
                },
            ],
        }
    )
    if duplicate_open_alternate_brief["metadata"]["open_alternate_available"] is not True:
        raise SystemExit(
            f"expected duplicate-source cluster to retain open alternate availability, got {duplicate_open_alternate_brief['metadata']}"
        )

    polluted_text_brief = build_grounded_brief(
        {
            "canonical_headline": "Oil routes remain under strain after strikes",
            "summary": "Oil routes remain under strain after strikes in the region.",
            "topic_label": "Business",
            "outlet_count": 2,
            "cluster_key_facts": [],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-polluted-1",
                        "headline": "Five reasons oil prices won't snap back from Iran war",
                        "summary": "Tanker backlogs and damaged infrastructure could keep gasoline prices elevated. A man walks along the shore in the UAE as oil tankers line up in the Strait of Hormuz. | Altaf Qadri/AP President Donald Trump may be pledging a quick end to the war.",
                        "body_text": (
                            "Tanker backlogs and damaged infrastructure could keep gasoline prices elevated. "
                            "A man walks along the shore in the United Arab Emirates as oil tankers line up in the Strait of Hormuz on Wednesday. | Altaf Qadri/AP "
                            "President Donald Trump may be pledging a quick end to the war, but the political fallout will persist. "
                            "Notes: Data shows future contract prices for Brent crude oil. Data delayed at least 15 minutes."
                        ),
                        "metadata": {
                            "feed_summary": "Tanker backlogs and damaged infrastructure could keep gasoline prices elevated.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/politico-oil",
                        "canonical_url": "https://example.com/politico-oil",
                        "outlets": {"canonical_name": "Politico"},
                    },
                },
                {
                    "rank_in_cluster": 2,
                    "framing_group": "center",
                    "articles": {
                        "id": "brief-polluted-2",
                        "headline": "Iran war live updates: Trump says US bombed military targets on Kharg Island",
                        "summary": "Iran's parliament speaker warned that attacks on the islands would provoke a new level of retaliation.",
                        "body_text": (
                            "Iran's parliament speaker warned that attacks on the islands would provoke a new level of retaliation. "
                            "Associated Press said the islands remain central to the country's economy and security. "
                            "The warning underscored the risk of wider disruption to oil routes."
                        ),
                        "metadata": {
                            "feed_summary": "Iran's parliament speaker warned that attacks on the islands would provoke a new level of retaliation.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                        },
                        "original_url": "https://example.com/ap-oil",
                        "canonical_url": "https://example.com/ap-oil",
                        "outlets": {"canonical_name": "Associated Press"},
                    },
                },
            ],
        }
    )
    polluted_snapshot_text = " ".join(source["used_snippet"] for source in polluted_text_brief["source_snapshot"])
    if any(marker in polluted_snapshot_text for marker in ("Altaf Qadri/AP", "A man walks along", "Notes: Data shows future contract prices")):
        raise SystemExit(f"expected polluted caption/chart note text to be cleaned from brief sources, got {polluted_snapshot_text}")

    thin_placeholder_cluster = {
        "id": "cluster-thin-placeholder",
        "slug": "thin-placeholder",
        "canonical_headline": "Senate Democrat calls for investigation into Texas drone incidents",
        "summary": "Senate Democrat calls for investigation into Texas drone incidents is drawing early coverage from The Hill as Prism waits for fuller reporting.",
        "topic_label": "Politics",
        "latest_event_at": "2026-03-14T14:00:00Z",
        "outlet_count": 1,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "framing_group": "center",
                "articles": {
                    "id": "thin-hill-1",
                    "headline": "Senate Democrat calls for investigation into Texas drone incidents",
                    "summary": "Senate Democrat calls for investigation into Texas drone incidents.",
                    "body_text": "",
                    "metadata": {
                        "feed_summary": "Senate Democrat calls for investigation into Texas drone incidents.",
                        "extraction_quality": "rss_only",
                        "access_signal": "open",
                        "fetch_blocked": True,
                    },
                    "original_url": "https://thehill.com/example-drone-story",
                    "canonical_url": "https://thehill.com/example-drone-story",
                    "outlets": {"canonical_name": "The Hill"},
                },
            },
        ],
    }
    thin_placeholder_brief = build_grounded_brief(thin_placeholder_cluster)
    thin_support = thin_placeholder_brief["metadata"]["section_support"]["paragraphs"]
    if not thin_placeholder_brief["source_snapshot"] or not thin_support or not thin_support[0].get("support"):
        raise SystemExit(f"expected thin placeholder brief to retain source snapshot and support refs, got {thin_placeholder_brief}")
    thin_placeholder_quality = evaluate_story_quality(thin_placeholder_cluster, thin_placeholder_brief)
    if thin_placeholder_quality["review_priority"] == "critical":
        raise SystemExit(f"expected thin placeholder early brief to avoid critical quality failure, got {thin_placeholder_quality}")

    metadata_summary_brief = build_grounded_brief(
        {
            "canonical_headline": "Georgia lawmakers grill former special prosecutor Nathan Wade over Trump election case",
            "summary": "State senators on Friday grilled the former special prosecutor who led the Georgia election interference case against President Donald Trump about communications his team had with federal investigators.",
            "topic_label": "Politics",
            "outlet_count": 1,
            "cluster_key_facts": [],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "id": "metadata-summary-1",
                        "headline": "Georgia lawmakers grill former special prosecutor Nathan Wade over Trump election case",
                        "summary": "State senators on Friday grilled the former special prosecutor who led the Georgia election interference case against President Donald Trump about communications his team had with federal investigators. But their efforts were largely frustrated by his repeated assertions that he couldn't remember details.",
                        "body_text": "",
                        "metadata": {
                            "feed_summary": "State senators on Friday grilled the former special prosecutor who led the Georgia election interference case against President Donald Trump about communications his team had with federal investigators.",
                            "extraction_quality": "metadata_description",
                            "access_signal": "open",
                            "named_entities": ["State", "Georgia", "President Donald Trump"],
                        },
                        "original_url": "https://example.com/georgia-brief",
                        "canonical_url": "https://example.com/georgia-brief",
                        "outlets": {"canonical_name": "PBS NewsHour"},
                    },
                }
            ],
        }
    )
    if len(metadata_summary_brief["paragraphs"]) < 3 or "couldn't remember details" not in metadata_summary_brief["paragraphs"][1]:
        raise SystemExit(f"expected metadata-summary brief to pull a second narrative paragraph, got {metadata_summary_brief}")

    watch_reuters_headline = "Reserve release aims to steady oil prices as shipping routes stay under scrutiny"
    watch_ap_headline = "Reserve move calms traders while shipping disruption risks remain"
    watch_reuters_snippet = "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny."
    watch_ap_snippet = "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened."

    full_watch_cluster = {
        "canonical_headline": "Reserve move calms oil markets while disruption risk remains",
        "summary": "Reuters and Associated Press both said the reserve move was meant to steady oil markets while shipping risks stayed in focus.",
        "topic_label": "Business",
        "outlet_count": 2,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "framing_group": "center",
                "articles": quality_article(
                    article_id="watch-a1",
                    outlet="Reuters",
                    headline=watch_reuters_headline,
                    summary=watch_reuters_snippet,
                    body_text=(
                        "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny. "
                        "Reuters reported that traders were watching tanker insurance costs and reserve policy for the next signal. "
                        "Analysts said the move was meant to calm markets without implying the disruption was over."
                    ),
                ),
            },
            {
                "rank_in_cluster": 2,
                "framing_group": "center",
                "articles": quality_article(
                    article_id="watch-a2",
                    outlet="Associated Press",
                    headline=watch_ap_headline,
                    summary=watch_ap_snippet,
                    body_text=(
                        "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened. "
                        "The report said shipping markets were still sensitive to tanker routing and port access. "
                        "Officials described the reserve step as a near-term stabilizer rather than a lasting solution."
                    ),
                ),
            },
        ],
    }
    full_watch_brief = build_grounded_brief(full_watch_cluster)
    if full_watch_brief["metadata"]["section_grounding_mode"]["what_to_watch"] != "scaffold":
        raise SystemExit(f"expected generic what-to-watch copy to be scaffolded, got {full_watch_brief}")

    npr_like_cluster = {
        "id": "cluster-npr-like",
        "slug": "npr-like-early",
        "canonical_headline": "Judge blocks DOJ's criminal probe of Federal Reserve",
        "summary": "A federal judge has put the brakes on a criminal probe of the Federal Reserve, saying it was part of an improper campaign by the Trump administration to pressure the central bank into cutting interest rates.",
        "topic_label": "Politics",
        "latest_event_at": "2026-03-14T15:00:00Z",
        "outlet_count": 1,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "framing_group": "center",
                "articles": quality_article(
                    article_id="npr-like-a1",
                    outlet="NPR",
                    headline="Judge blocks DOJ's criminal probe of Federal Reserve, blasting it as political",
                    summary="A federal judge put the brakes on the Justice Department's criminal probe of the Federal Reserve, saying it was part of an improper campaign by the Trump administration to pressure the central bank into cutting interest rates more aggressively.",
                    body_text=(
                        "A federal judge put the brakes on the Justice Department's criminal probe of the Federal Reserve, saying it was part of an improper campaign by the Trump administration to pressure the central bank into cutting interest rates more aggressively. "
                        "Judge James Boasberg quashed subpoenas that had been issued to the Fed in January, ostensibly seeking information about cost overruns on the renovation of the Fed's headquarters. "
                        "At the time, Fed chairman Jerome Powell had called that a pretext. "
                        "\"The Government has offered no evidence whatsoever that Powell committed any crime other than displeasing the President,\" Boasberg wrote."
                    ),
                ),
            },
        ],
    }
    npr_like_brief = build_grounded_brief(npr_like_cluster)
    npr_like_quality = evaluate_story_quality(npr_like_cluster, npr_like_brief)
    if any(flag["code"] == "duplicate_paragraphs" for flag in npr_like_quality["flags"]):
        raise SystemExit(f"expected early opener dedupe to avoid duplicate paragraph warning, got {npr_like_quality}")

    live_update_cluster = {
        "canonical_headline": "Trump says Iran is totally defeated as war reaches 2-week mark",
        "summary": "President Trump's comments came shortly after he said that the U.S. military had conducted one of the most powerful bombing raids on a vital Iranian oil hub.",
        "topic_label": "World",
        "outlet_count": 1,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "framing_group": "center",
                "articles": quality_article(
                    article_id="live-update-a1",
                    outlet="CBS News",
                    headline="Trump says Iran is totally defeated as war reaches 2-week mark",
                    summary="President Trump said Friday night that Iran had plans of taking over the entire Middle East and completely obliterating Israel.",
                    body_text=(
                        "President Trump said Friday night that Iran had plans of taking over the entire Middle East and completely obliterating Israel. "
                        "Ohio Gov. Mike DeWine said Friday that three of the six U.S. service members killed in Iraq were from Ohio. "
                        "The update kept the focus on the running conflict timeline."
                    ),
                ),
            }
        ],
    }
    live_update_brief = build_grounded_brief(live_update_cluster)
    if not live_update_brief["paragraphs"][0].startswith("President Trump said Friday night that Iran"):
        raise SystemExit(f"expected one-source opening to prefer the cleaner source sentence, got {live_update_brief}")
    if any("Ohio Gov. Mike DeWine" in paragraph for paragraph in live_update_brief["paragraphs"]):
        raise SystemExit(f"expected live-update detail selection to ignore unrelated later updates, got {live_update_brief}")

    transcript_cluster = {
        "canonical_headline": "More Marines heading to Middle East as U.S. continues relentless strikes on Iran",
        "summary": "Around 2,500 U.S. Marines are heading for the Middle East, along with a Navy amphibious warship. Their mission is not yet clear, but it signals a marked increase in U.S. forces in the region.",
        "topic_label": "World",
        "outlet_count": 1,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "framing_group": "center",
                "articles": quality_article(
                    article_id="transcript-a1",
                    outlet="PBS NewsHour",
                    headline="More Marines heading to Middle East as U.S. continues relentless strikes on Iran",
                    summary="Around 2,500 U.S. Marines are heading for the Middle East, along with a Navy amphibious warship. Their mission is not yet clear, but it signals a marked increase in U.S. forces in the region.",
                    body_text=(
                        "Around 2,500 U.S. Marines are heading for the Middle East, along with a Navy amphibious warship. "
                        "Their mission is not yet clear, but it signals a marked increase in U.S. forces in the region. "
                        "The deployment comes as the Pentagon said more than 15,000 targets had been struck in Iran over nearly two weeks of relentless bombing against the regime. "
                        "Notice: Transcripts are machine and human generated and lightly edited for accuracy. They may contain errors."
                    ),
                ),
            }
        ],
    }
    transcript_brief = build_grounded_brief(transcript_cluster)
    if any("machine and human generated" in paragraph.lower() for paragraph in transcript_brief["paragraphs"]):
        raise SystemExit(f"expected transcript boilerplate to stay out of early brief paragraphs, got {transcript_brief}")
    if len(transcript_brief["paragraphs"]) > 1 and transcript_brief["paragraphs"][1].startswith("Their mission is not yet clear"):
        raise SystemExit(f"expected detail paragraph to avoid repeating opening sentences, got {transcript_brief}")
    if any("machine and human generated" in snapshot.get("used_snippet", "").lower() for snapshot in transcript_brief["source_snapshot"]):
        raise SystemExit(f"expected source snapshot excerpt to filter transcript boilerplate, got {transcript_brief}")

    focused_full_brief = build_grounded_brief(
        {
            "canonical_headline": "Trump says Iran is totally defeated as war reaches 2-week mark",
            "summary": "President Trump said Friday night that Iran had plans of taking over the entire Middle East and completely obliterating Israel.",
            "topic_label": "World",
            "outlet_count": 2,
            "cluster_key_facts": [],
            "correction_events": [],
            "cluster_articles": [
                {
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": quality_article(
                        article_id="focus-a1",
                        outlet="CBS News",
                        headline="Trump says Iran is totally defeated as war reaches 2-week mark",
                        summary="President Trump said Friday night that Iran had plans of taking over the entire Middle East and completely obliterating Israel.",
                        body_text=(
                            "President Trump said Friday night that Iran had plans of taking over the entire Middle East and completely obliterating Israel. "
                            "CBS News also noted that Ohio officials identified three of the service members killed in the crash in Iraq. "
                            "The update kept the focus on the running conflict timeline."
                        ),
                    ),
                },
                {
                    "rank_in_cluster": 2,
                    "framing_group": "center",
                    "articles": {
                        **quality_article(
                            article_id="focus-a2",
                            outlet="The Hill",
                            headline="Trump says Iran is totally defeated and wants a deal",
                            summary="President Trump late on Friday declared that Iran is totally defeated and wants a deal with the United States.",
                            body_text=(
                                "President Trump late on Friday declared that Iran is totally defeated and wants a deal with the United States. "
                                "Trump wrote that the latest strike had obliterated every military target on Kharg Island. "
                                "The Hill spent more time on Trump's negotiating posture after the strike."
                            ),
                        ),
                        "metadata": {
                            "feed_summary": "President Trump late on Friday declared that Iran is totally defeated and wants a deal with the United States.",
                            "extraction_quality": "article_body",
                            "access_signal": "open",
                            "named_entities": ["President Trump", "Iran", "Truth Social"],
                        },
                    },
                },
            ],
        }
    )
    if "president and trump" in focused_full_brief["paragraphs"][-1].lower():
        raise SystemExit(f"expected focus phrasing to avoid 'president and trump', got {focused_full_brief}")

    mixed_access_cluster = {
        "id": "cluster-mixed-access",
        "slug": "mixed-access-full",
        "canonical_headline": "Officials use reserve policy to steady oil markets",
        "summary": "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny.",
        "topic_label": "Business",
        "latest_event_at": "2026-03-14T16:00:00Z",
        "outlet_count": 2,
        "cluster_key_facts": [],
        "correction_events": [],
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "articles": quality_article(
                    article_id="mixed-open-a1",
                    outlet="Reuters",
                    headline=watch_reuters_headline,
                    summary=watch_reuters_snippet,
                    body_text=(
                        "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny. "
                        "Reuters reported that traders were watching tanker insurance costs and reserve policy for the next signal. "
                        "Analysts said the move was meant to calm markets without implying the disruption was over."
                    ),
                ),
            },
            {
                "rank_in_cluster": 2,
                "articles": {
                    **quality_article(
                        article_id="mixed-paywalled-a2",
                        outlet="Financial Times",
                        headline="Reserve move steadies markets as shipping risks persist",
                        summary="Financial Times said the reserve move steadied markets as officials monitored shipping disruptions.",
                        body_text=(
                            "Financial Times said the reserve move steadied markets as officials monitored shipping disruptions. "
                            "The report said traders were watching tanker insurance and port access for the next signal. "
                            "Officials described the move as a near-term stabilizer rather than a lasting solution."
                        ),
                    ),
                    "metadata": {
                        "feed_summary": "Financial Times said the reserve move steadied markets as officials monitored shipping disruptions.",
                        "extraction_quality": "article_body",
                        "access_signal": "likely_paywalled",
                    },
                },
            },
        ],
    }
    mixed_access_brief = build_grounded_brief(mixed_access_cluster)
    mixed_access_quality = evaluate_story_quality(mixed_access_cluster, mixed_access_brief)
    if any(flag["code"] == "missing_open_alternate" for flag in mixed_access_quality["flags"]):
        raise SystemExit(f"expected mixed-access full brief without extra open source to avoid alternate warning, got {mixed_access_quality}")

    if infer_thehill_post_id("https://thehill.com/regulation/court-battles/5783614-cfpb-consumer-watchdog-trump-vought") != "5783614":
        raise SystemExit("expected second The Hill URL shape to resolve its post id")

    reuters_headline = "Reserve release aims to steady oil prices as shipping routes stay under scrutiny"
    ap_headline = "Reserve move calms traders while shipping disruption risks remain"
    reuters_snippet = "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny."
    ap_snippet = "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened."
    reuters_focus = "shipping routes and reserve policy"
    ap_focus = "trader reaction and disruption risk"

    quality_cluster_risk = {
        "id": "cluster-quality-risk",
        "slug": "oil-quality-risk",
        "canonical_headline": "Reserve release aims to steady oil prices",
        "summary": reuters_snippet,
        "latest_event_at": "2026-03-14T12:00:00Z",
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "articles": quality_article(
                    article_id="risk-a1",
                    outlet="Reuters",
                    headline=reuters_headline,
                    summary=reuters_snippet,
                    body_text=(
                        "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny. "
                        "Reuters reported that traders were watching tanker insurance costs and reserve policy for the next signal. "
                        "Analysts said the move was meant to calm markets without implying the disruption was over. "
                        "Energy desks said another reserve step would depend on whether the route closures widened."
                    ),
                ),
            },
            {
                "rank_in_cluster": 2,
                "articles": quality_article(
                    article_id="risk-a2",
                    outlet="Associated Press",
                    headline=ap_headline,
                    summary=ap_snippet,
                    body_text=(
                        "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened. "
                        "The report said shipping markets were still sensitive to tanker routing and port access. "
                        "Officials described the reserve step as a near-term stabilizer rather than a lasting solution. "
                        "Traders said the next major signal would be whether the shipping disruption spread further."
                    ),
                ),
            },
        ],
    }
    risk_reuters_ref = quality_ref(
        article_id="risk-a1",
        outlet="Reuters",
        headline=reuters_headline,
        snippet=reuters_snippet,
        focus=reuters_focus,
    )
    quality_risk_brief = {
        "cluster_id": "cluster-quality-risk",
        "revision_tag": "brief-risk-1",
        "status": "full",
        "title": "The story so far",
        "paragraphs": [
            reuters_snippet,
            reuters_snippet,
        ],
        "why_it_matters": "Reuters said the reserve release could steady oil prices while shipping routes stayed under scrutiny.",
        "where_sources_agree": "Reuters said the reserve release could steady oil prices while shipping routes stayed under scrutiny.",
        "where_coverage_differs": "It is too early to call a real split in coverage. Reuters still has the clearest line on the sequence.",
        "what_to_watch": "Watch for the next turn: whether officials widen the reserve release.",
        "source_snapshot": [
            quality_snapshot(
                article_id="risk-a1",
                outlet="Reuters",
                headline=reuters_headline,
                snippet=reuters_snippet,
                focus=reuters_focus,
            ),
            quality_snapshot(
                article_id="risk-a2",
                outlet="Associated Press",
                headline=ap_headline,
                snippet=ap_snippet,
                focus=ap_focus,
            ),
        ],
        "metadata": {
            "full_brief_ready": True,
            "open_alternate_available": True,
            "section_support": {
                "paragraphs": [
                    {"index": 0, "support": [risk_reuters_ref]},
                    {"index": 1, "support": [risk_reuters_ref]},
                ],
                "why_it_matters": [risk_reuters_ref],
                "where_sources_agree": [risk_reuters_ref],
                "where_coverage_differs": [risk_reuters_ref],
                "what_to_watch": [],
            },
        },
    }
    risk_quality = evaluate_story_quality(quality_cluster_risk, quality_risk_brief)
    if risk_quality["review_priority"] != "critical":
        raise SystemExit(f"expected risky brief quality review to be critical, got {risk_quality}")
    risk_flag_codes = {flag["code"] for flag in risk_quality["flags"]}
    for expected_flag in {
        "full_brief_single_outlet_support",
        "duplicate_paragraphs",
        "full_brief_limited_article_body_support",
        "full_brief_uses_early_split_boilerplate",
    }:
        if expected_flag not in risk_flag_codes:
            raise SystemExit(f"expected risky brief quality flags to include {expected_flag}, got {risk_flag_codes}")

    quality_cluster_control = {
        "id": "cluster-quality-control",
        "slug": "oil-quality-control",
        "canonical_headline": "Reserve move calms oil markets while disruption risk remains",
        "summary": "Reuters and Associated Press both said the reserve move was meant to steady oil markets while shipping risks stayed in focus.",
        "latest_event_at": "2026-03-14T13:00:00Z",
        "cluster_articles": [
            {
                "rank_in_cluster": 1,
                "articles": quality_article(
                    article_id="control-a1",
                    outlet="Reuters",
                    headline=reuters_headline,
                    summary=reuters_snippet,
                    body_text=(
                        "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny. "
                        "Reuters reported that traders were watching tanker insurance costs and reserve policy for the next signal. "
                        "Analysts said the move was meant to calm markets without implying the disruption was over. "
                        "Energy desks said another reserve step would depend on whether the route closures widened."
                    ),
                ),
            },
            {
                "rank_in_cluster": 2,
                "articles": quality_article(
                    article_id="control-a2",
                    outlet="Associated Press",
                    headline=ap_headline,
                    summary=ap_snippet,
                    body_text=(
                        "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened. "
                        "The report said shipping markets were still sensitive to tanker routing and port access. "
                        "Officials described the reserve step as a near-term stabilizer rather than a lasting solution. "
                        "Traders said the next major signal would be whether the shipping disruption spread further."
                    ),
                ),
            },
        ],
    }
    control_reuters_ref = quality_ref(
        article_id="control-a1",
        outlet="Reuters",
        headline=reuters_headline,
        snippet=reuters_snippet,
        focus=reuters_focus,
    )
    control_ap_ref = quality_ref(
        article_id="control-a2",
        outlet="Associated Press",
        headline=ap_headline,
        snippet=ap_snippet,
        focus=ap_focus,
    )
    quality_control_brief = {
        "cluster_id": "cluster-quality-control",
        "revision_tag": "brief-control-1",
        "status": "full",
        "title": "The story so far",
        "paragraphs": [
            "Officials said the reserve release could steady oil prices while shipping routes stayed under scrutiny.",
            "Associated Press said the move was meant to calm traders while officials watched whether the disruption widened.",
        ],
        "why_it_matters": "Reuters and Associated Press both describe the reserve move as a near-term stabilizer for oil markets.",
        "where_sources_agree": "Reuters and Associated Press agree that officials are using reserve policy to limit the market shock.",
        "where_coverage_differs": "Reuters focuses more on shipping routes, while Associated Press spends more time on trader reaction to the reserve move.",
        "what_to_watch": "Watch for the next turn: whether the shipping disruption widens and forces another reserve release.",
        "source_snapshot": [
            quality_snapshot(
                article_id="control-a1",
                outlet="Reuters",
                headline=reuters_headline,
                snippet=reuters_snippet,
                focus=reuters_focus,
            ),
            quality_snapshot(
                article_id="control-a2",
                outlet="Associated Press",
                headline=ap_headline,
                snippet=ap_snippet,
                focus=ap_focus,
            ),
        ],
        "metadata": {
            "full_brief_ready": True,
            "open_alternate_available": False,
            "section_support": {
                "paragraphs": [
                    {"index": 0, "support": [control_reuters_ref]},
                    {"index": 1, "support": [control_ap_ref]},
                ],
                "why_it_matters": [control_reuters_ref, control_ap_ref],
                "where_sources_agree": [control_reuters_ref, control_ap_ref],
                "where_coverage_differs": [control_reuters_ref, control_ap_ref],
                "what_to_watch": [],
            },
        },
    }
    control_quality = evaluate_story_quality(quality_cluster_control, quality_control_brief)
    if control_quality["review_priority"] != "pass":
        raise SystemExit(f"expected healthy brief quality review to pass, got {control_quality}")

    quality_report = build_quality_report([risk_quality, control_quality], limit=2, control_count=1)
    report_priorities = [story["review_priority"] for story in quality_report["stories"]]
    if report_priorities != ["critical", "control"]:
        raise SystemExit(f"expected quality report sample to include one critical and one control story, got {report_priorities}")
    markdown_report = render_markdown_report(quality_report)
    if (
        "# Brief Quality Review" not in markdown_report
        or "`full_brief_single_outlet_support`" not in markdown_report
        or "/stories/oil-quality-control" not in markdown_report
    ):
        raise SystemExit(f"expected markdown brief-quality report to contain review details, got {markdown_report}")

    sitemap_fetch_url = normalize_feed_fetch_url(
        "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml&from=100"
    )
    if sitemap_fetch_url != "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml&from=100":
        raise SystemExit(f"unexpected sitemap fetch normalization result: {sitemap_fetch_url}")

    thin_quality = summary_quality_score(
        "Markets brace for tariff shock",
        "Markets brace for tariff shock",
        extraction_quality="rss_only",
    )
    rich_quality = summary_quality_score(
        "Markets brace for tariff shock",
        "Officials said the emergency move could slow the price spike, though analysts warned the disruption might outlast the first intervention.",
        extraction_quality="article_body",
        body_text="Officials said the emergency move could slow the price spike, though analysts warned the disruption might outlast the first intervention. Traders were watching shipping routes and reserve policy for the next signal.",
    )
    if thin_quality >= 6:
        raise SystemExit(f"expected thin summary to score poorly, got {thin_quality}")
    if rich_quality <= thin_quality:
        raise SystemExit(f"expected rich summary to outscore thin summary: {rich_quality} <= {thin_quality}")

    selected_summary, selected_score, substantive_sources = choose_story_summary(
        [
            {
                "source": "Bloomberg",
                "title": "Markets brace for tariff shock",
                "summary": "Markets brace for tariff shock",
                "feed_summary": "Markets brace for tariff shock",
                "lede": "Markets brace for tariff shock",
                "body_preview": "",
                "extraction_quality": "rss_only",
            },
            {
                "source": "Reuters",
                "title": "Emergency reserve release aims to steady oil prices",
                "summary": "Officials said the emergency move could slow the price spike, though analysts warned the disruption might outlast the first intervention.",
                "feed_summary": "Emergency reserve release aims to steady oil prices.",
                "lede": "Officials said the emergency move could slow the price spike, though analysts warned the disruption might outlast the first intervention.",
                "body_preview": "Officials said the emergency move could slow the price spike, though analysts warned the disruption might outlast the first intervention. Traders were watching shipping routes and reserve policy for the next signal.",
                "extraction_quality": "article_body",
            },
        ],
        "Markets brace for tariff shock",
        ["Bloomberg", "Reuters"],
    )
    if "Officials said the emergency move could slow the price spike" not in selected_summary:
        raise SystemExit(f"unexpected selected story summary: {selected_summary}")

    aligned_summary, aligned_score, _aligned_sources = choose_story_summary(
        [
            {
                "source": "Reuters",
                "title": "UAE's Fujairah stops some oil loading operations after drone attack",
                "summary": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, as Iran vowed retaliation following the U.S. strike on Kharg Island.",
                "feed_summary": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, as Iran vowed retaliation following the U.S. strike on Kharg Island.",
                "lede": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, as Iran vowed retaliation following the U.S. strike on Kharg Island.",
                "body_preview": "",
                "extraction_quality": "rss_only",
            },
            {
                "source": "CBS News",
                "title": "What to know about Kharg Island, the Iranian oil site struck by U.S.",
                "summary": "President Trump said the U.S. military totally obliterated every military target on Kharg Island during large-scale precision strikes Friday.",
                "feed_summary": "Kharg Island is a small, heavily fortified, and strategically valuable island off Iran's northern coast.",
                "lede": "President Trump said the U.S. military totally obliterated every military target on Kharg Island during large-scale precision strikes Friday.",
                "body_preview": "President Trump said the U.S. military totally obliterated every military target on Kharg Island during large-scale precision strikes Friday. The island remains central to Iranian oil exports.",
                "extraction_quality": "article_body",
            },
        ],
        "Fire at UAE oil hub as Iran vows retaliation for US attack on Kharg Island",
        ["Reuters", "CBS News"],
    )
    if "Some oil-loading operations have been suspended in Fujairah" not in aligned_summary:
        raise SystemExit(f"expected story summary selection to stay aligned with the representative title, got {aligned_summary} ({aligned_score})")

    bio_filtered_summary, _bio_filtered_score, _bio_filtered_sources = choose_story_summary(
        [
            {
                "source": "Reuters",
                "title": "UAE's Fujairah stops some oil loading operations after drone attack",
                "summary": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, industry and trade sources said.",
                "feed_summary": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, industry and trade sources said.",
                "lede": "Some oil-loading operations have been suspended in Fujairah after a drone attack and fire, industry and trade sources said.",
                "body_preview": (
                    "Reporting by Sarah Example and Jane Example. Editing by Editor Example. "
                    "Our Standards: The Thomson Reuters Trust Principles. "
                    "Jane Example is an award-winning journalist covering the energy sector."
                ),
                "extraction_quality": "article_body",
            }
        ],
        "UAE's Fujairah stops some oil loading operations after drone attack",
        ["Reuters"],
    )
    if "Some oil-loading operations have been suspended in Fujairah" not in bio_filtered_summary:
        raise SystemExit(f"expected story summary selection to ignore misaligned author-bio body text, got {bio_filtered_summary}")
    if selected_score < 6 or substantive_sources != 1:
        raise SystemExit(
            f"unexpected story summary quality metrics: score={selected_score}, substantive_sources={substantive_sources}"
        )

    perspective_payload, _context_packs = build_perspective(
        {
            "topic_label": "Business",
            "canonical_headline": "Emergency reserve release aims to steady oil prices",
            "summary": "Oil reserve release aims to steady prices while markets watch shipping routes.",
            "cluster_key_facts": [
                {"fact_text": "Prism has 2 linked reports across 1 publishers in this story so far.", "sort_order": 0},
                {"fact_text": "Officials are using reserve releases to steady oil prices.", "sort_order": 1},
            ],
            "cluster_articles": [
                {
                    "article_id": "article-1",
                    "rank_in_cluster": 1,
                    "framing_group": "center",
                    "articles": {
                        "headline": "Emergency reserve release aims to steady oil prices",
                        "summary": "Oil reserve release aims to steady prices while markets watch shipping routes.",
                        "body_text": (
                            "Officials said the emergency reserve release could steady oil prices in the near term while traders watched shipping routes for new disruption signals. "
                            "Analysts said the intervention was designed to calm markets without suggesting the underlying shipping risk had faded. "
                            "Energy desks were also watching whether reserve policy would shift again if the disruption worsened."
                        ),
                        "metadata": {"extraction_quality": "article_body", "access_signal": "open"},
                        "outlets": {"canonical_name": "Reuters", "outlet_type": "wire"},
                    },
                },
                {
                    "article_id": "article-2",
                    "rank_in_cluster": 2,
                    "framing_group": "center",
                    "articles": {
                        "headline": "Oil prices ease after reserve move",
                        "summary": "Oil reserve release aims to steady prices while markets watch shipping routes.",
                        "body_text": (
                            "Traders said the reserve move briefly eased oil prices, though shipping markets remained sensitive to any signal of broader disruption. "
                            "Officials framed the step as a stabilizing move rather than a long-term answer to the supply shock. "
                            "Market watchers said the next useful signal would be whether the shipping disruption widened."
                        ),
                        "metadata": {"extraction_quality": "article_body", "access_signal": "open"},
                        "outlets": {"canonical_name": "Reuters", "outlet_type": "wire"},
                    },
                },
            ],
        }
    )
    if perspective_payload["status"] != "early":
        raise SystemExit(f"expected same-outlet perspective to stay early, got {perspective_payload['status']}")
    if "Prism has" in perspective_payload["summary"] or "linked reports" in perspective_payload["summary"]:
        raise SystemExit(f"expected perspective summary to avoid boilerplate focus, got {perspective_payload['summary']}")
    if current_revision_row_id(None) is not None:
        raise SystemExit("expected missing perspective current revision to resolve to None")
    if current_revision_row_id({"id": "current-perspective"}) != "current-perspective":
        raise SystemExit("expected current perspective revision id helper to return the row id when present")
    existing_revision_id = insert_perspective_revision_draft(
        ExistingPerspectiveDraftClient(),
        "cluster-1",
        "perspective-20260314020000",
        {
            "status": "ready",
            "input_signature": "signature-123",
            "source_snapshot": [],
            "summary": "Stored perspective summary.",
            "takeaways": [],
            "framing_presence": [],
            "source_family_presence": [],
            "scope_presence": [],
            "methodology_note": "Method note.",
            "metadata": {},
        },
    )
    if existing_revision_id != "existing-perspective-draft":
        raise SystemExit(
            f"expected perspective draft insert to reuse the existing revision id, got {existing_revision_id}"
        )
    existing_brief_revision_id = insert_brief_revision_draft(
        ExistingBriefDraftClient(),
        "cluster-1",
        "brief-20260314020000",
        {
            "status": "full",
            "label": "Prism Brief",
            "title": "Stored brief title",
            "input_signature": "brief-signature-123",
            "source_snapshot": [],
            "paragraphs": [],
            "why_it_matters": "Why this matters.",
            "where_sources_agree": "Agreement",
            "where_coverage_differs": "Differences",
            "what_to_watch": "Watch",
            "supporting_points": [],
            "metadata": {},
        },
    )
    if existing_brief_revision_id != "existing-brief-draft":
        raise SystemExit(
            f"expected brief draft insert to reuse the existing revision id, got {existing_brief_revision_id}"
        )

    for promote_revision in (promote_brief_revision_current_state, promote_perspective_revision_current_state):
        promotion_client = PromotionClient()
        try:
            promote_revision(promotion_client, "old-revision", "new-revision")
        except RuntimeError:
            pass
        else:
            raise SystemExit("expected promotion helper to raise on simulated promotion failure")

        if promotion_client.patches != [
            (promotion_client.patches[0][0], False),
            (promotion_client.patches[1][0], True),
            (promotion_client.patches[2][0], True),
        ]:
            raise SystemExit(f"unexpected promotion patch sequence: {promotion_client.patches}")
        if "id=eq.old-revision" not in promotion_client.patches[0][0]:
            raise SystemExit(f"expected first patch to clear old revision, got {promotion_client.patches}")
        if "id=eq.old-revision" not in promotion_client.patches[2][0]:
            raise SystemExit(f"expected failed promotion to restore old revision, got {promotion_client.patches}")

    fixture_cases = json.loads(FIXTURES_PATH.read_text())
    if len(fixture_cases) < 2:
        raise SystemExit("expected multiple clustering regression fixtures")
    for case in fixture_cases:
        fixture_items = [
            build_item(
                source=item["source"],
                title=item["title"],
                url=normalize_canonical_url(item["url"]),
                summary=item["summary"],
                tokens=set(item["tokens"]),
                event_tags=set(item["event_tags"]),
            )
            for item in case["items"]
        ]
        for fixture_item, fixture_source in zip(fixture_items, case["items"], strict=True):
            fixture_item.lede = fixture_source["lede"]
            fixture_item.body_preview = fixture_source["body_preview"]
            fixture_item.named_entities = fixture_source["named_entities"]
            fixture_item.extraction_quality = "article_body"

        cluster_groups = sorted(sorted(entry.url for entry in cluster) for cluster in cluster_items(fixture_items))
        expected_groups = sorted(sorted(group) for group in case["expected_cluster_groups"])
        if cluster_groups != expected_groups:
            raise SystemExit(f"fixture cluster mismatch for {case['name']}: {cluster_groups}")

        fixture_neighbors, _fixture_similarities = build_similarity_lookup(fixture_items)
        for url, expected_neighbors in case.get("expected_neighbors", {}).items():
            actual_neighbors = fixture_neighbors.get(url, [])
            if actual_neighbors[: len(expected_neighbors)] != expected_neighbors:
                raise SystemExit(
                    f"fixture neighbor mismatch for {case['name']} / {url}: {actual_neighbors}"
                )

    print("Python pipeline smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
