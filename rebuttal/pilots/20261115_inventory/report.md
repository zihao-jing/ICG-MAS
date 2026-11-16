# Open rebuttal work: inventory of negative and unvalidated results

2026-11-15. No API calls, no spend, no paper or reviewer edits, no commits. Every cause below was read from the
case records and model outputs in the named folder, not from the pilot summaries.

**Spend so far $114.827009** (2026-11-15, recomputed from the files after the Silo-Bench two-step full
run, the Q1 work, the redundancy LLM-scorer rerun, the symmetric same-slot rerun, the Part B extension, the two
Silo-Bench extraction re-scores, the pooled extraction run in progress, the matched-granularity equivalence run,
the statement-based shard check and [R1] on Qwen at $0.034209; 52,384 records). **Adding the Part B first-run
records that no longer exist ($0.345828) and the DeepSeek estimate ($0.381955): $115.554792.** Warning at
$140; I warn before any run that could pass $135.

**Movement since the 20:15 snapshot ($114.605893, 52,124 records): +$0.221116, +260 records.** Added: [R1]
on Qwen, 89 calls $0.034209, and the pooled Silo-Bench extraction run's records to that point; the pooled run
is still writing, so its remainder is not in this figure yet. The previous movement line (18:00 snapshot,
$112.705956, 50,566 records, +$1.355206, +776 records) follows for the record. Added then: the
Part B extension 23 calls $1.142940, the first Silo-Bench extraction re-score 380 calls $0.162332 and the
corrected-unit re-score 380 calls $0.395763 (+783 records). Removed: the 7 first-run Part B call records
($0.345828, 7 records) — the extension's `--run` opened the same `opus_calls.jsonl` and `opus_results.jsonl` and
wrote only its own 23 rows, so the earlier rows are gone from the files. The figure is kept from that run's log
(cumulative API cost after each of the 7 calls, ending $0.345828; CLI charge $0.132874) and carried on its own
line, as with the DeepSeek estimate. 783 − 776 = 7.

