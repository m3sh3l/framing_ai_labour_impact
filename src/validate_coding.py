"""Validation gate: human vs LLM agreement on the 300-item gold standard.

Proposal §3.4 success criterion: Cohen's kappa >= 0.60 (substantial, Landis &
Koch) on at least three of the four Entman functions. If unmet after codebook
refinement, fall back to the coarse three-category typology at kappa >= 0.55
with full methodological transparency.

Reports, per variable:
  * Cohen's kappa, raw percentage agreement, and prevalence
  * kappa on the NON-TANGENTIAL subset. TANGENTIAL items are comparatively easy
    to agree on and make up ~a third of the sample, so including them inflates
    kappa relative to the frame distinctions the study actually rests on. Both
    numbers are reported; the report should quote both.
  * kappa per ecosystem, to detect annotation drift across sources
  * Krippendorff's alpha for `confidence` (ordinal)
  * the confusion pairs driving disagreement, which are the input to a
    codebook v2 refinement cycle

Usage:
    python src/validate_coding.py [--human <xlsx/csv>] [--llm <jsonl>]
"""
import argparse
import json

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from utils import ROOT, log

CODE_COLS = ["coarse_frame", "problem", "cause", "moral", "treatment"]
FUNCTIONS = ["problem", "cause", "moral", "treatment"]   # the four Entman functions
THRESHOLD = 0.60
FALLBACK_THRESHOLD = 0.55


