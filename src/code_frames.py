"""Primary LLM frame coder: the Entman schema over the annotation text units.

Proposal §4.4 specifies the GABRIEL framework for this axis. GABRIEL was not
resolvable as an installable package (the `gabriel` name on PyPI is an unrelated
Discord tool), so the Entman prompts are implemented directly against the
Anthropic SDK. The methodological substance is unchanged: the same codebook,
the same decision rules, validated against the same 300 human-coded items, with
every call logged. Document this deviation in Methods §4.4.

Design decisions that matter for validity:

* **Identical instrument.** The model receives `prompts/frame_coding_system.md`,
  which is the same codebook text and disambiguation guidance the human coder
  works from. Proposal §4.3 requires the codebook be "used identically" by human
  and machine; giving the model a weaker instrument would confound coder
  disagreement with instrument disagreement.
* **Identical text unit.** Items come from `annotation_sheet.csv`, so the model
  sees exactly the string the human sees: same HTML cleaning, same 100-word
  body cap, same source-label blinding (no source, subreddit, outlet, URL or
  engagement metrics).
* **Structured outputs** constrain every field to the codebook's value set, so
  an unparseable or invented category cannot enter the dataset.
* **Refusals are caught, never silently coded.** `stop_reason == "refusal"` is
  logged and the item is left uncoded for retry, never written as a null,
  which would corrupt kappa invisibly.
* **Full audit trail.** Every call's prompt, model version, response and token
  usage is appended to `data/coding/llm_calls.jsonl` (proposal §4.7).
* **Resumable.** Already-coded ids are skipped, so an interrupted run costs
  nothing.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...        # or put it in .env
    python src/code_frames.py                  # codes the 300 gold items
    python src/code_frames.py --input data/clean/frozen_20260802/reddit_sample.csv \\
        --text-col text_unit --out data/coding/llm_codes_reddit.jsonl
"""
import argparse
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from utils import ROOT, log

MODEL = "claude-opus-5"
SYSTEM_PATH = ROOT / "prompts/frame_coding_system.md"

VALID = {
    "coarse_frame": ["REPLACEMENT", "AUGMENTATION", "TRANSFORMATION", "MIXED", "TANGENTIAL"],
    "problem": ["JOB_LOSS", "SKILL_CHANGE", "OPPORTUNITY", "INEQUALITY_POWER", "NONE"],
    "cause": ["TECHNOLOGY", "FIRMS", "POLICY", "WORKERS", "NONE"],
    "moral": ["NEGATIVE", "POSITIVE", "AMBIVALENT", "NEUTRAL", "NONE"],
    "treatment": ["REGULATE", "ADAPT", "REDISTRIBUTE", "ACCELERATE", "NONE"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "string", "enum": v} for k, v in VALID.items()},
        "confidence": {"type": "integer", "enum": [1, 2, 3]},
        "notes": {"type": "string"},
    },
    "required": list(VALID) + ["confidence", "notes"],
    "additionalProperties": False,
}


def load_env_key():
    """Read ANTHROPIC_API_KEY from the environment, falling back to .env."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/annotation/annotation_sheet.csv")
    ap.add_argument("--id-col", default="id")
    ap.add_argument("--text-col", default="text_unit")
    ap.add_argument("--out", default="data/coding/llm_codes_gold300.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=MODEL,
                    help="claude-opus-5 (default, best judgement on borderline "
                         "frames) | claude-sonnet-5 | claude-haiku-4-5 (cheapest). "
                         "The model id is recorded per call in the audit log, so "
                         "whichever you use is reportable.")
    args = ap.parse_args()
    model = args.model

    if not load_env_key():
        raise SystemExit(
            "No ANTHROPIC_API_KEY found.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...      (this shell)\n"
            "  or add a line ANTHROPIC_API_KEY=sk-ant-... to .env  (git-ignored)")

    import anthropic
    client = anthropic.Anthropic()

    system_text = SYSTEM_PATH.read_text()
    # stable across runs, unlike hash(); this fingerprints which prompt
    # version produced each code (proposal §4.7 auditability)
    system_sha = hashlib.sha256(system_text.encode()).hexdigest()[:16]
    df = pd.read_csv(ROOT / args.input)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path = out_path.parent / "llm_calls.jsonl"

    done = set()
    if out_path.exists():
        with open(out_path) as f:
            done = {json.loads(l)["id"] for l in f if l.strip()}
    todo = df[~df[args.id_col].isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    log.info("Coding %d items with %s (%d already done)", len(todo), model, len(done))
    if todo.empty:
        return

    lock = threading.Lock()
    stats = {"ok": 0, "refused": 0, "failed": 0}

    def code_one(rec):
        item_id, text = rec[args.id_col], str(rec[args.text_col])
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4000,
                system=[{"type": "text", "text": system_text,
                         "cache_control": {"type": "ephemeral"}}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user",
                           "content": f"Code this text unit:\n\n---\n{text}\n---"}],
            )
        except Exception as e:                       # network / API failure
            with lock:
                stats["failed"] += 1
                log.warning("call failed for %s: %s", item_id, e)
            return

        # A refusal must never be written as a code, as it would corrupt kappa
        # silently. Leave the item uncoded so a re-run retries it.
        if resp.stop_reason == "refusal":
            with lock:
                stats["refused"] += 1
                log.warning("REFUSAL on %s (%s) - left uncoded", item_id,
                            getattr(resp.stop_details, "category", None))
                with open(audit_path, "a") as f:
                    f.write(json.dumps({"id": item_id, "stop_reason": "refusal",
                                        "model": resp.model}) + "\n")
            return

        text_out = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            codes = json.loads(text_out)
        except json.JSONDecodeError:
            with lock:
                stats["failed"] += 1
                log.warning("unparseable response for %s", item_id)
            return

        row = {"id": item_id, **codes}
        u = resp.usage
        audit = {"id": item_id, "model": resp.model, "stop_reason": resp.stop_reason,
                 "system_sha": system_sha, "input": text,
                 "response": codes,
                 "usage": {"input": u.input_tokens, "output": u.output_tokens,
                           "cache_read": getattr(u, "cache_read_input_tokens", 0),
                           "cache_write": getattr(u, "cache_creation_input_tokens", 0)}}
        with lock:
            with open(out_path, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            with open(audit_path, "a") as f:
                f.write(json.dumps(audit, ensure_ascii=False) + "\n")
            stats["ok"] += 1
            if stats["ok"] % 25 == 0:
                log.info("coded %d/%d", stats["ok"], len(todo))

    records = todo.to_dict("records")
    # Send one request first so it writes the prompt cache; concurrent requests
    # issued before that would each pay the full uncached price.
    code_one(records[0])
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(code_one, records[1:]))

    log.info("Done: %d coded, %d refused, %d failed -> %s",
             stats["ok"], stats["refused"], stats["failed"], out_path)
    if stats["refused"] or stats["failed"]:
        log.warning("Re-run to retry the %d uncoded item(s).",
                    stats["refused"] + stats["failed"])


if __name__ == "__main__":
    main()
