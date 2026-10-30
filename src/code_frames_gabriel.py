"""Cross-framework validation axis: GABRIEL (OpenAI) on the gold 300.

Proposal §4.4 specifies GABRIEL for the primary axis; the primary coder here is
Claude via `src/code_frames.py`, so GABRIEL instead provides the **independent
cross-check**. That is a stronger design than the proposal's original
cross-model plan, because the two axes differ on two dimensions rather than one:

    axis 1  Claude Opus 5   direct categorical classification (single label)
    axis 2  GABRIEL + GPT   0-100 probability per category, argmax to a label

So agreement between them cannot be explained by a shared prompt scaffold or a
shared measurement formulation. Divergence is itself reportable (proposal §4.4).

GABRIEL (Asirvatham, Mokski & Shleifer 2026, `GABRIEL-ratings` on PyPI) is a
prompt-based wrapper over the OpenAI API. Its `generate_simple_classification`
asks the model to score how strongly a passage belongs to each named category,
given a description of each. We pass the codebook's own category names and
definitions, so the instrument is the same codebook expressed in GABRIEL's
native form.

Full 0-100 distributions are retained, not just the argmax: the margin between
the top two categories is a usable ambiguity measure, and near-ties are exactly
the items a codebook v2 refinement should target.

Setup:
    add a line  OPENAI_API_KEY=sk-...  to .env   (git-ignored)

Usage:
    python src/code_frames_gabriel.py --variables coarse_frame     # cheapest
    python src/code_frames_gabriel.py                              # all five
"""
import argparse
import asyncio
import json
import os
import re

import pandas as pd

from utils import ROOT, log

# Codebook category definitions, in GABRIEL's (name -> description) form.
CODEBOOK = {
    "coarse_frame": {
        "REPLACEMENT": "AI is characterised as taking over work previously done by humans; humans exit the task, job or occupation.",
        "AUGMENTATION": "AI is characterised as extending, assisting or increasing the value of human work; humans stay in the loop.",
        "TRANSFORMATION": "AI is characterised as restructuring the nature, organisation or distribution of work itself — neither simple loss nor simple gain.",
        "MIXED": "Two or more of replacement, augmentation and transformation are given roughly equal weight in the same passage.",
        "TANGENTIAL": "The passage makes no claim, even implicit, about AI's effect on human work.",
    },
    "problem": {
        "JOB_LOSS": "The issue is unemployment, displacement, redundancy or shrinking demand for workers.",
        "SKILL_CHANGE": "The issue is skills becoming obsolete or newly required, task recomposition, or retraining need.",
        "OPPORTUNITY": "The issue is productivity, growth, new capability or economic gain.",
        "INEQUALITY_POWER": "The issue is distributional: who captures gains, wage pressure, monitoring, employer power.",
        "NONE": "No labour problem or issue is defined in the passage.",
    },
    "cause": {
        "TECHNOLOGY": "The capability itself drives the effect, e.g. 'AI is coming for jobs'.",
        "FIRMS": "Employers or companies choosing to deploy, cut or restructure are responsible.",
        "POLICY": "Government, regulation or its absence, or institutions are responsible.",
        "WORKERS": "Workers' own choices, skills or adaptability are responsible.",
        "NONE": "No causal agent is identified.",
    },
    "moral": {
        "NEGATIVE": "The effect is characterised as harmful, threatening or unjust.",
        "POSITIVE": "The effect is characterised as beneficial, exciting or liberating.",
        "AMBIVALENT": "The passage explicitly presents the effect as both good and bad, or traded off.",
        "NEUTRAL": "The passage is descriptive, with no evaluative language.",
        "NONE": "Evaluation is absent from the passage entirely.",
    },
    "treatment": {
        "REGULATE": "Policy intervention, law, protections, slowing deployment, or organised resistance is urged.",
        "ADAPT": "Upskilling, reskilling, or individual/organisational adaptation is urged.",
        "REDISTRIBUTE": "Universal basic income, taxing AI gains, a shorter working week, or ownership change is urged.",
        "ACCELERATE": "Faster adoption, removing barriers, or embracing the technology is urged.",
        "NONE": "No treatment is stated or implied.",
    },
}

# Decision rules passed through GABRIEL's clarification slot, so both axes work
# from the same rules, and not only the same category names.
CLARIFICATION = (
    "Apply these rules. R0: being about AI and jobs is not the same as framing "
    "AI's labour effect; if the passage mentions both but characterises nothing, "
    "it is TANGENTIAL. R1: if one frame is clearly foregrounded, prefer it over "
    "MIXED. R2: a question codes the frame it presupposes. R3: a passage arguing "
    "against a frame is coded to the frame it engages, not away from it. R5: use "
    "only what the passage says, not outside knowledge. For causal attribution, "
    "if a named company performs the action, that is FIRMS even when AI is the "
    "stated reason. NONE is a legitimate and common answer for short headlines."
)


