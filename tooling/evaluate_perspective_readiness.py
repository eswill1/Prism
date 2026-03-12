#!/usr/bin/env python3

from __future__ import annotations

import json

from sync_story_content import REST_BASE, SUPABASE_SERVICE_ROLE_KEY, SupabaseRestClient


MAX_STORIES = 12


def main() -> int:
    client = SupabaseRestClient(REST_BASE, SUPABASE_SERVICE_ROLE_KEY)
    perspective_rows = client.get(
        "/story_perspective_revisions?select=cluster_id,revision_tag,status,metadata&is_current=eq.true&limit=200"
    ) or []
    perspective_by_cluster = {row["cluster_id"]: row for row in perspective_rows if row.get("cluster_id")}
    context_rows = client.get(
        "/context_pack_items?select=cluster_id,lens,article_id&limit=500"
    ) or []

    lens_counts_by_cluster: dict[str, dict[str, int]] = {}
    for row in context_rows:
        cluster_id = row.get("cluster_id")
        lens = row.get("lens")
        if not cluster_id or not lens:
            continue
        cluster_counts = lens_counts_by_cluster.setdefault(cluster_id, {})
        cluster_counts[lens] = cluster_counts.get(lens, 0) + 1

    rows = client.get(
        "/story_clusters?select=id,slug,canonical_headline,latest_event_at,metadata&order=latest_event_at.desc&limit=40"
    ) or []

    stories = []
    for row in rows:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("story_origin") not in ("automated_feed_ingestion", "live_snapshot"):
            continue

        revision = perspective_by_cluster.get(row["id"])
        lens_counts = lens_counts_by_cluster.get(row["id"], {})
        stories.append(
            {
                "slug": row["slug"],
                "title": row["canonical_headline"],
                "stored_perspective_current": bool(revision),
                "stored_perspective_status": (revision or {}).get("status"),
                "stored_perspective_revision_tag": (revision or {}).get("revision_tag"),
                "lens_counts": lens_counts,
                "all_launch_lenses_populated": all(
                    lens_counts.get(lens, 0) >= 1
                    for lens in (
                        "balanced_framing",
                        "evidence_first",
                        "local_impact",
                        "international_comparison",
                    )
                ),
            }
        )

    print(json.dumps({"stories": stories[:MAX_STORIES]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