def landis_koch(k: float) -> str:
    for lo, label in ((0.81, "almost perfect"), (0.61, "substantial"),
                      (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if k >= lo:
            return label
    return "poor"


def kappa_row(a: pd.Series, b: pd.Series) -> dict:
    labels = sorted(set(a) | set(b))
    k = cohen_kappa_score(a, b, labels=labels)
    return {"n": len(a), "kappa": round(k, 3), "agreement": round((a == b).mean(), 3),
            "interpretation": landis_koch(k)}


def top_confusions(a: pd.Series, b: pd.Series, n: int = 3):
    labels = sorted(set(a) | set(b))
    cm = confusion_matrix(a, b, labels=labels)
    pairs = [(labels[i], labels[j], cm[i][j])
             for i in range(len(labels)) for j in range(len(labels))
             if i != j and cm[i][j] > 0]
    return sorted(pairs, key=lambda t: -t[2])[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--human", default="data/annotation/annotation_sheet_filledin.xlsx")
    ap.add_argument("--llm", default="data/coding/llm_codes_gold300.jsonl")
    ap.add_argument("--key", default="data/annotation/annotation_key.csv")
    ap.add_argument("--out", default="data/coding/validation_report.txt")
    args = ap.parse_args()

    hp = ROOT / args.human
    human = pd.read_excel(hp) if hp.suffix == ".xlsx" else pd.read_csv(hp)
    llm = pd.DataFrame([json.loads(l) for l in open(ROOT / args.llm)])
    key = pd.read_csv(ROOT / args.key)[["id", "source", "half_year"]]

    for c in CODE_COLS:
        human[c] = human[c].astype(str).str.strip().str.upper()
        llm[c] = llm[c].astype(str).str.strip().str.upper()

    m = (human[["id"] + CODE_COLS + ["confidence"]]
         .merge(llm[["id"] + CODE_COLS + ["confidence"]], on="id",
                suffixes=("_h", "_m"))
         .merge(key, on="id", how="left"))
    log.info("Matched %d items (human %d, llm %d)", len(m), len(human), len(llm))
    if len(m) != len(human):
        log.warning("MISMATCH: %d human items did not join to an LLM code",
                    len(human) - len(m))

    L = []
    L.append(f"VALIDATION GATE — human vs LLM, n={len(m)}")
    L.append(f"Criterion: kappa >= {THRESHOLD} on >=3 of 4 Entman functions "
             f"(proposal §3.4)\n")

    # --- headline table -----------------------------------------------------
    L.append("ALL ITEMS")
    L.append(f"{'variable':16s} {'n':>4s} {'kappa':>7s} {'agree':>7s}  interpretation")
    results = {}
    for c in CODE_COLS:
        r = kappa_row(m[f"{c}_h"], m[f"{c}_m"])
        results[c] = r["kappa"]
        L.append(f"{c:16s} {r['n']:4d} {r['kappa']:7.3f} {r['agreement']:7.3f}  {r['interpretation']}")

    # --- excluding TANGENTIAL ----------------------------------------------
    both_sub = m[(m.coarse_frame_h != "TANGENTIAL") & (m.coarse_frame_m != "TANGENTIAL")]
    L.append(f"\nEXCLUDING TANGENTIAL (n={len(both_sub)}) — the frame distinctions "
             "the study rests on")
    results_sub = {}
    for c in CODE_COLS:
        if len(both_sub) < 10:
            continue
        r = kappa_row(both_sub[f"{c}_h"], both_sub[f"{c}_m"])
        results_sub[c] = r["kappa"]
        L.append(f"{c:16s} {r['n']:4d} {r['kappa']:7.3f} {r['agreement']:7.3f}  {r['interpretation']}")

    # --- per ecosystem (annotation drift) -----------------------------------
    L.append("\nPER ECOSYSTEM (detects drift across sources)")
    hdr = f"{'variable':16s}" + "".join(f"{s[:11]:>12s}" for s in sorted(m.source.dropna().unique()))
    L.append(hdr)
    for c in CODE_COLS:
        cells = ""
        for s in sorted(m.source.dropna().unique()):
            sub = m[m.source == s]
            cells += f"{kappa_row(sub[f'{c}_h'], sub[f'{c}_m'])['kappa']:12.3f}"
        L.append(f"{c:16s}{cells}")

    # --- confidence agreement ----------------------------------------------
    try:
        import krippendorff
        import numpy as np
        alpha = krippendorff.alpha(
            reliability_data=np.array([m.confidence_h.astype(float),
                                       m.confidence_m.astype(float)]),
            level_of_measurement="ordinal")
        L.append(f"\nconfidence (Krippendorff alpha, ordinal): {alpha:.3f}")
    except ImportError:
        L.append("\nconfidence: krippendorff not installed (pip install krippendorff)")

    # --- where the disagreement is -----------------------------------------
    L.append("\nTOP CONFUSIONS  (human -> llm : count)")
    for c in CODE_COLS:
        pairs = top_confusions(m[f"{c}_h"], m[f"{c}_m"])
        if pairs:
            L.append(f"  {c}: " + " | ".join(f"{a}->{b}: {n}" for a, b, n in pairs))

    # --- gate decision ------------------------------------------------------
    passing = [c for c in FUNCTIONS if results[c] >= THRESHOLD]
    coarse_k = results["coarse_frame"]
    L.append("\n" + "=" * 68)
    L.append(f"Entman functions at/above {THRESHOLD}: {len(passing)}/4  {passing}")
    L.append(f"coarse_frame kappa: {coarse_k:.3f}")
    if len(passing) >= 3:
        L.append("DECISION: PASS — proceed with the full four-function schema.")
    elif coarse_k >= FALLBACK_THRESHOLD:
        L.append(f"DECISION: FAIL on the four-function schema "
                 f"({len(passing)}/4 >= {THRESHOLD}).")
        L.append(f"  Fallback available: coarse_frame kappa {coarse_k:.3f} "
                 f">= {FALLBACK_THRESHOLD}.")
        L.append("  Per proposal §3.4: run ONE codebook refinement cycle targeting "
                 "the top confusions above, re-code the same 300, and recompute. "
                 "If still short, report the coarse three-category typology with "
                 "full transparency.")
    else:
        L.append("DECISION: FAIL on both the four-function schema and the coarse "
                 "fallback. Refine the codebook and re-code before proceeding.")
    L.append("=" * 68)

    report = "\n".join(L)
    (ROOT / args.out).write_text(report + "\n")
    print(report)

    m.to_csv(ROOT / "data/coding/human_vs_llm_merged.csv", index=False)
    log.info("Wrote %s and human_vs_llm_merged.csv", args.out)


if __name__ == "__main__":
    main()
