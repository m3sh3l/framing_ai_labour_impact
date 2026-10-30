"""Build the 300-item human-annotation gold standard (proposal §4.5).

SAMPLING DESIGN: why it is drawn this way
------------------------------------------
The gold standard exists to estimate inter-coder reliability (Cohen's kappa)
between the human coder and the LLM pipeline. That estimate is only valid for
the corpus if the 300 items are a PROBABILITY SAMPLE of the coding universe.
Hand-picking "interesting" or vivid items inflates apparent agreement on clear
cases and produces a kappa that does not transfer (Krippendorff 2004).

So diversity is engineered ONLY through stratifiers that are (a) known before
coding and (b) not the outcome variable:

  1. Ecosystem      : 100 each (proposal spec; the RQ3 between-group factor).
  2. Half-year      : even spread, so early and late discourse are both
                      represented and temporal drift in coding is detectable.
  3. Source outlet  : per-subreddit and per-outlet caps so no single community
                      or publisher dominates a 100-item cell. Reddit's sample is
                      63% top-5 subreddits and MediaCloud's includes newswire
                      /PR domains, either of which could otherwise swamp a cell.

Selection WITHIN each cell is uniform random on a fixed seed. Frame-relevant
metadata (query_groups, event_tags) is deliberately NOT stratified on: those
correlate with the outcome, and balancing them would bake the frame hypothesis
into the validation set, which is the circularity the study is designed to
avoid. Their achieved distribution is reported as a diagnostic instead.

The 300 are drawn from the frozen 1,800-item analysis sample, not the full
corpus, because kappa must be measured on items the LLM also codes.

BLINDING (proposal §4.5): source, subreddit, outlet, url, and all retrieval
metadata are withheld from the coding sheet and written to a separate key file.
Blinding is partial by nature, since headline-only news reads differently from
a Reddit self-post, so it is reported as "source-label blind", not "ecosystem
blind".

TEXT UNIT (codebook §1): MediaCloud = headline only (body never consulted);
Reddit and Hacker News = title plus at most the first 100 words of body text.
Truncation is applied here so the human and the LLM see an identical unit.

Usage:  python src/build_annotation_sheet.py [--seed 42] [--per-ecosystem 100]
"""
import argparse
import html
import random
import re
from pathlib import Path

import pandas as pd

from utils import ROOT, log

_P_BREAK = re.compile(r"<\s*/?\s*(p|br)\s*/?\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]*\n[ \t]*")

SEED = 42
BODY_WORD_CAP = 100          # codebook §1
BLOCKS = 3                   # annotation days
SUBREDDIT_CAP = 8            # max items per subreddit within the Reddit cell
OUTLET_CAP = 6               # max items per outlet within the MediaCloud cell

# Withheld from the coding sheet; preserved in the key file.
BLIND_COLS = ["source", "subreddit", "sub_category", "tier", "outlet",
              "outlet_category", "url", "query_groups", "matched_queries",
              "event_tags", "discovery_modes", "in_neutral_baseline",
              "keyword_matched", "n_groups_matched", "author_hash",
              "score", "num_comments", "language", "publish_date"]

CODE_COLS = ["coarse_frame", "problem", "cause", "moral", "treatment",
             "confidence", "notes"]

VALID = {  # codebook §3–§4
    "coarse_frame": ["REPLACEMENT", "AUGMENTATION", "TRANSFORMATION", "MIXED", "TANGENTIAL"],
    "problem": ["JOB_LOSS", "SKILL_CHANGE", "OPPORTUNITY", "INEQUALITY_POWER", "NONE"],
    "cause": ["TECHNOLOGY", "FIRMS", "POLICY", "WORKERS", "NONE"],
    "moral": ["NEGATIVE", "POSITIVE", "AMBIVALENT", "NEUTRAL", "NONE"],
    "treatment": ["REGULATE", "ADAPT", "REDISTRIBUTE", "ACCELERATE", "NONE"],
    "confidence": ["1", "2", "3"],
}


