"""Harvest Reddit posts via Arctic Shift's NO-QUERY listing path + local matching.

Why: Arctic Shift throttles keyword searches (~25/h sustained) but serves
no-query subreddit listings freely. So instead of one API request per
(sub, query, window) cell, we page through ALL posts per (sub, window) and do
the keyword matching locally, using the same AND-over-terms semantics the
archives use,
applied to title+selftext. Bonus: every matching query is recorded, not just
the one that fetched the post.

Covers the two crawl remainders:
  - extended-tier subs x half-year windows, matched against extended-scoped groups
  - event pulls: core event-category subs x event windows (monthly sub-windows),
    matched against event terms

Checkpointed per (sub, window) page-through in data/state/harvest_done.log.
Rows append to reddit_raw_harvest.jsonl (separate file: the keyword crawler may
write reddit_raw.jsonl concurrently); filter_clean globs reddit_raw*.jsonl.

Page caps guard against very high-volume subs; truncation is logged (newest-
first bias within a capped window, which is a documented sampling caveat).
"""
import argparse
import re
from datetime import date, timedelta

from utils import (ROOT, load_config, window, epoch, get_json_status,
                   append_jsonl, Checkpoint, Pacer, hash_username, log)
import queries as Q
from retrieve_reddit import (backend, half_year_windows, is_removed,
                             load_dead_subs)

PAGE_CAP_WINDOW = 30    # pages (x100 posts) per sub x half-year window
PAGE_CAP_MONTH = 5      # pages per sub x event month


_TERM_RE: dict[str, "re.Pattern"] = {}


def _term_re(term: str):
    """Cached word-boundary matcher for one search term."""
    rx = _TERM_RE.get(term)
    if rx is None:
        rx = _TERM_RE[term] = re.compile(rf"\b{re.escape(term)}\b")
    return rx


def match_terms(q: str, text: str) -> bool:
    """AND-over-terms on WORD BOUNDARIES, mirroring the archives' search.

    Word boundaries are essential: plain substring matching makes the two-letter
    term "ai" match inside said/email/available/again, which tagged ~79% of
    harvested posts with queries they do not actually contain.
    """
    return all(_term_re(t).search(text) for t in q.lower().split())


def matching_tags(text: str, scoped: dict[str, list[str]]):
    """(queries, groups) of every scoped query matching the text."""
    mq, mg = [], []
    for group, qs in scoped.items():
        for q in qs:
            if match_terms(q, text):
                mq.append(q)
                if group not in mg:
                    mg.append(group)
    return mq, mg


def page_window(api: str, sub: str, lo: int, hi: int, pacer: Pacer,
                page_cap: int, retries: int = 5):
    """Yield all posts in [lo, hi) newest-first, cursor-paginated; None on failure."""
    upper, pages = hi, 0
    while pages < page_cap:
        posts = None
        for _ in range(retries):
            pacer.wait()
            data, status = get_json_status(
                api, {"subreddit": sub, "limit": 100, "after": lo, "before": upper})
            if status == 429:
                pacer.backoff()
                continue
            if data is not None:
                pacer.success()
                posts = data.get("data", [])
                break
            pacer.backoff()
        if posts is None:
            return None  # cell will retry next run
        yield from posts
        pages += 1
        if len(posts) < 100:
            return True
        upper = min(int(p["created_utc"]) for p in posts)
    log.info("  page cap hit for %s (%d pages) - window truncated (newest-first)", sub, pages)
    return True


def month_windows(start: date, end: date):
    cur = start
    while cur <= end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield cur, min(nxt, end + timedelta(days=1))
        cur = nxt


def row(p, sub, cat, tier, salt, mq, mg, events):
    return {
        "source": "reddit",
        "id": f"rd_{p.get('id')}",
        "subreddit": p.get("subreddit", sub),
        "sub_category": cat,
        "tier": tier,
        "created_utc": int(p.get("created_utc", 0)),
        "title": p.get("title") or "",
        "text": (p.get("selftext") or "")[:2000],
        "url": f"https://www.reddit.com{p.get('permalink', '')}",
        "score": p.get("score") or 0,
        "num_comments": p.get("num_comments") or 0,
        "author_hash": hash_username(p.get("author", ""), salt),
        "matched_queries": mq,
        "query_groups": mg,
        "event_tags": events,
    }


