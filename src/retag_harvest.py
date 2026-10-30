"""Recompute keyword tags on already-harvested Reddit rows (offline, no API calls).

Why: the first harvest run matched query terms by plain substring, so the
two-letter term "ai" matched inside said/email/available/again. That kept (and
tagged) ~79% of rows with queries they do not actually contain, inflating the
`query_groups` used by the frame selection-bias check.

This rewrites data/raw/reddit_raw_harvest.jsonl in place (backup kept) using the
corrected word-boundary matcher, re-deriving `matched_queries` / `query_groups`
from each row's own stored title+text. Rows that match no scoped query keep an
empty `query_groups`: they were surfaced by the keyword-independent listing
harvest, not by any query, and that is exactly what the tag should say. Whether
such a row enters the corpus is decided, as for every source, by the relevance
rule in filter_clean.

Also stamps `discovery_modes` ("harvest") so analysis can separate
keyword-search-derived items from listing-harvested ones.

Usage: python src/retag_harvest.py [--dry-run]
"""
import argparse
import json
import re
import shutil
from collections import Counter

from utils import ROOT, load_config, log
import queries as Q
from harvest_reddit import match_terms

RAW = "data/raw/reddit_raw_harvest.jsonl"


def scoped_for(row, cfg, groups) -> dict[str, list[str]]:
    """The query set this row was collected under (mirrors harvest_reddit)."""
    if row.get("event_tags"):
        by_name = {e["name"]: e["terms"] for e in Q.event_windows(cfg)}
        terms = []
        for ev in row["event_tags"]:
            terms.extend(by_name.get(ev, []))
        return {"event": terms}
    return {g: groups[g] for g in Q.extended_scope(cfg, row["sub_category"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    groups = Q.load_groups(cfg)
    src = ROOT / RAW
    if not src.exists():
        log.warning("No %s - nothing to retag", src)
        return

    rows = [json.loads(l) for l in open(src)]
    log.info("Retagging %d harvested rows", len(rows))

    before, after, changed, emptied = Counter(), Counter(), 0, 0
    for r in rows:
        text = f"{r.get('title') or ''} {r.get('text') or ''}".lower()
        scoped = scoped_for(r, cfg, groups)
        mq, mg = [], []
        for group, qs in scoped.items():
            for q in qs:
                if match_terms(q, text):
                    mq.append(q)
                    if group not in mg:
                        mg.append(group)
        for g in r.get("query_groups", []):
            before[g] += 1
        for g in mg:
            after[g] += 1
        if set(mg) != set(r.get("query_groups", [])):
            changed += 1
        if not mq:
            emptied += 1
        r["matched_queries"], r["query_groups"] = mq, mg
        r["discovery_modes"] = ["harvest"]

    log.info("rows with changed tags: %d (%.0f%%)", changed, 100 * changed / len(rows))
    log.info("rows now matching no scoped query: %d (%.0f%%)", emptied,
             100 * emptied / len(rows))
    log.info("group counts before: %s", dict(before.most_common()))
    log.info("group counts after : %s", dict(after.most_common()))

    if args.dry_run:
        log.info("dry run - file not written")
        return

    shutil.copy2(src, src.with_suffix(".jsonl.substring_backup"))
    with open(src, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("Rewrote %s (backup: *.substring_backup)", src)


if __name__ == "__main__":
    main()
