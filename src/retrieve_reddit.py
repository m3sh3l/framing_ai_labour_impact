"""Retrieve Reddit submissions via PullPush (Pushshift successor; no auth).

Redesign (2026-07-13): tiered subreddits + frame-tagged query groups.
  - CORE tier: every scoped query is run per half-year window (temporal
    coverage for RQ4).
  - EXTENDED tier: one full-window top-by-score sweep per scoped query
    (lighter supplementary pull).
  - EVENT pulls: date-bounded terms from config `events`, run over the
    core-tier categories in `event_categories`, tagged event_tags.

Every raw row records matched_queries/query_groups/event_tags (single-element
lists); the same post found by several queries appears as several rows and is
merged (tags unioned) in filter_clean.py. The raw file is an append-only log.

Crawl state: each completed (sub, query, window, event) cell is recorded in
data/state/reddit_done.log, so an interrupted run resumes with no lost work.

Rate limiting: adaptive (base 2s, doubles on 429 up to 60s, decays on
success). The fixed 1s pause in v1 caused silent zero-yield subreddits.

Ethics (proposal §8.1): moderator-removed/deleted posts are excluded;
usernames are hashed at retrieval and never stored raw.
"""
import argparse
import csv
from collections import Counter
from datetime import date, datetime, timezone

from utils import (ROOT, load_config, window, epoch, get_json_status,
                   append_jsonl, Checkpoint, Pacer, hash_username, half_year, log)
import queries as Q


def backend(cfg) -> tuple[str, str]:
    """(name, url) of the selected archive backend."""
    name = cfg["reddit"].get("backend", "pullpush")
    return name, cfg["reddit"]["backends"][name]


def search_params(backend_name: str, sub: str, q: str, lo: int, hi: int) -> dict:
    if backend_name == "arctic_shift":
        # no sort support: returns newest <=100 posts in window
        return {"subreddit": sub, "query": q, "limit": 100, "after": lo, "before": hi}
    return {"subreddit": sub, "q": q, "size": 100, "after": lo, "before": hi,
            "sort": "desc", "sort_type": "score"}


def half_year_windows(start: date, end: date):
    cur = date(start.year, 1 if start.month <= 6 else 7, 1)
    wins = []
    while cur <= end:
        nxt = date(cur.year + (cur.month == 7), 1 if cur.month == 7 else 7, 1)
        wins.append((max(cur, start), min(nxt, end)))
        cur = nxt
    return wins


def is_removed(p: dict) -> bool:
    return (p.get("removed_by_category") is not None
            or p.get("selftext") in ("[removed]", "[deleted]"))


def all_subs(cfg):
    """[(subreddit, category, tier)] across both tiers."""
    out = []
    for tier in ("core", "extended"):
        for cat, subs in cfg["reddit"]["tiers"][tier].items():
            for sub in subs:
                out.append((sub, cat, tier))
    return out


