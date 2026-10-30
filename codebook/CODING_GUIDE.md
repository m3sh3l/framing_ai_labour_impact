# Coding guide — how to pick the right option

Keep this open while you annotate. Every example below is a **real item from
your corpus that is deliberately NOT in your 300** — coding your gold-standard
items with my help would make the human codes non-independent of the LLM and
invalidate the κ comparison. Learn the boundaries here, then judge your own 300
alone.

---

## Order of operations — always in this sequence

```
Step 0   Is this even about AI's effect on work?  ──NO──▶ TANGENTIAL, all functions N/A, stop
   │ YES
Step 1   Which coarse frame does the text construct?
   │
Step 2   Problem → Cause → Moral → Treatment   (NONE is a legitimate answer for each)
   │
Step 3   Confidence 1–3, plus a note if you hesitated
```

Do **not** read the functions first and infer the frame from them. The frame is
the characterisation the text builds; the functions describe how it is built.

---

## Step 0 — the TANGENTIAL screen

Ask exactly this: **does the text make a claim, however implicit, about AI's
effect on human work?**

`TANGENTIAL` is not a failure code. Your relevance filter deliberately casts
wide (an AI term *and* a labour term anywhere in the text), so a meaningful
share of items will legitimately fail this screen. Coding them honestly is what
lets you report corpus precision.

Four things that reach your corpus but are TANGENTIAL:

| Type | Real example |
|---|---|
| AI product with no labour claim | *"Show HN: AI Coloring Pages Generator"* |
| Labour content with no AI claim | *"[Virginia] Identity Verification Statement from Claimant"* |
| AI as the field someone works *in*, not an agent acting *on* work | *"Tips on how to transition from AI/ML to Front-End?"* |
| Pure filter coincidence | *"How I lost 95% of my cryptocurrency value in one year"* |

> **Rule R0 (frame ≠ topic).** Being *about* AI and jobs is not the same as
> *framing* AI's labour effect. If the text mentions both but characterises
> nothing, it is TANGENTIAL. This is the rule that answers Nicholls &
> Culpepper's critique — it is doing real theoretical work, so apply it strictly.

**Borderline worth knowing:** *"Created yet another cover letter generator"* —
an AI tool used in the labour market, but it makes no claim about AI's *effect*
on work. TANGENTIAL, confidence 2, note it.

---

## Step 1 — the coarse frame

### The four positive codes

| Code | The claim being made | Where humans end up |
|---|---|---|
| `REPLACEMENT` | AI takes over work humans did | Humans exit the task/job |
| `AUGMENTATION` | AI extends, assists, or raises the value of human work | Humans stay, doing it better |
| `TRANSFORMATION` | AI restructures the nature or organisation of work | Humans stay, doing something *different* |
| `MIXED` | Two or more of the above carry roughly equal weight | — |

### The four boundaries that will cost you κ

**① REPLACEMENT vs TRANSFORMATION** — the most common error.
Ask: *do humans exit, or does the work change shape?*

- *"AI Could Wipe Out 100 Million Jobs In The Next 10 Years"* → **REPLACEMENT**
  (jobs cease to exist)
- *"How AI Is Transforming Hiring for Employers and Job Seekers"* →
  **TRANSFORMATION** (hiring still happens, done differently)

**② AUGMENTATION vs TRANSFORMATION** — augmentation keeps the *same* work and
makes it better; transformation changes *what the work is*.

- *"Kaiser Permanente strikes a deal for physicians to use an AI copilot"* →
  **AUGMENTATION** (physicians still practising medicine, assisted)
- *"Will AI pull the career ladder up out of reach – or just change what it
  looks like?"* → the *ladder itself* is restructured → **TRANSFORMATION**
  (though see ④ — this one is genuinely arguable)

**③ MIXED vs TRANSFORMATION** — a real trap. TRANSFORMATION is its own frame,
not a blend. Use MIXED only when two *distinct* frames are both present and
balanced.

