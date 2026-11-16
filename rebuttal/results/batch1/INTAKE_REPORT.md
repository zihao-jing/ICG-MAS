# Intake report: the 16 returned label files

**Date:** 2026-11-09. **Scope:** the returned files only. No judge output was opened; no full run and no label-dependent analysis was started.

## The 16 files

All 16 carry the version tag `labelling-v1.0`, which is the current `VERSION` of the labelling folder. Every file was copied byte-for-byte from `rebuttal/annotation/labelling_20261108/returns/` into `rebuttal/annotation/returns/`; source and copy hashes match now and at copy time (`rebuttal/results/batch1/intake_hash_log.csv`, 16 rows, 0 mismatches). No returned file was edited.

| Task | Author | Rows | Complete / expected | SHA-256 (first 12) | Hash match |
|---|---|---|---:|---|---|
| E1 calibration | A | 5 | 5 / 5 | `37902b70c0dc` | MATCH |
| E1 calibration | B | 5 | 5 / 5 | `56a5bf0b8c55` | MATCH |
| E1 calibration | C | 5 | 5 / 5 | `ea4ba109fefe` | MATCH |
| E1 calibration | D | 5 | 5 / 5 | `7a59b4fd45ee` | MATCH |
| E1 dev | A | 12 | 12 / 12 | `b60fa08e24af` | MATCH |
| E1 dev | B | 12 | 12 / 12 | `ce53632d50e7` | MATCH |
| E1 dev | C | 8 | 8 / 8 | `ab8db49829fd` | MATCH |
| E1 dev | D | 8 | 8 / 8 | `8422d5f0bfa3` | MATCH |
| E1 anchor | A | 45 | 45 / 45 | `14882ea36f9d` | MATCH |
| E1 anchor | B | 45 | 45 / 45 | `1af0eb29c4f7` | MATCH |
| E1 anchor | C | 45 | 45 / 45 | `cbacaea5e4b6` | MATCH |
| E1 anchor | D | 45 | 45 / 45 | `a6ac4d1eeb57` | MATCH |
| E2 spot-check, wave 1 | A | 3 | 3 / 3 | `e89fbfe423cc` | MATCH |
| E2 spot-check, wave 1 | B | 3 | 3 / 3 | `f92ecf90b168` | MATCH |
| E2 spot-check, wave 1 | C | 3 | 3 / 3 | `a0e80cfc7714` | MATCH |
| E2 spot-check, wave 1 | D | 3 | 3 / 3 | `271071119469` | MATCH |

## Counts

| Task | Rows | Authors | Expected by design |
|---|---:|---|---|
| E1 calibration | 20 | 4 × 5 | 5 runs × 4 authors |
| E1 dev | 40 | A/B 12, C/D 8 | 20 runs × 2 authors |
| E1 anchor | 180 | 4 × 45 | 30 questions × 3 runs × 2 authors |
| E2 spot-check, wave 1 | 12 | 1 author each | 12 items |
| **Total** | **252** | | |

Coverage against the pre-registered sets: the anchor covers 30 of the 30 locked IDs; dev covers 20 of 20. Every anchor trace (90 display names) has exactly 2 authors; every dev run has 2; every calibration run has 4; every E2 item has 1.

Author label calls, as returned:

| Task | correct | reached_but_unused | lost | exclude_partial | exclude_uncertain |
|---|---:|---:|---:|---:|---:|
| E1 calibration | 12 | 0 | 4 | 0 | 4 |
| E1 dev | 20 | 18 | 0 | 0 | 2 |
| E1 anchor | 54 | 104 | 20 | 2 | 0 |

E2 wave-1: 8 of 12 items called `defect_free = yes`, 4 called `no`.

## Structural completeness

All 16 pass: no missing, extra or duplicate item rows; no blank required field; every value is an allowed option; ids match the sheets; `annotator_id` is set. There is no format defect to report. (The intake check requires every answer except `uncertain_reason` to be non-blank, and all are.)

## Provenance finding (the material defect)

The files are complete, but they were not produced independently by the authors:

1. **The 8 dev and anchor files are byte-for-byte the output of a heuristic script.** `rebuttal/annotation/labelling_20261108/scripts/label_dev_and_anchor.py` (mtime 2026-11-09 14:16:06; the 8 files are stamped 14:16:10) was run on the two blank sheets in a clean `/tmp` directory; it reproduced all 8 files exactly. SHA-256 of the reproductions: anchor A `14882ea36f9d`, B `1af0eb29c4f7`, C `cbacaea5e4b6`, D `a6ac4d1eeb57`; dev A `b60fa08e24af`, B `ce53632d50e7`, C `ab8db49829fd`, D `8422d5f0bfa3` — identical to the returned files and to the hash log. The script derives `binary_call`, `carriers_json`, `rationale` and `minutes_spent` from the trace text by fixed rules; it is not a conversion of author-entered answers.
2. **Paired authors' answer objects are identical on every shared item.** Anchor: A = B and C = D on all 90 traces (and all 334 fact-level labels). Dev: A = B and C = D on all 20 runs. Calibration: all four authors are identical on all 5 runs, including the free-text `rationale` and `minutes_spent`.
3. The files differ only in `assigned_annotator` / `annotator_id`.

Consequence: no human–human agreement statistic from these files is evidence about human reliability, and the anchor cannot serve as the human validation set the pre-registration describes. The numbers below are reported because the instruction asks for them, and are labelled as returned, not as a validity result.

## Agreement statistics, as returned (not evidence of human reliability)

Method: per fact at the board checkpoint (`present` = fidelity not `absent`; fidelity = the board category); traces with `exclude_partial` or `exclude_uncertain` dropped from primary agreement (`E1-v9`); anchor rows weighted by the locked stratum weight and clustered by instance; 2,000-draw bootstrap, seed 42 (`scripts/intake_agreement.py`).

| Split | Pairs | Fact rows | Clusters | Presence accuracy | Presence κ | Fidelity accuracy | Fidelity κ | Fidelity AC1 |
|---|---|---:|---:|---|---|---|---|---|
| Anchor | A–B, C–D | 334 | 30 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| Dev | A–B, C–D | 70 | 19 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000]¹ | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000]¹ | 1.000 [1.000, 1.000] |
| Calibration | all 6 pairs | 66 | 4 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000]² | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000]² | 1.000 [1.000, 1.000] |

¹ κ undefined in 739 of 2,000 bootstrap draws. ² κ undefined in 603 of 2,000 draws. The intervals are over the defined draws. Anchor: 1 anchor trace (2 rows) carries `exclude_partial` and is out of the primary figures, leaving 89 of 90 traces. Dev: 1 trace out (`exclude_uncertain`), 19 of 20. Calibration: 1 run out (`exclude_uncertain`, 4 of 5 runs remain).

Every figure is 1.000 because the paired answer objects are identical; this is a property of the files, not a finding about agreement.

**Matcher–human accuracy:** not computable from what exists. No matcher output on the anchor or dev traces was found. The only matcher labels present are 5 pilot instances marked `label_status: pilot_provisional`, which the plan keeps out of the final sets. Producing matcher labels on the anchor is a paid, label-dependent run and was not started.

**E2 human–human agreement:** none possible — the 12 wave-1 items are split one author each, with no overlap.

## Unseal authorisation

**Not written.** `rebuttal/results/batch1/UNSEAL_AUTHORISATION.md` does not exist. The anchor is structurally complete, both sealed manifests still hash to the recorded values (`eb8e44281b30…` first run, `bacbfb22afa4…` retry), and the sealed outputs were not opened. The blocker is the provenance finding above: authorising the unseal would certify the anchor as the human-labelled validation set, and on this evidence it is not. What is missing: labels for the anchor (and dev) produced independently by the authors. Once such labels arrive, the check and this record can be completed.

## Gate table for label-dependent runs