def uniform_main(args):
    """Uniform retrieval layer: EVERY query group against EVERY subreddit.

    Fixes the non-uniform keyword-crawl scoping (LIMITATIONS.md §1.3). Writes to
    its own raw file and checkpoint so the earlier passes stay intact and
    filter_clean merges both by id (unioning tags). Rows are stamped
    discovery_modes=['harvest_uniform'] so the uniformly-retrieved layer can be
    isolated for RQ3.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    cfg = load_config()
    rcfg = cfg["reddit"]
    salt = cfg.get("hash_salt", "")   # withheld from the shared config
    _, api = backend(cfg)
    dead = load_dead_subs(cfg)
    groups = Q.load_groups(cfg)
    scoped = {g: groups[g] for g in rcfg["uniform_scope"]}
    start, end = window(cfg)
    ckpt = Checkpoint(ROOT / cfg["paths"]["state"] / "harvest_uniform_done.log")
    raw_path = ROOT / cfg["paths"]["raw"] / "reddit_raw_uniform.jsonl"
    lock = threading.Lock()

    subs = [(s, cat) for tier in ("core", "extended")
            for cat, lst in rcfg["tiers"][tier].items() for s in lst
            if s not in dead]
    work = [(s, cat, epoch(lo), epoch(hi))
            for s, cat in subs for lo, hi in half_year_windows(start, end)]
    todo = [w for w in work if not ckpt.is_done(f"uniform|{w[0]}|{w[2]}|{w[3]}")]
    log.info("Uniform harvest: %d subreddits x %d windows = %d total, %d to go "
             "(scope: %s)", len(subs), len(work) // max(len(subs), 1), len(work),
             len(todo), ",".join(rcfg["uniform_scope"]))
    if args.limit_windows:
        todo = todo[:args.limit_windows]

    counter = {"done": 0, "kept": 0}

    def run_window(item):
        sub, cat, lo, hi = item
        pacer = Pacer(args.pause, rcfg["rate"]["max_pause"])
        batch, complete = [], None
        gen = page_window(api, sub, lo, hi, pacer, PAGE_CAP_WINDOW)
        while True:
            try:
                p = next(gen)
            except StopIteration as stop:
                complete = stop.value
                break
            if is_removed(p) and rcfg["exclude_removed"]:
                continue
            text = f"{p.get('title') or ''} {p.get('selftext') or ''}".lower()
            mq, mg = matching_tags(text, scoped)
            if not mq:
                continue
            r = row(p, sub, cat, "uniform", salt, mq, mg, [])
            r["discovery_modes"] = ["harvest_uniform"]
            batch.append(r)
        if complete is None:
            log.warning("window failed, retry next run: %s %s", sub, lo)
            return
        with lock:
            append_jsonl(batch, raw_path)
            ckpt.mark(f"uniform|{sub}|{lo}|{hi}")
            counter["done"] += 1
            counter["kept"] += len(batch)
            if counter["done"] % 20 == 0 or counter["done"] == len(todo):
                log.info("uniform progress %d/%d windows, %d rows kept",
                         counter["done"], len(todo), counter["kept"])

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(run_window, todo))
    log.info("Uniform harvest done: %d rows -> %s", counter["kept"], raw_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-windows", type=int, default=0, help="smoke testing")
    ap.add_argument("--uniform", action="store_true",
                    help="uniform layer: every query group x every subreddit")
    ap.add_argument("--workers", type=int, default=3,
                    help="concurrent windows (listing path is not keyword-throttled)")
    ap.add_argument("--pause", type=float, default=3.0,
                    help="per-worker base pause; workers x 1/pause = aggregate rate")
    args = ap.parse_args()
    if args.uniform:
        uniform_main(args)
        return

    cfg = load_config()
    rcfg = cfg["reddit"]
    salt = cfg.get("hash_salt", "")   # withheld from the shared config
    _, api = backend(cfg)
    dead = load_dead_subs(cfg)
    groups = Q.load_groups(cfg)
    start, end = window(cfg)
    ckpt = Checkpoint(ROOT / cfg["paths"]["state"] / "harvest_done.log")
    pacer = Pacer(2.0, rcfg["rate"]["max_pause"])
    raw_path = ROOT / cfg["paths"]["raw"] / "reddit_raw_harvest.jsonl"

    # work list: (kind, sub, cat, tier, lo, hi, scoped-queries, event-name)
    work = []
    for cat, subs in rcfg["tiers"]["extended"].items():
        scoped = {g: groups[g] for g in Q.extended_scope(cfg, cat)}
        for sub in subs:
            if sub in dead:
                continue
            for lo, hi in half_year_windows(start, end):
                work.append(("extended", sub, cat, epoch(lo), epoch(hi),
                             scoped, None, PAGE_CAP_WINDOW))
    for ev in Q.event_windows(cfg):
        scoped = {"event": ev["terms"]}
        for cat in rcfg["event_categories"]:
            for sub in rcfg["tiers"]["core"][cat]:
                if sub in dead:
                    continue
                for mlo, mhi in month_windows(ev["start"], ev["end"]):
                    work.append((f"event:{ev['name']}", sub, cat, epoch(mlo), epoch(mhi),
                                 scoped, ev["name"], PAGE_CAP_MONTH))

    todo = [w for w in work
            if not ckpt.is_done(f"{w[0]}|{w[1]}|{w[3]}|{w[4]}")]
    log.info("Harvest: %d windows total, %d to go", len(work), len(todo))
    if args.limit_windows:
        todo = todo[:args.limit_windows]

    n_kept = 0
    for i, (kind, sub, cat, lo, hi, scoped, ev_name, cap) in enumerate(todo, 1):
        batch, complete = [], None
        gen = page_window(api, sub, lo, hi, pacer, cap)
        while True:
            try:
                p = next(gen)
            except StopIteration as stop:
                complete = stop.value
                break
            if is_removed(p) and rcfg["exclude_removed"]:
                continue
            text = f"{p.get('title') or ''} {p.get('selftext') or ''}".lower()
            mq, mg = matching_tags(text, scoped)
            if not mq:
                continue
            tier = "extended" if kind == "extended" else "core"
            events = [ev_name] if ev_name else []
            if ev_name:
                mg = ["event"]
            batch.append(row(p, sub, cat, tier, salt, mq, mg, events))
        if complete is None:
            log.warning("window failed, will retry next run: %s %s", kind, sub)
            continue
        append_jsonl(batch, raw_path)
        ckpt.mark(f"{kind}|{sub}|{lo}|{hi}")
        n_kept += len(batch)
        if i % 25 == 0 or i == len(todo):
            log.info("harvest progress %d/%d windows, %d rows kept, pause %.1fs",
                     i, len(todo), n_kept, pacer.pause)

    log.info("Harvest done: %d rows -> %s", n_kept, raw_path)


if __name__ == "__main__":
    main()
