"""Recompute the pipeline attrition funnel from the raw files.

Replicates `filter_clean.process()` stage by stage so the slide-7 figure and the
report can quote counts that are derived, not transcribed. Writes
`data/meta/funnel.json`, which `make_pipeline_slide_figure.py` reads.

The date-window filter sits between dedup and relevance in `process()`, but it
drops almost nothing (the retrievers are already date-bounded), so the funnel
folds it into the "unique items" stage instead of showing a flat step.

Run:  python src/compute_funnel.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from filter_clean import (  # noqa: E402
    is_english, load_raw, merge_duplicates, normalise_dates, normalise_tags,
)
from utils import is_relevant, load_config  # noqa: E402

cfg = load_config()
stages = {k: 0 for k in
          ("retrieved", "unique", "relevant", "english", "deduped", "clean")}
per_source = {}

RAW = ROOT / cfg["paths"]["raw"]
PATTERNS = {"mediacloud": "mediacloud_raw.jsonl",
            "hackernews": "hackernews_raw.jsonl",
            "reddit": "reddit_raw*.jsonl"}          # crawler + harvester + uniform

for source, pattern in PATTERNS.items():
    df = pd.concat([load_raw(p) for p in sorted(RAW.glob(pattern))],
                   ignore_index=True)
    n_raw = len(df)
    df = normalise_tags(df)
    df = merge_duplicates(df)
    df = normalise_dates(df, cfg)
    n_unique = len(df)

    df["fulltext"] = df["title"].fillna("") + " " + df.get("text", "").fillna("")
    df = df[df["fulltext"].apply(lambda t: is_relevant(t, cfg))]
    n_relevant = len(df)

    df = df[df["title"].apply(is_english)]
    n_english = len(df)

    df = df.drop_duplicates(subset=["title"]).copy()
    n_dedup = len(df)

    if source == "hackernews":
        df = df[df["num_comments"] >= cfg["hackernews"]["min_comments"]]
    n_clean = len(df)

    for k, v in zip(stages, (n_raw, n_unique, n_relevant, n_english, n_dedup, n_clean)):
        stages[k] += v
    per_source[source] = {"retrieved": n_raw, "clean": n_clean,
                          "survival_pct": round(100 * n_clean / n_raw, 1)}
    print(f"{source:12s} {n_raw:>8,} -> unique {n_unique:>8,} -> relevant {n_relevant:>7,}"
          f" -> english {n_english:>7,} -> dedup {n_dedup:>7,} -> clean {n_clean:>7,}"
          f"  ({per_source[source]['survival_pct']}%)")

coded = sum(1 for _ in open(ROOT / "data/coding/llm_codes_full1800.jsonl"))
analysis = sum(1 for l in open(ROOT / "data/coding/llm_codes_full1800.jsonl")
               if json.loads(l)["coarse_frame"] != "TANGENTIAL")
stages["coded"], stages["analysis"] = coded, analysis

out = {"stages": stages, "per_source": per_source}
(ROOT / "data/meta").mkdir(parents=True, exist_ok=True)
(ROOT / "data/meta/funnel.json").write_text(json.dumps(out, indent=2))

print("\nTOTAL FUNNEL")
for k, v in stages.items():
    print(f"  {k:12s} {v:>8,}")
print("\nwrote data/meta/funnel.json")