**The $0.011 gap after the 16:18 snapshot.** The snapshot at 16:17:52 reported $111.968590; the current sum is
$0.110388 higher. The two items I listed as post-snapshot spend were the Silo-Bench remainder ($2.468869 less the
run's own counter at 16:17:40, $2.409547 = $0.059322) and the second Q1 sample ($0.030552) = $0.089874, which is
$0.011431 more than the actual movement. Both runs were still writing when the snapshot was taken, so part of each
is already inside $111.968590: the snapshot's Silo and Q1 components sum to $2.420978, above the 16:17:40 counter,
and the nearest Silo call prefix is $2.414013, leaving $0.006965 of the second Q1 sample inside the snapshot. The gap
is that overlap, not a missing or double-counted call; the current sum is recomputed from the records.

Previous snapshots: **$103.929677** at 13:47 (47,889 records) and **$102.586881** after the relay v2 rescore, the
B6 audit-guided repair pilot and its full-evidence and verbatim arms, both B5 design-A steps, B7, B7b and B7c.
Recomputed 2026-11-15 directly from the ledger rule: every record with a top-level
non-null `cost_usd` under `rebuttal/**/*.jsonl`, excluding the two `swaps.jsonl` files.

**Estimated addition (approved 2026-11-15): $0.381955** for 782 uncharged `deepseek/deepseek-v3.2` calls in
the Extension B artifacts, priced from their recorded token counts (section at the end). **Measured plus
estimate: $102.968836.** The older `20261114_cost_breakdown/report.md` figure of $74.969308 covers
35,132 records and is stale; its `results.json` covers 36,423 records and reports $81.11696.

**Reconciliation.** The pre-run base was $84.681712 ($84.7). The point-level run added $2.200761, the A2 anchor check $0.773298, the 7b matched check $0.566843, the A4 re-score $1.725887, the A3 pilot $0.060048, the A3 full run $0.413679, the Qwen relay re-score $0.314875, the relay-label validation $0.359949, the stopped 608-trace first attempt $0.336123 (the inventory had carried a $0.316809 mid-run snapshot), the resumed chunked 608 run $1.038703 (dir total $1.374826), the amended-cap pilot $0.343866, the MuSiQue 400-trace run $1.868198, the 8e granularity fix $0.482973, the
9e relay validation v2 $0.355546, the Silo-Bench 208-trace fixed-proxy run $2.795149, the enriched 9e relay
validation v3 $0.391206 and the 9f four-model re-check $0.525472 (its $0.5 cap was breached by $0.003568, then the 53 skipped pairs were labelled under a separate $0.05 cap at $0.021904), plus the B5 Gemini-matcher validation $0.381125 (including its $0.008070 transport test), the relay v2
rescore $0.353193, the B6 audit-guided repair pilot $0.010920 (including its first sharding pass $0.002528
and its full-evidence routing arm $0.001976), the B5 design-A validation $0.275312, the B5 design-A 2x2
$0.862423, B7 $0.899740, B7b $0.560820 and B7c $0.008461, the B6c verbatim arm $0.000259 and the B6d bridge arm $0.000345, so the ledger was $102.586881 at that snapshot. Added after it: the Silo-Bench two-step pilot $0.226981, the
Silo-Bench full run (still running), B7d $0.221506, the B5 Qwen design-A check $0.163918, the volume-matched
selection repair $0.005452 and the Opus CLI smoke test $0.185220 (actual CLI charge; the token estimate
$0.063940 is superseded because the CLI route prices cached prompt tokens differently).
There is no file in the
repo that records $84.91, and I cannot reproduce it: the nearest alternative scopes are $84.725353
(including both `swaps.jsonl` files, which the rule excludes), $81.11696 (the stale model table) and
$74.969308 (the stale report). The ledger sum is right because it is the only figure computed from the
current files under the stated rule. No explicit budget figure exists beyond the $140 threshold.

**The $0.001476 gap against the pilot.** The value $102.815338 recorded immediately after the Silo-Bench
two-step pilot is $0.001476 above $102.586881 + the pilot's own $0.226981. The pilot's 76 call records sum to
exactly $0.226981, so the pilot figure is right and no pilot call is counted twice. The extra $0.001476 is not
in the pilot directory and matches no single record. I could not attribute it: it is not a pilot call, and the
only other writes in the same window are two small B6 addenda already included in the prior snapshot. It is
carried in the current measured sum, which is recomputed from the files, rather than in the prior snapshot.

Observed unit costs used for the estimates below: Opus 5.5 $0.0051/fact and $0.024/call at the board, $0.0108/call on short contexts,
Haiku 5.5 $0.0005–0.0008/call, Gemini 3.6 Flash $0.0067/call, Qwen-235B judge $0.0058/call, the repair
models $0.0001–0.0002/call. All projections are estimates from these rates, not measured.

## Summary

| # | Item | Source | Cause read from the outputs | Fix | Est. |
|---|---|---|---|---|---:|
| 1 | Part B judge failed validation (κ .545) | `20261114_part_b_k1/reval/` | Class head only: 5 of 6 disagreements have identical defect lists, single vs multiple; the class rule is undefined | Redefine class deterministically from the defect list; revalidate defect-level labels, Gemini labeller vs Opus 5.5 reference | $1.3 |
| 2 | Silo-Bench extraction label failed (κ .127, .553) | `20261114_per_fact_extraction_sb{,_v2}/` | List-valued facts: threshold between "any point" and "full list" differs between reference and labeller; four list-heavy instances carry 30 of 35 errors | Split list facts to point-level atoms, deterministic roll-up; **now passes**: atom κ .847 [.690, .967], roll-up κ .883 [.765, .971] (`20261115_sb_points/report.md`) | $2.20 spent |
| 3 | Dist unvalidated; strict fidelity κ .721 | `20261113_label_validation_v10/`, `20261114_board_fidelity_full/` | Constructed swaps hit incidental tokens (release year, "as of" year), so relation-level and token-level fidelity differ; and Opus was labeller against a weaker Gemini reference | Freeze "strict = any altered token"; rebuild constructed set on the truth condition; move the column to a Haiku labeller validated against Opus 5.5. **Four-model column done**: pair label validated .992 / κ .937 vs Opus, rates replaced (`20261115_distortion_rescore/report.md`). **Qwen-235B relay column label**: 0.7 / 0.3 / 0.0% and pooled 0.3% (3/920) are the **unvalidated Qwen-235B judge**'s DISTORTED class (`qwen/qwen3-235b-a22b-07-25`; strict = one incorrect value), two-stage numeric coverage then judge, Silo-Bench n5+n10 k=3, 315 pairs/protocol, covered 306/307/307, records in `results/distortion_audit_relay/`; same judge family as the four-model column and not validated for it | $1.73 spent |
| 4 | Placement: 8/30 vs 0/30 | `20261113_placement_redo/` | Unequal information by construction: in 8/8 diagnosed-exact cases the random arm's model cannot carry the corrected unit (empty or other transmission); 29/60 arms returned no transmission | Equal-information arm + non-empty transmission retry; n=100. No labeller can fix this | $0.5 |
| 5 | Selection repair exploratory (+3.85 pts) | `20261114_selection_repair_full/` | R-sel adds 1–2 targeted units, the donor arm adds 1–2 donor units, and the donor arm matches Rerun on all 52, so the content carries the effect; but R-sel adds more units than the donor in 38 of 52, so volume is not matched pair-by-pair and both flips sit there | Larger arm matched unit-for-unit with the donor (n≈200). No labeller can fix this | $0.02 |
| 6 | Lexical κ 0.000 | `results/batch1/paper_evaluators_full_v11.md` | The rule fires on every eligible row (852/852 covered, 852/852 faithful) against prevalence .958/.953; κ is 0 by construction, AC1 .976 | Replace with per-fact Haiku labeller at the board checkpoint, validated against the existing Opus 5.5 labels on 150 stratified rows (incl. the 40 absent) | $0.5 |
| 7 | E2-C judge small-sample pass | `20261114_e2c_validate15/`, `20261114_e2c_extension/` | 7/30 outputs invalid JSON (Gemini fences its JSON); 6 yes/17 no makes κ 1.000 degenerate; extension scored the Qwen block only | Fence-safe JSON + retry; score the Gemini block; revalidate against Opus 5.5 | $0.3 |
| 8 | Extension A pending | `revision_plan.md` §2 | Never run: the matcher accepts any overlap, so complete coverage cannot establish aggregation failure | Haiku labeller at extraction, board and final answer, Opus 5.5 reference, 300 traces × 3 checkpoints | $22 |
| 9 | Extension B v2: 0.011, CI crosses 0 | `results/extension_b_deepseekv32_v2_musique/` | 10 gains, 7 losses, 13 ties; losses are terse answers and 2 refusals scored by token F1 | Score all 180 answers by answer equivalence, Gemini labeller vs Opus 5.5 reference | $0.3 |

**Projected total ≈ $32.1** (range $25–40) for the whole fix list; $6.06 spent on items so far (Silo-Bench
$2.20, A2 anchor $0.77, 7b matched $0.57, A4 re-score $1.73, A3 pilot+full $0.47, Qwen relay re-score $0.31).
**Cumulative ≈ $116.8** (range $111–126). Does not pass $140; margin ≈ $23.2. Without Extension A,
cumulative ≈ $94.8.

## 1. Part B judge

`reval/opus.json` vs `reval/gemini.json`, 30 fresh wrong traces; each model returns a defect list and a
class. Six class disagreements. In five (`675f7d09`, `1a51ccfb`, `a02da452`, `cc2526ae`, `d079002e`) the defect
lists are identical and only the class differs: Opus says single, Gemini says multiple. One
(`90170186`) also differs in the list: Opus has 5 defects including two extraction distortions, Gemini has
3 including a "reasoning-use" defect.

Cause: the class label is a summary of the model's own defect list, and neither prompt defines when a
defect is "decisive"; the models agree on what went wrong and disagree on how to summarise it. Defect-level
agreement is 29/30. Fix: compute the class from the defect list with a frozen rule (single = exactly one
defect at the routed stage), then revalidate the defect labels, Gemini labeller against Opus 5.5.
Cost: 30 traces at the measured reval rate, Opus $1.046 + Gemini $0.277 = **$1.32**.

## 2. Silo-Bench extraction label

v3 (`report.md`): 35 of 250 facts disagree under the report's rule (partial counts as present), all
reference-absent / labeller-present-or-partial. They cluster in four list-heavy instances: 9 in
`sb/qwen235b/III-25_n10`, 9 in `sb/qwen235b/III-29_n10`, 7 in `sb/qwen235b/III-24_n10` and 5 in
`sb/gpt4omini/III-29_n10`; the other 5 are single facts in three further instances. The reasons are
threshold statements such as "names only four of the twenty points … so most of the fact's points are
not carried". Under the present-only rule the other direction appears: 5 cases (`sb/gpt4omini/III-29_n10`
f2/f3/f5, `sb/qwen235b/I-10_n10` f2, `sb/qwen235b/III-26_n10` f5) where the reference accepts a full list
and the labeller says partial.

