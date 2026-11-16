# Diagnosis of the four repair experiments

2026-11-12. No model calls, no reruns, no paper edits. Every number below is
recomputed from the frozen action manifests and raw provider responses with the
project's own scorer (`answer_f1`, `silobench_exact_match`). The per-case sheets
with quoted board text are in [`case_sheets.md`](case_sheets.md); the
machine-readable records are in [`cases.json`](cases.json) and the reviewed
labels in [`verdicts.json`](verdicts.json). The explicit (a)-(f) tag index is
[`tags.md`](tags.md); the R4 rebuild check is [`R4_rebuild.md`](R4_rebuild.md);
the corrected scores are [`corrected_scores.md`](corrected_scores.md); the
R2/R6 gate pre-flight is [`gates_preflight.md`](gates_preflight.md).
Regenerate the sheets with `./run.sh python -m scripts.build_e4_diagnosis`
(they keep the archived scorer, punctuation deleted).

## 1. Headline

The three adverse results are not evidence against the audit method. They are
mostly broken cases, a wrong scoring rule, and a swap step that never inserted
the distortion it was meant to insert.

| Experiment | Cases | What the repair arm did | Honest reading |
| --- | --- | --- | --- |
| Missing-fact repair | 17 | 1/17 carried the target fact at recall ≥ 0.8 | Not a test of the method: 9 cases have a wrong fact, a wrong gold, or a multi-pointer chain; 2 of the 9 can be rebuilt from the source |
| Direct insertion | 17 | 17/17 carried the exact fact, 1/17 reached the gold | The one clean case works; six of the nine refusals insert a fact the gold does not need (two of those six are rebuilt from the source below), three refuse with the needed sentence already on the board |
| Distortion repair | 25 | 0/25 swaps contained the distorted fact | Invalid manipulation; the experiment cannot be read |
| Selection | 1 of 219 | The single case is a distorted carrier, not a dropped unit | The cohort is empty by construction |

## 2. Missing-fact repair (17 traces: gemma 9, gpt-4o-mini 4, qwen 4)

Cause counts for the repaired arm (R-ext), with the first failure in the chain:

| Class | n | Cases |
| --- | --- | --- |
| (c) scorer rejected a right answer | 2 | `3hop1__132795` gemma (F1 0.370); `3hop1__465684` qwen (F1 0.857) |
| (b) present but unused | 3 | `3hop1__147225` gemma and gpt: the answer sentence was already on the board and the model still refused; `2hop__511454` gpt: the 918 sentence is on the board and the model refused |
| (e) delivery not as intended | 2 | `2hop__280583` gemma; `2hop__142621` gemma: re-extraction returned a refusal sentence |
| (d) model already knew it | 1 | `III-29_n5` gemma: both control arms hit exact match with the gold dict |
| (f) data / case design | 9 | `4hop1__814349` (both models), `3hop2__132957`, `2hop__491195`, `3hop2__304722`, `2hop__28287`, `4hop1__802394`, `II-18_n10`, `II-18_n5` |

The delivery failure is mechanical: R-ext re-extracts units from the target
agent's source context, but 16 of 17 extractions carry the fact at recall < 0.8,
and five return a literal refusal ("No evidence units were found…"). The exact
fact reaches the board in 17/17 insertion runs, which isolates the failure to
the re-extraction step, not to the model's willingness to use evidence.

The nine (f) cases are not close calls:

- wrong relation: `2hop__491195` asks for the mother, the fact says "Britta
  Holmberg is the wife of Stig Olin"; gold is their daughter Lena Olin.
- wrong event: `3hop2__304722` uses a 1963 League Cup result for an
  FA Cup question whose gold is 1 December 2010; the 2010 match is against
  Aston Villa, and the 1894-95 winner that makes Villa the target is also absent.
- wrong year: `3hop2__132957` inserts "The 1973 oil crisis occurred in 1973";
  the source puts the plant openings "a decade after 1973", not in 1981.
- malformed gold: `4hop1__814349` asks for a county bordering Cuyahoga County
  and gives "Cabarrus County", a North Carolina county that cannot border it.
- multi-pointer tasks: `II-18_n5`/`n10` insert one pointer into a 40/80-node
  chain; the chain cannot close.
- fixable fact choice: `2hop__28287` and `4hop1__802394` name the wrong fact
  (the character is SpongeBob / the race was revived), but a source sentence
  gives the needed fact (Mr. Lawrence voices Plankton / Andretti's final
  victory at Phoenix). These two are rebuilt, not dropped.

## 3. Direct insertion (same 17 traces)

| Class | n | Cases |
| --- | --- | --- |
| correct | 1 | `2hop__280583` gemma, "Will Arnett", F1 1.000 |
| (c) scorer rejected a right answer | 2 | `3hop1__147225` gemma (F1 0.480, gold recall 1.0); `3hop1__465684` qwen (F1 0.375) |
| (b) present but unused | 4 | `3hop1__132795`; `2hop__142621`; `3hop1__147225` gpt; `2hop__511454` gpt |
| (d) model already knew it | 1 | `III-29_n5` |
| (f) data / case design | 9 | same nine as above |

Two facts matter here. First, the exact fact reaches the board in every case
(`ins_fact.contained = 17/17`), so the repair mechanism is sound. Second, the
answer still refuses in 9 of 17 cases: in 6 the inserted fact is not what the
gold needs (2 of those 6 are rebuildable from the source), and in 3
(`2hop__142621`, `3hop1__147225` gpt, `2hop__511454` gpt) the needed sentence
was already on the board and the model refused anyway (class b). The one
genuinely missing fact that the model does
not already have (`2hop__280583`) flips from refusal to the exact gold.

## 4. Distortion repair (25)

All 25 are class (e): the swap text did not contain the distorted fact.

| Swap content | n | Recall against the distorted fact |
| --- | --- | --- |
| The question itself ("Question: …") | 14 | < 0.35 |
| A document header (`[Document: 1985 FA Cup Final]`) | 1 | 0.33 |
| An unrelated or truncated fragment | 10 | < 0.65 |

- 18/25 have swap recall < 0.3; 25/25 are below 0.8.
- 22/25 of the units the swap replaces are themselves below 0.5 recall against
  the fact the carrier assigns to them, so the "before" text is also suspect.
- R-dist refuses in 15/25 and gives the same answer as Rerun in 17/25; only
  3/25 score above 0 (max F1 0.25).
- 10/25 original boards already contain a refusal or error unit.
- The manifest records `swap_preserves_fact = "yes"` for 2 cases whose swap is
  literally the question text; the run script asserts `author_checked` but never
  checks the swap against the fact. The gate is a flag, not a check.
- One scorer bug: in `3hop1__640171` the donor control answered "fleur-de-lis",
  which is the gold "fleur - de-lis" up to punctuation; `normalize()` deletes
  the hyphen without inserting a space and scores it 0.

**Labeller-generated swaps (2026-11-12).** The 25 swaps were regenerated by
the swap labeller (`swap-v1`, Claude Haiku 5.5, same model and prompt family as
v2) instead of hand-authored spans. Each candidate is a verbatim source span,
checked by `distortion_gate` and `delivery_reasons`. **1 of 25 passes**:
`4hop3__152056_698586_91248_54362` / gpt-4o-mini, where the board unit
attributes the burning of Atlanta to Sherman but the source says Hood; the
span "On September 1, 1864, Confederate Gen. John Bell Hood evacuated
Atlanta..." has swap recall 0.938 and replaced-unit recall 0.625. Of the other
24, 20 fail the distortion gate (the replaced board unit is not a distorted
near-copy of the fact, or the returned span misses it), 9 of those also show
delivery recall 0.44-0.71 on a paraphrased fact, and 4 returned no span. Cost
$0.005423.
Record: `rebuttal/pilots/20261112_swap_labeller/swap_report.md`; the accepted
swap is in `swaps.jsonl` beside the originals, not written into any frozen
manifest.

**Stage 2 swaps (2026-11-12).** The same labeller ran over the 176 Stage 2
distortion cases: **6 accepted, 170 rejected, $0.038218**. The spot-check of the
6 shows **5 are the same false positive**: the Piedmont winter-temperature unit
(`3hop1__131110`, `3hop1__129675`, gemma/gpt/qwen), whose board text states the
same temperatures as the source; the matcher marks it distorted, but the swap
replaces a faithful unit and cannot change the answer. Only the Warner unit
("Warner Bros. Records is a parent company of Warner Music Group", relation
reversed against the fact) is a genuine distortion. So of 7 gate-passing swaps
from 201 cases, **2 are genuine distortions** (the Warner inversion and the
earlier Hood/Sherman attribution).

Cause, from the same gate values: 153 of the 176 distorted units are not
near-copies at all (refusals, headers, unrelated text), so no swap can repair
them; only 23 have replaced-unit recall >= 0.5. Among those 23, 17 fail only the
0.8 fact-recall on the labeller's span, at 0.50-0.79 — genuine contradictions
such as Jack Clay teaching at Southern Methodist 1966-86 (fact: University of
Miami 1957-61), Aeson as father of Promachus (fact: of Jason), and "Nanjing is
not the capital of Yangzhou" — because the matcher's fact text is a paraphrase
and the span must be verbatim source. The 0.8 recall gate therefore measures
paraphrase distance, not distortion.
Record: `rebuttal/pilots/20261112_swap_labeller/stage2/swap_report.md`.

## 5. Why only one selection case survived

`E4_cohort_frozen.json` has 232 cases, 13 unscored, 219 scored. The matcher
labels a trace "selection omission" only when a fact has an extraction carrier
and no board carrier.

- 1 of 219 scored traces has any such fact; 0 of 219 has a *faithful* one.
- The single hit, `3hop1__41865`, has `extraction:a0:u2` marked **distorted**,
  and that unit is about Erich Raeder, not the fact it is attached to
  ("Under Caesar, an invasion fleet was assembled in the English Channel").
- R-sel appended `extraction:a0:u0` and `a0:u1`, which repeat `board:a0:u0` and
  `a0:u1` verbatim, so the board gained no evidence and the answer stayed "The
  British".

The cohort is empty because in this cohort every faithfully extracted support
fact also appears on the board (0/219 exceptions). The one hit is a carrier-label
error, not a selection event. Report selection as 0/219 and drop it; do not
present the singleton as a result.

## 6. Fix rules to apply before any rerun

Every rule is a setup check, not a rerun. The first five cost no API calls.

| Rule | Cause | What changes | Calls | Est. cost |
| --- | --- | --- | --- | --- |
| R1 scoring | SQuAD normalisation and wrong metric | Score Silo-Bench with `silobench_exact_match`, never `answer_f1`. Fix `normalize()` to map punctuation to a space ("fleur-de-lis" → "fleur de lis"). Re-score archived runs into a corrected copy; keep originals. | 0 | $0 |
| R2 delivery gate | R-ext returned refusals / irrelevant units | Before an answer call, require the repair text to contain the target fact (recall ≥ 0.8). Reject question text, `[Document:` headers, refusal sentences, data-list fragments. If extraction fails, record a delivery failure and skip the answer call. | 0 | $0 (saves calls) |
| R3 case design | Multi-pointer and multi-fact tasks | Require exactly one non-present support fact and a unique pool unit. Exclude Silo-Bench list-ranking and count tasks (`II-18_n5/n10`, `I-02_n5/n10`) until a whole-chain repair is defined. | 0 | $0 |
| R4 data | Wrong facts and malformed gold | Before a case enters a cohort: the board alone does not reach the gold, the target fact is in the support set, the board plus that fact entails the gold, and the fact is not a tautology. Rebuild or drop the nine (f) cases. | 0 | $0 |
| R5 model control | "already knew it" was invisible | Add a board-only control arm (original board, no repair) to every case; compare the repair arm against it, not against Rerun alone. | 17 per 17-case pilot | ≈ $0.01 |
| R6 matcher gate | distorted carrier labelled selection; unchecked swaps | Selection requires a *faithful* extraction carrier with no board carrier. Distortion requires the swap text to carry the distorted fact (recall ≥ 0.8) and the replaced unit to match that fact (recall ≥ 0.5); reject otherwise. | 0 | $0 |

