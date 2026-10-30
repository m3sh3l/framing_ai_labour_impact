"""Clean, filter, and merge the three raw corpora. No down-sampling here.

Steps (proposal §4.2 + redesign 2026-07-13):
  1. load raw jsonl per source (append-only logs may contain the same post
     several times, once per matching query)
  2. merge duplicate ids, unioning matched_queries / query_groups / event_tags
  3. labour-relevance filter (AI term AND labour term, title + text)
  4. English-only (langdetect on title; skipped gracefully if not installed)
  5. dedupe exact titles within source
  6. HN: drop stories with < min_comments comments
  7. derive date/quarter/half_year, in_neutral_baseline, n_groups_matched
  8. write data/clean/{source}_clean.csv + combined corpus.duckdb + summaries
     (per half-year AND per query-group: the §11 selection-bias check table)

The corpus keeps EVERY relevant item ("collect big"); stratified sampling to
the proposal targets is a separate optional step: src/sample_corpus.py.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    import duckdb
except ImportError:
    duckdb = None

from utils import ROOT, load_config, is_relevant, half_year, quarter, log

LIST_COLS = ["matched_queries", "query_groups", "event_tags", "discovery_modes"]
LIST_SEP = "|"

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 42

    def is_english(text: str) -> bool:
        try:
            return detect(text) == "en"
        except Exception:
            return True
except ImportError:
    log.warning("langdetect not installed - skipping language filter")

    def is_english(text: str) -> bool:
        return True


def load_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        log.warning("Missing %s - run its retrieval script first", path)
        return pd.DataFrame()
    rows = []
    with open(path) as f:
        for line in f:
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def normalise_tags(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the three tag columns exist as lists (handles v1 raw files that
    had a singular matched_query string and no group tagging)."""
    if "matched_query" in df.columns and "matched_queries" not in df.columns:
        df["matched_queries"] = df["matched_query"].apply(
            lambda q: [q] if isinstance(q, str) and q else [])
        df = df.drop(columns=["matched_query"])
    for col in LIST_COLS:
        if col not in df.columns:
            # rows predating a column: keyword-search retrieval is the default
            # provenance (only the listing harvester stamps discovery_modes)
            default = {"query_groups": ["legacy"], "discovery_modes": ["search"]}.get(col, [])
            df[col] = [list(default) for _ in range(len(df))]
        else:
            df[col] = df[col].apply(
                lambda v: v if isinstance(v, list)
                else (["search"] if col == "discovery_modes" else []))
    return df