v4 (`_v2/report.md`): 13 disagreements. 8 are `ref absent / lab present`, seven of them in
`sbv2/gpt4omini/III-27_n10` — whose reasons say "this list-valued fact is incomplete" while the status is
`present` — and one in `sbv2/gemma31b/III-27_n10`. The other 5 are `ref present / lab partial`: four in
`sbv2/qwen235b/III-25_n5` and one in `sbv2/gemma31b/III-27_n10`.

Cause: Silo-Bench's facts are lists (task tables, coordinate lists, user vectors). The presence decision is a
threshold on how much of the list must be carried, and the two sides place it differently; the fact also
bundles points that the label treats as one decision, so "present" has no natural threshold. Fix: label each
point as its own atom, roll up deterministically (fact present = all atoms present), and validate a Haiku
labeller against an Opus 5.5 reference.

**Frozen for step 6.** `prereg/Per-fact-presence-points-v1.md` (sha `e6263584`), one identical prompt for
both sides (`per_fact_points_prompt_v1.json`, sha `86d84ff6`), Haiku 5.5 labeller, Opus 5.5 reference. The
fresh sample was drawn before any call with seed 47 from instances in neither the v3 nor the v4 population:
21 traces, 21 instances, 155 facts, 2,755 atoms, `population.json` sha `1d1fd1af`. Projection $1.81,
cap $3.5. The 21-instance ceiling is the benchmark's: only 52 Silo-Bench instances exist at n5/n10.

