"""Shared analysis layer for the results notebook.

Everything the report quotes is computed by a function in this module, so the
notebook stays readable and the statistics can be checked in one place. These
are the same implementations used to produce the figures in the report; they
were copied across without rewriting, so the numbers cannot drift.

Contents
--------
loading      load_coded()      the 1,800 coded items joined to their metadata
             load_clean()      the 40,735-item clean corpus
             analytic()        the 1,205 non-tangential items used for RQ1-RQ4
statistics   cramers_v()       chi2 + effect size + expected-count assumption check
             perm_chi2()       Monte-Carlo chi2 for tables with small expected cells
             std_residuals()   which cells drive an association
             cluster_boot_props()  proportions with CIs that resample authors/outlets
             trend()           logistic odds-of-replacement per year, cluster-robust
             wilson()          binomial proportion intervals
constants    SRC_ORDER, FRAME_ORDER, labels and the report's colour palette
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency
from statsmodels.stats.proportion import proportion_confint

warnings.filterwarnings("ignore")

# Repository root, resolved from this file so notebooks work from any cwd.
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIGURES = ROOT / "figures"

# The frozen snapshot the report is built on. Named for the date it was cut;
# every number in the submitted report refers to this copy and no other.
FROZEN = DATA / "clean" / "frozen_20260802"

SOURCES = ("hackernews", "reddit", "mediacloud")
SRC_ORDER = ["mediacloud", "reddit", "hackernews"]
SRC_SHORT = {"mediacloud": "MediaCloud", "reddit": "Reddit", "hackernews": "Hacker News"}
SRC_LABEL = {"mediacloud": "MediaCloud\n(news)", "reddit": "Reddit\n(public)",
             "hackernews": "Hacker News\n(insider)"}

FRAME_ORDER = ["REPLACEMENT", "AUGMENTATION", "TRANSFORMATION", "MIXED"]
FRAME_LAB = {"REPLACEMENT": "Replacement", "AUGMENTATION": "Augmentation",
             "TRANSFORMATION": "Transformation", "MIXED": "Mixed"}
FUNCTIONS = ["problem", "moral", "treatment", "cause"]
FUNC_LAB = {"problem": "Problem definition", "moral": "Moral evaluation",
            "treatment": "Treatment recommendation", "cause": "Causal attribution"}
CODE_COLS = ["coarse_frame", "problem", "cause", "moral", "treatment"]

# Report palette (also the deck's theme, so figures match across deliverables).
NAVY, BLUE, ORANGE, RED = "#44546A", "#4472C4", "#ED7D31", "#C0362C"
GREEN, MUTED, GRID = "#4E9F50", "#8A93A5", "#DDDDDD"
SRC_COL = {"mediacloud": BLUE, "reddit": RED, "hackernews": ORANGE}
FRAME_COL = {"REPLACEMENT": RED, "AUGMENTATION": GREEN,
             "TRANSFORMATION": BLUE, "MIXED": MUTED}

WINDOW_START = pd.Timestamp("2022-11-01")
GPT4_RELEASE = pd.Timestamp("2023-03-14")     # pre-registered event anchor


# --------------------------------------------------------------------- load
def load_coded() -> pd.DataFrame:
    """The 1,800 coded items joined to the frozen sample metadata.

    `cluster` is the unit standard errors are grouped on: author for the forums,
    outlet for news, falling back to the item id when neither exists. Treating
    items as independent would understate uncertainty, since ~30% of Reddit
    items come from repeat authors.
    """
    codes = pd.DataFrame([json.loads(l) for l in
                          open(DATA / "coding" / "llm_codes_full1800.jsonl")])
    meta = []
    for s in SOURCES:
        d = pd.read_csv(FROZEN / f"{s}_sample.csv")
        d["source"] = s
        meta.append(d)
    df = codes.merge(pd.concat(meta, ignore_index=True), on="id", how="left",
                     suffixes=("", "_m"))
    df["cluster"] = df.author_hash.fillna(df.get("outlet")).fillna(df.id)
    df["date"] = pd.to_datetime(df.date)
    return df


def analytic(df: pd.DataFrame) -> pd.DataFrame:
    """Non-tangential items (n = 1,205): the set RQ1-RQ4 are computed on.

    Derived columns: `t_years` (decimal years since the window opened, the RQ4
    time variable), `is_repl` (the RQ4 outcome), `half` (half-year bucket).
    """
    nt = df[df.coarse_frame != "TANGENTIAL"].copy()
    nt["t_years"] = (nt.date - WINDOW_START).dt.days / 365.25
    nt["is_repl"] = (nt.coarse_frame == "REPLACEMENT").astype(int)
    nt["half"] = nt.date.dt.year.astype(str) + "H" + ((nt.date.dt.month > 6) + 1).astype(str)
    nt["n_words"] = (nt.title.fillna("").str.split().str.len()
                     + nt.text.fillna("").str.split().str.len())
    return nt


def load_clean() -> pd.DataFrame:
    """The full clean corpus (40,735 items) across all three sources."""
    out = []
    for s in SOURCES:
        d = pd.read_csv(DATA / "clean" / f"{s}_clean.csv", low_memory=False)
        d["source"] = s
        out.append(d)
    return pd.concat(out, ignore_index=True)


def load_human() -> pd.DataFrame:
    """The 300 hand-coded validation items merged to the model's codes.

    Merged on `id`, never on row order. Merging on position gives a plausible
    but wrong coefficient (kappa 0.182 instead of 0.797) without raising an
    error, so the assertion below guards against it.
    """
    human = pd.read_excel(DATA / "annotation" / "annotation_sheet_filledin.xlsx")
    llm = pd.DataFrame([json.loads(l) for l in
                        open(DATA / "coding" / "llm_codes_gold300.jsonl")])
    for c in CODE_COLS:
        human[c] = human[c].astype(str).str.strip().str.upper()
        llm[c] = llm[c].astype(str).str.strip().str.upper()
    m = human[["id"] + CODE_COLS].merge(llm[["id"] + CODE_COLS], on="id",
                                        suffixes=("_h", "_m"))
    assert len(m) == len(human), f"join lost rows: {len(human)} -> {len(m)}"
    return m


# --------------------------------------------------------------- statistics
def cramers_v(ct: pd.DataFrame) -> dict:
    """chi2 test, Cramer's V, and an explicit expected-count assumption check.

    `cells_lt5` is reported because the asymptotic chi2 is unreliable when
    expected counts fall below 5; where it is non-zero, `perm_chi2` should be
    run alongside.
    """
    chi2, p, dof, exp = chi2_contingency(ct)
    n = ct.values.sum()
    r, c = ct.shape
    return {"chi2": chi2, "p": p, "dof": dof,
            "V": np.sqrt(chi2 / (n * (min(r, c) - 1))),
            "n": int(n), "cells_lt5": int((exp < 5).sum()),
            "cells": exp.size, "min_exp": exp.min()}


def perm_chi2(ct: pd.DataFrame, n_perm: int = 5000, seed: int = 42) -> float:
    """Monte-Carlo chi2 for tables where expected counts are too small for the
    asymptotic approximation. Resamples the table under independence."""
    rng = np.random.default_rng(seed)
    obs = ct.values.astype(float)
    stat = chi2_contingency(obs)[0]
    rows, cols, n = obs.sum(1), obs.sum(0), obs.sum()
    p_cell = np.outer(rows, cols).ravel() / (n * n)
    hits = 0
    for _ in range(n_perm):
        sim = rng.multinomial(int(n), p_cell).reshape(obs.shape).astype(float)
        if sim.sum(1).all() and sim.sum(0).all():
            if chi2_contingency(sim)[0] >= stat:
                hits += 1
    return (hits + 1) / (n_perm + 1)


def std_residuals(ct: pd.DataFrame) -> pd.DataFrame:
    """Standardised Pearson residuals, which show WHICH cells drive an
    association. Roughly, |z| > 2 is notable and |z| > 4 is strong."""
    chi2, p, dof, exp = chi2_contingency(ct)
    return pd.DataFrame((ct.values - exp) / np.sqrt(exp),
                        index=ct.index, columns=ct.columns)


def cluster_boot_props(data: pd.DataFrame, group_col: str, value_col: str,
                       categories: list, n_boot: int = 2000,
                       seed: int = 42) -> pd.DataFrame:
    """Category proportions within each group, with 95% CIs from a bootstrap
    that resamples CLUSTERS (authors/outlets), not rows."""
    rng = np.random.default_rng(seed)
    out = []
    for g, sub in data.groupby(group_col):
        clusters = sub.cluster.unique()
        idx = {c: sub.index[sub.cluster == c] for c in clusters}
        point = sub[value_col].value_counts(normalize=True)
        reps = np.zeros((n_boot, len(categories)))
        for b in range(n_boot):
            pick = rng.choice(clusters, size=len(clusters), replace=True)
            rows = np.concatenate([idx[c] for c in pick])
            vc = data.loc[rows, value_col].value_counts(normalize=True)
            reps[b] = [vc.get(c, 0.0) for c in categories]
        for j, c in enumerate(categories):
            lo, hi = np.percentile(reps[:, j], [2.5, 97.5])
            out.append({group_col: g, value_col: c, "prop": point.get(c, 0.0),
                        "lo": lo, "hi": hi})
    return pd.DataFrame(out)


def trend(d: pd.DataFrame, label: str = "", outcome: str = "is_repl",
          extra: str = "") -> dict:
    """Odds of `outcome` per year from an item-level logistic regression with
    standard errors clustered on author/outlet.

    `extra` appends covariates, e.g. "+ C(sub_c)" for the subreddit-adjusted
    RQ4 model that rules out a changing community mix producing the trend.
    """
    formula = f"{outcome} ~ t_years {extra}".strip()
    m = smf.logit(formula, data=d).fit(disp=0, cov_type="cluster",
                                       cov_kwds={"groups": d.cluster})
    ci = np.exp(m.conf_int().loc["t_years"])
    return {"subset": label, "n": len(d), "OR": float(np.exp(m.params.t_years)),
            "lo": float(ci.iloc[0]), "hi": float(ci.iloc[1]),
            "p": float(m.pvalues.t_years)}


def wilson(count, nobs):
    """Wilson binomial interval. Better behaved than the normal approximation
    for proportions near 0 or 1, which several half-year cells are."""
    lo, hi = proportion_confint(count, nobs, method="wilson")
    return np.asarray(lo), np.asarray(hi)


def ratio_table(nt: pd.DataFrame) -> pd.Series:
    """Replacement-to-augmentation ratio per ecosystem.

    Note this is invariant to whether the denominator includes tangential
    items, since both counts come from the same source. This is why the ratios
    were unaffected by a denominator error that did change the percentages.
    """
    ct = pd.crosstab(nt.source, nt.coarse_frame)
    return (ct["REPLACEMENT"] / ct["AUGMENTATION"]).reindex(SRC_ORDER)


def apply_report_style():
    """Matplotlib settings matching the figures in the submitted report."""
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "text.color": NAVY, "axes.labelcolor": NAVY,
        "xtick.color": NAVY, "ytick.color": NAVY,
        "figure.dpi": 110, "savefig.bbox": "tight", "pdf.fonttype": 42,
    })


def despine(ax, keep=("bottom",), grid_axis="y"):
    """Report figure convention: no box, one anchoring spine, light grid."""
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)
    for side in keep:
        ax.spines[side].set_color(GRID)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=.6)
        ax.set_axisbelow(True)
    ax.tick_params(length=0)