Status of the rules:

- **R1 implemented.** `normalize()` now maps punctuation to a space
  (`src/eval/evaluate.py`). The archived sheets keep the old scorer so their
  numbers do not move; `corrected_scores.md` re-scores all 206 arms and lists
  the 10 that changed. The `fleur-de-lis` donor in `3hop1__640171` moves from
  0 to 1.000.
- **R2, R3, R4, R6 implemented** as text checks in
  `src/audit/e4_fix_gates.py`, with no model calls. `gates_preflight.md`
  applies them to the frozen artifacts: R2 rejects 16/17 R-ext repair texts
  and 0/17 R-ins texts; R6 finds 0 faithful selection carriers in 227 matcher
  records and 0/25 distortion swaps that carry the distorted fact. R4 now
  also requires that the board alone not reach the gold (otherwise the case
  is present-but-unused) and that the repair fact link to the question or the
  board rather than to itself. The R4 output is the list in section 6b.
- R2 was applied before the answer call in the missing-fact pilot (section 7f);
  the main rerun runner still has to call it. R5 is applied in that pilot: the
  board-only control was run after the delivery check, and all four controls
  refuse, so the cohort does not already know the gold.

After R4, 4 of the 17 extraction/insertion traces are clean single-fact repair
cases: `2hop__280583` and `2hop__142621` on their frozen facts, and
`2hop__28287` and `4hop1__802394` on the rebuilt facts above. The other 13
measure scoring, board-use, or malformed data, not missing-fact delivery.

| Pilot | Arms | Calls | Est. cost |
| --- | --- | --- | --- |
| Missing-fact repair, 4 clean cases | Rerun, R-ext, board-only control | 12 | ≈ $0.005 |
| Direct insertion, 4 clean cases | Rerun, R-ins, volume-matched control | 12 | ≈ $0.005 |
| Distortion, 25 rebuilt swaps | Rerun, R-dist, V-dist | 75 | ≈ $0.03 |

Each is under the $5 per-pilot cap; together they are ≈ $0.04 of the $100
phase budget. The 25 swaps must be re-authored before the third pilot.

## 6b. R4 rebuild of the ten traces originally tagged (f): list for review

Each trace was retried under R3 (exactly one absent support fact) and R4
(the board alone does not reach the gold; the target fact is in the support
set; the board plus that fact reaches the gold; no tautology), trying every
missing fact in that case and every gold-bearing sentence in its source
contexts. No single frozen missing fact reaches the gold in any of the ten.
The source contexts change the answer for two traces: a faithful sentence
exists and one corrected fact closes the chain. `2hop__511454` is not a
missing-fact case at all: its 918 sentence is already on the board.

| case | model | frozen fact | source sentence | decision |
| --- | --- | --- | --- | --- |
| `4hop1__814349` | gemma, gpt | none | Cabarrus County line, disconnected from Cuyahoga | drop: malformed gold; a correct Lake County answer needs 2 facts |
| `3hop2__132957` | gemma | none | "a decade after 1973 ... 1981 voluntary export restraints" | drop: 1981 dates the restraints, not the plant opening |
| `2hop__491195` | gemma | none | "father of actress Lena Olin" | drop: gold is the daughter; question asks the mother |
| `3hop2__304722` | gemma | none | 1 December 2010, Birmingham 2-1 Aston Villa | drop (R3): the 1894-95 winner fact is also absent |
| `2hop__28287` | gpt | none | "Mr. Lawrence as the voice of Plankton" | **keep**: rebuild with "Mr. Lawrence is the voice of Plankton." |
| `4hop1__802394` | qwen | none | "final career victory for ... Mario Andretti (1993)" at Phoenix | **keep**: rebuild with "Mario Andretti won the Indy car race in Phoenix in 1993." |
| `II-18_n10` | qwen | none | none | drop (R3): 56 pointers absent from an 80-node ranking |
| `II-18_n5` | qwen | none | none | drop (R3): 25 pointers absent from a 40-node ranking |
| `2hop__511454` | gpt | none (board has gold) | "Æthelflæd died in 918 ..." is board:a0:u1 | reclassify (b), exclude from the repair cohort |

The two rebuilt facts pass both the lexical gate and a semantic reading: the
first links Plankton (the name the question reaches through "annelid larvae
live like plankton") to its voice actor; the second links Phoenix (the city
the question reaches through Mingus) to the race winner. The five dropped
traces and the two multi-pointer traces have no single faithful fact that
closes the chain. The 511454 refusal happened with the needed sentence
already on the board, so it measures use, not delivery.

One more case fails R4 outside the nine: `3hop1__147225` gpt-4o-mini. The gold
phrase is not stated by any support fact; the board only paraphrases it
("stemming the flow ... to prevent Allied support"). The gemma trace of the
same instance passes, because its board carries the exact sentence. Approved
and applied: drop the gpt trace as an R4 failure; its verdict stays (b), and
the gold is not relabelled. `III-29_n5` is also outside the repair cohort:
three support facts are absent (R3) and both controls answer the gold exactly,
so it is class (d); it is recorded as excluded.

These decisions were approved and are applied in the diagnosis record:
7 traces dropped, 2 rebuilt, `2hop__511454` reclassified and excluded,
`3hop1__147225` gpt dropped as an R4 failure, `III-29_n5` excluded (R3, class
d), and 3 traces excluded because the board already had the gold. No frozen
cohort or insertion manifest was changed. `R4_rebuild.md` gives the per-case
signals, source quotes, the all-case table, and the resulting 4-trace clean
cohort.

## 7. Stronger-model labeller (v1 pilot failed; v2 re-pilot and full run passed)

**Model.** Claude Haiku 5.5, $0.10 / $0.50 per million input / output tokens
(prompts under 100 K tokens). The direct Anthropic key is absent in this
environment, so the pilot used `anthropic/claude-haiku-5.5` through the
OpenRouter key in `.env`, at the same price. The repo's direct adapter
(`utility/apis/claude_api.py`) still defaults to `claude-haiku-4-5-20251001`.
DeepSeek V4 Pro is not configured in the repo (only
`deepseek/deepseek-v4-flash` through OpenRouter); it stays a backup.

**Task.** One call per trace. Input: question, gold, extraction pool, board,
final answer. Output: binary DEFECT / CORRECT plus the carrier JSON (which
support fact is missing at which checkpoint), matching the author schema.

**Validation set.** 150 author-labelled traces: 90 from the 30-instance E1
anchor and 60 from the 20-instance Silo-Bench anchor, two author labels each,
so 300 labeller–author comparisons over 50 instance clusters. Report raw
agreement and Cohen's κ with 95% CIs (cluster bootstrap, 2,000 draws, seed 42).

**Go / no-go.** Lower CI bound ≥ 0.80 agreement and κ ≥ 0.60. Below that the
label set is not used.

**Disagreements.** List every trace where the labeller differs from either
author, with both labels and the quoted board unit that decided it. No aggregate
only.

**Spot-check before use.** Read 12 traces against the real question, board and
answer (8 DEFECT, 4 CORRECT); a label set that fails the spot check is discarded
regardless of agreement.

**Pilot run.** `scripts/pilot_llm_labeller.py --build` wrote the 150-trace set
(90 E1 + 60 Silo-Bench, two author labels each, 50 clusters) to
`rebuttal/pilots/20261112_labeller/validation_150.jsonl`, and a seeded 20-trace
pilot (12 E1 + 8 SB) to `pilot_20.jsonl`. Measured size: 10,282 characters
mean, 18,034 p90; ≈ 2,571 tokens mean, 4,509 p90.