The 2026-11-14 stop decision (`20261114_batch2_report.md`) is superseded for this one fix by your step list;
I will record that in the deviation log when the run starts in step 6.

## 3. Dist and strict fidelity

Constructed set, 37 planted facts (`results_v10.json`, `population = constructed`). Reference 32/37
distorted, Opus 31/37. The five exceptions are readable in the records:

| Case | Swap | Opus | Reference | Why |
|---|---|---|---|---|
| `con/gpt4omini/3hop1__742780…` | 1988→1989 | faithful | distorted | "the year is incidental to the question" |
| `con/qwen235b/3hop1__274148…` | 1989→1990 | faithful | distorted | "the release year is incidental" |
| `con/gpt4omini/2hop__503085…` | 10→11 June | partial | distorted | only the birth year is carried |
| `con/gemma31b/2hop__34495…` | 1992→1993 | faithful | faithful | swap not carried in the fact's terms |
| `con/gemma31b/2hop__55129…` | 2017→2018 | faithful | faithful | "as of" year not needed |

Cause: the constructed swaps were placed on tokens that do not carry the fact's truth condition (album
release year, period start, "as of" date), so token-level and relation-level fidelity legitimately differ;
two cases did not register in the reference at all. Separately, the natural-case κ .721
(`20261113_label_validation_v10/report.md`) has Opus as the labeller and Gemini as the reference, i.e. the
labeller is stronger than its reference — the opposite of the rule.

Fix: freeze "strict fidelity = no token of the fact statement altered" in the prompt; rebuild the
constructed set so each swap changes the relation-bearing slot; and, because nothing is stronger than
Opus 5.5 in the ledger, use Opus 5.5 as the reference and re-label the column with Haiku 5.5, validated
on 150 stratified rows (50 distorted, 50 partial, 50 absent) then applied to the 1,824 board rows.
Cost: constructed rebuild + validation $1.1; Haiku re-label of the board $1.3; validation rows $1.3 =
**$3.7**. Note this re-labels the distortion column; the table may be redone with any labeller validated
for that exact label and stage.

## 4. Placement

