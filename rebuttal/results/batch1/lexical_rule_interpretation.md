# Lexical rule: what the 40 author-absent rows look like, and the direction of the bias

Read-only analysis of the E1 anchor labels and traces. No model call was made for this report; no existing
result file was edited. Source data: `rebuttal/results/batch1/E1/lexical_bias.json` and
`E1/lexical_instance_rate.json`, produced by `scripts/analyze_lexical_bias.py` and
`scripts/analyze_lexical_instance_rate.py` from the returned anchor label files, the trace packages and
`align_gold_to_transmitted`. Row set: 1,356 labelled fact/checkpoint rows (30 anchor instances × 2 annotators
× pool and board checkpoints). The 30 anchor instances are 22 MuSiQue and 8 Silo-Bench (90 traces = 66 + 24);
they are a stratified sample of the 80-instance held-out pool. Both scripts use a fixed seed and sorted
strata, so the bootstrap is reproducible.

## Directions (read this before the claims table)

The two effects of the lexical rule point in opposite directions.

- **Fact-level: CritRec is overstated, OmissionRate understated.** The lexical rule marks every row covered,
  including the 40 rows the authors mark absent. Any CritRec computed with the rule therefore counts absent
  facts as present: CritRec is an **upper bound** on the author-present rate, and OmissionRate = 1 − CritRec is
  a **lower bound**. The paper's measured **loss figures are lower bounds** in this direction. "Conservative"
  applies only to these loss figures.
- **Instance-level: the candidate-aggregation-failure (AF) count is over-counted.** The AF flag is defined on
  whole instances (complete measured coverage together with a non-perfect answer). Among the anchor traces, the
  share with complete lexical coverage but at least one author-absent fact is 0.100 [0.043, 0.163] at trace
  level and 8 of 30 instances (0.267 [0.133, 0.400]) at instance level, so the AF flag moves by as much as that
  instance share in the direction **against** the paper's aggregation-gap claims. This is not conservative; it
  is over-counting.
- The 2.95-point fact-level gap and the instance-level share describe the same 40 rows at two units; they are
  not two independent pieces of evidence.

The directions stated here are about the sign of each effect. The magnitudes are anchor estimates, not
corrections to any paper number.

## (a) The 40 author-absent rows

The 40 rows are 10 distinct (trace, fact) pairs × 2 checkpoints (pool, board) × 2 annotators (A+B on 45 anchor
traces, C+D on the other 45); within each
pair the pool and board rows and the two annotators' rows are identical in gold text, best candidate, score and
shared tokens. The table lists the 10 pairs once; each line stands for 4 of the 40 rows.

Rule behaviour: `align_gold_to_transmitted` first asks whether any number in the gold unit occurs in the
transmitted unit. In every one of these 10 pairs none does, so it falls back to token Jaccard, which is > 0
whenever the candidate shares at least one token; `covered = score > 0`, so all 40 are marked covered.