def merge_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Same post found by several queries -> one row with unioned tag lists."""
    def union(series):
        return sorted({x for lst in series for x in lst})

    agg = {c: union if c in LIST_COLS else "first"
           for c in df.columns if c != "id"}
    return df.groupby("id", as_index=False, sort=False).agg(agg)


def normalise_dates(df: pd.DataFrame, cfg) -> pd.DataFrame:
    if "publish_date" in df.columns:  # mediacloud
        ts = pd.to_datetime(df["publish_date"], errors="coerce", utc=True)
        # unit-independent epoch seconds (pandas 3 parses dates at ms resolution,
        # so astype("int64")//1e9 silently mangles them)
        secs = (ts - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)
        df["created_utc"] = secs.where(ts.notna(), 0).astype("int64")
    from utils import window, epoch
    start, end = window(cfg)
    df = df[(df["created_utc"] >= epoch(start)) &
            (df["created_utc"] < epoch(end) + 86400)].copy()
    df["date"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat())
    df["quarter"] = df["created_utc"].apply(quarter)
    df["half_year"] = df["created_utc"].apply(half_year)
    return df


def process(source: str, df: pd.DataFrame, cfg) -> pd.DataFrame:
    n0 = len(df)
    if df.empty:
        return df
    df = normalise_tags(df)
    df = merge_duplicates(df)
    n_unique = len(df)
    df = normalise_dates(df, cfg)
    if df.empty:
        log.warning("%s: 0 items inside the date window (raw had %d rows)", source, n0)
        return df
    df["fulltext"] = (df["title"].fillna("") + " " + df.get("text", "").fillna(""))
    df = df[df["fulltext"].apply(lambda t: is_relevant(t, cfg))]
    df = df[df["title"].apply(is_english)]
    df = df.drop_duplicates(subset=["title"]).copy()
    if source == "hackernews":
        df = df[df["num_comments"] >= cfg["hackernews"]["min_comments"]]
    df["in_neutral_baseline"] = df["query_groups"].apply(lambda g: "core" in g)
    df["n_groups_matched"] = df["query_groups"].apply(len)
    # Listing-harvested items can pass the relevance rule while matching no
    # keyword query at all, giving a keyword-independent subsample and the
    # cleanest
    # control available for keyword-selection bias (doc §11).
    df["keyword_matched"] = df["query_groups"].apply(lambda g: len(g) > 0)
    log.info("%s: %d raw rows -> %d unique posts -> %d relevant/clean (kept ALL)",
             source, n0, n_unique, len(df))
    if len(df) < 500:
        log.warning("%s below 500-item success criterion - widen queries!", source)
    return df.drop(columns=["fulltext"])


def serialise_lists(df: pd.DataFrame) -> pd.DataFrame:
    """Pipe-join list columns for CSV/duckdb friendliness."""
    df = df.copy()
    for col in LIST_COLS:
        if col in df.columns:
            df[col] = df[col].apply(lambda lst: LIST_SEP.join(lst))
    return df


def main():
    cfg = load_config()
    raw = ROOT / cfg["paths"]["raw"]
    clean_dir = ROOT / cfg["paths"]["clean"]
    clean_dir.mkdir(parents=True, exist_ok=True)

    frames = {}
    for source, pattern in [("hackernews", "hackernews_raw.jsonl"),
                            ("reddit", "reddit_raw*.jsonl"),   # crawler + harvester files
                            ("mediacloud", "mediacloud_raw.jsonl")]:
        paths = sorted(raw.glob(pattern))
        if not paths:
            log.warning("Missing %s - run its retrieval script first", raw / pattern)
            df = pd.DataFrame()
        else:
            df = pd.concat([load_raw(p) for p in paths], ignore_index=True)
        df = process(source, df, cfg)
        if not df.empty:
            serialise_lists(df).to_csv(clean_dir / f"{source}_clean.csv", index=False)
            frames[source] = df

    if not frames:
        return

    combined = pd.concat(frames.values(), ignore_index=True)
    combined_flat = serialise_lists(combined)
    if duckdb is not None:
        con = duckdb.connect(str(ROOT / cfg["paths"]["duckdb"]))
        con.execute("CREATE OR REPLACE TABLE corpus AS SELECT * FROM combined_flat")
        con.close()
    else:
        log.warning("duckdb not installed - skipped corpus.duckdb (CSVs still written)")

    summary = combined.groupby(["source", "half_year"]).size().unstack(fill_value=0)
    summary.to_csv(clean_dir / "corpus_summary.csv")

    by_group = (combined.explode("query_groups")
                .groupby(["source", "query_groups", "half_year"]).size()
                .unstack(fill_value=0))
    by_group.to_csv(clean_dir / "corpus_by_group.csv")

    log.info("Combined corpus: %d items", len(combined))
    print("\n=== CORPUS SUMMARY (items per half-year) ===")
    print(summary.to_string())
    print("\n=== BY QUERY GROUP (selection-bias check, doc §11) ===")
    print(by_group.to_string())
    print("\nSelection-bias indicators per source:")
    bias = combined.groupby("source").agg(
        n=("id", "size"),
        keyword_matched=("keyword_matched", "mean"),
        neutral_baseline=("in_neutral_baseline", "mean"),
    ).round(3)
    print(bias.to_string())
    print("\n(keyword_matched < 1 means part of the corpus was surfaced by the "
          "keyword-independent listing harvest and matched no query — a control "
          "sample for keyword-selection bias.)")


if __name__ == "__main__":
    main()
