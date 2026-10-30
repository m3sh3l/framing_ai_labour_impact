# Frame-Coding Codebook (final version)

**Project:** From Augmentation to Replacement: Competing Frames of AI's Labour Impact across News, Public, and Insider Discourse, 2022–2026
**Author:** Meshaal Kirmani
**Supervisor:** Dr Chico Camargo
**Version:** final, as applied to all 1,800 coded items
**Supersedes:** the pilot draft written before coding began (`codebook_v1.md`, kept in this folder for comparison)

## 1. What this codebook is for

This codebook turns Entman's (1993) four-function definition of framing into a
set of labelled fields that can be applied the same way every time. Three coders
use it: myself on the 300-item validation set, `claude-opus-5` on all 1,800
items, and GABRIEL on `gpt-4o` as a cross-check on the coarse frame only.

The text given to the model is `frame_coding_system.md` in this folder. It is
this codebook compiled into a system prompt, and it was cached as a fixed prefix
so that every item was coded against identical instructions.

Each rule needs to be specific enough that two people reading it reach the same
label without discussing the item first. Where I could not make a rule that
specific, I said so in Section 7 instead of pretending otherwise.

### Unit of analysis

| Source | What gets coded |
|---|---|
| News (MediaCloud) | the headline only. Body text is not consulted, following Liu et al. (2019) |
| Reddit | the submission title plus the first 100 words of self-text |
| Hacker News | the story title plus the first 100 words of story text |

HTML entities and tags are removed before coding, so the human coder and the
model see exactly the same characters.

## 2. Changes from the pilot draft

| Change | Reason |
|---|---|
| The primary coder is `claude-opus-5`, not GABRIEL | GABRIEL wraps the OpenAI API and cannot call Claude. Moving it to the cross-check position turned out to be better: the two axes now differ in model family and in how the measurement is posed, so agreement between them means more than agreement between two prompts sent to the same model. |
| Value sets fixed to the five fields the decoder enforces | Structured outputs restrict each field to its allowed values while the model is generating, so an invalid label cannot be produced at all. |
| Rule R1 kept unchanged | The pilot draft set 15% MIXED as a warning level. The observed rate was 2.7%, so no change was needed. |
| `INEQUALITY_POWER` kept in the problem set | Pilot coding found items whose main issue is bargaining power or who captures the gains, rather than jobs or skills. |
| Status changed from draft to final | κ = 0.797 on the coarse frame, and three of four Entman functions passed the pre-registered threshold. |

## 3. Step 0: is this item in scope?

Ask: does this text make a claim, however indirect, about AI's effect on human
work?

If yes, continue to Step 1. If no, code `TANGENTIAL`, set all four function
codes to `NONE`, and stop.

Items coded `TANGENTIAL` include AI product announcements with no labour claim,
job advertisements, technical discussion of AI with no reference to work, labour
news with no AI component, and items where AI and work appear together only
incidentally, such as "I work at an AI company".

> **R0: topic is not the same as frame.** An item being *about* AI and jobs does
> not mean it *frames* AI's labour effect. Code the characterisation the text
> builds, not the subject it mentions. If it mentions both but characterises
> neither, it is `TANGENTIAL`.

R0 is my response to Nicholls and Culpepper (2021), who show that automated
framing methods often end up measuring topic instead. It is also why I treat the
tangential rate as a statement about how precise my retrieval was, not about
coder reliability. An item enters the corpus by containing an AI term and a
labour term, and some sources meet that test far more often without saying
anything about the relationship between the two.

Observed tangential rates: Hacker News 45.8%, Reddit 27.7%, MediaCloud 25.7%.

## 4. Step 1: the coarse frame

Assign exactly one label.