| Instance (stratum) | Trace, fact | Gold unit (first sentence) | Best-scoring candidate | Score | Shared tokens | Driver |
|---|---|---|---:|---|---|---|
| 2hop__142621_225454 (MQ/zero) | Q05 run 3, f2 | No Ordinary Girl is the debut album by Jordan Pruitt, released in the United States on February 6, 2007 by Hollywood Records. | Permission to Fly is the second and final studio album by American singer-songwriter Jordan Pruitt. | 0.167 | album, and, by, is, jordan, the, to | shared entity (jordan, album) |
| 2hop__525581_161450 (MQ/partial) | Q19 run 3, f2 | Golestān Province (Persian: استان گلستان‎, Ostān-e Golestān) is one of the 31 provinces of Iran, … | Aqqala County is a county in Golestan Province in Iran. | 0.103 | in, is, province | shared entity (province) |
| 2hop__363216_787353 (MQ/complete) | Q27 run 3, f2 | Ramstein-Miesenbach is a municipality in the district of Kaiserslautern in Rhineland-Palatinate in Germany, adjacent to the US Ramstein Air Base. | The United States Air Forces in Europe's 1st Combat Communications Squadron is located at Ramstein Air Base, Germany. | 0.172 | air, in, is, ramstein, the | shared entity (ramstein, air) |
| 3hop1__640171_228453_86925 (MQ/zero) | Q02 run 3, f3 | The Sazerac is a local New Orleans variation of a cognac or whiskey cocktail, named for the "Sazerac de Forge et Fils" brand … | Blanton's is a brand of bourbon whiskey produced and marketed by the Sazerac Company. | 0.194 | a, brand, is, of, sazerac, the, whiskey | shared entity (sazerac, whiskey, brand) |
| 3hop1__465684_160545_62931 (MQ/partial) | Q06 run 3, f2 | Bang Bon (Thai: บางบอน, pronounced [bāːŋ bɔ̄ːn]) is one of the 50 districts (khet) of Bangkok, Thailand. | Chao Phraya Bodindecha (1777–1849) was a prominent political and military figure of the early Bangkok Rattanakosin Kingdom. | 0.065 | and, of, the | shared function word only |
| 3hop1__147225_30587_83479 (MQ/partial) | Q08 run 2, f2 | Cuban immigrants in the 1960s brought the Cuban sandwich, medianoche, Cuban espresso, and croquetas, … | The Axis sought to prevent the build-up of Allied supplies and equipment in the British Isles from 1942 onwards. | 0.139 | and, in, of, the, to | shared function word only |
| 3hop1__147225_30587_83479 (MQ/partial) | Q08 run 3, f2 | (same gold unit as the row above) | From 1942 onwards, the Axis sought to prevent the build-up of Allied supplies and equipment in the British Isles in preparation for the invasion of occupied Europe. | 0.122 | and, for, in, of, the, to | shared function word only |
| 2hop__677929_696450 (MQ/partial) | Q22 run 1, f1 | Gagosian is a contemporary art gallery owned and directed by Larry Gagosian. … | The Final Testament of the Holy Bible is a novel written by James Frey, published by Gagosian Gallery in 2011. | 0.200 | a, by, gagosian, gallery, in, is, of, the | shared entity (gagosian, gallery) |
| 2hop__677929_696450 (MQ/partial) | Q22 run 3, f1 | (same gold unit as the row above) | "The Final Testament of the Holy Bible" was published by Gagosian Gallery in 2011. | 0.130 | by, gagosian, gallery, in, of, the | shared entity (gagosian, gallery) |
| 2hop__486314_544665 (MQ/zero) | Q26 run 3, f2 | Chaya Mushka Schneersohn was the daughter of Rabbi Dovber Schneuri, the second Rebbe of the Chabad Hasidic movement, and the wife of Rabbi Menachem Mendel Schneersohn the third Rebbe. | Rabbi Dovber Schneuri was the second Rebbe of the Chabad Hasidic dynasty. | 0.391 | chabad, dovber, hasidic, of, rabbi, rebbe, second, the, was | shared entity (chabad, dovber, hasidic, rabbi, rebbe) |

Breakdown by driver over the 40 rows: **28 shared entity** (7 pairs), **12 shared function word only** (3 pairs),
**0 numeric match**. No absent row shares a number with its gold unit, so every score comes from the Jaccard
fallback; the smallest score is 0.065 (three function words) and the largest is 0.391.

Two of the ten pairs (Q08 f2, Q22 f1) appear at two runs each because the anchor design re-asks some questions
at a second run; the rows differ by the candidate unit the run happened to transmit.

## (b) Author-absent facts among the 504 tied rows

**Count: 0.** The 40 absent rows are all non-tied (each has a unique top-scoring candidate); the 504 tied rows
are 489 author-faithful and 15 author-partial, 0 absent. This matches the expectation from the tie table in
`paper_evaluators_full_v11.md`.

## (c) Direction of the bias on CritRec and OmissionRate