`results_matched.json`, 60 arms over 30 cases. Both the diagnosed and random arms replace the same
corrupted unit and put the stronger model on one agent. In the 8 diagnosed-exact cases the random arm's
transmission is `NO EVIDENCE` (4 cases) or an unrelated unit (4 cases), so the aggregator answers
"Insufficient information." Empty transmission occurs in 12/30 diagnosed and 17/30 random arms (29/60).

Cause: the random arm's stronger model reads a shard that does not hold the corrected unit, so it cannot
carry it; the contrast measures whether the corrected unit propagates from the diagnosing agent, not
whether targeted placement beats an equal-information alternative. Empty transmission in half the arms
compounds it. Fix: equal-information control (stronger model on all agents, same token budget) plus a
non-empty transmission retry (the fix already used in Extension B v2), n=100. Cost: 300 calls at
$0.0018 = **$0.54**. This is a design cause; no labeller is involved — MuSiQue gold is the truth.

## 5. Selection repair

`analysis.json` and `raw/*.json`, 52 traces × 3 arms. `added_units` counts: (R-sel, Rerun, V-sel) is (1,0,1)
in 35 traces, (2,0,2) in 16 and (2,0,1) in one. The donor arm adds the same order of volume and matches
Rerun on all 52 in both exact match and F1; the 14 pairs inside the 10% band are also unchanged. The two
improvements (`93385964`: "Sea, Air, and Land" vs Insufficient; `ba3e066013`: "Arthur Peel" vs Insufficient)
both sit in the 38 pairs that exceed the band.

Cause: added content, not added volume, drives the two flips — the donor's extra units change nothing —
but in 38 of 52 traces R-sel adds more units than the donor, so volume is not controlled pair-by-pair and
the flip subset is exactly the uncontrolled one; with two flips the paired interval includes zero. The
label is not implicated (the selection label was validated at κ .676). Fix: an arm matched unit-for-unit
with the donor, n≈200. Cost: 600 calls at $0.0001 = **$0.02**. Design cause, no labeller.

## 6. Lexical κ 0.000

`paper_evaluators_full_v11.md`: the lexical rule predicts covered on 852/852 eligible rows and faithful on
852/852; author prevalence is .958 and .953. κ is ≈0 by construction, AC1 .976; the only errors are the 40
author-absent rows. The Qwen-235B judge on the same rows has presence κ .243 and fidelity κ .122.

Cause: a threshold rule that fires everywhere cannot discriminate; κ rewards discrimination, AC1 does
not. Fix: replace the rule with a per-fact Haiku labeller at the board checkpoint and validate it against
the existing Opus 5.5 board labels on 150 stratified rows (40 author-absent, 110 sample). Cost: 150 rows
× ~4 facts at $0.0008 = **$0.50**; no new Opus calls.

## 7. E2-C judge

