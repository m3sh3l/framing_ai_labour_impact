# Frame-Coding Codebook — v1.0

**Project:** From Augmentation to Replacement: Competing Frames of AI's Labour Impact Across News, Public, and Insider Discourse, 2022–2026
**Author:** Meshaal Kirmani | **Supervisor:** Dr Chico Camargo
**Version:** 1.0 (draft for pilot coding) | **Date:** 2026-07-09
**Status:** To be refined after pilot coding of 50 items per corpus (→ v2.0)

---

## 1. Purpose and scope

This codebook operationalises Entman's (1993) four-function framing schema for the AI-labour domain. It is used identically by (a) the human annotator, (b) the primary LLM coder (GABRIEL), and (c) the cross-model robustness check. Every rule must be explicit enough that two coders reading the same rule reach the same code without discussion.

**Unit of analysis:** one text unit =
- **News (MediaCloud):** the headline. Body text is NOT consulted (headline-only mode, per Liu et al. 2019).
- **Reddit:** the submission title, plus self-text if the title alone is ambiguous (≤ first 100 words of self-text).
- **Hacker News:** the story title, plus story text for Ask/Show HN posts (≤ first 100 words).

## 2. Step 0 — Relevance screen

Before frame coding, answer: **"Does this text make a claim, however implicit, about AI's effect on human work?"**

- **YES** → proceed to coarse frame (Step 1).
- **NO** → code `TANGENTIAL` and stop. All function codes = `N/A`.

`TANGENTIAL` includes: AI product announcements with no labour claim; job ads; AI technical discussion; labour news with no AI component; texts where AI and work co-occur only incidentally ("I work at an AI company").

> **Rule R0 (frame ≠ topic).** Being *about* AI and jobs is not the same as *framing* AI's labour effect. Code the characterisation the text constructs, not the subject matter it mentions. If the text mentions both but characterises nothing, it is TANGENTIAL. *(This rule addresses the topical-overlap ambiguity flagged in proposal feedback.)*

## 3. Step 1 — Coarse frame (primary variable)

Assign exactly one:

| Code | Definition | Positive indicators |
|---|---|---|
| `REPLACEMENT` | AI is characterised as taking over work previously done by humans; humans exit the task/job/occupation | "replace", "take your job", "displace", "automate away", "obsolete", "layoffs due to AI", "no longer need" |
| `AUGMENTATION` | AI is characterised as extending, assisting, or increasing the value of human work; humans stay in the loop | "copilot", "assist", "boost productivity", "supercharge", "AI skills increase pay", "works alongside" |
| `TRANSFORMATION` | AI is characterised as restructuring the nature, organisation, or distribution of work itself — neither simple loss nor simple gain | "reshape work", "new kinds of jobs", "redefine the profession", "future of work", "task recomposition" |
| `MIXED` | Two or more of the above are given roughly equal weight in the same unit | "will kill some jobs and create others", explicit both-sides framing |
| `TANGENTIAL` | Failed the Step 0 screen | — |

**Decision rules:**

- **R1 (dominance).** If one frame is clearly foregrounded (headline emphasis, first clause, evaluative language) code that frame even if another is mentioned. Use `MIXED` only when weighting is genuinely equal. Aim for < 15% MIXED; if pilot coding exceeds this, tighten R1 in v2.
- **R2 (questions count).** A headline posed as a question ("Will AI take your job?") codes the frame the question presupposes — here REPLACEMENT. The interrogative form does not neutralise the frame (Entman: selection *and* salience).
- **R3 (denial still invokes).** A text *arguing against* a frame ("AI won't take your jobs") is coded to the frame it engages — REPLACEMENT — with moral evaluation capturing the stance (see 4.3). Rationale: the frame inventory (RQ1) tracks which frames structure discourse, not which are endorsed.
- **R4 (sarcasm/informality — Reddit/HN).** Code the literal frame invoked unless sarcasm is unmistakable from the text unit alone (no thread context). If unmistakable, code the intended frame. Note the ambiguity in the `notes` field; these items feed codebook refinement.
- **R5 (no outside knowledge).** Code only what the text says. Do not use knowledge of the linked article, the author, or subsequent events.