| Code | Definition | Typical wording |
|---|---|---|
| `REPLACEMENT` | AI takes over work people used to do; people leave the task, job or occupation | replace, take your job, displace, automate away, obsolete, layoffs due to AI |
| `AUGMENTATION` | AI extends or assists human work; people stay involved | copilot, assist, boost productivity, works alongside, AI skills raise pay |
| `TRANSFORMATION` | AI restructures what work is or how it is organised, which is neither straightforward loss nor straightforward gain | reshape work, new kinds of jobs, redefine the profession, task recomposition |
| `MIXED` | Two or more of the above carry roughly equal weight in the same item | "will kill some jobs and create others", explicit both-sides framing |
| `TANGENTIAL` | Did not pass Step 0 | |

### Decision rules

**R1 (dominance).** Where one frame is clearly in front, through headline
emphasis, the opening clause, or evaluative wording, code that frame even if
another is present. Use `MIXED` only where the two are genuinely balanced.
Observed MIXED rate: 2.7%, well under the 15% warning level.

**R2 (questions carry their assumption).** A headline asked as a question, such
as "Will AI take your job?", is coded to the frame the question assumes, so
`REPLACEMENT` in that example. Putting something as a question does not remove
the frame.

**R3 (denial still invokes).** A text arguing *against* a frame, such as "AI
won't take your jobs", is coded to the frame it engages, so `REPLACEMENT`, and
the moral evaluation field captures the stance. RQ1 asks which frames structure
the discussion, not which ones people agree with.

**R4 (sarcasm).** Code the frame the words invoke, unless the sarcasm is
unmistakable from the item alone. No thread context is available to the coder.
Where this was difficult I noted it.

**R5 (no outside knowledge).** Code only what the text says. Do not use anything
you know about the linked article, the author, or what happened afterwards.

## 5. Step 2: the four Entman functions

One value per function. `NONE` is a legitimate answer and a common one, because
headlines often carry only one or two of the four functions. That is a property
of the material, not a coding failure.

### 5.1 Problem definition: what is the issue?

| Code | Definition |
|---|---|
| `JOB_LOSS` | Unemployment, displacement, redundancy, falling demand for workers |
| `SKILL_CHANGE` | Skills becoming obsolete or newly required; retraining |
| `OPPORTUNITY` | Productivity, growth, new capability or economic gain as the central issue |
| `INEQUALITY_POWER` | Distribution, bargaining power, who captures the gains |
| `NONE` | No problem is stated |

### 5.2 Causal attribution: what or who is held responsible?

| Code | Definition |
|---|---|
| `TECHNOLOGY` | The technology itself, treated as an impersonal force |
| `FIRMS` | Employers, executives, corporate decisions |
| `POLICY` | Government, regulation, or the absence of it |
| `WORKERS` | Workers' own skills, choices, or failure to adapt |
| `NONE` | No cause given |

### 5.3 Moral evaluation: is it treated as good or bad?

`NEGATIVE`, `POSITIVE`, `AMBIVALENT` (both, explicitly), `NEUTRAL`
(descriptive, no evaluation), `NONE`.

`NEUTRAL` and `NONE` are different. Neutral means the text evaluates and lands
on neither good nor bad. None means there is no evaluative content at all.

### 5.4 Treatment recommendation: what should be done?

| Code | Definition |
|---|---|
| `REGULATE` | Law, policy limits, protections, bans |
| `ADAPT` | Reskilling, education, individual adjustment |
| `REDISTRIBUTE` | Universal basic income, taxation, redistribution of gains |
| `ACCELERATE` | Adopt faster, invest more, remove barriers |
| `NONE` | No recommendation |

A warning about this field. `NONE` dominates it: 81.6% of replacement-framed
items and around four fifths of all items recommend nothing. This is a finding
in its own right, but it also drives the low reliability figure discussed in
Section 6. A coder should not invent a recommendation to avoid choosing `NONE`.

## 6. Step 3: confidence and notes

`confidence` takes the values 1, 2 or 3, where 1 means genuinely uncertain and 3
means unambiguous. A free-text `notes` field records why I hesitated on any item.

