# Zero-cost checks: E3 on Silo-Bench, granularity, stage derivation, Part B step 1

2026-11-15. No API calls. Spend $0. No paper edits, no commits, no reviewer-file changes.

## 1. E3 on Silo-Bench under the point-level label: not possible, and why

The E3 routes that exist for Silo-Bench were computed on the earlier extraction label
(`20261114_e3_sb/report.md`): 51 qwen235b random_relay traces, routes selection 26, aggregation 19,
distortion 2, correct 4; checkpoint removal changes pool 0/51, fidelity 2/51, aggregation 19/51.

**The frozen point-level label (atom κ .847) does not cover those 51 traces.** It covers 21 traces
(`20261115_sb_points/`), models deepseekr1_32b (12) and geminiflashlite (9), drawn from fresh instances. Those
21 traces carry no board labels, and their instances do not overlap the 51 (0 shared keys). Recomputing the
51 routes under the point label would need new labelling calls: at the observed rate ($2.200761 for 21 traces,
155 facts, 2,755 atoms) a 51-trace run costs about **$5.3**, which this step does not spend.

**Why the extraction route is 0/51.** Across the 51 traces the extraction checkpoint has 380 fact labels:
293 present, 87 partial, **0 absent**. The route fires only on an absent fact, so no trace can be routed to
extraction. The cause is the fact granularity, not the labeller: the proxy facts are built from the same
shards that the extraction checkpoint restates, so every fact is found at least partially in that
checkpoint's output. This is the same mechanism that sends coarse facts to sharding in the main-table run.

Reporting rule for the paper: the Silo-Bench E3 row stays labelled by the label it was computed with. It is
not silently presented as a point-level result.

## 2. Silo-Bench granularity: proxy facts per question vs gold

| source | traces | proxy facts mean | proxy median | max | gold mean | gold median | ratio of means | per-trace equal / above / below gold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| one-step v2 facts (200 traces with a valid set) | 200 | 8.44 | 6 | 120 | 7.47 | 5 | 1.129 | 172 / 23 / 5 |
| two-step v3 (108 traces completed so far) | 108 | 10.07 | — | 60 | 9.08 | — | 1.109 | 1 trace above 30 |

The one-step mean is within 13% of gold, but that average hides the tails: 172 traces match gold exactly,
23 overshoot (one to 120 facts), and 5 undershoot. The two-step run, on the completed subset, is slightly
under gold (ratio .957). Neither figure is evidence that the proxy recovers gold supports; that is the
equivalence question (98.7% one-step, pilot-level for two-step), reported separately.


**Granularity bar.** The bar is mean facts <= 1.2 x gold, no trace above 30, no generation failure. On the 108
completed traces the mean ratio is 1.109 and generation failures are 0, but **one trace exceeds the 30-fact
ceiling**: `qwen235b|SB|results/run_qwen235b_n10|score_ranked_relay|III-27_n10` produced 60 facts. The max<=30
test therefore fails once (1/108 = 0.9% of completed traces), and the bar is reported as failed, not as passed
with an exception. The trace stays in the population; its stage results are counted with the rest.

## 3. Stage derivation from gold-fact labels: labels do not exist for the main tables

- The only gold-fact labels with per-atom presence are the E1 anchor: 80 facts across 55 instances, board
  checkpoint, from the authors' released fact lists (`20261115_anchor_points/`). They are independent of the
  proxy by construction: the facts and their carrier units come from the authors' files, not from any proxy
  run, and the labeller reads the board text only.
- Those 55 instances do not overlap the 400 MuSiQue main-table traces (0 shared keys) and do not cover the 51
  Silo-Bench E3 traces.
- Silo-Bench has no gold-fact labels at all: the anchor run was never executed there, because its facts carry
  no ids or carrier list to compare against.

**Therefore proxy-vs-gold stage agreement is not computed for either main table.** It cannot be computed from
the labels that exist, and pooling the 55 anchor instances with a different population would not answer the
main-table question. The correct statement in the paper is that the audit stage distribution is the proxy's own
label distribution, with no independent stage ground truth.

## 4. Part B step 1: are the judge-vs-reference disagreements multi-stage traces?

Both earlier validations (30 traces each, Gemini 3.6 Flash judge vs Opus 5.5 reference, frozen prompt v1 and
v2) had 6 class disagreements each (agreement .800; κ .595 and .545).

| validation | disagreements | traces with ≥2 stages across the two label sets | both sides list identical defect sets |
| --- | ---: | ---: | ---: |
| v1 | 6 | 6 | 2 |
| v2 | 6 | 6 | 6 |
| both | 12 | **12** | 8 |

Every disagreement sits on a trace that fails at more than one stage: v1 adds aggregation as a second defect
where the judge folds it into transmission, or splits extraction vs transmission; v2's six are all
single-vs-multiple calls where both models list the same two or three defects and differ only on whether any
one of them would suffice.

**Condition met.** Most disagreements (12 of 12) are multi-stage, so the step-2 truth rule "a method is right
if it names any valid stage" is the appropriate one. Step 2 remains queued until it is started; the rescore of
the old 60 existing labels is $0, and the 30-trace validation through the Opus CLI is the paid part.