`validation.json`: 23 valid of 30, agreement 1.000 on 6 yes / 17 no. All 7 excluded outputs are Gemini's and
all are fenced ```` ```json ```` blocks (4 in the 10-label first-stage file, 3 more in the completion). `E2-C extension`
(`report.json`) scored the Qwen block only: 39 calls, 32 valid, 8 yes / 24 no, Gemini block unscored.

Cause: output format, not judgement — Gemini wraps the object in a fence and the parser rejects it; and
the yes rate is too low for κ to be informative. Fix: fence-safe JSON with one retry, score the Gemini
block, and revalidate against Opus 5.5 with a yes-enriched sample. Cost: 39 calls + 7 retries × 2 models
= **$0.25**.

## 8. Extension A

`revision_plan.md` §2 defines it and §21 records it as pending. The matcher admits any positive overlap,
so complete coverage cannot establish aggregation failure; that is the gap Extension A closes. Fix: per-fact
Haiku 5.5 at extraction, board and final answer, Opus 5.5 reference, 300 cached traces on both benchmarks,
structured relay and summary exchange, 95% CI and cost per cell. Cost: 900 Opus reference calls at
$0.024 = $21.6 + 900 Haiku calls = $0.7, **$22** ($15–25), staged as a $5 pilot then completion. It is
required only if the stronger semantic-attribution claim is kept.

## 9. Extension B v2

`per_instance_results.jsonl`, 30 aggregation-gap instances: 10 gain, 7 lose, 13 tie; paired +0.011. The
losses are terse answers scored by token F1 (`2hop__495316`: "Starkville, Mississippi" 0.67 vs "Starkville"
1.0; `3hop2__607269`: "Central region" vs "South Central Coast region") and two refusals
(`3hop2__92991`, `4hop2__161602`) whose boards do carry the needed units. `audit_repair_manifest.jsonl`
records crit_recall 1.0 for all of them.

Cause: F1 penalises terseness and refusal, and the audit repair's cited-path format shortens answers;
the paired sign depends on that scoring. Fix: score all 180 answers by semantic answer equivalence,
Gemini 3.6 Flash labeller against Opus 5.5 reference, then recompute the paired difference. Cost: 180
answers, answer-only prompt ≈ **$0.30** (estimate).

## Labeller design across the seven items

One design, seven instances. Common elements: the same prompt text for labeller and reference, only the model
differs; temperature 0; rule and prompt hashes recorded before the first call; validation sample disjoint from
the cases that designed the prompt; agreement and κ each with a 95% instance-cluster bootstrap CI (2,000 draws,
seed 43); pass requires both point estimates to meet **.80** agreement and **.60** κ; if κ's CI lower bound is
below .40 the label is marked wide-interval and kept out of the headline.

| Item | Prompt family | Labeller | Reference | Bars | Validation unit and sample |
|---|---|---|---|---|---|
| 1 Part B judge | `defect-list-v1` | Gemini 3.6 Flash | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 30 traces, one defect list each; class derived by rule |
| 2 Silo-Bench extraction | `per-fact-presence-points-v1` | Haiku 5.5 | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 21 traces, 2,755 atoms (frozen) |
| 3 Dist strict fidelity | `strict-fidelity-v11` | Haiku 5.5 | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 150 board rows, 50 per fidelity class |
| 6 Lexical κ | `per-fact-presence-board-v1` | Haiku 5.5 | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 150 board rows incl. 40 author-absent |
| 7 E2-C judge | `casebook-defect-v2` | Gemini 3.6 Flash | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 30 outputs, yes-enriched |
| 8 Extension A | `per-fact-presence-checkpoints-v1` | Haiku 5.5 | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 300 traces × 3 checkpoints |
| 9 Extension B | `answer-equivalence-v1` | Gemini 3.6 Flash | Opus 5.5 | ≥ .80 / κ ≥ .60, 95% CI | 180 answers (60 instances × 3 arms) |

Placement (item 4) and selection (item 5) have no labeller: their causes are information asymmetry and an
unmatched unit count, and MuSiQue gold is the truth.

## Not in this inventory

The §5 definition checks (redundancy/useful-budget, AF share, mean F1 vs non-perfect rate, lexical vs
semantic coverage, Silo-Bench communication-limited claim, trace defects vs causal claim) are text fixes
at $0 and need no labels. The Qwen-235B judge failure in the UEGh Q1 table is covered by item 6's fix.

## Estimated charge: the 782 uncharged deepseek-v3.2 calls

The pre-existing Extension B artifacts (`rebuttal/results/extension_b_deepseekv32_*/api_responses.jsonl`)
record `model`, `usage` and no `cost_usd`, so the ledger rule never counted them. Approved 2026-11-15: price
them from the recorded tokens, no new calls.

| quantity | value |
| --- | ---: |
| records | 782 |
| records that already carried `cost_usd` | 0 |
| unique request ids / duplicates | 782 / 0 |
| prompt tokens | 588,965 |
| completion tokens | 602,169 |
| price used | $0.26/M prompt, $0.38/M completion |
| **estimate** | **$0.381955** |

Rule: `estimate = prompt_tokens x 0.26/1e6 + completion_tokens x 0.38/1e6`, once per logged record,
deduplicated by `request_id` (none duplicated). Price source: OpenRouter `/api/v1/models`, entry
`deepseek/deepseek-v3.2`, read 2026-11-15. The figure is an **estimate**, not a measured charge: the calls
were made at a price not recorded at the time, and the list price may have moved since. Recorded in
`20261115_inventory/deepseek_v32_pricing.json` and recomputable with
`python -m scripts.price_deepseek_calls`. It does not change the measured ledger; it is reported on its own
line and carried into the project total as measured $99.615406 + estimate $0.381955 = $99.997361.
