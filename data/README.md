# Data in this repository

What is here are my own research outputs: the model's codes, the human/model
agreement table, the validation report, and the stage-by-stage corpus counts.
These are identifiers and labels only.

| File | Contents |
|---|---|
| `coding/llm_codes_full1800.jsonl` | frame codes for all 1,800 sampled items |
| `coding/llm_codes_gold300.jsonl` | codes for the 300-item validation subset |
| `coding/gabriel_codes_gold300.jsonl` | the cross-check model's codes |
| `coding/human_vs_llm_merged.csv` | my hand codes joined to the model's |
| `coding/validation_report.txt` | the reliability gate output |
| `meta/funnel.json` | item counts at each pipeline stage |
| `valid_values.csv` | the codebook's permitted values per field |

## What is deliberately not here

The corpus itself, the raw API responses, the annotation sheets and the full
API call log are excluded. Three reasons:

1. **Platform terms.** Reddit, Hacker News and MediaCloud do not permit raw API
   responses to be redistributed.
2. **Author privacy.** The corpus metadata pairs post URLs with author
   identifiers. A URL identifies a post, and a post identifies its author, so
   publishing them would make the pseudonymisation meaningless. Much of this
   material is people writing about losing their jobs.
3. **Size.** The raw pull is roughly 460 MB, including a single file above
   GitHub's 100 MB limit.

The notebooks are committed with their outputs saved, so every table, figure
and number can be read without running anything.

The corpus is available for academic replication on request.