# ---------------------------------------------------------------------------
# Preflight: verify PullPush actually indexes each configured subreddit
# (r/ArtificialIntelligence returns a clean zero; dead subs waste the budget
# and, worse, look like real absence of discourse).
# ---------------------------------------------------------------------------
def verify_subs(cfg):
    import sys
    import time
    bname, api = backend(cfg)
    log.info("verify-subs against backend: %s", bname)
    probe = ({"limit": 10} if bname == "arctic_shift" else {"size": 10, "sort": "desc"})
    report_path = ROOT / cfg["paths"]["meta"] / "subreddit_index_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for sub, cat, tier in all_subs(cfg):
        data, status = None, None
        for _ in range(3):
            data, status = get_json_status(api, {"subreddit": sub, **probe})
            if status == 200:
                break
            time.sleep(3)
        posts = (data or {}).get("data", [])
        newest = max((int(p.get("created_utc", 0)) for p in posts), default=0)
        newest_date = (datetime.fromtimestamp(newest, tz=timezone.utc).date().isoformat()
                       if newest else "")
        ok = status == 200
        # A sub is only DEAD on a clean empty answer; a non-200 means we
        # simply couldn't check (server outage must never mark subs dead).
        rows.append({"subreddit": sub, "category": cat, "tier": tier,
                     "status": "ok" if ok else f"http_{status or 'error'}",
                     "indexed": bool(posts) if ok else "",
                     "n_sample": len(posts),
                     "newest_utc": newest, "newest_date": newest_date})
        log.info("verify %-22s %-14s %s  newest=%s", sub, cat,
                 ("OK" if posts else "DEAD") if ok else f"UNREACHABLE({status})",
                 newest_date or "-")
    n_err = sum(1 for r in rows if r["status"] != "ok")
    if n_err > len(rows) // 2:
        sys.exit(f"PullPush appears to be DOWN ({n_err}/{len(rows)} probes failed) "
                 "- report NOT written; retry when the API is back")
    with open(report_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    log.info("Wrote %s (%d subs, %d dead, %d unreachable)", report_path, len(rows),
             sum(1 for r in rows if r["indexed"] is False), n_err)


def load_dead_subs(cfg) -> set[str]:
    report_path = ROOT / cfg["paths"]["meta"] / "subreddit_index_report.csv"
    if not report_path.exists():
        log.warning("No subreddit_index_report.csv - run --verify-subs first "
                    "(crawling all subs, dead ones will waste budget)")
        return set()
    with open(report_path) as f:
        return {r["subreddit"] for r in csv.DictReader(f)
                if r["status"] == "ok" and r["indexed"] == "False"}


# ---------------------------------------------------------------------------
# Cell construction: one cell = one API request's worth of crawl work.
# ---------------------------------------------------------------------------
def year_windows(start: date, end: date):
    cur = start
    while cur <= end:
        nxt = date(cur.year + 1, 1, 1)
        yield cur, min(nxt, end)
        cur = nxt


def build_cells(cfg) -> list[dict]:
    start, end = window(cfg)
    groups = Q.load_groups(cfg)
    wins = [(epoch(lo), epoch(hi)) for lo, hi in half_year_windows(start, end)]
    # extended tier: yearly windows preserve time-spread now that the backend
    # returns newest-first with no score sort (a single full-window pull would
    # only ever see the newest 100 posts)
    ext_wins = [(epoch(lo), epoch(hi)) for lo, hi in year_windows(start, end)]
    cells = []

    for cat, subs in cfg["reddit"]["tiers"]["core"].items():
        for sub in subs:
            for g in Q.core_scope(cfg, cat):
                for q in groups[g]:
                    for lo, hi in wins:
                        cells.append({"sub": sub, "cat": cat, "tier": "core",
                                      "group": g, "q": q, "lo": lo, "hi": hi,
                                      "event": None})

    for cat, subs in cfg["reddit"]["tiers"]["extended"].items():
        for sub in subs:
            for g in Q.extended_scope(cfg, cat):
                for q in groups[g]:
                    for lo, hi in ext_wins:
                        cells.append({"sub": sub, "cat": cat, "tier": "extended",
                                      "group": g, "q": q, "lo": lo, "hi": hi,
                                      "event": None})

    event_subs = [(sub, cat) for cat in cfg["reddit"]["event_categories"]
                  for sub in cfg["reddit"]["tiers"]["core"][cat]]
    for ev in Q.event_windows(cfg):
        for sub, cat in event_subs:
            for term in ev["terms"]:
                cells.append({"sub": sub, "cat": cat, "tier": "core",
                              "group": "event", "q": term,
                              "lo": ev["start_i"], "hi": ev["end_i"],
                              "event": ev["name"]})
    return cells


def cell_key(c: dict) -> str:
    return f"{c['sub']}|{c['q']}|{c['lo']}|{c['hi']}|{c['event'] or ''}"


def fetch_cell(c: dict, api: str, bname: str, pacer: Pacer, retries: int):
    """One paced request with adaptive 429 handling; returns post list or None."""
    for _ in range(retries):
        pacer.wait()
        data, status = get_json_status(
            api, search_params(bname, c["sub"], Q.pullpush_query(c["q"]), c["lo"], c["hi"]))
        if status == 429:
            pacer.backoff()
            continue
        if data is not None:
            pacer.success()
            return data.get("data", [])
        pacer.backoff()  # network error / non-200: slow down too
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-subs", action="store_true",
                    help="check PullPush indexing per configured subreddit, write report")
    ap.add_argument("--limit-cells", type=int, default=0,
                    help="stop after N not-yet-done cells (smoke testing)")
    args = ap.parse_args()

    cfg = load_config()
    if args.verify_subs:
        verify_subs(cfg)
        return

    rcfg = cfg["reddit"]
    salt = cfg.get("hash_salt", "")   # withheld from the shared config
    bname, api = backend(cfg)
    log.info("Reddit backend: %s (%s)", bname, api)
    dead = load_dead_subs(cfg)
    ckpt = Checkpoint(ROOT / cfg["paths"]["state"] / "reddit_done.log")
    pacer = Pacer(rcfg["rate"]["base_pause"], rcfg["rate"]["max_pause"])
    raw_path = ROOT / cfg["paths"]["raw"] / "reddit_raw.jsonl"

    cells = [c for c in build_cells(cfg) if c["sub"] not in dead]
    todo = [c for c in cells if not ckpt.is_done(cell_key(c))]
    # event cells first: highest-value remainder (RQ4 anchors) under throttling
    todo.sort(key=lambda c: c["event"] is None)
    log.info("Reddit crawl: %d cells total, %d already done, %d to go (%d dead subs skipped)",
             len(cells), len(cells) - len(todo), len(todo), len(dead))
    if args.limit_cells:
        todo = todo[:args.limit_cells]

    n_items, yields, consecutive_failures = 0, Counter(), 0
    for i, c in enumerate(todo, 1):
        posts = fetch_cell(c, api, bname, pacer, rcfg["rate"]["retries"])
        if posts is None:
            consecutive_failures += 1
            log.warning("Cell exhausted retries (%d consecutive), will retry next run: %s",
                        consecutive_failures, cell_key(c))
            if consecutive_failures >= 30:
                log.error("30 consecutive cell failures - PullPush looks DOWN. "
                          "Aborting; checkpoint is intact, re-run to resume.")
                break
            continue
        consecutive_failures = 0
        batch = []
        for p in posts:
            pid = p.get("id")
            if not pid or (rcfg["exclude_removed"] and is_removed(p)):
                continue
            batch.append({
                "source": "reddit",
                "id": f"rd_{pid}",
                "subreddit": p.get("subreddit", c["sub"]),
                "sub_category": c["cat"],
                "tier": c["tier"],
                "created_utc": int(p.get("created_utc", 0)),
                "title": p.get("title") or "",
                "text": (p.get("selftext") or "")[:2000],
                "url": f"https://www.reddit.com{p.get('permalink', '')}",
                "score": p.get("score") or 0,
                "num_comments": p.get("num_comments") or 0,
                "author_hash": hash_username(p.get("author", ""), salt),
                "matched_queries": [c["q"]],
                "query_groups": [c["group"]],
                "event_tags": [c["event"]] if c["event"] else [],
            })
        append_jsonl(batch, raw_path)
        ckpt.mark(cell_key(c))
        n_items += len(batch)
        for it in batch:
            yields[(c["cat"], half_year(it["created_utc"]))] += 1
        if i % 50 == 0 or i == len(todo):
            log.info("progress %d/%d cells, %d rows appended, pause %.1fs",
                     i, len(todo), n_items, pacer.pause)

    log.info("Yield report this run (category, half-year -> rows):")
    for k in sorted(yields):
        log.info("  %-15s %-7s %5d %s", k[0], k[1], yields[k],
                 "<-- SPARSE" if yields[k] < 10 else "")
    log.info("Appended %d rows -> %s (dedupe/merge happens in filter_clean)",
             n_items, raw_path)


if __name__ == "__main__":
    main()
