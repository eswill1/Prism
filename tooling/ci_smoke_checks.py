#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from datetime import UTC, datetime, timedelta


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
    )
    from tooling.enrich_articles_to_supabase import merge_article_metadata
    from tooling.generate_temporary_live_feed import (
        FeedItem,
        classify_fetch_block,
        choose_story_summary,
        cluster_items,
        detect_fetch_block,
        normalize_feed_fetch_url,
        summary_quality_score,
    )
    from tooling.local_ingest_runtime import build_launchd_plist, choose_due_job
    from tooling.semantic_story_candidates import build_similarity_lookup
    from tooling.url_normalization import normalize_canonical_url
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from generate_perspective_to_supabase import build_perspective, current_revision_row_id, insert_perspective_revision_draft, promote_revision_current_state as promote_perspective_revision_current_state
    from generate_story_briefs_to_supabase import build_grounded_brief, insert_brief_revision_draft, promote_revision_current_state as promote_brief_revision_current_state
    from enrich_articles_to_supabase import merge_article_metadata
    from generate_temporary_live_feed import FeedItem, classify_fetch_block, choose_story_summary, cluster_items, detect_fetch_block, normalize_feed_fetch_url, summary_quality_score
    from local_ingest_runtime import build_launchd_plist, choose_due_job
    from semantic_story_candidates import build_similarity_lookup
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
