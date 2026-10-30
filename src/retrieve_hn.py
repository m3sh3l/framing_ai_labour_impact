"""Retrieve Hacker News stories via Algolia search API (no auth required).

Redesign (2026-07-13): runs every query group from config (the API is free and
fast, so HN gets the full keyword net) plus date-bounded event pulls (RQ4).
Each story records ALL groups/queries that matched it (merged in-memory here,
since the whole crawl fits one run) as matched_queries / query_groups /
event_tags lists. Filtering/stratification happens in filter_clean.py.

Strategy per query: paginate backwards on created_at_i (search_by_date +
numericFilters cursor), dedupe by story id across queries.

Schema validated against live API on 2026-07-09.
"""
from utils import ROOT, load_config, window, epoch, get_json, save_jsonl, hash_username, log
import queries as Q

API = "https://hn.algolia.com/api/v1/search_by_date"
FIELDS = "objectID,title,story_text,url,created_at_i,points,num_comments,author"


def fetch_query(query: str, start_i: int, end_i: int) -> list[dict]:
    items, upper = [], end_i
    while True:
        data = get_json(API, {
            "query": query,
            "tags": "story",
            "hitsPerPage": 1000,
            "numericFilters": f"created_at_i>{start_i},created_at_i<{upper}",
            "attributesToRetrieve": FIELDS,
            "attributesToHighlight": "",
        })
        if not data or not data.get("hits"):
            break
        hits = data["hits"]
        items.extend(hits)
        log.info("  %-40s +%4d hits (total %d)", query[:40], len(hits), len(items))
        if len(hits) < 1000:
            break
        upper = min(h["created_at_i"] for h in hits)  # page backwards
    return items


def merge_hit(store: dict, h: dict, salt: str, query: str, group: str, event: str | None):
    sid = h["objectID"]
    if sid not in store:
        store[sid] = {
            "source": "hackernews",
            "id": f"hn_{sid}",
            "created_utc": h["created_at_i"],
            "title": h.get("title") or "",
            "text": h.get("story_text") or "",
            "url": h.get("url") or "",
            "score": h.get("points") or 0,
            "num_comments": h.get("num_comments") or 0,
            "author_hash": hash_username(h.get("author", ""), salt),
            "matched_queries": [],
            "query_groups": [],
            "event_tags": [],
        }
    it = store[sid]
    if query not in it["matched_queries"]:
        it["matched_queries"].append(query)
    if group not in it["query_groups"]:
        it["query_groups"].append(group)
    if event and event not in it["event_tags"]:
        it["event_tags"].append(event)


def main():
    cfg = load_config()
    start, end = window(cfg)
    start_i, end_i = epoch(start), epoch(end) + 86400
    salt = cfg.get("hash_salt", "")   # withheld from the shared config

    store: dict[str, dict] = {}
    for group, qs in Q.load_groups(cfg).items():
        log.info("HN group: %s (%d queries)", group, len(qs))
        for q in qs:
            for h in fetch_query(Q.hn_query(q), start_i, end_i):
                merge_hit(store, h, salt, q, group, None)

    for ev in Q.event_windows(cfg):
        log.info("HN event: %s (%d terms)", ev["name"], len(ev["terms"]))
        for term in ev["terms"]:
            for h in fetch_query(Q.hn_query(term), ev["start_i"], ev["end_i"]):
                merge_hit(store, h, salt, term, "event", ev["name"])

    save_jsonl(list(store.values()), ROOT / cfg["paths"]["raw"] / "hackernews_raw.jsonl")


if __name__ == "__main__":
    main()