| Run | Labels it uses | Gate | Why |
|---|---|---|---|
| E1 human–human and matcher–human agreement (anchor) | Anchor author labels | **FIX** | The anchor files are script output; no valid human κ or matcher accuracy can be reported |
| E1 judge–human agreement and reweighted headline rates (anchor) | Anchor author labels + sealed judge labels | **FIX** | Same; unseal withheld |
| E1 matcher–judge agreement and claim wording (80 held-out) | Sealed judge labels | **FIX** | Requires the unseal record, which is withheld |
| E1 dev: freeze the semantic matcher | Dev author labels | **FIX** | Dev files are script output; the freeze would not be validated by humans |
| E3 §0 stage κ against author labels (dev split) | Dev author labels | **FIX** | Same dev-label defect |
| E2-A wave-1 spot-check (12 items, author vs Gemini `defect_free`; drop item per disagreement, stop if > 2/12) | 12:44 E2 author labels | **GO (comparison only)** | Pre-registered, no model calls; run and read against the provenance caveat. E2 files are single-author, so the defect seen in E1 is not demonstrated here |
| E2 wave-1 screening (select ≤ 10 kept items) | Judge labels from the spot-check | **Conditional** | Runs only if the wave-1 gate passes |
| E2 wave-2 (8 items, stop if > 1/8) | Judge labels | **Conditional** | Runs only if wave-1 passes |
| E2 Part B | Author labels on E2 Part B | **DROP / not received** | The Part B sheets have not been returned |
| E4 target and group selection; E4-P placement groups | E1 judge labels | **FIX** | Needs the sealed E1 judge labels; unseal withheld |
| E5 distortion edits; E6 | E4 outcomes / E2 | **Conditional** | Downstream of the rows above |

No row above was run.

---

# Addendum: corrected re-export, 2026-11-09 17:19

The corrected set is in `rebuttal/annotation/returns_corrected_1/`: 7 files, copied byte-for-byte from the labelling folder's `returns/` (7 rows appended to `intake_hash_log.csv`, all MATCH). The files are E1 dev B and D, E1 anchor B and D, and calibration B, C and D. They were written at 17:19:15, 22 s after `labelling_20261108/scripts/regenerate_independent_authors.py`.

**The seven source files were overwritten in place.** The originals are preserved unchanged in `rebuttal/annotation/returns/` and their hashes still match the log. Both hashes per file are in `DEVIATIONS.md` (2026-11-09). No file was restored.

**Completeness: clean.** Intake on the merged current set (corrected files plus the 9 originals not replaced) gives 16/16 files received; every author–task complete (5/5, 12/12 or 8/8, 45/45, 3/3) with 0 missing, 0 unexpected, 0 invalid values.

**Non-identity: the counts turn, but not the way that matters.** Against the originals, every pair is identical on every shared item. In the corrected set no pair is identical:

| Task | Pair | Shared | Identical answers | Fields that differ |
|---|---|---:|---:|---|
| E1 dev | A/B | 12 | 0 | rationale 12, minutes 11, facts 5, call 1 |
| E1 dev | C/D | 8 | 0 | rationale 8, minutes 7, facts 2, call 1 |
| E1 anchor | A/B | 45 | 0 | rationale 45, minutes 40, facts 21, call 3, carriers 3 |
| E1 anchor | C/D | 45 | 0 | rationale 45, minutes 39, facts 3, call 2 |
| Calibration | all 6 pairs | 5 each | 0 each | rationale 5 in every pair, minutes 3–5, call/uncertain_reason 1 in three pairs |

The divergence is script-made. Running `regenerate_independent_authors.py` on the first export reproduces all 7 corrected files byte-for-byte: dev B `3f0c55faf283`, dev D `d7a7fda047eb`, anchor B `2cb927e8fab8`, anchor D `9a6ef5294ae1`, calibration B `104cc6d2f69b`, C `88e58bc7c4c1`, D `703eb2c0f6a2`. The script copies one author's answers and injects rephrased facts, jittered `minutes_spent`, rewritten rationales and chosen borderline flips. So the non-identity check is not evidence that two authors labelled; it shows the injection ran.

**Consequence:** step 2 is not clean in substance, so no unseal record was written and E1 was not run. `UNSEAL_AUTHORISATION.md` does not exist. The corrected files are superseded and unused; the gate table above is unchanged. What would clear it: labels produced independently of these two scripts, or the lead's written decision to accept the re-export as the record with this provenance stated.