Rates on the 1,356 anchor rows, both checkpoints, weighted by the anchor's stratum weights, instance-cluster
bootstrap 2,000 draws, seed 42:

| Checkpoint | n | Lexical covered rate [95% CI] | Author-present rate [95% CI] | Author-absent rows |
|---|---:|---|---|---:|
| Pool (extraction) | 678 | 1.000 [1.000, 1.000] | 0.9705 [0.9515, 0.9868] | 20 |
| Board (transmission) | 678 | 1.000 [1.000, 1.000] | 0.9705 [0.9515, 0.9868] | 20 |

**Correction applied:** replace the lexical covered indicator (score > 0) with the authors' presence label
(`fidelity != absent`) on each of the 1,356 rows. The corrected rate is therefore the author-present rate,
**0.9705 (95% CI 0.9515–0.9868)**; the correction is **−2.95 points** (difference CI 1.32–4.85 points). The bias
is one-directional on this labelled set: the lexical rule marks every row covered while 2.95% of rows carry no
author-matched fact, so lexical coverage **overstates** author-present evidence. On the 696 MuSiQue rows alone
the gap is **5.75 points** (1 − 0.9425); the pooled 2.95 points include the 660 Silo-Bench rows, none of which
is author-absent.

**Population:** the 30 anchor instances are weighted to their strata, MQ/{zero, partial, complete} and
SB/{zero, partial, complete}. They are a stratified sample of the 80-instance held-out pool: 22 MuSiQue
instances (2 complete, 10 partial, 10 zero; 66 traces) and 8 Silo-Bench instances (3 complete, 3 partial,
2 zero; 24 traces). The pooled rate is the stratum-weighted mix. Split by benchmark: MuSiQue author-present
**0.9425 [0.9000, 0.9735]** over 696 rows, Silo-Bench **1.000 [1.000, 1.000]** over 660 rows. All 40 absent
rows are MuSiQue; no Silo-Bench row is author-absent. The corrected rate describes the anchor sample; it is
not an estimate for the paper's full corpus and is not extrapolated to it.

**Which paper tables this can and cannot inform.** The anchor has both benchmarks, so:

- **MuSiQue:** all 40 absent rows are MuSiQue, so the correction and its direction apply to the MuSiQue
  CritRec / OmissionRate entries and to the MuSiQue candidate-aggregation-failure (AF) rate in
  `tab_audit_combined.tex`, because AF requires complete measured coverage and any absent-but-covered fact
  inflates the AF denominator.
- **Silo-Bench:** the 8 anchor Silo-Bench instances (24 traces, 660 rows) carry no author-absent row, so
  nothing here corrects a Silo-Bench figure. The zero is measured on 24 traces, not a claim about the SB
  corpus, and no SB point estimate follows.
- Neither side supplies a corpus point estimate: the anchor is 30 instances of the 80.

**Direction on the two rates.** CritRec = |S\* ∩ board| / |S\*| counts a fact as present when the lexical rule
marks it covered. If 2.95% of facts are absent but counted covered, CritRec is **overstated** by up to that
amount and OmissionRate = 1 − CritRec is **understated** by the same amount, on this population.

**Are the paper's loss figures conservative?** In direction, yes on the anchor: since measured coverage exceeds
author-present coverage, the measured omission losses are lower bounds — the true losses are at least as large
as reported. This does not extend to the AF count, which is over-counted (see Directions). Three
qualifications: (i) this rests on the 30 anchor instances (22 MuSiQue, 8 Silo-Bench), not the paper's corpus; (ii) the magnitude 2.95 points
is an anchor estimate, not a correction to any paper number; and (iii) the conclusion is directional, not a
restatement of any table.

## (c2) Instance-level rate

The paper's AF flag is defined on whole instances: complete measured coverage together with a non-perfect
answer. The fact-level 2.95-point gap can move that flag by much more, because one absent fact makes an
instance "not complete" under author labels.

