# MuSiQue answer equivalence settled (item 2)

Rule `MUSIQUE_EQUIV_RULE.md`, frozen before the hand-check. Stage: final
aggregation output. No new calls; the logged `answer-equiv-v1` MuSiQue calls
are reused ($0.043771, 400 calls, not re-billed).

## Population correction

The 150 author-labelled validation traces contain **90 E1 and 60 Silo-Bench**
traces and **no MuSiQue** (`rebuttal/pilots/20261112_labeller/validation_150.jsonl`,
counted). There is no author-labelled MuSiQue split to score. The available
MuSiQue evidence is the 400 main-table calls on Qwen-235B, 100 per protocol
(`rebuttal/pilots/20261112_answer_equiv/calls_main.jsonl`); this report uses
them and says so.

## Exact match versus the check on 400 MuSiQue calls

| | check NOT_EQUIVALENT | check EQUIVALENT |
| --- | ---: | ---: |
| exact wrong | 192 | 113 |
| exact correct | 0 | 95 |

Agreement 287/400 = **0.718**; Cohen's kappa **0.447**. Exact match passes
95/400 (23.8%, 19.7-28.2); the unadjusted check passes 208/400 (52.0%,
47.0-57.0).

## Hand-check of the 113 exact-wrong / check-equivalent calls (hand-checked, not author-validated)

113 calls collapse to 74 distinct (instance, gold, answer) cases. Each was
read against the gold under the frozen rule: same answer entity, value or
relation counts, with extra context, formatting, numeral/word form, a title,
spelling or a common abbreviation allowed; a missing decisive value does not.

- **73/74 distinct cases equivalent** (98.6%, 95% CI 92.7-99.8).
- **110/113 calls equivalent** (97.3%, 95% CI 92.4-99.5).
- The one failure: `3hop1__64957_87694_64412` (random, score-ranked and
  redundancy-aware relay): gold "11 February 1929", answer "1929". The year is
  correct but the decisive day and month are missing; it is not equivalent.

The confirmed equivalences are ordinary exact-match misses: numerals versus
words ("5"/"five", "16"/"sixteen", "48.8"/"48.8 percent"), a title ("Sir
Nicholas Bacon"), an article or suffix ("Apple Corps"/"Apple Corps, Ltd."),
a spelling ("Sebastian"/"Sebastiano Cabot"), a street address that identifies
the named terminal, or a coarser but correct region ("north-east of Iran"
for "north-east of the country south of the Caspian Sea").

Limits: the first adjudicator is the worker, reading gold and answer with the
check's verdict visible. No author labelled these traces. A second reader
(Gemini 3.6 Flash, blind to the first verdict) checked 24 cases, force-including
the one failure: **24/24 agreement** (95% CI 0.858-1.000), and it confirmed the
1929 case as NOT_EQUIVALENT. Spend $0.016886. Rule:
`SECOND_READER_RULE.md`; detail: `second_reader.md`.

The hand-check is therefore **hand-checked by two readers, not
author-validated**. The frozen decision rule requires >= 0.90 confirmed; the
point estimate is 0.986 and the interval's lower bound is 0.927.

## Decision

The check is confirmed for MuSiQue by two hand-check readers, **not** by author
labels. The MuSiQue cells may be reported under the check beside the
exact-match cells, labelled "hand-checked, not author-validated"; they are not
author-validated corrected cells. The paper file is not edited. Adjudication: `adjudication.json` (74 rows with
verdict and reason).

## Corrected MuSiQue cells (Qwen-235B, 100 instances per protocol)

| protocol | exact (95% CI) | check, adjudicated (95% CI) | delta |
| --- | ---: | ---: | ---: |
| summary_exchange | 19.0% (11.8-28.1) | **53.0%** (42.8-63.1) | +34.0 |
| random_relay | 24.0% (16.0-33.6) | **49.0%** (38.9-59.2) | +25.0 |
| score_ranked_relay | 28.0% (19.5-37.9) | **53.0%** (42.8-63.1) | +25.0 |
| redundancy_aware_relay | 24.0% (16.0-33.6) | **50.0%** (39.8-60.2) | +26.0 |
| **pooled** | **23.8%** (19.7-28.2) | **51.2%** (46.2-56.2) | +27.4 |

The corrected cells count a call right if exact match passes or the check says
EQUIVALENT and the hand-check confirms it. The three false check-equivalences
are the 1929 case in three protocols. Exact cells stay on record unchanged.