def clean_text(s: str) -> str:
    """Strip HTML and decode entities.

    Hacker News story_text arrives as HTML fragments (<p> paragraphs, <a href>
    links, &#x27; entities). 23% of drawn items carried some. Raw markup hurts
    annotation consistency and would reach the LLM coder identically, so both
    see the same cleaned text. Anchor text is kept; the tag is dropped.
    """
    s = _P_BREAK.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    return _WS.sub("\n", s).strip()


def text_unit(row) -> str:
    """Title + capped body, per codebook §1. News is headline-only."""
    title = clean_text(str(row.get("title") or ""))
    if row["source"] == "mediacloud":
        return title
    body = clean_text(str(row.get("text") or ""))
    if not body or body.lower() == "nan":
        return title
    words = body.split()                       # cap AFTER cleaning, so the
    clipped = " ".join(words[:BODY_WORD_CAP])  # 100-word budget is real words
    if len(words) > BODY_WORD_CAP:
        clipped += " […]"
    return f"{title}\n\n{clipped}"


def capped_pick(pool: pd.DataFrame, n: int, group_col: str | None,
                cap: int, rng: random.Random, used: dict) -> list:
    """Random n indices from pool, at most `cap` per group_col value.

    `used` is a running counter SHARED across half-year strata, so the cap is a
    global dominance guard on the ecosystem's whole cell, not a per-cell
    one (a per-cell cap of 8 across 8 strata would still permit 64).
    Falls back to uncapped random if the cap makes n unreachable. The cap
    bounds dominance, it never leaves the cell short.
    """
    idx = list(pool.index)
    rng.shuffle(idx)
    chosen = []
    if group_col and group_col in pool.columns:
        for i in idx:
            key = pool.at[i, group_col]
            if pd.isna(key):
                key = "__na__"
            if used.get(key, 0) >= cap:
                continue
            chosen.append(i)
            used[key] = used.get(key, 0) + 1
            if len(chosen) == n:
                break
        if len(chosen) < n:                       # cap too tight, top up randomly
            for i in idx:
                if i not in chosen:
                    chosen.append(i)
                    if len(chosen) == n:
                        break
    else:
        chosen = idx[:n]
    return chosen


