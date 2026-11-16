# Zero-cost checks: A4, B8, B9

2026-11-15. No API calls. No paper edits, no commits, no reviewer-file changes.

## A4 — source of the UEGh W2 additional-model distortion rates

All four rates come from one file: `results/distortion_new_models/distortion_results.json`, produced by
`scripts/run_distortion_new_models.py` (Qwen-235B judge, prompt classes EXACT / PARAPHRASE / PARTIAL /
DISTORTED / NO_MATCH, Silo-Bench, `score_ranked_relay`, n5 + n10 runs).

| Model | Rate in UEGh W2 | Field | Count | Covered | Protocol | Label |
|---|---:|---|---:|---:|---|---|
| Gemini-FL | 1.3% | `distortion_strict` .01323 | 5 DISTORTED | 378 / 390 | score_ranked_relay | Qwen-235B judge |
| GPT-4o-mini | 4.6% | `distortion_strict` .04585 | 16 | 349 / 390 | score_ranked_relay | Qwen-235B judge |
| Gemma-4-31B | 0.8% | `distortion_strict` .00843 | 3 | 356 / 390 | score_ranked_relay | Qwen-235B judge |
| DeepSeek-R1-32B | 10.6% | `distortion_strict` .10569 | 13 | 123 / 350 (35.1%) | score_ranked_relay | Qwen-235B judge |

