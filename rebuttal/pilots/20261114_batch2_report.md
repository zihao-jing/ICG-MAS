# Batch 2 report

2026-11-14. No paper edit, no commit. The six answers are unchanged except for
the new exploratory selection line, the explicit tie wording in R5, and
source/CI fixes. Silo-Bench extraction is stopped: no further prompt versions
and no further Silo-Bench extraction spend. Silo-Bench rows stay exploratory
and out of the headline.

## Headline (MuSiQue only)

| Card | Result | 95% CI | Cost | Status |
|---|---|---|---:|---|
| E3 route ablation, MuSiQue | 2,395 traces; extraction 737, selection 56, distortion 148, aggregation 789, correct 665 | removal shares below | $0.00 | Extraction presence validated (prompt v3, extraction checkpoint, MuSiQue 176 facts: .915 [.863, .952], κ .780 [.665, .877] — distinct from the Silo-Bench board .915 [.887, .937]); board carrier validated (.881 [.823, .925]); fidelity unvalidated |
| E2-C casebook | 20 traces (7 existing + 13 new), five cells: SB extraction 3, **SB selection 0 of 4 wanted (no selection claim)**, MQ extraction 4, MQ aggregation 8, SB aggregation 5; extension 78 calls, $0.598672; judge Qwen block only, 39 calls, 32 valid, 8 yes / 24 no, 8 traces any yes, 8 disagreements; **Gemini block 39 outputs, 0 judge calls** | descriptive, no test | $0.823536 extension ($0.598672 baselines + $0.224864 judge); $1.232078 casebook total including earlier $0.408542 | E2-C judge **small-sample pass** on the 15-trace validation (23/30 valid, 7 excluded); extension labels Qwen-only, not validated |
| E2-C judge validation | 15 traces / 30 outputs; 23 valid, 7 excluded (invalid JSON); agreement 1.000 | agreement [1.000, 1.000]; κ [1.000, 1.000] | $0.339496 | Degenerate at the ceiling; **small-sample pass**, not strong agreement; shortfall 7/30 stated |
| Part B batch 1 | 51 traces, 973 calls, 0 failed | none claimed | $3.876627 | Agreement-only, **unvalidated** judge: v1 κ .595 [.267, .864]; v2 κ .545 [.225, .831]; outside the headline |

*Interval methods in this report: E3 removal shares use the Wilson score 95%
interval for independent proportions; the pooled presence CR/complete values
use the instance-cluster bootstrap over instances, 2,000 draws, seed 43,
percentile 95%; E2-C counts are descriptive; Part B κ intervals are as
computed by its validation run.*

Sources: `20261114_e3_full/report.md` (E3 MuSiQue removal);
`20261113_musique_presence_full/report.md` (central-claim values and
reconciliation note);
`20261114_e2c_main/selection.json`, `20261114_e2c_extension/report.json`,
`20261114_e2c_validate15/validation.json` (E2-C);
`20261114_part_b_k1/report.md` (Part B).

### E3 MuSiQue removal counts

| Check removed | Changed | Share [95% CI] |
|---|---:|---|
| pool | 737/2,395 | .308 [.290, .327] |
| fidelity | 148/2,395 | .062 [.053, .072] |
| aggregation | 789/2,395 | .329 [.311, .349] |
| all three | 2,395/2,395 | 1.000 [.998, 1.000] |

*Intervals: Wilson score 95% CI for independent proportions.*

Central-claim values behind the routes (MuSiQue): extraction checkpoint CR .912
[.888, .935], complete .779 [.716, .838]; board checkpoint CR .902 [.878, .922],
complete .756 [.698, .811]; board AF .496 [.428, .562]. These are the figures
used in the chSu Q2 answer.