My confidence ratings and the model's agree only weakly (Krippendorff's α =
0.324, ordinal). Confidence is therefore reported descriptively and is never
used as a weight, a filter, or a reason to exclude an item.

## 7. Reliability

The threshold was fixed in the proposal before any coding took place: Cohen's κ
of at least 0.60 on three or more of the four Entman functions. If that had not
been met, the plan was to fall back to a three-category typology at κ ≥ 0.55
after one documented round of codebook revision.

| Variable | κ (all 300) | κ (excluding tangential) | Raw agreement | Difference |
|---|---|---|---|---|
| Coarse frame | 0.797 | 0.765 | 0.860 | 0.063 |
| Problem definition | 0.834 | 0.860 | 0.887 | 0.053 |
| Causal attribution | 0.792 | 0.749 | 0.857 | 0.065 |
| Moral evaluation | 0.803 | 0.794 | 0.853 | 0.050 |
| Treatment recommendation | 0.591 | 0.641 | 0.877 | 0.286 |

Three of four functions passed, so the full four-function scheme was kept and no
fallback was used.

**Treatment recommendation.** This is the one value below the threshold, and the
reason is how the answers are distributed rather than how carefully the coding
was done. Raw agreement on treatment is 0.877, the second highest of the five
variables, but roughly four fifths of items recommend nothing, so a large amount
of agreement is expected by chance and the correction is severe. The last column
shows this: the difference between raw agreement and κ is 0.286 for treatment
against 0.050 to 0.065 for everything else. This is the kappa paradox, and I
report both figures so the coefficient is not read as evidence of unreliable
coding. Consistent with that explanation, treatment is the only variable whose κ
rises when tangential items are removed, from 0.591 to 0.641.

**No drift between sources.** Per-ecosystem κ ranges from 0.745 to 0.876 for the
coarse frame and the first three functions. Treatment varies more, from 0.467 on
Hacker News to 0.683 on MediaCloud, which follows the same explanation, since
the share of items recommending nothing itself differs by source.

## 8. Limitations of this instrument

1. **One human coder.** Reliability here mixes the quality of the instrument
   with my own consistency. When I re-read my earlier codes I found two I would
   have coded differently later. A second coder on 50 to 100 items would
   separate the two effects, and I did not have one.
2. **Implicit framing is not captured.** Both the relevance rule and the coding
   work on explicit wording. A post that implies job loss without naming AI or
   work in recognisable terms never reaches the coder.
3. **Text length differs by source.** News items have a median of 13 words
   against 106 to 109 for the two forums, and the four functions are easier to
   detect when there is more text. The length-split check in Section 4.3 of the
   report holds, but re-coding the forum items on their titles alone would be a
   cleaner test, and I did not run it.
4. **No thread context.** R4 asks for sarcasm to be unmistakable from the item
   alone, which will miss irony that a reader of the whole thread would catch.

## 9. Files

| File | Contents |
|---|---|
| `codebook_final.md` | this document |
| `codebook_v1.md` | the pilot draft, kept for comparison |
| `CODING_GUIDE.md` | worked examples and boundary cases used while hand-coding |
| `frame_coding_system.md` | the exact system prompt given to the model |

## References

Entman, R. M. (1993). Framing: toward clarification of a fractured paradigm.
*Journal of Communication*, 43(4), 51–58.

Krippendorff, K. (2018). *Content Analysis: An Introduction to Its Methodology*
(4th ed.). Sage.

Landis, J. R. and Koch, G. G. (1977). The measurement of observer agreement for
categorical data. *Biometrics*, 33(1), 159–174.

Liu, S., Guo, L., Mays, K., Betke, M. and Wijaya, D. T. (2019). Detecting frames
in news headlines and its application to analyzing news framing trends
surrounding U.S. gun violence. *Proceedings of CoNLL 2019*, 504–514.

Nicholls, T. and Culpepper, P. D. (2021). Computational identification of media
frames: strengths, weaknesses, and opportunities. *Political Communication*,
38(1–2), 159–181.
