# F38 cause-driven repairs: run record

Rule: `rebuttal/pilots/prereg/F38-cause-driven-repairs-rule.md`. Amendment 1: `rebuttal/pilots/prereg/F38-amendment-1-targeted-reread.md` (sha256 086691b247cd113874b0d6f251edcc1a8c49ac6855d0aeb3d50b00f9436af9ae; manifest `amendment1_manifest.json`).

## 1. Order of operations (post hoc)

- The v0 runs of Fix B and Fix C were run before the cause was identified. The v0 prompt asked for an untargeted quote, and presence was tested at passage level.
- The cause (passage-level presence; untargeted quote) was found after the v0 results were in.
- Amendment 1 (sentence-level presence; fact-targeted verbatim quote with a NONE option; delivery gate unchanged) was frozen after those v0 results. It is post hoc and is reported as such.
- v0 results are archived in `v0_untargeted_prompt/` (results_B.json, results_C.json, calls_B.jsonl, calls_C.jsonl, run_B.log, run_C.log, populations_v0.json). They are not hidden and are not part of the amended results.

## 2. Deleted call log (breach of the log rule)

- At restart, the partial Fix A call log from the v0 attempt (`calls_A.jsonl`) and `run_A.log` were deleted. They covered the v0 Fix A attempt that crashed on the 9 instances without trace packages.
- Spend covered by the deleted partial run: **unknown**. Not recoverable from the remaining logs.
- This is separate from the completed Fix A run, whose log is intact: 184 result rows, logged cost $0.087506.
- No call log is to be deleted from now on.

## 3. Logged spend per call log (current files)

| Log | Result rows | Logged cost (USD) |
|---|---:|---:|
| calls_A.jsonl (Fix A, completed) | 184 | 0.087506 |
| calls_B.jsonl (Fix B, amended) | 11 | 0.003961 |
| calls_C.jsonl (Fix C, amended) | 35 | 0.012767 |
| v0_untargeted_prompt/calls_B.jsonl | 11 | 0.004156 |
| v0_untargeted_prompt/calls_C.jsonl | 55 | 0.019795 |
| calls_A.jsonl from v0 attempt | deleted | unknown |

Amended total logged: $0.104234. Including archived v0 (B and C): $0.128185. Cap was $10.

## 4. Fix A: nine cases with no trace package

- Search at $0: `run_expansion_stage2.packages(model)` for gemma31b, gpt4omini and qwen235b returns 800 packages each. None of the nine instance ids is among them.
- Instance ids also appear in `rebuttal/results/batch1/expansion_stage1/relay_*` outputs. Those are a different run (stage 1), and the matcher records behind these cases come from stage 2, so no package was built from stage 1.
- Status: **not run** (nine cases: gemma31b 6, gpt4omini 2, qwen235b 1). Denominator stays 51.
- Fix A result on the 42 runnable cases: control 1/31 → repair 8/31 (A1); 0/8 → 1/8 (A2); 0/3 → 1/3 (A3). Repaired 10 of 51 (10 of 42 runnable).

## 5. Fix B aggregator

- The B2 repair answer was produced by the paper-model aggregator (`answer()` with `MODEL_IDS[model]`), the same path as Fix A.
- No restored sentence was applied to B cases. B cases are not restore-arm cases. The B2 repair instead quoted the flagged distorted units from source (targeted verbatim quote, amendment 1).

## 6. Fix C classification (corrected twice; current version)

Rule text, `rebuttal/pilots/20261113_sharding_diagnosis/SHARDING_RULE.md`, lines 18–23:

> sharding_omission: no source shard contains the fact (content recall absent in every source-agent context).
> extraction_omission (unchanged): at least one source shard contains the fact (present or partial).

Presence thresholds (same file; PRESENCE_RULE.md Amendment 2, content rule): present ≥0.8, partial ≥0.4, absent <0.4. Several shards: present if any present, else partial if any partial, else absent. Source shards = `source_contexts` whose agent is listed in the fact's `source_ids`.

**Check of the earlier values ($0; `scripts/f38_fixc_shard_check.py`; output `fixc_shard_check.json`).** The earlier C best-recall values in `populations.json` were computed over `source_supports` with full-token recall. On MuSiQue, `source_supports` are the gold supporting paragraphs, not the agents' input shards, and the full-token recall is not the content rule. Those values are therefore not valid for the rule and are replaced by the recomputation below. The 0.8/0.4 group split of v1 is also withdrawn.

Recomputed per fact over its source shards with the content rule (`content_recall`, `evidence_sentences` from `scripts/repair_presence_check.py`):

| Content rule, no manual read | Count |
|---|---:|
| present | 12 |
| partial | 10 |
| absent | 5 |

Manual reads. `scripts/repair_presence_check.py` MANUAL holds reads of the stage-2 missing-fact cohort that the sharding rule says are part of the frozen rule for that cohort. Fifteen of the 27 Fix C facts are the same facts (fact texts match the reasons). Applying them:

| Final label (manual read where recorded, else content rule) | Count |
|---|---:|
| present | 6 |
| partial | 2 |
| absent (sharding_omission) | 19 |

Cross-tab with v1 groups: the 19 absent are 17 C3, 2 C1. Five C1 cases stay present.

Two readings, both reported. Under the content rule alone: 22 extraction, 5 sharding. Under the cohort manual reads: 8 extraction, 19 sharding. Only the second reproduces the earlier "19" count, but the 19 are a different set of cases from the v1 C3 group.

Open point (one case): 4hop1__37608_32392_823060_610794 f5 has a manual read "absent" (the cohort decision), but the content rule finds the fact present in shard 3 (recall 1.0). The rule's "any shard present" would make it present. This is not resolved here; it is one of the 19.

Choice needed (not decided here): whether manual cohort reads apply to Fix C facts. I have not chosen; the Fix C counts above stay unused until this is settled.

## 7. Known limits

- Fix B: 1 of 17 fixed (2 re-read, 15 not applicable).
- Fix C: 1 of 27 fixed.
- Single-rater labels are internal only.
