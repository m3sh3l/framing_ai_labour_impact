"""Optional stratified sampling of the full clean corpus to proposal targets.

Run at analysis time (make sample). The clean corpus itself keeps every
relevant item. Sampling is time-balanced ONLY (half-year strata); query-group
frame tags are deliberately not sampling strata (locked design decision:
frames are discovered in analysis, not baked into collection).

Within a stratum, items are ranked by score where the source has one
(HN points, Reddit upvotes) and sampled at random (seeded) for MediaCloud.
Shortfall in a stratum is redistributed to the pool of remaining items.
Output: data/clean/sampled/{source}_sample.csv, reproducible (seed 42).
Not shipped: the analysis uses the dated snapshot in data/clean/frozen_20260802.
"""
import math

import pandas as pd

from utils import ROOT, load_config, log

SEED = 42


def stratified_sample(df: pd.DataFrame, target: int) -> pd.DataFrame:
    """Balanced sample across half-years; redistributes shortfall; logs it."""
    has_score = "score" in df.columns and df["score"].notna().any()

    def rank(grp):
        if has_score:
            return grp.sort_values("score", ascending=False)
        return grp.sample(frac=1, random_state=SEED)

    strata = sorted(df["half_year"].unique())
    per = math.ceil(target / len(strata))
    picked, leftover_pool = [], []
    for s in strata:
        grp = rank(df[df["half_year"] == s])
        if len(grp) <= per:
            picked.append(grp)
            log.info("  stratum %s: %d/%d (SHORTFALL)", s, len(grp), per)
        else:
            picked.append(grp.head(per))
            leftover_pool.append(grp.iloc[per:])
    out = pd.concat(picked)
    shortfall = target - len(out)
    if shortfall > 0 and leftover_pool:
        pool = pd.concat(leftover_pool)
        pool = rank(pool)
        out = pd.concat([out, pool.head(shortfall)])
        log.info("  redistributed %d items to reach target", min(shortfall, len(pool)))
    return out.head(target).sort_values("created_utc")


def main():
    cfg = load_config()
    clean_dir = ROOT / cfg["paths"]["clean"]
    out_dir = clean_dir / "sampled"
    out_dir.mkdir(parents=True, exist_ok=True)

    for source, target in cfg["targets"].items():
        path = clean_dir / f"{source}_clean.csv"
        if not path.exists():
            log.warning("Missing %s - run make clean-data first", path)
            continue
        df = pd.read_csv(path)
        log.info("%s: sampling %d from %d clean items", source, target, len(df))
        sample = stratified_sample(df, target) if len(df) > target else df
        sample.to_csv(out_dir / f"{source}_sample.csv", index=False)
        log.info("  wrote %d -> %s", len(sample), out_dir / f"{source}_sample.csv")


if __name__ == "__main__":
    main()