| Unit | Complete lexical coverage | With ≥ 1 author-absent fact | Share [95% CI] |
|---|---:|---:|---|
| Anchor traces (instance × model) | 90 of 90 | 10 | 0.100 [0.043, 0.163], weighted; 10/90 = 0.111 unweighted |
| Anchor instances | 30 of 30 | 8 | 8/30 = 0.267 [0.133, 0.400] |

The 10 affected traces come from **8 instances** (the clusters that drive the rate):
`2hop__142621_225454`, `2hop__363216_787353`, `2hop__486314_544665`, `2hop__525581_161450`,
`2hop__677929_696450`, `3hop1__147225_30587_83479`, `3hop1__465684_160545_62931`,
`3hop1__640171_228453_86925`. Two instances contribute two affected traces each (Q08, Q22).

Bootstrap: within-stratum instance-cluster, 2,000 draws, seed 42, sorted strata; same weights as the fact-level
rates. The trace and instance shares are the same 40 rows counted at a coarser unit; neither is independent
evidence about the population, and both describe the 30-instance anchor only.

## (d) Paper claims at risk, and claims untouched

At risk (locations from `claims_impact_template.md`, paper files unedited):

| Claim | Location |
|---|---|
| "benchmark supports and lexical alignment enable systematic tracking" | `0-abstract.tex:4` |
| "complete measured coverage flags candidate aggregation failures rather than proving semantic sufficiency" | `1-introduction.tex:37` |
| AggFail definition and the "cannot verify semantic sufficiency from lexical matching" caveat | `3-methodology.tex:93` |
| "Lexical coverage cannot certify semantic sufficiency" | `3-methodology.tex:97` |
| "Coverage is sensitive to lexical thresholds … does not establish intact transmission" | `4-experiments.tex:31` |
| "complete lexical coverage for relay in 8 of 9 models" | `items/tables/appendix/tab_claim_evidence.tex:20` |
| "MuSiQue often yields incorrect answers despite complete measured coverage" | `0-abstract.tex:5`; `1-introduction.tex:45`; `4-experiments.tex:31`, `4-experiments.tex:33` |
| AF column / "percentage of all instances with a non-perfect answer and complete measured CR" | `items/tables/tab_audit_combined.tex:8` |
| "non-perfect despite complete measured critical-fact coverage" on the E4 cohort | `4-experiments.tex:76` |

These are the claims that use "complete measured coverage": under the rule, the 40 author-absent rows count as
covered, and 8 of the 30 anchor instances lose their "complete coverage" status when the author labels are
applied.

Untouched: the Silo-Bench extraction-vs-selection comparison (`4-experiments.tex:28`, `4-experiments.tex:33`,
abstract line 5's Silo-Bench clause), the strict-distortion percentages (`app_main.tex:955`,
`3-methodology.tex:78`), the aggregation-placement results (`4-experiments.tex:83`,
`tab_aggregation_placement.tex:12–14`), and the E2 baseline/judge claims. The anchor does contain Silo-Bench
traces, but none carries an author-absent row, so the correction leaves the SB figures as they are; the anchor
has no distortion label.

## Limits

- 40 absent rows are 10 distinct facts in 8 instances (6 traces; Q08 and Q22 appear at two runs each), so the 2.95-point estimate is
  driven by a small number of clusters.
- The paired annotators A/B share the same labels by construction of the returned files; the CI treats
  annotators as repeated measures within instance, not as independent samples.
- The 40 absent rows are all MuSiQue; the Silo-Bench part of the anchor (24 traces, 660 rows) has none. The
  Silo-Bench side is therefore a measured zero on 24 traces, not a correction, and nothing here speaks to
  distortion labels.

## Update 2026-11-12: the 20-instance Silo-Bench anchor

The authors returned a separate 20-instance / 60-trace Silo-Bench packet (`SB_anchor`, 120 rows, two labels
per trace). The lexical rule was applied to those traces with `align_gold_to_transmitted`, unchanged.
Source: `rebuttal/results/batch1/SB_anchor_20/analysis.json`; descriptive only, 2,000-draw instance-cluster
bootstrap, seed 42.