**Yes — every one rests on the unvalidated Dist label.** It is the same judge and the same DISTORTED class
as the paper's Dist column, not the Opus/Haiku strict-fidelity label that passed validation at κ .721 on
natural board cases. The Dist view failed its own validation on constructed cases (κ .467), so these four
rates carry the unvalidated label into UEGh W2. The coverage denominators are not affected (they come from
the same file's `n_covered`/`n_total` and are the numeric-overlap bound).

Re-scoring with the validated strict-fidelity label needs 4 models × 390 (350) covered pairs, about
1,510 pairs; at the board rate ($0.0051/fact) that is ~$7.7 of Opus, or ~$3 with Haiku and an Opus reference
sample. Not done here.

## B8 — main table ranked on validated labels only

**Validated columns and cells.** Silo-Bench board presence (per-fact A, κ .653 [.447, .854] — point pass,
wide interval) gives CR, omission, complete and AF for 3 models × 4 relay/summary protocols
(`20261113_sb_presence_full/report.md`, board, new column). MuSiQue board presence (κ .857 [.708, .955])
covers three Stage 2 models on score-ranked relay only, and they are not the paper's three models, so MuSiQue
cannot be re-ranked against the table; it is excluded.

**Excluded as unvalidated:** Dist, redundancy, useful budget, and every full-sharing AF cell (no validated
label for full sharing). The published columns are the lexical record.

**Flips.** Comparing pairwise orderings among protocols within a model, and among models within a protocol,
published vs validated: **24 flips — 11 reversals and 13 tie changes.**

| Metric | Scope | Pair | Published | Validated | Kind | Takeaway touched |
|---|---|---|---|---|---|---|
| CR | Qwen-235B | Random vs Score | 0.844 / 0.844 | 0.987 / 0.959 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| CR | Qwen-235B | Random vs Redundancy | 0.844 / 0.844 | 0.987 / 0.997 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| CR | Qwen-235B | Score vs Redundancy | 0.844 / 0.844 | 0.959 / 0.997 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| AF | Qwen-235B | Score vs Redundancy | 65.4 / 65.4 | 0.788 / 0.808 | tie broken | Relay AF ordering (score-ranked vs redundancy-aware) |
| CR | Mistral-S | Random vs Score | 0.885 / 0.885 | 0.972 / 0.969 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| CR | Mistral-S | Random vs Redundancy | 0.885 / 0.885 | 0.972 / 0.977 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| CR | Mistral-S | Score vs Redundancy | 0.885 / 0.885 | 0.969 / 0.977 | tie broken | Relay-tie bolding in Table 3 (relays tied on CR) |
| AF | Mistral-S | Score vs Redundancy | 69.2 / 69.2 | 0.769 / 0.750 | tie broken | Relay AF ordering (score-ranked vs redundancy-aware) |
| AF | Qwen-3.6-F | Summary vs Random | 50.0 / 28.8 | 0.327 / 0.392 | reversal | Key Finding 2 AF sentence (summary has the highest AF) |
| AF | Qwen-3.6-F | Summary vs Score | 50.0 / 32.7 | 0.327 / 0.404 | reversal | Key Finding 2 AF sentence (summary has the highest AF) |
| AF | Qwen-3.6-F | Summary vs Redundancy | 50.0 / 26.9 | 0.327 / 0.392 | reversal | Key Finding 2 AF sentence (summary has the highest AF) |
| AF | Qwen-3.6-F | Random vs Redundancy | 28.8 / 26.9 | 0.392 / 0.392 | tie created | Relay AF ordering (score-ranked vs redundancy-aware) |
| CR | Summary protocol | Mistral-S vs Qwen-3.6-F | 0.750 / 0.725 | 0.792 / 0.805 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Random protocol | Qwen-235B vs Mistral-S | 0.844 / 0.885 | 0.987 / 0.972 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Random protocol | Qwen-235B vs Qwen-3.6-F | 0.844 / 0.844 | 0.987 / 1.000 | tie broken | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Random protocol | Mistral-S vs Qwen-3.6-F | 0.885 / 0.844 | 0.972 / 1.000 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Score protocol | Qwen-235B vs Qwen-3.6-F | 0.844 / 0.844 | 0.959 / 1.000 | tie broken | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Score protocol | Mistral-S vs Qwen-3.6-F | 0.885 / 0.844 | 0.969 / 1.000 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Redundancy protocol | Qwen-235B vs Mistral-S | 0.844 / 0.885 | 0.997 / 0.977 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Redundancy protocol | Qwen-235B vs Qwen-3.6-F | 0.844 / 0.844 | 0.997 / 1.000 | tie broken | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| CR | Redundancy protocol | Mistral-S vs Qwen-3.6-F | 0.885 / 0.844 | 0.977 / 1.000 | reversal | Model ranking in the per-model audit appendix (Mistral-S best on CR) |
| AF | Random protocol | Qwen-235B vs Mistral-S | 67.3 / 67.3 | 0.827 / 0.712 | tie broken | Qwen-235B vs Mistral-S AF ordering |
| AF | Score protocol | Qwen-235B vs Mistral-S | 65.4 / 69.2 | 0.788 / 0.769 | reversal | Qwen-235B vs Mistral-S AF ordering |
| AF | Redundancy protocol | Qwen-235B vs Mistral-S | 65.4 / 69.2 | 0.808 / 0.750 | reversal | Qwen-235B vs Mistral-S AF ordering |

**What survives.** Summary exchange keeps the lowest CR in all three models (upper bounds, but the gap is
large), so Key Finding 2's relay-versus-summary direction stands. Qwen-3.6-F keeps the lowest AF on relays.

**What flips.**
- **Summary's AF is not highest everywhere.** For Qwen-3.6-F, summary AF falls from 50.0% to .327, the lowest of
  its four audited protocols; Key Finding 2's "summary has the highest AF" holds for Qwen-235B and Mistral-S only.
- **The relay CR tie breaks.** Validated CR orders Redundancy > Random > Score for Qwen-235B and Mistral-S, and
  Redundancy = Random > Score for Qwen-3.6-F; the table's equal .844/.885 cells become a strict order.
- **Mistral-S is no longer the highest-CR model.** On all three relay protocols Qwen-3.6-F (1.000) and
  Qwen-235B (.987/.959/.997) overtake Mistral-S (.972/.969/.977); on summary, Qwen-3.6-F (.805) overtakes
  Mistral-S (.792). The per-model appendix ordering changes.
- **Relay-model AF ordering reverses** between Qwen-235B and Mistral-S on score-ranked and redundancy-aware.
- **The AF range in §4.2 cannot be re-derived here.** The published 26.9–71.2% spans all ten models
  (71.2 is Gemini-FL score-ranked in the appendix); validated labels exist for three models, whose validated
  range is .327–.827. Labelling the other seven models is what B8 would need to restate the sentence.

**Caveat carried.** The Silo-Bench A label's κ lower bound is .447, below .60; the flips above are point
estimates, and the wide interval applies to every validated cell.

## B9 — placement test verified from the records

From `20261113_placement_redo/results_matched.json` (60 arm records, 30 cases):

- **Discordance.** Exact cells: (diagnosed exact, random wrong) = 8, (wrong, wrong) = 22, (exact, exact) = 0,
  (wrong, exact) = 0. So 8 discordant pairs, all favouring diagnosed placement; McNemar's b and c are 8 and 0.
- **Exact McNemar.** Two-sided p = 2 × 2^-8 = **.0078125**, i.e. ≈ .008. Confirmed.
- **Intervals.** 8/30 Clopper-Pearson [12.3%, 45.9%]; 0/30 [0.0%, 11.6%]. Non-overlapping: 12.3 > 11.6.
  Confirmed with the repo's `cp_ci` (Wilson would give [14.0, 45.4] and [0.0, 11.3], also non-overlapping).
- **Reading kept.** Both arms replace the same corrupted unit, and in the 8 diagnosed-exact cases the random
  arm's transmission is empty (4) or an unrelated unit (4), so the random arm cannot carry the corrected unit
  by construction. The test justifies placement as a mechanism check, not a general efficacy claim.

## A2 — anchor check of the new labeller: blocked at $0

The new point-level labeller has labels only on the 21 fresh traces; it has not run on either anchor, and
neither anchor supplies per-fact labels on the same units:

- **E1 anchor.** 22 instance clusters / 90 traces with 339 paired author fact labels. Its instances have
  **zero overlap** with any existing per-fact labeller run (`20261113_main_table_redo` population: 0 of 800
  instances; `20261113_musique_presence_full`: separate sample). A fact-level check needs the labeller run on
  those 22 instances: about 30 instances x ~3 facts x 2 models ≈ 180 calls, ~$0.7–1.0, plus calls to align
  the labeller's support-derived facts to the authors' critical-fact strings.
- **Silo-Bench anchor.** All 8 anchor instances are in `20261113_sb_presence_full`, so per-fact presence labels
  exist there, but the authors' critical facts are free-form strings (e.g. "Target computation requirement:
  80"), not the support-derived atoms the labeller labels. Alignment would be a model call, not a join.

The trace-level anchor numbers already on record are the ones next to the author–author κ .530 [.307, .810]:
reference-judge–author κ .676 [.530, .806], matcher–author κ .674 [.496, .824], and the reference judge is
stricter than the authors (18 lost-where-reached, 0 the reverse). They are trace-level, so they do not check
the fact-level label.

**Proposal if A2 is wanted:** run the point-level labeller on the 22 E1 anchor instances and the 8 Silo-Bench
anchor instances at the board checkpoint (the anchor facts are board facts), with the same prompt and models,
then a trace-level and, where the atoms align by text, a fact-level comparison. Estimated $1.0–1.5, cap $2.