**Interval method and recount (2026-11-14).** The same method as the source
run: instance-cluster bootstrap over instances, 2,000 draws, seed 43,
percentile 95% interval. Recount from `results.json`: extraction 2,176/2,385
facts = .91237 [.88759, .93529]; board 2,867/3,180 = .90157 [.87825, .92241];
board complete 907/1,200 traces = .75583 [.69750, .81083]. Standard rounding to
three decimals gives .888/.902/.698, which is what this report and the final
text now use. The source records and this report agree; no discrepancy remains.
A dated reconciliation note is in `20261113_musique_presence_full/report.md` and
`20261114_piece2_final/CLOSURE.md`.

The pool row is **definitional**: `route()` assigns `extraction` exactly when
the pool check finds a required fact absent, so removing the check moves every
extraction-routed trace and no other. The fidelity row is likewise exactly the
148 traces the fidelity check routes to `distortion`. The extraction presence
label over-credits in all 15 MuSiQue disagreements (0 misses), so extraction
loss counts are lower bounds.

## Exploratory: Silo-Bench E3 routes

| Route (51 qwen235b traces, random_relay) | n |
|---|---:|
| selection | 26 |
| aggregation | 19 |
| correct | 4 |
| distortion | 2 |
| extraction | 0 |

| Check removed | Changed | Share [95% CI] |
|---|---:|---|
| pool | 0/51 | .000 [.000, .070] |
| fidelity | 2/51 | .039 [.011, .132] |
| aggregation | 19/51 | .373 [.253, .510] |
| all three | 51/51 | 1.000 [.930, 1.000] |

*Intervals: Wilson score 95% CI for independent proportions.*

**Exploratory, not like-for-like, out of the headline.** The Silo-Bench
extraction label is unvalidated (v3 κ .127; fixed v4 κ .553), the Silo-Bench
board-carrier and fidelity labels are unvalidated, and these traces use
`random_relay`, not the score-ranked relay of the MuSiQue E3 run. The sample is
qwen235b only. No Silo-Bench row is a validated correction, and no further
Silo-Bench extraction spend will be made.

## Selection-repair control (exploratory)

56 MuSiQue E3 traces routed to `selection`; 4 have no pool carrier and are
unrepairable, leaving 52 x 3 arms = 156 calls, 0 failed, $0.015254.

| Arm | Exact | Rate |
|---|---:|---:|
| Rerun | 14/52 | .269 |
| R-sel (targeted request) | 16/52 | .308 |
| V-sel (same-volume donor) | 14/52 | .269 |

The rates are simple proportions. The paired-difference intervals use an
instance-cluster bootstrap over instances, 2,000 draws, seed 42 (the analysis
run); this is a paired contrast, not a pooled ratio.

R-sel − Rerun = +.0385 [0.0, .098], 2 improved, 0 worsened, 50 unchanged;
on the 38 wrong-at-Rerun traces, +.0526 [0.0, .1351]. **38 of 52 pairs exceed
the 10% token-volume band** and the 14 volume-matched pairs are unchanged, so
the result is **exploratory**, not a clean selection effect. The 38
volume-flagged and 38 wrong-at-Rerun sets overlap in 27 traces (11 flagged but
correct, 11 wrong but volume-matched); both improvements are volume-flagged.
Source: `20261114_selection_repair_full/analysis.json`,
`20261114_selection_repair/selection.json`.

## E3 scope disclosure

The approved card covers MuSiQue and Silo-Bench, but the approved E3 source
(`20261113_main_table_redo/results.json`) is the MuSiQue Stage 2 corpus only.
The first E3 run therefore covered MuSiQue alone and did not say so. The
Silo-Bench routes above were added afterwards at **$0** from existing
Silo-Bench presence-full labels, marked exploratory. MuSiQue results are
unchanged (737 / 56 / 148 / 789 / 665).

## Registry status for Silo-Bench extraction

| Version | Prompt system | Agreement [95% CI] | κ [95% CI] | Status |
|---|---|---|---|---|
| v3 | `3f7f19bb…` | .860 [.811, .901] | .127 [.000, .270] | **FAIL** |
| v4 (list rule) | `47cd9e47…` | .938 [.850, 1.000] cluster | .553 [.000, 1.000] cluster | **FAIL** |