- *"Americans fear AI will cost jobs and dull thinking. Experts aren't so sure"*
  → two opposed positions, neither dominant → **MIXED**
- *"AI will kill some jobs and create others"* → **MIXED** (loss + gain), not
  transformation
- A text saying work is *recomposed* is TRANSFORMATION even though that sounds
  like "a bit of both"

> Target under 15% MIXED. If you exceed that, you are probably using MIXED where
> rule R1 (dominance) should apply — see below.

**④ Question headlines** — *"Will AI pull the career ladder up out of reach –
or just change what it looks like?"* poses two options explicitly. If neither is
foregrounded, MIXED is defensible; if the phrasing tilts, code the tilt. Either
way, **confidence 2 and a note** — these are exactly the items that should feed
codebook v2.

### The three decision rules people forget

**R1 — dominance.** If one frame is foregrounded (headline emphasis, first
clause, evaluative language), code it even if another is mentioned. MIXED is for
genuine parity, not for "both appear".

**R2 — questions count.** A question codes the frame it *presupposes*.
- *"Which skill will take the longest to be replaced by AI?"* → presupposes
  replacement → **REPLACEMENT**. The interrogative does not neutralise it.

**R3 — denial still invokes.** A text *arguing against* a frame is coded to the
frame it engages; the stance is captured in moral evaluation.
- *"AI Won't Cause Unemployment"* → **REPLACEMENT**
- *"Goldman Sachs CEO Says AI 'Job Apocalypse' Is 'Overblown'"* → **REPLACEMENT**

This feels wrong the first few times. The rationale: RQ1 tracks which frames
*structure* the discourse, not which are endorsed. A rebuttal keeps the frame
alive.

**R5 — no outside knowledge.** Code only what the text says. Not what the linked
article says, not what you know about the company.

---

## Step 2 — the four Entman functions

`NONE` is legitimate and will be common, especially on 13-word headlines. Do not
manufacture a code from inference.

### 2.1 Problem definition — *what is the issue?*

| Code | Use when the central issue is |
|---|---|
| `JOB_LOSS` | Unemployment, displacement, redundancy, shrinking demand |
| `SKILL_CHANGE` | Skills obsolete or newly required; retraining; task recomposition |
| `OPPORTUNITY` | Productivity, growth, new capability, economic gain |
| `INEQUALITY_POWER` | Who captures the gains; wage pressure; monitoring; employer power |
| `NONE` | No labour problem is defined |

**JOB_LOSS vs SKILL_CHANGE:** does the *job* go, or does the *skillset* change?
- *"IBM to pause hiring for jobs that AI could do"* → JOB_LOSS
- *"Silicon Valley is dishing out million-dollar salaries to engineers literate
  in new tech"* → SKILL_CHANGE (a skill premium, not a job loss)

**When INEQUALITY_POWER beats JOB_LOSS:** if the emphasis is on *distribution*
rather than the loss itself. *"We must ensure workers benefit from AI"* is
INEQUALITY_POWER even though job loss is nearby.

### 2.2 Causal attribution — *who or what is responsible?*

**This is the highest-disagreement function. Ask: who is the grammatical and
moral agent?**

| Code | Agent |
|---|---|
| `TECHNOLOGY` | The capability itself does it |
| `FIRMS` | Employers choose to deploy, cut, restructure |
| `POLICY` | Government, regulation, or its absence |
| `WORKERS` | Workers' own choices, skills, adaptability |
| `NONE` | No agent identified |

The distinction that matters most — **TECHNOLOGY vs FIRMS**:

| Text | Code | Why |
|---|---|---|
| *"AI Could Wipe Out 100 Million Jobs"* | TECHNOLOGY | AI is the actor |
| *"IBM is cutting jobs as tech's shift to AI continues"* | FIRMS | IBM cuts; AI is context |
| *"Australian lender CBA to cut 45 jobs in AI shift"* | FIRMS | CBA acts |
| *"IBM to pause hiring for jobs that AI could do"* | FIRMS | IBM decides |