## 4. Step 2 — Entman function codes (secondary variables)

Assign one value per function. Use `NONE` when the function is absent from the text unit — headlines often carry only 1–2 functions; that is data, not failure.

### 4.1 Problem definition — "what is the issue?"

| Code | Definition |
|---|---|
| `JOB_LOSS` | Unemployment, displacement, redundancy, shrinking demand for workers |
| `SKILL_CHANGE` | Skills becoming obsolete or newly required; task recomposition; retraining need |
| `OPPORTUNITY` | Productivity, growth, new capability or economic gain as the central issue |
| `INEQUALITY_POWER` | Distributional effects: who captures gains, wage pressure, monitoring, employer power |
| `NONE` | No labour problem/issue is defined |

### 4.2 Causal attribution — "who/what is responsible?"

| Code | Definition |
|---|---|
| `TECHNOLOGY` | The capability itself drives the effect ("AI is coming for jobs") |
| `FIRMS` | Employers/companies choosing to deploy, cut, or restructure |
| `POLICY` | Government, regulation (or its absence), institutions |
| `WORKERS` | Workers' own choices, skills, adaptability ("learn AI or fall behind") |
| `NONE` | No causal agent identified |

### 4.3 Moral evaluation — "is it good or bad?"

| Code | Definition |
|---|---|
| `NEGATIVE` | Harmful, threatening, unjust |
| `POSITIVE` | Beneficial, exciting, liberating |
| `AMBIVALENT` | Explicitly both / traded off |
| `NEUTRAL` | Descriptive; no evaluative language |
| `NONE` | Function absent (rare — prefer NEUTRAL if the text describes without evaluating) |

### 4.4 Treatment recommendation — "what should be done?"

| Code | Definition |
|---|---|
| `REGULATE` | Policy intervention, law, protections, slowing deployment |
| `ADAPT` | Upskilling, reskilling, individual or organisational adaptation |
| `REDISTRIBUTE` | UBI, taxation of AI gains, shorter week, ownership changes |
| `ACCELERATE` | Adopt faster, remove barriers, embrace |
| `NONE` | No treatment stated or implied |

## 5. Worked examples (real items from the corpora)

| Text | Coarse | Problem | Cause | Moral | Treatment |
|---|---|---|---|---|---|
| "Does ChatGPT Mean Robots Are Coming for the Skilled Jobs?" (HN, Dec 2022) | REPLACEMENT | JOB_LOSS | TECHNOLOGY | NEUTRAL | NONE |
| "300 million jobs could be affected by latest wave of AI, says Goldman Sachs" (Reddit, Mar 2023) | REPLACEMENT | JOB_LOSS | TECHNOLOGY | NEUTRAL | NONE |
| "AI skills improve job prospects: causal evidence from a hiring experiment" (lit.) | AUGMENTATION | SKILL_CHANGE | WORKERS | POSITIVE | ADAPT |
| "We are probably never going to see the changes envisioned by AI enthusiasts" (Reddit, Mar 2023) | REPLACEMENT (R3: engages and denies the displacement frame) | JOB_LOSS | TECHNOLOGY | NEGATIVE (toward the discourse) | NONE |

*(Extend to ≥ 20 examples during pilot coding; disagreement cases become the v2 edge-case appendix.)*

## 6. Annotation procedure

1. **Pilot:** 50 items per corpus (150 total), coded by author. Compute per-category frequencies; refine rules; freeze v2.
2. **Gold standard:** 300 items (100 per ecosystem), stratified by half-year. Daily cap ≈ 60 items to manage fatigue. Randomised order, ecosystem-blind where possible (source column hidden).
3. **Record per item:** `item_id, coarse_frame, problem, cause, moral, treatment, confidence (1–3), notes`.
4. **Validation gate:** GABRIEL vs human Cohen's κ per variable. Target κ ≥ 0.60 on ≥ 3 of 4 functions; fallback per proposal → coarse typology only, κ ≥ 0.55, reported transparently.
5. Codebook is versioned; every rule change after pilot is logged with rationale (goes in the logbook + repo).

## 7. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-07-09 | Initial draft from proposal §4.3, with R0–R5 decision rules added in response to proposal feedback (framing vs topic; coding consistency) |