The pilot ran through OpenRouter after three attempts (reasoning disabled,
then a "do not solve or recompute" instruction): all 20 traces parsed, total
spend **$0.048739**, under the $0.25 cap. Raw agreement **0.850** (95% CI
0.650-1.000), Cohen's κ **0.634** (95% CI 0.211-1.000). The three
disagreements are all labeller CORRECT against two author DEFECTs: rounded
scores in Q03 run 3, a missing `variance` field in Q09 run 3, and "Ramstein
Air Base" accepted for the gold "Ramstein-Miesenbach" in Q27 run 2. All 20
traces were checked against the real gold and answer (exact token-F1); four
have F1 < 1.0 while the labeller says CORRECT. On the fourth (Q16, "Rio
Linda, Sacramento, CA") both authors also say correct, so it is a
scorer-strictness case; the other three are the disagreements. The labeller is
too lenient on rounded, partial and adjacent answers.

**Go / no-go failed.** The planned lower bounds (0.80 agreement, 0.60 κ) are
not met. The v1 label set is not used. A re-pilot after the prompt changes in
`pilot_report.md` (exact comparison via `normalize()`, all structured fields
required, the three cases as DEFECT examples) must be reviewed first.

**v2 prompt and re-pilot.** The revised prompt is frozen at
`rebuttal/pilots/20261112_labeller/labeller_prompt_v2.json`. Two hashes are
recorded, and they mean different things: the **file** sha256
`7f9e281669ca06e00eac86405312bb54c05cc69834eb51a732e48a669e8268c6` is the
frozen reference; the **system text** sha256
`585d0d453ffceffe2372169ae7d312a2fbcab9d5854e241e96244f33dfdb8e6e` is the
value recorded in every call log. Both are in
`labeller_prompt_v2.manifest.json`, and the runner checks both. The re-pilot
on 20 disjoint dev traces parsed 20/20 (one trace emitted two objects and used
the declared last-object rule), cost $0.011987, and scored agreement **0.950**
(95% CI 0.850-1.000) and κ **0.900** (95% CI 0.667-1.000). One disagreement:
gold `Nicholas Bacon` vs answer `Sir Nicholas Bacon`, where the exact rule is
stricter than both authors. Canonical record:
`rebuttal/diagnosis/repilot_v2_report.md`.

**Full 150-trace run (2026-11-12).** All 150 parsed; 4 traces hit the 800-token
output limit on the first call and were retried at 2,000 tokens. Spend
**$0.114821** under the $0.25 cap. Raw agreement **0.953** (286 of 300; 95% CI
0.913-0.987), Cohen's κ **0.878** (95% CI 0.760-0.965). Seven traces disagree,
listed with gold, answer, score and rationale in
`rebuttal/pilots/20261112_labeller_v2_full/full_report.md`. The lower CI bounds
clear the gate. Twenty of the 150 are the v1 pilot traces used to design v2;
excluding them, the held-out 130 score agreement 0.954 (95% CI 0.907-0.992)
and kappa 0.881 (95% CI 0.756-0.976), with 6 of the 7 disagreements.

**Caveat.** The 150-trace set is also author-unanimous: both authors give the
same label on every trace, so neither the dev re-pilot nor the full run tests
disagreement resolution. Of the 7 disagreements, 4 are the labeller returning
CORRECT where the authors say DEFECT. Two are evidence-flow-faithful cases
that the prompt treats as CORRECT despite a computation-only wrong answer; two
(Q18 run 1, `GDR` vs `East Germany`, and Q19 run 1, `country` vs `Iran`) state
the strict rule gives DEFECT and return CORRECT anyway. The two explicit
contradictions are genuine prompt-following errors. The pass is against
consensus labels, not against author splits.

**Cost.** Mean trace is ≈ 2,571 tokens (p90 4,509); budget 3,000 input + 400
output. The 150-call estimate was ≈ $0.07 (cap $0.25); the measured full run
was **$0.114821**, including four 2,000-token retries. Attempts 1-3 cost
$0.0487 in total because the two failed attempts still spent. At Haiku 4.5
rates the same run is ≈ $0.68.

## 7b. Case-pool expansion for a 95% CI (plan; Stage 1 and Stage 2 run)

The full sizing is in [`expansion_plan.md`](expansion_plan.md). Stage 1 ran on
2026-11-12. Stage 2 was approved at 800 instances, ran on 2026-11-12 (2,400
traces at a $5 cap; PID 72926, log
`rebuttal/pilots/20261112_expansion_stage2/stage2.log`), and finished at
**$4.2688**. Its report is `stage2_report.md` in that directory. The measured
per-experiment expectations are in
[`../pilots/20261112_expansion_stage1/stage2_expected.md`](../pilots/20261112_expansion_stage1/stage2_expected.md).

- **Supply.** MuSiQue dev has 2,417 answerable instances; 100 were sampled and
  60 entered the cohort, leaving 2,317 uncohort dev instances plus 40 sampled
  but unused (2,357 instances, 7,071 traces at three models). MuSiQue test has
  no gold in the repository and cannot be scored. Every Silo-Bench benchmark
  output is a structured list/count dict, which R3 excludes, so it supplies no
  single-fact repair cases.
- **Yield.** The original 172 MQ traces give 14 extraction-omission candidates
  (8.1%) and 4 clean cases after R4 (23.5%; 11.8% if only frozen facts count).
- **Size.** At the central yield, 100 clean cases need 5,370 screened traces
  (1,790 instances), about $16.7 at $0.0031 per trace (base relay $0.0013 +
  matcher $0.0018). The full pool gives about 134 clean cases for $21.9 in
  screening ($22.2 with the repair and distortion arms), or about 68 under
  the conservative yield.
- **Stages.** The 40 sampled dev IDs outside the cohort can be matcher-screened
  first for $0.22 because their base traces exist. A 600-trace screening pilot
  (200 new instances) costs $1.86 and is inside the $5 per-pilot cap; Stage 2 adds
  2,400 traces ($7.44); Stage 3 reaches 100 clean cases. Stop if the candidate
  rate falls below 6% or clean yield below 10%.
- **Arms.** Missing-fact repair and direct insertion share the clean cases:
  300 calls each, about $0.09. Distortion needs 100 re-authored swaps (300
  calls, $0.08, plus about 25 hours of authoring). Selection is not sized:
  0/219 faithful carriers means the carrier definition must be fixed first;
  a 100-trace revised-prompt pilot is about $0.09.

The plan itself creates no manifest and runs no call. Stage 1 was approved
separately on 2026-11-12 and has now run; its manifest and result are below.
The frozen cohort, insertion plan and pre-registrations are unchanged.

### Stage 1 result (run 2026-11-12)

200 unused dev instances x 3 models = 600 traces; manifest sha256
`31c5916b...e639`. Matcher scored 597 and failed 3 on transport errors
(2 connection, 1 timeout), not schema. It found 366 wrong answers, 43
extraction-omission candidates (7.2%), and 11 R3/R4 clean cases (25.6% of
candidates; 1.84% per screened trace, against the plan's 1.90% central
estimate). Both stop thresholds pass. Stage 2 was then approved at 800
instances and has now run. Cost $1.0471 against the $5 per-pilot cap ($0.5894
relay, $0.4577 matcher). Detail:
`rebuttal/pilots/20261112_expansion_stage1/stage1_report.md`.

### Stage 2 result (run 2026-11-12)

800 unused instances x 3 models; manifest sha256 `5663d338...87c7d`; 2,400/2,400
matcher records ok, no transport failures; $4.2688 (relay $2.3625, matcher
$1.9063). 1,524 wrong answers, 216 extraction-omission candidates (9.0%), **69
R3/R4 clean traces / 59 unique instances**, 176 distortion diagnoses / 150
unique.

| experiment | Stage 2 | Stage 1 + 2 | target 30 |
| --- | ---: | ---: | --- |
| Extraction | 69 traces / 59 unique | 80 / 69 | met |
| Direct insertion (same cohort) | 69 / 59 | 80 / 69 | met |
| Distortion, diagnosed | 176 / 150 | 214 / 184 | met |
| Distortion, gate-passing swaps | 6 swaps, 1 genuine | 7 / 2 genuine | **not met** |

Per model (800 traces each): gemma 44 clean / 101 distortion; gpt-4o-mini 16 /
40; qwen 9 / 35. Qwen's candidate rate is the lowest (4.1%) but it still
contributes 9 clean traces and 35 distortion diagnoses, so the Stage 2 yields
do not support dropping it.

## 7c. Main-table re-score pilot (v2 labeller is not an answer-accuracy scorer)

Rule frozen before any call:
`rebuttal/pilots/20261112_rescore/SCORING_RULE.md`. Pilot scope: Qwen-235B, both
benchmarks, the four protocols with a trace package (3 relays + summary
exchange), 608 traces. The frozen v2 prompt scored 607/608 traces for
**$0.400727** against a $2 cap; every call is in
`rebuttal/pilots/20261112_rescore/calls.jsonl`.

Side by side, pooled over the four protocols (paper cell / lexical exact rule /
v2 CORRECT rate):

| benchmark | paper cell | lexical | v2 CORRECT | agreement | kappa [95% CI] |
| --- | ---: | ---: | ---: | ---: | --- |
| SB | 16.3% EM | 16.3% | 19.7% | 0.966 | 0.886 [0.745, 0.966] |
| MQ | 41.8 mean F1 | 23.8% exact | 44.1% | 0.792 | 0.557 [0.443, 0.661] |

The v2 label is **not** an answer-accuracy score on this population. The
prompt defines DEFECT as "answer wrong and a critical fact absent or distorted
at a checkpoint", so a wrong answer with faithful evidence (a computation or
aggregation error) falls outside both labels and the model returns CORRECT.
Of the 89 traces where the labeller says CORRECT and the lexical rule says
wrong, 46 are answers containing the gold entity plus extra words (which the
prompt's own normalization rule calls DEFECT), 36 are wrong answers with
faithful evidence, and 7 are explicit self-contradictions. The CORRECT rate
overstates accuracy by +20.3 points on MQ and +3.4 on SB. Re-scoring the main
tables with this prompt as an accuracy oracle is not supported; no full run was
started. Detail: `rebuttal/pilots/20261112_rescore/rescore_report.md`.

## 7d. Answer-equivalence check (frozen, validated, run)

The withdrawn plan to re-score with v2 is replaced by a separate check:
`answer_equiv_v1.json` (Claude Haiku 5.5, temperature 0), file sha256
`51082bc8...c8153`, system sha256 `2831314b...8ba63`. The rule (validation set,
go/no-go, caps) was frozen in
`rebuttal/pilots/20261112_answer_equiv/ANSWER_EQUIV_RULE.md` before any call.

**Validation on the 150 author-labelled traces** (38 author-CORRECT, 112
author-DEFECT): agreement **0.940** (95% CI 0.900-0.973), kappa **0.848**
(95% CI 0.725-0.939), EQUIVALENT recall 0.947, NOT_EQUIVALENT recall 0.938.
Gate (agreement >= 0.90, kappa >= 0.75, EQUIVALENT recall >= 0.85) passes. Cost
$0.020857.

**Main tables: Silo-Bench only**, 52 traces x four protocols, $0.083332 in
total (the 100 MuSiQue calls are logged but not used):

| protocol | paper cell | lexical exact | answer-equiv |
| --- | ---: | ---: | ---: |
| SB summary | 9.6% | 9.6% | 11.5% |
| SB random | 17.3% | 17.3% | 17.3% |
| SB score-ranked | 19.2% | 19.2% | 19.2% |
| SB redundancy | 19.2% | 19.2% | 19.2% |
| **SB pooled** | 16.3% | 16.3% | **16.8%** |

On Silo-Bench the check matches the lexical rule on 207/208 traces (99.5%,
kappa 0.983). The single disagreement is a summary trace that lexical scores
wrong and the check calls equivalent; no answer lexical scores right is called
not-equivalent. So the check moves one cell by one trace and leaves the other
three unchanged.

**MuSiQue: settled by hand-check (2026-11-13, item 2).** The 150 validation
traces contain no MuSiQue (90 E1 + 60 Silo-Bench), so no author-labelled
MuSiQue split exists. The 400 logged Qwen-235B MuSiQue calls were used instead:
exact versus check agreement 287/400 = 0.718, kappa 0.447. All 113 exact-wrong
/ check-equivalent calls (74 distinct cases) were hand-read; **73/74 distinct
cases are equivalent** (98.6%, 92.7-99.8) and **110/113 calls** (97.3%,
92.4-99.5). The one failure is gold "11 February 1929" answered as "1929".
Under the frozen >= 0.90 rule the check passes, so the MuSiQue cells may be
reported under it beside exact: summary **53.0%**, random **49.0%**,
score-ranked **53.0%**, redundancy **50.0%**, pooled **51.2%** (46.2-56.2)
against exact 23.8% (19.7-28.2). The first hand-check was one adjudicator with
the verdict visible; a second reader (Gemini 3.6 Flash, blind) then checked 24
cases including the failure and agreed **24/24** (0.858-1.000), confirming the
1929 case. The figure is therefore **hand-checked by two readers, not
author-validated**, and the cells are not presented as author-validated
corrections. Second-reader spend $0.016886. Paper cells stay unchanged. Rule,
adjudication and table: `rebuttal/pilots/20261113_musique_equiv/`. Earlier detail:
`rebuttal/pilots/20261112_answer_equiv/validation_report.md` and
`main_tables_report.md`.

## 7e. Constructed distortion cases (option C): blocked by consistent sources

Frozen prompts `construct-v1` (file `365f105d...`) and `confirm-v1`
(`194d3bbe...`) in `rebuttal/pilots/20261112_constructed_distortion/`. The
labeller picks one verbatim source span that contradicts the critical fact of a
faithful board unit; a second call must confirm the contradiction; a case is
accepted only if the span is verbatim, confirmed, and not the question, a
header or a refusal.

A 12-candidate pilot accepted **0**: in 12/12 the labeller returned a null span
and explained that the trace's own documents are internally consistent ("the
only Lang death date is 2...", "no document names a different mascot for
Oregon State University"). Constructed contradictions cannot be copied
verbatim from the trace's own sources while those sources agree. Cost
$0.005610. No repair test of the 176 observed distortion diagnoses was run;
they remain a descriptive count (7 gate-passing swaps, 2 genuine).
Record: `rebuttal/pilots/20261112_constructed_distortion/`.

**Corpus scan for genuine contradictions (zero cost).** The fallback decision
required a count of same-subject, different-value sentences over the Stage 1+2
sources. `scripts/scan_corpus_conflicts.py` read 2,670 unique documents and
42,700 sentences, kept sentences that start with a proper name and contain a
value, and paired them on the same subject with a content-token Jaccard >= 0.5
and a different number/date set. It returns 144 pairs in 9 subject groups, 22
pairs within a single instance's documents, but only **4 genuine distinct
pairs** after reading them: Dodgers 21 vs 22 National League pennants, Dodgers
18 vs 19 appearances (inside a multi-team paragraph), the US death-penalty
count 57 vs 54 countries, and the Searle feature named after Debussy vs
Dvorak. The other six inspected groups are different tournament editions, cities,
elections or anaphoric "Summers"/"Thailand" templates, not one subject with two
values. 4 is below 30, so option C is closed and the fallback is option A,
**labelled "constructed substitution" in every table and sentence**: it uses a
verbatim source span for a different statement and does not claim a
contradiction found in the sources. Ten candidate substitutions with source
text are shown in
`rebuttal/pilots/20261112_constructed_distortion/substitution_candidates.md`
before any pilot; all ten are verbatim spans from the cited agent's own
context, none is the question line, and every heading says "constructed
substitution". The generator has only **12 candidates in total**, so a
30-case cohort does not exist under option A either; the construct as
specified supports at most a 12-case descriptive pilot, 10 of them shown.

## 7f. Missing-fact repair pilot 1 (4 phase-1 cases): delivery blocks every case

Run 2026-11-12 by `scripts/missing_fact_repair_pilot.py`; prompts recorded in
`prompt_manifest.json` before the first call (extraction system
`810084ff...`, aggregation system `62f0a128...`), temperature 0, cap $1.
The four cases are the R4-clean cohort from section 6b: `2hop__280583` gemma
and `2hop__142621` gemma on their frozen facts; `2hop__28287` gpt and
`4hop1__802394` qwen on the rebuilt facts. The order was fixed before the run:
R-ext extraction, then the R2 delivery gate, then the board-only control, and a
repair answer only for a delivered case.

**Delivery check (read first).** Delivered **0/4**, exact 95% CI 0.000-0.602.
R-ext re-extracts up to three units from the target agent's own context with
the frozen relay extraction prompt. Recall against the target fact was 0.000
(`2hop__280583`, the model returned a refusal sentence), 0.250
(`2hop__142621`, a refusal sentence), 0.167 (`2hop__28287`: annelids, Derek
Drymon, the 1999 debut, no Mr. Lawrence) and 0.214 (`4hop1__802394`: the
revived Phoenix GP, the Mingus album, Mingus's birthplace, no Andretti). All
four are below the 0.8 gate, so no repair answer was called.

**Scoring check.** Repair answers called: 0. There is no repair outcome to
score, and no wrong repair answer to sample. The board-only control was run
after the delivery file was written: 0/4 exact (95% CI 0.000-0.602), all four
answers are "Insufficient information." against golds Will Arnett, Hollywood
Records, Mr. Lawrence and Mario Andretti. So the four cases do need the fact;
the control does not already know it.

**Reading.** The failure is in the repair's delivery step, not in the model's
use of evidence. In `2hop__280583` the target agent's context says only that
Amy Poehler and Will Arnett star in *On Broadway*; the marriage fact is in the
support set, not in that document. In `2hop__142621` the record label is implicit
(*No Ordinary Girl* "by Jordan Pruitt ... by Hollywood Records"), and in the two
rebuilt cases the extraction returns the surrounding article but not the
needed sentence. Re-extraction from the target agent is therefore the wrong
slice; a delivery-side fix (insert the known support fact, or extract from the
document that states it) is a design change, not a rerun, and needs a decision.
CIs are exact Clopper-Pearson over the four cases (a cluster bootstrap over
four clusters is degenerate). Cost $0.000888 in new calls, logged in
`rebuttal/pilots/20261112_missing_fact_repair/calls.jsonl`; report
`report.md`, delivery record `delivery_check.md`.

## 7g. Delivery (presence) check on the Stage 2 clean cohort (59 instances)

Run 2026-11-12 by `scripts/repair_presence_check.py`; **zero model calls**. The
cohort is the Stage 2 clean extraction-omission set (69 traces / 59 unique
instances, the same set as section 7b). For each case the target agent is the
E4-v7 extraction target, and only that agent's own context is read. The rule
`PRESENCE_RULE.md` was frozen before the run; Amendments 1 and 2 (drop the
question/header lines, use content tokens not function words) were both
written before any paid call. `presence.json` and `presence_check.md` hold the
records.

**Split after a manual read of every case** (the manual step is allowed by the
rule and every change is listed with a reason):

| level | present | partial | absent | total |
| --- | ---: | ---: | ---: | ---: |
| instances | 33 | 6 | 20 | 59 |
| traces | 34 | 8 | 27 | 69 |

The raw content rule gave 36 / 18 / 5; the manual read moved 24 cases, because
token co-location is not entailment. The clearest failures of the token rule
are cast sentences: "Flesh and Bone ... stars Meg Ryan, Dennis Quaid" reaches
0.8 recall against the fact "Dennis Quaid is married to Meg Ryan" without the
marriage being stated, and "Dian Bachar (born ... in Denver, Colorado) ... by
or starring his friends Trey Parker" is about Bachar, not Trey Parker's
birthplace. Those cases are **absent**, not present. Conversely, table rows
that state the fact ("5 12" for season 5 of Ray Donovan, "Parent company
Warner Music Group") were called present after reading.

The **20 absent** cases are a design finding: the fact needed for the answer
is not in the target agent's own context, so no extraction from that context
can deliver it. They are not repaired here, and the full document pool is not
used. The **6 partial** cases are not piloted either.

## 7h. Extraction-fix pilot (33 present instances): delivery 18/33, repair 6/18

Run 2026-11-12 by `scripts/extraction_fix_pilot.py`; rule
`EXTRACTION_FIX_RULE.md` frozen before the first call (system prompt sha256
`fe4306bc...`, cases sha256 `8c5e9791...`), cap $5, temperature 0. One
**oracle-targeted** extraction call per case on the target agent's own context:
the locator is given the question and the missing claim and returns up to three
verbatim sentences. The R2 gate is unchanged, and the answer step refuses to
run before the delivery file exists. Files are under
`rebuttal/pilots/20261112_missing_fact_repair/extraction_fix/`.

**Delivery (read first).** **18/33 delivered** (54.5%), exact 95% CI
0.364-0.719; spend $0.004753. The 15 blocks split into:
- **10 verbatim sentences at 0.70-0.79**, blocked by function-word
  differences (e.g. "was born on 1 January 1986" vs "(born 1 January 1986)");
  the locator found the stating sentence, the full-token gate rejected it.
- **4 "NONE"**, of which 3 are tabular evidence (season tables, a comparison
  table) that is not sentence-shaped; the prompt asks for sentences.
- **1 lower-recall** (0.50) where the unit states part of the claim.

**Scoring (frozen exact answer_f1).** Board-only control **0/33 exact** (95% CI
0.000-0.106), all "Insufficient information." or wrong. Repair arm **6/18
exact** (95% CI 0.133-0.590); on the same 18 cases the board-only control is
**0/18 exact** (95% CI 0.000-0.185), the paired result. Repair is better in 6
cases and worse in 0. The repair answers are right for sentence-shaped facts
(Bindi Irwin/Terri Irwin, Adams County, Randall County, Socialist Party, Warner
Music Group, conga). Three delivered cases have the right content but fail
exact match ("Johan Remkes (King's Commissioner of North Holland)", "Nearly
25,000 students.", "22 times."): the frozen exact rule counts the extra words
as wrong. They are reported as a separate list in `report.md`, not as repair
failures. A fourth, `2hop__95970` ("Claudia Cardinale, who acted in the film,
was born in La Goulette" vs "La Goulette"), appears only under gate v2a below.

**Reading.** A targeted pass fixes the extraction slice for sentence-shaped
evidence: 6/18 delivered cases move from wrong (control 0/33) to correct, with
no regressions. The remaining delivery failures are the R2 gate's
function-word sensitivity and tabular evidence, both design issues rather than
evidence-use failures. This is an oracle-targeted arm and does not by itself
show a deployable repair. Total spend $0.009024, every call in `calls.jsonl`.

## 7i. Direct insertion on the full 59: control 0/59, insert 32/59

Run 2026-11-13 by `scripts/direct_insertion_pilot.py`; rule
`DIRECT_INSERTION_RULE.md` frozen before any call (sha256
`57eb798e...42ccdf`; cases sha256 `bb1ccb53...5090db0`), cap $5, temperature 0.
The missing fact is supplied verbatim as one board unit at the E4-v7 target
agent, so it is always delivered; no extractor and no gate. Both arms are
called on every case. This is an **oracle upper bound**, not an achievable
repair. The pilot was the first 10 instances in sorted id order ($0.001438,
20 answers); the full run reused those and answered the remaining 49 pairs
($0.008406, 98 answers). The fact is supplied in 59/59 insert cases by
construction; the control adds no unit and, under the R4 diagnosis, no board
unit carries the targeted fact.

**Full result.** Board-only control **0/59 exact** (95% CI 0.000-0.061);
insert **32/59 exact** (0.408-0.673); insert better in 32, worse in 0. By
presence label: present **19/33** (0.392-0.745), partial **0/6** (0.000-0.459),
absent **13/20** (0.408-0.846). The pilot's 3 exact answers are part of the 32
(e.g. `2hop__435184`, January 20, 2017, a present case whose v1 extraction
returned NONE on a season table). Total spend $0.009844 against the $5 cap, 118
answer calls, 0 failures. Detail:
`rebuttal/pilots/20261112_missing_fact_repair/direct_insertion/`.

**Reading.** With the claim guaranteed on the board, 32/59 answers are exact;
the board answerer can use a supplied fact. On the 33 present cases insert
reaches 19/33 exact. The v1 repair arm could answer only the 18 cases its gate
delivered and reached 6 exact there (6 of the 33 present cases overall); the
board-only control is 0/33. So the gap is the cost of extraction and the gate,
not of the answerer. The absent-case 13/20 is an oracle bound only; those 20
stay recorded as misdiagnosed and no full-pool extraction was run.

## 7j. Gate versions piloted beside v1 (33 present instances)

Both were frozen as new versions, each in its own rule file with its hash
recorded before any call. v1 stays on record and is not replaced. Combined
report: `rebuttal/pilots/20261112_missing_fact_repair/gate_versions_report.md`.

**v2a: content-token recall** (`GATE_V2A_RULE.md`, sha256
`0edb26ba...6f61`; implemented
in `src/audit/e4_fix_gates_v2.py`; v1 untouched). The fact's content tokens
(minus STOP) must be carried at recall >= 0.8; all other v1 reasons kept. It
re-gates the frozen v1 extraction output; no new extraction call. Result:
delivery **25/33** (95% CI 0.577-0.889), 8 newly delivered (242753, 520033,
655505, 677160, 693444, 765678, 95970, 3hop1__662618) and 1 lost (2hop__94507,
where the content tokens "member" of "Socialist Party of America" drop recall
to 0.714). Repair exact **10/25** (0.211-0.613) versus paired board-only
**0/25**; the 8 new deliveries add 5 exact and the loss removes 1, so 6 -> 10.
One new answer has the right content but fails exact (`2hop__95970`, above).
Spend $0.000671 (8 answer calls).

**Tabular locator prompt** (`TABLE_PROMPT_RULE.md`, sha256 `63e9...`; system
sha256 `4de7...`), same 33 cases, fresh locator calls, **unchanged v1 gate** so
the prompt is the only change. Delivery **18/33** (0.364-0.719), 1 gained
(`4hop3__131775`, the USC/Clemson comparison row) and 1 lost (`2hop__673655`,
the conga sentence). Repair exact **5/18** (0.097-0.535) versus paired control
0/18: the gained table row is exact, the lost sentence is an exact answer, and
`3hop1__389761` turns from exact into a right-content/exact-fail answer ("Warner
Music Group owns the record label..."), so 6 -> 5 net. Of the three tabular
cases, only `4hop3__131775` passes; the two
season tables (`2hop__435184`, `2hop__619265`) return rows but fail the v1
full-token recall because the row lacks the claim's words ("season",
"episodes"). Spend $0.006853 (33 locator + 18 answer calls).

**Reading.** v2a is the stronger change: it uses the same extraction and moves
repair from 6/18 to 10/25. Of the 8 new deliveries, 5 are exact, 2 have the
right content but extra words (242753, 95970; scored 0) and 1 is a refusal; one
previously correct case (94507) is lost. The tabular prompt alone is not a
drop-in replacement: it swaps one
table case for one sentence case. A table row needs both a row-aware prompt and
a gate that does not demand the claim's prose words; that combination is a
third version and has not been run.

## 7k. Answer-equivalence beside exact match, and insertion paired with repair

Run 2026-11-13 by `scripts/answer_equiv_beside.py` with the frozen
`answer-equiv-v1` prompt; 169 calls, `$0.021138`. Report:
`rebuttal/pilots/20261113_answer_equiv_beside/report.md`. The equivalence
prompt was validated on Silo-Bench author labels only, and both cohorts here are
MuSiQue (Stage 2), so every equivalence count is marked **not validated on
MuSiQue-style answers**; exact match stays primary.

| cohort | arm | n | exact | exact or equivalent | equivalent-only |
| --- | --- | ---: | ---: | ---: | ---: |
| direct insertion | control | 59 | 0 | 1 | 1 |
| direct insertion | insert | 59 | 32 | 39 | 7 |
| extraction fix | board-only | 33 | 0 | 0 | 0 |
| extraction fix | repair | 18 | 6 | 8 | 2 |

Right-content, exact-fail answers under equivalence: direct insertion 7 insert
answers (e.g. `2hop__304852` "Hubbard County, Minnesota" for "Hubbard County";
`4hop1__3496` "2" for "two") and 1 control (`2hop__554145`, "ADM Michael S.
Rogers USN"); repair 2 (`2hop__810884` "Nearly 25,000 students." for "nearly
25,000"; `3hop1__593288` "22 times." for "22"). These are scorer misses, not
wrong answers.

**Same 18 delivered cases (paired).** Insertion is run on exactly the cases the
repair gate delivered, so both denominators are 18: insert **7/18** exact
(0.173-0.643), 11/18 exact-or-equivalent; repair **6/18** exact (0.133-0.590),
8/18. Both controls are 0/18 (0.000-0.185). The 19/33 insertion figure is on all
33 present cases and is not comparable to the 6/18 repair figure; the paired
numbers are.

## 7l. Input-presence (sharding) check in the diagnosis

Run 2026-11-13 by `scripts/sharding_diagnosis.py`; **zero model calls**
($0.000000). Rule `rebuttal/pilots/20261113_sharding_diagnosis/SHARDING_RULE.md`
frozen before the run, with Amendment 1 (the 2,400-trace population) written
before that run. The check is additive in `src/audit/sharding_check.py`
(`diagnose_with_sharding`); the old `diagnose` function and every old label
stay unchanged. Instrument: the frozen presence rule from §7g (content recall,
0.8 present / 0.4 partial).

| population | old extraction diagnoses | new sharding | new mixed | unchanged extraction | moved (95% CI) |
| --- | ---: | ---: | ---: | ---: | --- |
| missing-fact cohort, 59 instances | 59 | 20 | 0 | 39 | 20/59 (33.9%, 22.1-47.4) |
| missing-fact cohort, 69 traces | 69 | 27 | 0 | 42 | 27/69 (39.1%, 27.6-51.6) |
| E1 anchor, 8 diagnoses | 8 | 0 | 2 | 6 | 2/8 (25.0%, 3.2-65.1) |
| main table (Stage 2), 216 diagnoses | 216 | 28 | 9 | 179 | 37/216 (17.1%, 12.4-22.8) |

At the fact level, 40 of 275 targeted main-table facts are absent from every
source shard; 235 are present or partial. By model the main-table moves are
gemma31b 12/126, gpt4omini 14/57, qwen235b 11/33. The 20/59 cohort figure is
the number the rebuttal expected; the main-table set is broader (the cohort is
contained in it) and moves 37/216, so the paper's assumption that every
critical unit is in its shard by construction (Appendix stage-wise, item (1))
does not hold. The check is lexical and can read co-located tokens as
presence, so these are lower bounds. Detail:
`rebuttal/pilots/20261113_sharding_diagnosis/report.md`.

## 7m. Per-fact labeller at the relay checkpoints (author-label FAIL; V5 cross-model validation)

Built 2026-11-13 by `scripts/per_fact_labeller.py`; rule
`rebuttal/pilots/20261113_per_fact_labeller/PER_FACT_RULE.md` frozen before any
call (sha256 `5e91680b...`), Amendment 1 (annotator fact list) written before
the validation set ran. Stage: relay checkpoints (extraction pool and board).
Population: 78 maker-ok anchor traces over 26 instances, two author
annotations each; split 13 tune / 8 validation / 5 reserve instances.

**Tuning** (board complete coverage vs `author_complete`): matcher-fact v1
0.603 (47/78, kappa 0.221); annotator-fact v2 0.400; decisive-content v3
0.397; question-relevance v4 0.436. Moving to the annotator's fact list did
not help.

**Validation** (frozen v3, 48 comparisons): agreement **0.625**
(0.474-0.760), kappa **0.316** (0.072-0.714) — **FAIL** against the frozen
0.80/0.60 rule. All 18 disagreements are labeller-incomplete /
author-complete; there are no labeller-complete / author-incomplete cases.

**Cause (measured):** the reference label is near constant and lenient. The
authors mark 158 of 168 board carriers faithful in the validation set, and
some carrier records mark a fact faithful with a unit that does not state it:
on `2hop__28287_89399 / gemma31b / C`, the fact "annelids were originally
animals with two separate sexes ... released ova and sperm via their
nephridia" is marked faithful with `board:a1:u0`, which says "Annelid
fertilized eggs develop into trochophore larvae, which live as plankton."
Reproducing this label requires calling an unsupported carrier faithful. The
disagreements do not shrink under decisive-content (v3) or question-relevance
(v4) wording, so the gap is the reference, not the prompt. The reserve split
is held unused because the rule reserves it for re-validation after a cause is
fixed; no labeller-side fix addresses this reference.

**Carrier-target check under the authors' actual label (option b).** Rule
`PER_FACT_RULE_V2.md` changed the target from semantic fidelity to the board
`unit_ids` each author cites per fact. A fact matches when the labeller's
returned units intersect the author's carrier units; complete means every fact
matches. On the 8-instance validation split: agreement **41/48 = 0.854**
(0.722-0.939), kappa **0.649** (0.263-1.000) — an **exploratory
carrier-identification pass, n=48**, not a validation, because the target was
chosen after this set was seen.

**Fresh held-out check (reserve).** Rule `PER_FACT_RULE_V3.md` frozen before
60 calls on the 5 reserve instances, which were not used for the target
change. Agreement **20/30 = 0.667** (0.472-0.827), kappa **0.194**
(0.000-0.595) — **FAIL** against 0.80/0.60; per-fact carrier match 106/120 =
0.883. The author-label run failed; the cause below is the author labels, and
the V5 cross-model run recorded in `VALIDATION_RECORD.md` supplies the
validation.

**Audit of the reserve disagreements.** All 10 reserve disagreements (labeller
incomplete, author complete) are author-citation errors: the board units the
author cites do not state the fact in any model's trace
(`author_citation_audit.md`, zero calls). The labeller's calls match the board
text. The prompt is unchanged; corrected reserve labels are in
`corrected_reserve_labels.json` and the originals stay unchanged.

**Fresh check (V4) is not a validation; it FAILS on the original labels.**
Rule `PER_FACT_RULE_V4.md` (sha256 `0bc7d8c6...`), 64 comparisons: four unused
synthetic E1 anchor instances (24) and the 20 E1 dev runs (40). Against the
authors' original labels: agreement **47/64 = 0.734** (0.609-0.837), kappa
**0.279** (0.000-0.577) - **FAIL** against 0.80/0.60; per-fact 255/298. V4
alone leaves the labeller unvalidated even for carrier identification. A post-hoc
corrected-label audit gives 64/64 (0.944-1.000, kappa 1.000; per-fact
289/298), but it is **not** a validation: the references were corrected after
the labeller output was seen and 40 rows are dev rows used in labeller
development. Star: $0.028203 (64 calls). Composition is Silo-Bench only, so
MuSiQue carrier identification is unvalidated. Detail: `fresh_report.md`,
`fresh_review.md`.

**V5 independent-reference validation (run 2026-11-13).** Design
`PER_FACT_RULE_V5.md` (sha256 `27f981d8...`): 60 MuSiQue main-table boards
never used in labeller development, audit matcher fact list, reference labels
from **Gemini 3.6 Flash** under the frozen prompt
`v5_reference_prompt.json`, hashed before any Haiku call. The reference
labeller differs from the labeller under test (Claude Haiku 5.5) and from the
assistant that wrote the rubric. **Per-fact carrier agreement 155/176 = 0.881**
(0.823-0.925): all 21 disagreements are over-credits where the reference lists
no carrier and the labeller returns a unit (12 `present`, 9 `partial`); no
reference carrier is missed and there are no wrong-unit-only cases. Board-level
complete agreement 60/60 (0.940-1.000), kappa 1.000, PASS against 0.80/0.60;
reference and labeller each complete 26/60. The per-fact figure is the
headline; the board-level figure hides the over-credits. Spend $0.382002 (149
calls: 88 Gemini reference incl. retries + 61 Haiku). This is cross-model
agreement on MuSiQue against an LLM reference, not author ground truth and not
semantic fidelity or coverage. Detail: `v5_report.md`,
`reference_labels_v5.json` (sha256 `319e8730...`).

**Validation record.** The V5 cross-model result is the labeller's
validation, for one label and stage only: **carrier identification at the
board checkpoint on MuSiQue**. It is cross-model agreement against Gemini 3.6
Flash, not author ground truth, so it does not validate semantic fidelity,
semantic coverage, or any extraction-pool label. The author-label run failed
because the author labels were wrong: all 10 reserve disagreements were
author-citation errors (the cited units do not state the fact;
`author_citation_audit.md`), and the corrected-label 30/30 is a post-hoc
audit, not a validation. The V4 fresh Silo-Bench FAIL on original labels
(47/64) is a separate held-out check on a different benchmark and stays on
record. The semantic-target FAIL, the reserve FAIL and the V4 FAIL stay on
record. The main-table coverage, recall, omission, fidelity and AF columns
initially stayed lexical or matcher; the 2026-11-13 main-table redo reports
the labeller columns beside them (§7s). Spend $0.259277 (766 calls; reserve
$0.026698; fresh $0.028203). Detail: `VALIDATION_RECORD.md`, `v5_report.md`,
`revalidation.md`, `revalidation_reserve.md`; contact sheet: `report.md`.

## 7n. Protocol comparison as repair evidence (item 3)

Zero-cost comparison of the frozen distortion audits
(`results/distortion_audit_se/`, `results/distortion_audit_relay/`; Qwen-235B,
Silo-Bench n=5/n=10). Stage: relay checkpoint. Rule:
`rebuttal/pilots/20261113_protocol_comparison/COMPARISON_RULE.md`.

| protocol | omission (95% CI) | strict distortion among covered (95% CI) |
| --- | ---: | ---: |
| Summary Exchange | 62.1% (57.0-66.9), n=390 | 8.8% (4.8-14.5), 13/148 |
| Random relay | 2.9% (1.3-5.4), n=315 | 0.7% (0.1-2.3), 2/306 |
| Score-ranked relay | 2.5% (1.1-4.9) | 0.3% (0.0-1.8), 1/307 |
| Redundancy-aware relay | 2.5% (1.1-4.9) | 0.0% (0.0-1.2), 0/307 |
| Relay pooled | 2.6% (1.7-3.9), n=945 | 0.3% (0.1-1.0), 3/920 |

Verbatim relay reduces both omission and distortion at the relay checkpoint;
summary's 8.8% is conditional on the 38% of pairs it covers. This is repair
evidence for Answer 3's relay branch, not a deployed repair. Detail:
`rebuttal/pilots/20261113_protocol_comparison/report.md`.

## 7o. Restore-the-source pilot on real-run distortions (item 4)

Pilot 2026-11-13, `scripts/restore_source_pilot.py`; rule
`rebuttal/pilots/20261113_restore_source/RESTORE_RULE.md` frozen before calls.
Stages: relay checkpoint and final aggregation. From 184 unique distortion
diagnoses, 40 sampled; for each, the source sentence with the best recall to
the distorted fact is checked by Haiku 5.5 (states the fact, verbatim in the
shard), then two Haiku 5.5 aggregation arms on the unchanged board and the
source-restored board.

- Confirmed: **23/40** (57.5%, 40.9-73.0). The other 17 are distortion
  diagnoses whose source does not restate the fact.
- Answer arms on the 23: control exact **0/23**, restore exact **4/23**
  (17.4%, 5.0-38.8); mean F1 0.000 -> 0.338; 4 improved, 0 worse, 19 same.
- Spend $0.008642. No full run before review; projected full cost about
  $0.04.

**Full run (approved 2026-11-13; addendum `RESTORE_FULL_ADDENDUM.md` frozen
before the remaining calls).** All **184/184** cases, 450 calls, **$0.043831**.
Confirmed **132/184 = 71.7%** (64.6-78.1). On the confirmed cases: control
exact **2/132**, restore exact **20/132 = 15.2%** (9.5-22.4); mean F1 0.051 ->
0.326; 18 improved, 0 worse, 114 same. The pilot's 23/40 57.5% stays on
record. The confirmer is **Claude Haiku 5.5** with the frozen prompt. It has
since been validated against an independent **Gemini 3.6 Flash** reference
under a frozen copy of the same prompt, on the **144 held-out cases** (the 40
pilot cases excluded): agreement on `source_states_fact` **123/144 = 0.854**
(0.786-0.907), kappa **0.660** (0.524-0.781) - **PASS** at the frozen
point-estimate bar: 0.854 clears 0.85, but the 95% CI lower bound 0.786 does
not; spend $0.250881 (`confirmer_validation_report.md`). The
reference is an LLM, not author ground truth, and it is stricter: on the same
144 cases the confirmer's gate gives 109/144 = 0.757 and the reference's
92/144 = 0.639 (19 confirmer-yes/reference-no, 2 the reverse). The
verbatim-substring part is mechanical; the 132 remains a confirmer-gated
count on all 184, not an author-validated one.

**Reference-gated subset (run 2026-11-13).** Rule
`RESTORE_REFERENCE_SUBSET_RULE.md` frozen before any new call. On the **92
held-out cases** where the Gemini reference says the source states the fact
and the sentence is verbatim, the restore comparison was rerun: 90 arms are
reused from the frozen full run, 2 reference-only cases were answered here
(4 calls, **$0.000558**, cap $0.25). Control exact **0/92**; restore exact
**13/92 = 14.1%** (7.7-23.0); paired **+13** (13 improved, 0 worse, 79 same),
case-bootstrap 95% CI [7, 20]. The restore effect **holds** on the stricter
subset; the two reference-only cases were 0/2 in both arms. The 132 figure
and its 2/132 vs 20/132 comparison stay on record beside this. Detail:
`rebuttal/pilots/20261113_restore_source/reference_subset_report.md`.

Reading: restoring the source recovers a minority of the confirmed cases
because the board aggregation is the bottleneck even when the fact is back.
Detail: `rebuttal/pilots/20261113_restore_source/report_full.md`; pilot
`report.md`.

## 7p. Faithful-rewrite control tightened (item 5)

The 7/30 control failures in the injected-distortion pilot were read. All 7
rewrites preserve the original's entities and values; the failures are at
aggregation. Rule `CONTROL_TIGHTENING.md` frozen before a 7-case base-board
rerun (`scripts/control_stability.py`, $0.000767). Re-asking the **unchanged**
original board:

- 2 are answer-equivalent exact misses ("in Northern Florida" vs "Northern
  Florida");
- 2 are rewrite-induced (base_repeat exact, control wrong): 1853 -> 1886 and
  an empty output, neither removing the fact;
- 3 are aggregation instability (the same original board is also wrong on the
  re-ask).

Tightened control rate **2/27** (7.4%, 0.9-24.3) after removing the unstable
cases; the original 7/30 stays on record. Detail:
`rebuttal/pilots/20261113_injected_distortion/control_stability/report.md`.

## 7q. Method comparison on known-stage cases (item 6)

Zero-cost, rule `rebuttal/pilots/20261113_method_comparison/COMPARISON_RULE.md`.
Stage: all four. Baseline proposed before building: a lexical checkpoint-drop
baseline using the same shard/extraction/board checkpoints and gold supports
but no critical-fact labels; reference baseline always-aggregation.

| family | audit | lexical baseline | always aggregation |
| --- | ---: | ---: | ---: |
| injected distortions, truth relay (30) | 30/30 by construction | 0/30 (0.0-11.6) | 0/30 |
| missing-fact cohort, truth from presence (59) | 59/59 (93.9-100) | 39/59 (52.6-77.9) | 0/59 |
| cohort against old truth "extraction for all" | old 59/59, new 39/59 | 59/59 | 0/59 |

The audit's two perfect scores are by construction and are labelled; the
comparison shows what critical-fact labels and the input-presence check add.
The baseline is not a released attribution framework (Who&When/MAST not run).
Detail: `rebuttal/pilots/20261113_method_comparison/report.md`.

## 7r. Placement by redoing the blamed relay step (item 7, pilot)

Pilot 2026-11-13, `scripts/placement_redo.py`; rule
`rebuttal/pilots/20261113_placement_redo/PLACEMENT_REDO_RULE.md` frozen before
calls. Stage: relay checkpoint, aggregation held at the original model and
prompt. 10 injected distortions; Gemini 3.6 Flash re-transmits from the blamed
agent's own shard (diagnosed arm) or another agent's shard (random arm), each
replacing one board unit; no oracle text.

Diagnosed exact **2/10** (20.0%, 2.5-55.6); random **0/10** (0.0-30.8); paired
+2 at n=10. Descriptive pilot only; spend $0.059244, including two discarded
configurations kept on record (corruption not applied; Gemini reasoning
disabled). Detail: `rebuttal/pilots/20261113_placement_redo/report.md`.

**Expansion (approved 2026-11-13; addendum `PLACEMENT_EXPANSION.md` frozen
before the new calls).** 30 cases (10 pilot reused + 20 new), same setup:
diagnosed exact **11/30 = 36.7%** (19.9-56.1); random **0/30**; paired +11.
Spend **$0.132218** total, 200 calls. The arms are not symmetric: the random
arm replaces an intact unit and can only displace correct text, while the
diagnosed arm replaces the injected corrupted unit. The 11/30 versus 0/30 gap
is therefore **confounded** and is **not** reported as a placement effect.
Detail: `report_expansion.md`.

**Matched run (addendum `PLACEMENT_MATCHED.md` frozen before the calls).**
Same 30 cases; both arms replace the corrupted unit at the same position, so
both remove the injected corruption and only the agent whose shard the
stronger model reads changes. Diagnosed exact **8/30 = 26.7%** (12.3-45.9);
random **0/30**; paired +8. Spend **$0.109805**, 120 calls. The matched gap is
smaller than the confounded 11/30 and remains a placement signal for the one
replaced unit, not a full repair. Detail: `report_matched.md`.

## 7s. Main-table redo with the validated per-fact labeller (item 3)

Run 2026-11-13 by `scripts/main_table_redo.py`; rule
`rebuttal/pilots/20261113_main_table_redo/REDO_RULE.md` frozen before the
pilot call. Stage: relay checkpoints (extraction pool and shared board).
Population: the Stage 2 main table, **2,400 MuSiQue traces** (800 instances at
each of gemma31b, gpt4omini, qwen235b, score-ranked relay), **7,665 matcher
facts**. Pilot 120 calls $0.035358; full run **4,800 calls, $1.402666** (5
unparsed, scored as absent). Old column: the frozen matcher carrier label on
the same facts and checkpoint. New column: the per-fact labeller (prompt v3).
The paper's original Table 3 lexical cells come from the earlier 10-model
cohort and stay on record unchanged.

Pooled by checkpoint (95% CI, instance-cluster bootstrap, seed 43):

| checkpoint | CR old | CR new | complete old | complete new | dist old | dist new | AF old | AF new |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| extraction | 0.947 [0.940, 0.954] | 0.881 [0.871, 0.890] | 0.848 [0.831, 0.866] | 0.691 [0.667, 0.714] | 0.044 [0.038, 0.050] | 0.035 [0.029, 0.040] | 0.511 [0.484, 0.537] | 0.385 [0.360, 0.410] |
| board | 0.946 [0.938, 0.953] | 0.882 [0.872, 0.892] | 0.845 [0.828, 0.862] | 0.694 [0.670, 0.717] | 0.044 [0.038, 0.050] | 0.041 [0.035, 0.047] | 0.508 [0.482, 0.535] | 0.385 [0.359, 0.410] |

By model at the board: CR old/new gemma 0.905/0.813, gpt4omini 0.959/0.894,
qwen235b 0.972/0.938; AF old/new 0.454/0.295, 0.539/0.404, 0.532/0.456;
complete 0.756/0.568, 0.870/0.705, 0.909/0.810.

**Reading.** On the same facts and checkpoint the labeller calls fewer facts
carried than the matcher (CR 6.4 points lower at the board) and flags fewer
traces as candidate aggregation failures (AF 12.3 points lower). The V5
over-credits were labeller-present/reference-none; here the matcher is the
more lenient instrument, so the two columns genuinely differ in direction and
the redo reports both. The **board** carrier column is the validated one
(cross-model with Gemini 3.6 Flash, not author ground truth); **extraction**
rows are exploratory, and **fidelity/distortion** labels were not checked by
the V5 reference and are unvalidated. The MuSiQue answer-equivalence cells
(exact 23.8% vs check 51.2% pooled) are reproduced in the report for the
earlier 400-call Qwen-235B table, **hand-checked by two readers, not
author-validated**, and are not applied to this population's AF. Detail:
`rebuttal/pilots/20261113_main_table_redo/report.md`.

## 8. Status

- New files: this directory (including `expansion_plan.md`,
  `pilot_report.md`, `repilot_v2_report.md`), the pilot directories
  `rebuttal/pilots/20261112_labeller/` (with `labeller_prompt_v2.json` and
  `labeller_prompt_v2.manifest.json`), `rebuttal/pilots/20261112_repilot_v2/`,
  `rebuttal/pilots/20261112_labeller_v2_full/`, and
  `rebuttal/pilots/20261112_expansion_stage1/` (with
  `stage2_expected.md`), `rebuttal/pilots/20261112_expansion_stage2/`,
  `rebuttal/pilots/20261112_swap_labeller/` (with `swap_prompt_v1.json` and its
  manifest, and `stage2/` for the Stage 2 cases),
  `rebuttal/pilots/20261112_answer_equiv/` (with
  `ANSWER_EQUIV_RULE.md`), `rebuttal/pilots/20261112_constructed_distortion/`
  (with both frozen prompts, `conflict_scan.json` and
  `corpus_conflict_scan.md`), `rebuttal/pilots/20261112_missing_fact_repair/`,
  `rebuttal/pilots/20261112_rescore/` (with `SCORING_RULE.md`),
  `rebuttal/pilots/20261113_answer_equiv_beside/`,
  `rebuttal/pilots/20261113_main_table_redo/` (with `REDO_RULE.md`),
  `rebuttal/pilots/20261113_per_fact_labeller/VALIDATION_RECORD.md`,
  `rebuttal/pilots/20261113_restore_source/CONFIRMER_RULE.md` and its
  validation prompt/calls, `scripts/main_table_redo.py`,
  `scripts/confirmer_validation.py`,
  `rebuttal/pilots/20261113_injected_distortion/` (with
  `INJECTED_DISTORTION_RULE_V2.md`, both prompts, and the preview),
  `scripts/answer_equiv.py`, `scripts/answer_equiv_beside.py`,
  `scripts/injected_distortion_pilot.py`,
  `scripts/build_constructed_distortion.py`,
  `scripts/scan_corpus_conflicts.py`, `scripts/missing_fact_repair_pilot.py`,
  `scripts/repair_presence_check.py`, `scripts/extraction_fix_pilot.py`,
  `scripts/direct_insertion_pilot.py`, `scripts/gate_version_pilots.py`,
  plus `scripts/generate_distortion_swaps.py`,
  `scripts/rescore_main_tables.py`, `scripts/build_e4_diagnosis.py`,
  `scripts/build_e4_tag_index.py`, `scripts/check_e4_r4_rebuild.py`,
  `scripts/check_e4_gates.py`, `scripts/rescore_e4_corrected.py`,
  `scripts/pilot_llm_labeller.py`, `scripts/repilot_llm_labeller_v2.py`,
  `scripts/full_llm_labeller_v2.py`, `scripts/run_expansion_stage1.py`,
  `scripts/run_expansion_stage1.sh`, `scripts/run_expansion_stage2.py`,
  `scripts/run_expansion_stage2.sh`, `src/audit/e4_fix_gates.py`, and
  `src/audit/e4_fix_gates_v2.py` (the frozen v2a gate; v1 untouched). The only
  existing-file edit is `normalize()` in `src/eval/evaluate.py` (R1). No raw
  result, cohort manifest, paper, or plan file was changed; nothing committed.
- The earlier results remain on record unchanged. `case_sheets.md` and
  `cases.json` still use the archived scorer; `corrected_scores.md` sits
  beside them. One verdict was corrected on re-reading: `2hop__511454` gpt
  moved from (f) to (b) in both arms, because the 918 sentence is already on
  the board. Cause counts are now 17 (0/3/2/1/2/9/0), 17 (0/4/2/1/0/9/1),
  1, and 25.
- R4 decisions are applied in the diagnosis record; all 17 cases are accounted
  for (15 actions plus 2 clean cases with no action), and the clean single-fact
  cohort is 4 traces (section 6b). `III-29_n5` is recorded as excluded (R3,
  three facts absent, class d).
- The v1 labeller pilot ran under the $0.25 cap ($0.048739 total across three
  attempts) and failed the go/no-go; the v1 label set is not used. The prompt
  was revised and frozen as v2: file sha256 `7f9e2816...8268c6` is the frozen
  reference, system sha256 `585d0d45...b8e6e` is the text hash in the call log.
  The disjoint 20-trace re-pilot passed ($0.011987; agreement 0.950, 95% CI
  0.850-1.000; kappa 0.900, 95% CI 0.667-1.000); one disagreement, `Nicholas
  Bacon` vs `Sir Nicholas Bacon`.
- The full 150-trace labeller run passed: 150/150 parsed, $0.114821, agreement
  0.953 (95% CI 0.913-0.987), kappa 0.878 (95% CI 0.760-0.965), 7
  labeller-vs-author disagreements. The 150 traces are author-unanimous, so
  this validates consensus labels, not author splits. Detail:
  `rebuttal/pilots/20261112_labeller_v2_full/full_report.md`.
- Expansion Stage 1 ran: 43 candidates (7.2%) and 11 clean cases (25.6% of
  candidates; 10 unique instances) at $1.0471. Stage 2 ran at 800 instances
  (2,400 traces, $4.2688): 69 R3/R4 clean traces / 59 unique (Stage 1 + 2:
  80/69) and 176 distortion diagnoses / 150 unique. Extraction and direct
  insertion reach 30 unique cases; gate-passing genuine distortion swaps do not.
- The 25 distortion swaps were regenerated by the swap labeller: 1/25 passes
  the R6 gate and is recorded beside the originals. Cost $0.005423; the case
  that passes is `4hop3__152056` / gpt-4o-mini. The 176 Stage 2 distortion
  cases went through the same path: 6/176 pass ($0.038218), but 5 are one
  false-positive temperature unit repeated, so of 7 gate-passing swaps only 2
  are genuine distortions. Detail:
  `rebuttal/pilots/20261112_swap_labeller/swap_report.md` and
  `stage2/swap_report.md`.
- The main-table re-score pilot ran on Qwen-235B (607/608 traces, $0.400727)
  and found that the v2 labeller's CORRECT label is an evidence-flow label,
  not an answer-accuracy score: it calls 89 wrong answers CORRECT (46 contain
  the gold plus extra words, 36 are wrong with faithful evidence, 7 are
  explicit contradictions). The withdrawal is recorded; v2 stays an
  evidence-flow column. Detail:
  `rebuttal/pilots/20261112_rescore/rescore_report.md`.
- The separate answer-equivalence check is frozen, validated (agreement 0.940,
  kappa 0.848, 95% CI 0.725-0.939 on the 150 author labels, $0.020857; the
  point estimate passes the gate, the interval makes it descriptive) and run.
  It is reported for **Silo-Bench only** ($0.083332 total, including the 100
  MuSiQue calls that are logged but not used): SB 16.8% vs 16.3% lexical,
  agreement 207/208, kappa 0.983, one summary trace moved. MuSiQue stays at
  lexical exact/F1 pending an answer-style validation set. Detail:
  `rebuttal/pilots/20261112_answer_equiv/`.
- The constructed-distortion generator was frozen and piloted on 12
  candidates: 0 accepted, because each trace's own documents are consistent
  and the labeller correctly returns no contradicting verbatim span. The
  zero-cost corpus scan then found **4 genuine same-subject, different-value
  sentence pairs** (Dodgers 21/22 pennants, Dodgers 18/19 appearances, US
  death-penalty 57/54 countries, Searle Debussy/Dvorak) in 2,670 documents and
  42,700 sentences, below the threshold of 30. Option C is closed; the fallback
  is option A, labelled "constructed substitution" in every table and sentence;
  ten candidates with source text are in `substitution_candidates.md` (12
  available in total, so no 30-case cohort).
  Observed distortions stay a descriptive count (176 diagnosed, 7 gate-passing,
  2 genuine); no repair test.
- The first missing-fact repair pilot ran on four phase-1 cases, delivery
  first: **0/4 delivered** (exact 95% CI 0.000-0.602), so no repair answer was
  called; the board-only control was **0/4 exact** (95% CI 0.000-0.602), all
  refusals. Cost $0.000888. That was the wrong cohort (four single-fact
  cases); it stays on record. Detail:
  `rebuttal/pilots/20261112_missing_fact_repair/report.md`.
- The zero-cost delivery check on the intended Stage 2 clean cohort (59
  instances) split **33 present / 6 partial / 20 absent** after a manual read
  (raw content rule 36/18/5; 24 changes with reasons in `presence_check.md`).
  Absent cases are a design finding: the fact is not in the target agent's own
  context, so no extraction from it can deliver. No full-pool repair was run.
- The extraction-fix pilot on the 33 present instances used an
  oracle-targeted locator and kept the R2 gate: delivery **18/33** (95% CI
  0.364-0.719), board-only **0/33 exact** (0.000-0.106), repair **6/18 exact**
  (0.133-0.590), 6 better and 0 worse; the paired board-only control on the
  same 18 is 0/18 (0.000-0.185). The 15 delivery failures are 10 verbatim
  sentences just under the gate because of function words, 4 "NONE" (3
  tabular), and 1 lower-recall unit. Three right-content/exact-fail answers are
  listed separately. Cost $0.004753 delivery + $0.004271 answers = $0.009024.
  Detail: `rebuttal/pilots/20261112_missing_fact_repair/extraction_fix/`.
- Direct insertion ran on the full 59 (pilot 10 first, then the remaining 49
  with the pilot answers reused): control **0/59** (0.000-0.061), insert
  **32/59** (0.408-0.673), 32 better and 0 worse. By presence label: present
  19/33 (0.392-0.745), partial 0/6, absent 13/20 (0.408-0.846). The fact is
  always supplied, so this is an oracle upper bound; the absent split is not a
  repair. Spend $0.001438 pilot + $0.008406 full = $0.009844, 118 calls, 0
  failures. Detail:
  `rebuttal/pilots/20261112_missing_fact_repair/direct_insertion/`.
- Gate v2a (content-token recall, frozen `GATE_V2A_RULE.md`) piloted beside v1
  on the 33 present cases: delivery **25/33** (0.577-0.889), 8 gained and 1
  lost; repair **10/25** (0.211-0.613) versus paired control 0/25; 6 -> 10
  exact. Spend $0.000671. The tabular locator prompt (`TABLE_PROMPT_RULE.md`,
  v1 gate unchanged) delivered **18/33** (0.364-0.719), 1 gained and 1 lost;
  repair 5/18 (0.097-0.535); only one of the three tabular cases passes; spend
  $0.006853. v1 stays on record; neither version replaces it. Detail:
  `rebuttal/pilots/20261112_missing_fact_repair/gate_versions_report.md`.
- Answer-equivalence beside exact match (frozen `answer-equiv-v1`, 169 calls,
  $0.021138) is in section 7k: insert 32/59 exact vs 39/59 exact-or-equivalent;
  repair 6/18 vs 8/18; on the same 18 delivered cases insertion is 7/18 exact
  and repair 6/18. Labelled **not validated on MuSiQue-style answers**.
- Injected distortion, preview only: rule v2 (`INJECTED_DISTORTION_RULE_V2.md`)
  frozen before any answer call. The first preview failed review because 5 of 10
  corrupt values were category errors (an organization as a person, a university
  as a role); it is kept in `PREVIEW_FAILED.md` and
  `accepted_preview_failed.json`. The rebuild adds an entity-class constraint
  (`CLASS_MATCH_NOTE.md`, then v2 with `building` split from `place`, and claim
  context for bare numbers): the distractor must have the same class as the gold
  by the frozen class prompt, and the frozen class-match labeller must confirm
  it. The second review rejected cases 8 and 10 on plausibility and cases 1, 2
  and 6 for using a same-class value that never held the office; that reviewed
  set is archived as `preview_v3_reviewed.md` /
  `accepted_preview_v3_reviewed.json`. The refix keeps each control and replaces
  only the distractor: Babe Ruth (career hits), Spadina House (Toronto Gothic
  Revival mansion), Xanana Gusmão (Timor-Leste presidency), Harry Borghouts
  (North Holland King's Commissioner, 2002-2010). The current preview has 10
  accepted cases from 9 unique instances (cases 3 and 9 are one fact on two
  traces, counted once in every instance count), all class-confirmed, in
  `rebuttal/pilots/20261113_injected_distortion/preview.md`; spend to the
  preview is $0.151283 (all attempts). v1 and the intermediate attempts stay on
  record with their cost; paraphrase-then-corrupt replaced exact-word-count
  paraphrasing because the editor could not hit an exact count (0/80
  candidates). The approved >=30 expansion (`EXPANSION_30.md`, frozen before
  any new call) continued the frozen candidate order with the same rule and
  distractor review; every case passes class, class-match, contradiction and
  equal-length checks and is labelled "injected distortion". The pilot now has
  30 accepted cases from 35 further rejected attempts: base 30/30 recorded
  exact, **corrupt 0/30** (95% CI 0.000-0.116), control 23/30 (0.577-0.901),
  repair 24/30 (0.614-0.923); paired repair vs corrupt 24 better / 0 worse,
  control vs corrupt 23/0, repair vs control 2/1. Total $0.185914 against the
  $5 cap. Casa Loma refuses on all three arms including control and repair, so
  its corrupt failure is an edit/volume effect, not the corruption; read the
  other 29 cases. Detail:
  `rebuttal/pilots/20261113_injected_distortion/report.md`.
- Three tracks started 2026-11-13, none waiting for the distortion set:
  (1) coverage and aggregation-failure re-score, rule frozen in
  `rebuttal/pilots/20261113_coverage_rescore/SCORING_RULE.md`, 120 Qwen-235B
  traces, lexical and evidence-only labeller side by side. 119/120 scored after
  the `COVERAGE_AMENDMENT_V1.md` output-budget fix; endpoints use all 120 with
  the unparsed trace counted as not complete and not AF, exact Clopper-Pearson
  CIs: complete coverage lexical 20/120 (10.5-24.6%), labeller 27/120
  (15.4-31.0%); aggregation failure 11/120 (4.7-15.8%) and 18/120 (9.1-22.7%);
  agreement 0.825, kappa 0.447; spend $0.067733. The labeller finds complete
  coverage more often in three protocols and equally in score_ranked (14
  labeller-only vs 7 lexical-only disagreements); the coverage prompt was then
  validated against author carrier labels and **failed**: 70/180 agreement
  (38.9%, 31.7-46.4%), kappa 0.031, prompt complete 58 vs author 156
  (`rebuttal/pilots/20261113_coverage_validation/report.md`, spend $0.037058).
  The labeller column is reported beside the lexical column and is not a
  correction; lexical stands alone. Detail:
  `rebuttal/pilots/20261113_coverage_rescore/report.md`.
  (2) injection screening gate, `rebuttal/pilots/20261113_injection_screening/`.
  The v2 labeller is answer-based and cannot certify a base (negative pilot on
  record, $0.028673); `GATE_AMENDMENT_V1.md` froze an evidence-only gate. On 48
  sampled bases the gate certifies 4/47 parsed (8.5%, 2.4-20.4%) and no
  evidence-fault pair passes (0/5); the hand spot-check agrees on 2/6 bases and
  0/4 evidence pairs, because paragraph-level supports make every loyal but
  compressed board look partial. Total spend $0.046534. This gate is not usable
  for the full wave-2 screen as frozen.
  (3) placement test v1, pre-registration
  `rebuttal/pilots/prereg/PLACEMENT-TEST-v1.md` with its own action manifest
  (78 seed-43 traces). Labelled 78/78 with the validated v2 labeller
  (`labeller_prompt_v2.json`, file sha256 `7f9e2816…8268c6`): DEFECT 65/78
  (73.2-90.8%), CORRECT 12, unparsed 1; hand spot-check 9/10 (exact
  Clopper-Pearson 55.5-99.7%), labels read by the worker without a model. Pilot
  6 traces x 2 arms: target 0/6, hash
  0/6 (descriptive); spend $0.121998 including labels. Detail:
  `rebuttal/pilots/20261113_placement/report.md`. No full run for any track.
- Coverage labeller diagnosis and re-validation (2026-11-13). The v1 prompt
  judged a whole support passage with one unit; the authors label per critical
  fact and allow joint carriers (878 board carriers, 400 joint; 594 cite three
  units), so the units differed. `coverage_prompt_v2.json` (frozen before the
  run) allowed joint carriers, decisive content and record-to-sentence
  conversion; on 25 held-out E1 items (60 author comparisons, not in the
  validation 150) it agrees **18/60** (30.0%, 18.8-43.2%) with kappa **0.060**
  (0.019-0.128), against a pre-frozen pass rule of agreement >= 0.80 and kappa
  >= 0.60: **FAIL**. Prompt complete 8/60 vs author 50/60. Cause: the passages
  are whole documents and `author_complete` requires only the authors' listed
  facts to be carried, so the labeller marks a passage partial for omitting
  document detail the question does not need (Calibration run 2: board has
  "31 December 406" verbatim, v2 asks for the 409/411/585 events). Development
  revisions on the Anchor set (not validation) raise agreement 0.422 -> 0.506
  -> 0.708 and kappa 0.095 -> 0.111 -> 0.275, still below the floor; they were
  written after the held-out result, so they are not a clean held-out test.
  The labeller is not validated and lexical remains the reported figure. Spend
  $0.009452 held-out + $0.128394 development. Detail:
  `rebuttal/pilots/20261113_coverage_labeller_v3/report.md`.
- Injection screening with the decisive-clause gate (amendment frozen before
  the call): same 48 bases / 6 pairs, cap $5. Bases defect-free **13/46**
  (28.3%, 16.0-43.5%), up from 4/47 (8.5%) under the whole-paragraph v1 gate;
  hand agreement 4/6 vs 2/6; evidence-fault pairs 1/5 (20.0%, 0.5-71.6%), the
  aggregation pair reported separately. The two residual false defects mark a
  distractor as required (USS Sanderling in ef980c2a1d19; the 1642 date and
  author-citizenship link in d57d523a9e33). The v1 result stays on record; the
  gate is improved but not reliable. Spend $0.018837. Detail:
  `rebuttal/pilots/20261113_injection_screening_v2/report.md`.
- Placement v2 is a **delivery diagnostic, not a placement result** (amendment
  frozen before the call): v1 inserted the target agent's raw input shard,
  which contained the stored gold answer in 0/6 traces; v2 inserts an oracle
  evidence statement containing the gold in 6/6, identical in both arms.
  Because both arms receive the decisive evidence, the target-vs-hash
  comparison cannot test whether placement brings missing evidence to the
  model; it tests only whether a sufficient corrective unit is used. Target
  exact was **2/6** (33.3%, 4.3-77.7%) and hash **3/6** (50.0%, 11.8-88.2%),
  paired -1 at n=6; this is not a placement effect. The oracle unit is used in
  5/12 arm calls vs 0/12 in v1, consistent with the v1 failure being delivery;
  on III-28 both arms ignore it, and on II-17 the target arm emits a
  degenerate repeated "the" while the hash arm is correct. Spend $0.006502. Detail:
  `rebuttal/pilots/20261113_placement_v2/report.md`.
- Open: wire R2 into the rerun runner; option A constructed substitutions are
  built and ten are shown with source text (12 in total) but are **not** to be
  piloted: a substitution answers a different entity, not a contradiction, so
  the distortion repair arm stays diagnosis-only. Direct insertion is complete
  on the full 59. A combined row-aware prompt + content-token gate is **not
  frozen and not run**; it needs its own rule file, hash, and pilot on the 33
  present cases, reported beside v1 and v2a. MuSiQue answer-equivalence still
  needs an answer-style validation set. The injected-distortion pilot is
  complete on the approved 30-case set (three answer arms; $0.008740 of answer
  calls, $0.185914 total); no full run has started. Qwen stays in the pool.
### Cost ledger (reconciled 2026-11-13)

One row per experiment of this round; each row is the sum of the `cost_usd`
field on the calls logged in that experiment's ledger, so the table reproduces
from the files:

| experiment | ledger | cost-bearing records | cost |
| --- | --- | ---: | ---: |
| coverage re-score | `20261113_coverage_rescore/calls.jsonl` | 147 (120 + 27 retries) | $0.067733 |
| coverage validation | `20261113_coverage_validation/calls.jsonl` | 90 | $0.037058 |
| coverage validation v2 (held-out) | `20261113_coverage_validation_v2/calls.jsonl` | 25 | $0.009452 |
| coverage labeller development (v3-v5) | `20261113_coverage_labeller_v3/calls.jsonl` | 270 | $0.128394 |
| injection screening | `20261113_injection_screening/calls.jsonl` | 121 | $0.046534 |
| injection screening v2 (decisive clause) | `20261113_injection_screening_v2/calls.jsonl` | 60 | $0.018837 |
| placement labels + pilot | `20261113_placement/calls.jsonl` | 90 (78 + 12) | $0.121998 |
| placement v2 (oracle delivery) | `20261113_placement_v2/calls.jsonl` | 12 | $0.006502 |
| injected distortion (preview + answer pilot) | `20261113_injected_distortion/calls.jsonl` | 2154 (preview + 90 answers); preview $0.177174, answers $0.008740 | $0.185914 |
| per-fact labeller (tune + validation + reserve + fresh) | `20261113_per_fact_labeller/calls.jsonl` + `calls_fresh.jsonl` | 766 | $0.259277 |
| per-fact labeller V5 (Gemini reference + Haiku) | `20261113_per_fact_labeller/reference_calls.jsonl` + `calls_v5.jsonl` | 149 | $0.382002 |
| restore-the-source (pilot + full) | `20261113_restore_source/calls.jsonl` | 450 | $0.043831 |
| distortion confirmer validation (Gemini reference) | `20261113_restore_source/confirmer_reference_calls.jsonl` | 144 | $0.250881 |
| main-table redo (per-fact labeller, two checkpoints) | `20261113_main_table_redo/calls.jsonl` | 4800 | $1.402666 |
| restore, reference-gated subset (4 new arms; 90 reused) | `20261113_restore_source/reference_subset_calls.jsonl` | 4 | $0.000558 |
| control stability rerun | `20261113_injected_distortion/control_stability/calls.jsonl` | 7 | $0.000767 |
| placement redo (pilot + expansion + matched, incl. two discarded configurations) | `20261113_placement_redo/calls.jsonl` | 320 | $0.242022 |
| MuSiQue second reader | `20261113_musique_equiv/second_calls.jsonl` | 24 | $0.016886 |
| **sum** | | **9633** | **$3.221313** |

Zero new calls: sharding check, MuSiQue first hand-check, per-fact
re-validation under the carrier target, protocol comparison and method
comparison (all read frozen outputs; $0.000000).

Cumulative by ledger group (every `*.jsonl` under `rebuttal/`, every record
carrying `cost_usd`, whatever its event field):

| group | cost-bearing records | cost |
| --- | ---: | ---: |
| 20261108 pilot round | 1423 | $1.562394 |
| 20261112 round | 2095 | $0.756994 |
| 20261113 round (table above + answer-equivalence-beside $0.021138) | 9802 | $3.242451 |
| `rebuttal/results/batch1` runs | 12480 | $10.715476 |
| **cumulative** | **25815** | **$16.277313** |

Two files, `rebuttal/pilots/20261112_swap_labeller/swaps.jsonl` (25 records,
$0.005423) and `rebuttal/pilots/20261112_swap_labeller/stage2/swaps.jsonl` (176
records, $0.038218), carry the **same per-record costs** as that experiment's
`calls.jsonl`; counting both would double those calls, so their 201 records and
$0.043641 are excluded from the counts above. They are not byte-identical
files: `swaps.jsonl` holds one parsed per-case record, `calls.jsonl` holds the
call log (intent and result). Earlier I reported $13.1987: that sum kept only
records with an `event: result` field, which misses the labeller,
answer-equivalence and constructed-distortion ledgers, and the filename filter
dropped `calls_main`/`calls_validate`/`calls_attempt*`/`repilot_calls.jsonl`.
The reconciled cumulative **$13.484005 replaced the ~$12.0 figure given
earlier** (it is $1.48 higher, from ledgers that were not in the earlier
tally). The second round of 2026-11-13 adds five rows (distortion expansion,
coverage v2 and labeller development, screening v2, placement v2): the
nineteen-row sum is 9633 records and $3.221313, and the cumulative is
**$16.277313 over 25815 records**, against the $100 budget.

Reconciliation of the later runs against their call logs:

| stage / ledger row | records added | cost added |
| --- | ---: | ---: |
| prior cumulative as published | — | $13.995038 |
| four earlier runs (restore full $0.043831 + placement expansion $0.132218 + fresh labeller $0.028203 + placement matched $0.109805), less the two pilots already carried in that baseline (restore $0.008642 + placement $0.059244) | 775 | +$0.246171 |
| cumulative after the four runs, as published | — | $14.241209 (file sum $14.241206) |
| V5: `reference_calls.jsonl` (88 records) $0.365430 + `calls_v5.jsonl` (61 records) $0.016572 | 149 | +$0.382002 |
| cumulative after V5 | 20,867 | $14.623209 (file sum $14.623208) |
| confirmer validation: `confirmer_reference_calls.jsonl` | 144 | +$0.250881 |
| main-table redo: `20261113_main_table_redo/calls.jsonl` | 4,800 | +$1.402666 |
| reference-gated restore subset: `reference_subset_calls.jsonl` | 4 | +$0.000558 |
| cumulative after the later runs | 25,815 | $16.277313 (file sum $16.277313) |

The three later runs add **$1.654105** (confirmer $0.250881 + redo
$1.402666 + subset $0.000558), moving the published cumulative from
$14.623209 to $16.277313; the exact file sums are $14.62320828 and
$16.27731318, a sub-$0.000001 rounding difference.

**$0.628173 is not the V5 increment.** It is $0.246171 (the four earlier runs)
+ $0.382002 (V5): the net since the $13.995038 baseline. From the $14.241209
row the only movement is V5's $0.382002, which reads as $0.382000 when the two
rounded published rows are subtracted ($14.623209 − $14.241209). The $0.000002
gap is rounding in the published figures: the exact pre-V5 file sum is
$14.24120628 and the exact total $14.62320828, while the published rows are
$14.241209 and $14.623209. Their sum with the net ($13.995038 + $0.246171 +
$0.382002) is $14.623211, $0.000003 above the exact total, per-call rounding.
Row check on the files:
pre-run logs 19,884 records/$13.927150 + the five run files 983
records/$0.696058 = 20,867/$14.623208, so the published $13.995038 is
$0.067888 above the pre-run file sum, the two pilots ($0.067886) plus
$0.000002 rounding. The 775 new records are 450 restore + 320 placement (200
expansion + 120 matched) + 64 fresh + 149 V5 minus the 208 pilot records
already counted; the cumulative record count is the file sum (20,867), which
includes 15 zero-cost records outside these runs. The table rows sum
$3.221313; adding answer-equivalence-beside $0.021138 gives the 20261113
group $3.242451. Earlier corrected 2026-11-13: the five-row record sum is 2097, not
the 1997 first written, and the cumulative record count was 18264 after
removing the 201 duplicate records.

Reproduce with: sum `cost_usd` over every record of every `rebuttal/**/*.jsonl`
file except the two `swaps.jsonl` files that repeat per-record costs already in
their `calls.jsonl`.