Heuristic: **if a named company is doing the verb, it is FIRMS**, even when AI
is the stated reason. "AI is taking jobs" is TECHNOLOGY; "X is cutting jobs
because of AI" is FIRMS. Getting this consistent is worth more κ than any other
single habit.

### 2.3 Moral evaluation — *good or bad?*

| Code | Use when |
|---|---|
| `NEGATIVE` | Harmful, threatening, unjust |
| `POSITIVE` | Beneficial, exciting, liberating |
| `AMBIVALENT` | Explicitly both / traded off |
| `NEUTRAL` | Descriptive, no evaluative language |
| `NONE` | Function genuinely absent (rare — prefer NEUTRAL) |

**Frame and evaluation are independent.** The clearest demonstration in your
corpus: *"IBM CEO Says It's a 'Good Thing' If AI Takes Your Job"* →
REPLACEMENT + **POSITIVE**. Do not let a replacement frame pull you to NEGATIVE
by reflex.

- *"'White-Collar Bloodbath': Anthropic Warns of AI Job Losses"* → NEGATIVE
  (the metaphor carries it)
- *"IBM is cutting jobs as tech's shift to AI continues"* → NEUTRAL (reporting)

**NEUTRAL vs NONE:** if the text describes without evaluating, that is NEUTRAL.
Reserve NONE for texts where evaluation is not in play at all.

### 2.4 Treatment recommendation — *what should be done?*

| Code | Use when the text urges |
|---|---|
| `REGULATE` | Policy, law, protections, slowing deployment, resistance |
| `ADAPT` | Upskilling, reskilling, individual or organisational adaptation |
| `REDISTRIBUTE` | UBI, taxing AI gains, shorter week, ownership change |
| `ACCELERATE` | Adopt faster, remove barriers, embrace |
| `NONE` | No treatment stated or implied |

`NONE` is the **majority answer for headlines** — most state a problem without a
remedy. Do not over-read.

- *"State Dept prioritises 'AI-ready workforce' in its first AI strategy"* → ADAPT
- *"Longshoremen's Fight Against Automation Confronts an AI Future"* → REGULATE
  (organised resistance / protection)
- *"We must ensure workers benefit from AI"* → REDISTRIBUTE (or REGULATE — note it)

---

## Confidence — use the full scale

| | Meaning |
|---|---|
| **3** | Unambiguous. Another coder would agree without discussion. |
| **2** | A judgement call between two defensible codes. **Write the alternative in `notes`.** |
| **1** | Genuinely unclear; you picked the least-bad option. |

Confidence is not a self-assessment of competence — it is data. Items coded 1–2
are what you use to (a) diagnose κ failures by function, and (b) build the
codebook v2 edge-case appendix. **A run of all 3s is a warning sign**, not a
good result.

Always note the *rival* code, not just "unclear": `2 — could be TRANSFORMATION`
is useful; `2 — hard` is not.

---

## Traps that quietly destroy κ

1. **Coding the topic, not the frame.** The single biggest risk. Re-read R0.
2. **Letting the frame decide the moral.** REPLACEMENT ≠ NEGATIVE. See the IBM
   CEO example.
3. **Drifting on TECHNOLOGY vs FIRMS** across a session. Pick the named-agent
   heuristic and hold it.
4. **Over-using MIXED** instead of applying dominance (R1).
5. **Inferring functions a headline does not state.** A 13-word headline
   legitimately carries one or two functions. NONE is not laziness.
6. **Using outside knowledge** about the company or the linked article (R5).
7. **Fatigue drift.** Your codes at item 90 differ from item 10. Take the block
   structure seriously — stop at 100, and start the next block fresh.

---

## Before you start

Code **ten items as a warm-up, then stop and re-read this guide.** Check whether
your early calls still look right; recode them if not. That ten-minute
calibration is the cheapest κ improvement available to you.

Record for every item: `coarse_frame, problem, cause, moral, treatment,
confidence, notes`. If the frame is TANGENTIAL, all four functions are `NONE`
and you move on.
