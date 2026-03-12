#!/usr/bin/env python3

from __future__ import annotations

import json

from generate_story_briefs_to_supabase import main as brief_generation_main
from enrich_articles_to_supabase import main as enrich_main
from ingest_live_feeds_to_supabase import main as ingest_main


def main() -> int:
    print(json.dumps({"stage": "ingest_feeds"}, indent=2))
    ingest_exit_code = ingest_main()
    if ingest_exit_code != 0:
        return ingest_exit_code

    print(json.dumps({"stage": "enrich_articles"}, indent=2))
    enrich_exit_code = enrich_main()
    if enrich_exit_code != 0:
        return enrich_exit_code

    print(json.dumps({"stage": "generate_grounded_briefs"}, indent=2))
    brief_generation_exit_code = brief_generation_main()
    if brief_generation_exit_code != 0:
        return brief_generation_exit_code

    print(json.dumps({"stage": "complete"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