v3 was 30 traces from 16 instances with trace-level CIs; v4 was 30 traces
from 18 fresh instances with instance-cluster CIs. Both are recorded as
failures; Silo-Bench extraction is exploratory and unvalidated.

## Silo-Bench extraction-presence use audit

Check of every use of Silo-Bench presence in the six answers and the main
table, prompted before this report. Labels are prompt v9 unless stated.

| Use | Where | Rests on | Status |
|---|---|---|---|
| Missing-fact cohort (69 traces / 59 instances) | Answers "Extraction loss" lines 98–100; line 183 cohort truth | Lexical input-shard rule `20261112_missing_fact_repair/PRESENCE_RULE.md` (token-recall present ≥.8 / partial ≥.4 / absent), zero model calls, recorded manual read | **Unaffected** — no AI presence label |
| Sharding reattribution **20/59** (27/69 traces) | Answers lines 98–100; `20261113_sharding_diagnosis/report.md` | Same lexical input-shard rule; also 37/216 main-table diagnoses, 2/8 E1 anchor | **Unaffected**; lexical rule can read co-located tokens as presence, so the sharding count is a lower bound |
| Input-presence check in the audit | Answers line 183 | Same lexical rule on the agent's own input shard; no model label | **Unaffected** |
| Silo-Bench CR / complete **board** columns | Answers lines 64–68, 77–78; table header says "Quantity (board)" | Prompt v9 at the **board** checkpoint; validated on 69 board cases, 471/515 = .915 [.887,.937], κ .653 [.447,.854] | **Unaffected by the extraction failure**; point passes but κ lower bound .447 < .60, so the interval is wide |
| Silo-Bench CR / complete **extraction** columns | Main table `20261114_piece2_final/CLOSURE.md` (A CR .986 [.976,.994], complete .944 [.910,.976]); `20261113_sb_presence_full/report.md` extraction rows | Prompt v9 at the **extraction** checkpoint | **Unvalidated** — SB validation covered the board checkpoint only; extraction-specific v3 κ .127 and v4 κ .553 both failed. Now marked in both files |
| Silo-Bench presence κ .653 | Answers line 22 and line 37 | Same board validation: 69 **board** cases, 515 facts, 471/515; `RULE.md` states "Only the board checkpoint is validated" | **Confirmed board, not extraction**; unaffected by the extraction failure, wide interval caveat stands |

No figure in the six answers rests on the Silo-Bench extraction label, so no
answer number or text was changed. The two answer lines the check flagged
(77–78) are board figures: they match the board pooled rows of
`20261113_sb_presence_full/report.md`, and the answer table is headed
"Quantity (board)". The extraction figures are the ones in `CLOSURE.md`, and
those are the ones now marked unvalidated. The lexical input-shard rule and
the manual read in the missing-fact cohort use no AI presence label at all, so
the 20/59 sharding count and the line-183 cohort truth are unaffected by the
Silo-Bench extraction failure (they remain lower bounds because the rule is
lexical).

## Small-sample caveats

- The board validation's **complete κ 1.000 [1.000, 1.000]** is **60/60
  traces**. It is degenerate; the per-fact figure (.881 [.823, .925]) is the
  informative one.
- The E2-C judge pass is **23 valid of 30** on the full 15-trace validation
  (10-trace first stage + 5-trace completion), 7 excluded as invalid JSON.
  κ 1.000 is degenerate at the ceiling; **small-sample pass**, not strong
  agreement. The extension judge ran on the **Qwen block only**: 39 calls, 32
  valid, 8 yes / 24 no; the Gemini block's 39 outputs were not scored.
- The E2-C selection label was validated **against the authors' labels**
  (κ .676 [.526, .804]); those labels are the validation reference, never an
  input.

## Part B

Batch 1 labels are on record and marked unvalidated. v1 κ .595 [.267, .864];
v2 κ .545 [.225, .831]. The Part B claim is out of the headline. Batches 2 and
3 were not run; no further Part B spend. Fidelity/distortion remains
unvalidated; coverage and CR are upper bounds; loss and omission are lower
bounds.