def sample_ecosystem(df: pd.DataFrame, n: int, group_col: str | None,
                     cap: int, rng: random.Random) -> pd.DataFrame:
    """Even spread across half-years; shortfall in a thin stratum is
    redistributed to the others (mirrors src/sample_corpus.py). The source cap
    is enforced globally via a shared counter."""
    strata = sorted(df["half_year"].unique())
    base = n // len(strata)
    used: dict = {}
    picked, shortfall = [], 0
    for s in strata:
        grp = df[df["half_year"] == s]
        take = min(base, len(grp))
        shortfall += base - take
        picked.extend(capped_pick(grp, take, group_col, cap, rng, used))
    remaining = n - len(picked)
    if remaining > 0:
        pool = df.drop(index=picked)
        if len(pool):
            picked.extend(capped_pick(pool, min(remaining, len(pool)),
                                      group_col, cap, rng, used))
    if shortfall:
        log.info("  redistributed %d items from thin half-year strata", shortfall)
    return df.loc[picked]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--per-ecosystem", type=int, default=100)
    ap.add_argument("--frozen", default="data/clean/frozen_20260802")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    frozen = ROOT / args.frozen
    out_dir = ROOT / "data/annotation"
    out_dir.mkdir(parents=True, exist_ok=True)

    group_by = {"reddit": ("subreddit", SUBREDDIT_CAP),
                "mediacloud": ("outlet", OUTLET_CAP),
                "hackernews": (None, 0)}

    frames = []
    for source in ("hackernews", "reddit", "mediacloud"):
        df = pd.read_csv(frozen / f"{source}_sample.csv")
        df["source"] = source
        col, cap = group_by[source]
        log.info("%s: drawing %d of %d", source, args.per_ecosystem, len(df))
        frames.append(sample_ecosystem(df, args.per_ecosystem, col, cap, rng))

    # Assign blocks WITHIN each ecosystem, so every block is source-balanced and
    # a partially-completed set (e.g. only blocks 1-2) is still a usable,
    # unbiased subset rather than one skewed toward whichever source landed there.
    for i, f in enumerate(frames):
        shuffled = f.sample(frac=1, random_state=args.seed + i).reset_index(drop=True)
        shuffled["block"] = (shuffled.index % BLOCKS) + 1
        frames[i] = shuffled

    gold = pd.concat(frames, ignore_index=True)
    gold["text_unit"] = gold.apply(text_unit, axis=1)

    # Randomise order within each block so ecosystems interleave (guards against
    # coder drift and anchoring on a run of same-source items).
    gold = (gold.sample(frac=1, random_state=args.seed)
                .sort_values("block", kind="stable")
                .reset_index(drop=True))
    gold.insert(0, "annotation_id", range(1, len(gold) + 1))

    # --- coding sheet (blind) ---
    sheet = gold[["annotation_id", "block", "id", "text_unit"]].copy()
    for c in CODE_COLS:
        sheet[c] = ""
    sheet.to_csv(out_dir / "annotation_sheet.csv", index=False)

    # --- key file (do NOT open while coding) ---
    key_cols = ["annotation_id", "id"] + [c for c in BLIND_COLS if c in gold.columns] \
               + ["date", "half_year", "quarter"]
    gold[key_cols].to_csv(out_dir / "annotation_key.csv", index=False)

    pd.DataFrame([{"variable": k, "valid_values": " | ".join(v)}
                  for k, v in VALID.items()]).to_csv(
        out_dir / "valid_values.csv", index=False)

    # --- composition report (the defensible audit trail) ---
    lines = [f"GOLD STANDARD COMPOSITION  (seed={args.seed}, n={len(gold)})", ""]
    lines.append("source x half_year")
    lines.append(gold.groupby(["source", "half_year"]).size().unstack(fill_value=0).to_string())
    lines.append("")
    lines.append("block x source  (each block is a self-contained balanced subset)")
    lines.append(gold.groupby(["block", "source"]).size().unstack(fill_value=0).to_string())
    lines.append("")
    for c, label in (("subreddit", "distinct subreddits"), ("outlet", "distinct outlets")):
        if c in gold.columns and gold[c].notna().any():
            vc = gold[c].value_counts()
            lines.append(f"{label}: {len(vc)}; max from one = {vc.max()} ({vc.idxmax()})")
    lines.append("")
    lines.append("DIAGNOSTIC ONLY — not stratified on (would bias kappa):")
    if "query_groups" in gold.columns:
        exploded = gold.assign(g=gold["query_groups"].fillna("").str.split("|")).explode("g")
        exploded = exploded[exploded.g != ""]
        lines.append("  query_groups: " + str(exploded.g.value_counts().to_dict()))
    for c in ("in_neutral_baseline", "keyword_matched"):
        if c in gold.columns:
            lines.append(f"  {c}: {gold[c].value_counts().to_dict()}")
    wl = gold["text_unit"].str.split().str.len()
    lines.append("")
    lines.append(f"text unit words: median {wl.median():.0f}, p90 {wl.quantile(.9):.0f}, max {wl.max()}")
    lines.append(f"  (news = headline only; reddit/HN = title + <={BODY_WORD_CAP} words body)")
    report = "\n".join(lines)
    (out_dir / "composition_report.txt").write_text(report + "\n")
    print(report)
    log.info("Wrote annotation_sheet.csv / annotation_key.csv / valid_values.csv -> %s", out_dir)


if __name__ == "__main__":
    main()