def ensure_ssl_certs():
    """Point Python's default SSL context at certifi's CA bundle.

    GABRIEL calls the API through aiohttp, which builds an ssl.create_default_context()
    and therefore reads the SYSTEM trust store. On a python.org macOS install that
    store is empty unless "Install Certificates.command" has been run, so every
    request fails with CERTIFICATE_VERIFY_FAILED. (The Anthropic SDK is unaffected:
    httpx bundles certifi itself.) ssl.create_default_context() honours SSL_CERT_FILE,
    so setting it here fixes aiohttp without touching the system.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass


def load_openai_key() -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return True
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.split("=", 1)[1].strip()
                return True
    return False


def parse_scores(raw: str, categories: list) -> dict | None:
    """Pull a {category: 0-100} mapping out of GABRIEL's response.

    GABRIEL's classification template returns markdown-fenced JSON shaped as
        {"data": [{"classification category": "REPLACEMENT", "rating": 0}, ...]}
    so the rows have to be walked instead of read as a flat mapping. A flat
    {category: rating} form is also accepted, since the template wording varies
    with the `format` argument and across library versions.
    """
    blob = re.search(r"\{.*\}", raw or "", re.S)      # tolerates the ```json fence
    if not blob:
        return None
    try:
        d = json.loads(blob.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None

    wanted = {c.upper(): c for c in categories}
    out = {}

    rows = d.get("data")
    if isinstance(rows, list):                        # GABRIEL's documented shape
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = next((str(v) for k, v in row.items()
                         if "categ" in str(k).lower()), None)
            rating = next((v for k, v in row.items()
                           if "rating" in str(k).lower() or "score" in str(k).lower()), None)
            if name and rating is not None and name.strip().upper() in wanted:
                try:
                    out[wanted[name.strip().upper()]] = float(rating)
                except (TypeError, ValueError):
                    pass
    else:                                             # flat {category: rating}
        for k, v in d.items():
            if str(k).strip().upper() in wanted:
                try:
                    out[wanted[str(k).strip().upper()]] = float(v)
                except (TypeError, ValueError):
                    pass
    return out or None


async def main_async(args):
    from gabriel.archangel import OpenAIClient
    from gabriel.foundational_functions import generate_simple_classification

    client = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"])
    df = pd.read_csv(ROOT / "data/annotation/annotation_sheet.csv")
    if args.limit:
        df = df.head(args.limit)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if out_path.exists():
        with open(out_path) as f:
            done = {(json.loads(l)["id"], json.loads(l)["variable"]) for l in f if l.strip()}

    variables = args.variables.split(",")
    jobs = [(r["id"], r["text_unit"], v) for _, r in df.iterrows() for v in variables
            if (r["id"], v) not in done]
    log.info("GABRIEL: %d calls (%d items x %d variables), model=%s",
             len(jobs), len(df), len(variables), args.model)
    if not jobs:
        return

    # Pace to stay under the org's tokens-per-minute ceiling. Each call costs
    # roughly 1.2k tokens, so a 30k TPM tier supports ~24 calls/min; exceeding it
    # returns 429s that waste the call without producing a code.
    delay = args.workers * 60.0 / max(args.rpm, 1)
    sem = asyncio.Semaphore(args.workers)
    lock = asyncio.Lock()
    stats = {"ok": 0, "bad": 0}

    async def one(item_id, text, var):
        cats = list(CODEBOOK[var])
        async with sem:
            try:
                raw = await generate_simple_classification(
                    attributes=cats,
                    descriptions=[CODEBOOK[var][c] for c in cats],
                    passage=str(text),
                    object_category="text unit about artificial intelligence and work",
                    attribute_category=f"Entman {var}",
                    classification_clarification=CLARIFICATION,
                    model=args.model, client=client, temperature=0.0, timeout=90,
                )
            except Exception as e:
                async with lock:
                    stats["bad"] += 1
                    msg = str(e)
                    log.warning("call failed %s/%s: %s", item_id, var,
                                "rate limit" if "rate_limit" in msg else msg[:120])
                await asyncio.sleep(delay)
                return
            await asyncio.sleep(delay)
        scores = parse_scores(raw or "", cats)
        if not scores:
            async with lock:
                stats["bad"] += 1
                log.warning("unparseable %s/%s", item_id, var)
            return
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        margin = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else None
        rec = {"id": item_id, "variable": var, "code": ranked[0][0],
               "margin": margin, "scores": scores, "model": args.model}
        async with lock:
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["ok"] += 1
            if stats["ok"] % 50 == 0:
                log.info("  %d/%d", stats["ok"], len(jobs))

    await asyncio.gather(*(one(i, t, v) for i, t, v in jobs))
    log.info("GABRIEL done: %d ok, %d failed -> %s", stats["ok"], stats["bad"], out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variables", default=",".join(CODEBOOK),
                    help="comma-separated; 'coarse_frame' alone is the cheapest useful run")
    ap.add_argument("--model", default="gpt-4o",
                    help="OpenAI model. gpt-4o-mini is GABRIEL's default but is a "
                         "weak comparator against a frontier primary coder.")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--rpm", type=int, default=20,
                    help="target requests/minute; keep below (org TPM / ~1200 tokens per call)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="data/coding/gabriel_codes_gold300.jsonl")
    args = ap.parse_args()

    ensure_ssl_certs()
    if not load_openai_key():
        raise SystemExit("No OPENAI_API_KEY found.\n"
                         "  add a line  OPENAI_API_KEY=sk-...  to .env  (git-ignored)")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