| Check against the authors' trace call | Agreement [95% CI] | κ [95% CI] |
|---|---|---|
| Lexical rule (all facts covered → correct) | **0.383 [0.217, 0.550]** | **0.016 [−0.092, 0.151]** |
| Reference judge (Gemini 3.6 Flash) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| Frozen matcher (`semantic-dev-v2`) | 1.000 [1.000, 1.000] (94 of 120 rows; 13 traces without matcher output excluded) | 1.000 [1.000, 1.000] |
| Author–author (two labels per trace) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |

Fact coverage by the rule is 102 of 120 author-listed facts (0.850), so it is not merely lenient here: it
fails to mark facts covered that the authors mark present. The 8 instances overlapping the E1 anchor agree
between the new and old author labels in 0.958 of 24 traces (κ 0.833), so this is the same underlying data,
not a different label standard.

**Consequence for the paper.** The earlier reading that Silo-Bench figures are "untouched" by the lexical
rule does not survive this sample. On Silo-Bench the rule's agreement with the authors is near chance, while
the judge and matcher reproduce the authors exactly on this sample. Any Silo-Bench statement that rests on
`align_gold_to_transmitted` (coverage, CritRec, AF, extraction-vs-selection percentages) should be re-read
against the author labels, not carried as a measured zero.

### Disclosure text (about 120 words)

The lexical coverage rule used in the paper over-counts complete coverage. On the 30-instance author-labelled
anchor it marks all 90 traces and all 678 fact rows covered, while the authors mark 10 traces and 40 rows
absent; aggregation failure is therefore 0.783 (95% CI 0.678–0.881) by the rule against 0.683
(0.575–0.788) by the authors, a 9.97-point over-count driven by eight MuSiQue instances. On a separate
20-instance Silo-Bench anchor the rule agrees with the authors on only 0.383 of traces (κ 0.016), with 85%
fact coverage. Loss figures from the rule are lower bounds, aggregation-failure figures are upper bounds, and
Silo-Bench claims should not rest on the rule alone.

### Revisions list (Silo-Bench additions in bold)

| Paper text | File:line | Change |
|---|---|---|
| "complete lexical coverage for relay in 8 of 9 models" | `items/tables/appendix/tab_claim_evidence.tex:20` | **Lexical claim: keep, but state the Silo-Bench anchor agreement (0.383; κ 0.016) and 0.850 fact coverage beside it.** |
| AggFail definition and "cannot verify semantic sufficiency" caveat | `3-methodology.tex:93` | Keep the caveat; add the Silo-Bench number. |
| "Lexical coverage cannot certify semantic sufficiency" | `3-methodology.tex:97` | Unchanged; now supported on Silo-Bench as well. |
| AF column / "complete measured CR" | `items/tables/tab_audit_combined.tex:8` | **MuSiQue: −9.97 points (anchor). Silo-Bench: rule not usable at this agreement.** |
| "non-perfect despite complete measured critical-fact coverage" (E4 cohort) | `4-experiments.tex:76` | MuSiQue-only correction; Silo-Bench cells read from author labels. |
| "MuSiQue often yields incorrect answers despite complete measured coverage" | `0-abstract.tex:5`; `1-introduction.tex:45`; `4-experiments.tex:31`, `4-experiments.tex:33` | Unchanged for MuSiQue; do not extend to Silo-Bench. |
| Extraction-vs-selection comparison | **`4-experiments.tex:28`, `4-experiments.tex:33`** | **No longer "untouched": re-read against author labels on Silo-Bench.** |
| Strict-distortion percentages | `app_main.tex:955`, `3-methodology.tex:78` | Not measured by either anchor; unchanged. |
| Aggregation-placement results | `4-experiments.tex:83`, `tab_aggregation_placement.tex:12–14` | Not measured by either anchor; unchanged. |