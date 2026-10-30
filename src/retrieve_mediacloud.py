"""Retrieve news headlines via the MediaCloud API (requires free API key).

Setup:
  1. Register at https://search.mediacloud.org -> profile -> API key
  2. export MC_API_KEY="your-key"
  3. python src/retrieve_mediacloud.py --list-collections   # confirm collection IDs
  4. fill config.yaml mediacloud.collections, then: python src/retrieve_mediacloud.py

Redesign (2026-07-13): per collection category we now run
  - the broad base_query (tagged query group "core", the frame-neutral pull),
  - one OR-of-phrases boolean per frame-loaded query group,
  - date-bounded event queries (RQ4), tagged event_tags.
Stories found by several queries are merged in-memory (tags unioned).

Headline-only mode (proposal §4.2): we store title, date, outlet, url only.
"""
import argparse
import os
import sys
import time
from datetime import date, timedelta

import mediacloud.api

from utils import ROOT, load_config, window, save_jsonl, log
import queries as Q

TIMEOUT_SECS = 300   # broad boolean queries over year-scale windows exceed the SDK's 60s default
RETRIES = 3


def client() -> mediacloud.api.SearchApi:
    key = os.environ.get("MC_API_KEY")
    if not key:
        sys.exit("Set MC_API_KEY first (see docstring).")
    api = mediacloud.api.SearchApi(key)
    api.TIMEOUT_SECS = TIMEOUT_SECS
    return api


def list_collections():
    key = os.environ.get("MC_API_KEY")
    d = mediacloud.api.DirectoryApi(key)
    for name in ["United States - National", "United Kingdom - National",
                 "business", "technology"]:
        found = d.collection_list(name=name)
        for c in found.get("results", [])[:8]:
            print(f"{c['id']:>12}  {c['name']}  ({c.get('platform', '?')})")
        print("-" * 60)


def half_year_chunks(start: date, end: date):
    """Split [start, end] into half-year spans, cheaper per request than one
    multi-year query, and a slow chunk only re-fetches itself on retry."""
    cur = start
    while cur <= end:
        nxt = date(cur.year + (cur.month > 6), 7 if cur.month <= 6 else 1, 1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def fetch(search, query: str, start: date, end: date, coll_ids: list[int]) -> list[dict]:
    out = []
    for lo, hi in half_year_chunks(start, end):
        token, more = None, True
        while more:
            for attempt in range(RETRIES):
                try:
                    page, token = search.story_list(query, start_date=lo, end_date=hi,
                                                    collection_ids=coll_ids,
                                                    pagination_token=token)
                    break
                except Exception as e:
                    log.warning("story_list failed (%s..%s attempt %d): %s",
                                lo, hi, attempt + 1, e)
                    time.sleep(20 * (attempt + 1))
            else:
                log.error("Giving up on chunk %s..%s for this query", lo, hi)
                more = False
                continue
            out.extend(page)
            more = token is not None
    return out


def merge_story(store: dict, s: dict, category: str, query_label: str,
                group: str, event: str | None):
    sid = str(s["id"])
    if sid not in store:
        store[sid] = {
            "source": "mediacloud",
            "id": f"mc_{sid}",
            "created_utc": None,  # filled from publish_date in filter_clean
            "publish_date": str(s.get("publish_date") or ""),
            "title": s.get("title") or "",
            "text": "",
            "url": s.get("url") or "",
            "outlet": s.get("media_name") or "",
            "outlet_category": category,
            "language": s.get("language") or "",
            "matched_queries": [],
            "query_groups": [],
            "event_tags": [],
        }
    it = store[sid]
    if query_label not in it["matched_queries"]:
        it["matched_queries"].append(query_label)
    if group not in it["query_groups"]:
        it["query_groups"].append(group)
    if event and event not in it["event_tags"]:
        it["event_tags"].append(event)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-collections", action="store_true")
    args = ap.parse_args()
    if args.list_collections:
        list_collections()
        return

    cfg = load_config()
    start, end = window(cfg)
    mc = cfg["mediacloud"]
    search = client()

    store: dict[str, dict] = {}
    for category, ids in mc["collections"].items():
        if not ids:
            log.warning("No collection IDs for %s - skipping (see --list-collections)", category)
            continue

        log.info("%s: base query (group=core)", category)
        for s in fetch(search, mc["base_query"], start, end, ids):
            merge_story(store, s, category, "base_query", "core", None)

        for group, terms in Q.load_groups(cfg).items():
            if group == "core":
                continue  # base_query is the core pull
            q = Q.mediacloud_group_query(terms)
            log.info("%s: group %s", category, group)
            for s in fetch(search, q, start, end, ids):
                merge_story(store, s, category, f"group:{group}", group, None)

        for ev in Q.event_windows(cfg):
            q = Q.mediacloud_group_query(ev["terms"])
            log.info("%s: event %s", category, ev["name"])
            for s in fetch(search, q, ev["start"], ev["end"], ids):
                merge_story(store, s, category, f"event:{ev['name']}", "event", ev["name"])

        log.info("%s done: %d unique stories so far", category, len(store))

    save_jsonl(list(store.values()), ROOT / cfg["paths"]["raw"] / "mediacloud_raw.jsonl")


if __name__ == "__main__":
    main()
