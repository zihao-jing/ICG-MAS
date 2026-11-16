# Injected distortion rule (frozen before any call)

Frozen 2026-11-13, before the first paid call. Every table, sentence, and file
label in this experiment says **injected distortion**. This is a new experiment;
it does not replace the constructed-substitution or observed-distortion records.

## Question

If a faithful board unit is corrupted in place so that it contradicts the
source, does restoring the original verbatim unit recover the answer? A
volume-matched, faithful edit controls for the amount of text changed.

## Pool

All Stage 2 traces (800 instances x 3 models, 2,400 traces; the full cohort
pool, not only the 59 extraction-omission cases). A candidate needs:

- matcher status `ok` and the trace's recorded answer exact (`answer_correct`);
- exactly one board unit whose text contains the gold answer as an exact
  substring (so corruption cannot leave the true value elsewhere on the board);
- a `faithful` board carrier for that unit in the matcher record.

Candidates are deduplicated by (instance, model, unit id) and ordered by
`digest([43, instance, model, unit_id])`. The seed 43 is fixed for this
experiment.

## Corruption (deterministic, injected)

Take the target unit text and replace the first exact occurrence of the gold
answer with a **distractor value from the same pool**:

- same surface type (number, date, or other text);
- same normalized token count as the gold;
- different normalized tokens from the gold.

The rest of the unit is copied verbatim. The edit changes no words outside the
gold span, so the corrupted unit has the same word count as the original. The
corrupted unit is used only if the frozen contradiction labeller returns
`CONTRADICTION` for (original, corrupted).

## Control (volume-matched, faithful)

The frozen control editor rewrites the target unit so it states exactly the
same claim, keeps the gold and all its facts, and has exactly the corrupted
unit's word count. Deterministic checks before use:

- word count equals the corrupted unit's;
- the gold is still covered (normalized gold tokens are present);
- the control differs from the original text;
- the frozen contradiction labeller returns `NO_CONTRADICTION` for
  (original, control).

The control therefore matches the corruption in edited-unit volume and in the
number of values changed, but asserts no contradiction.

## Arms

- **base**: the trace's recorded answer, no call.
- **corrupt**: the board with the target unit text replaced by the corrupted
  text.
- **control**: the board with the target unit text replaced by the control
  text.
- **repair**: the board with the target unit restored to the original verbatim
  text. The board is then identical to the base board; the call checks that
  restoration returns the base answer.

Answer calls use the frozen relay aggregation system prompt,
`max_tokens=1024`, `temperature=0`, and the trace's own model. Scoring is the
frozen exact rule `answer_f1 == 1.0` with the instance's aliases. No judge and
no re-scoring of main tables.

## Preview and pilot

- First build the first 10 accepted cases and show original, corrupted, and
  control text with both labeller verdicts. **No answer call is made before
  this preview exists.**
- Then pilot the four arms on those 10 cases under a $5 cap.
- Then extend to at least 30 accepted cases from fresh candidates under this
  same rule; the extension is reported with the pilot.
- Every call is logged with a call id, model, token usage, and cost. The cap is
  enforced before each call.

## Reporting

- Counts of corrupted cases accepted and rejected, with reasons.
- Exact answers for base, corrupt, control, and repair, each with exact
  Clopper-Pearson 95% intervals; paired corrupt-vs-repair and corrupt-vs-control
  comparisons.
- Per-case table with the original, corrupted, and control text and the
  answers.
- Cost by stage (preview generation/labelling, pilot answers, extension).

## Interpretation fixed in advance

- A drop from base/repair to corrupt, with control near base, is evidence that
  the injected contradiction changed the answer and that restoring the source
  recovered it.
- A corrupt answer that stays exact is not a failure of the manipulation by
  itself; the labeller already confirmed the contradiction. It means the
  answerer did not use the corrupted unit.
- These are injected corruptions, not observed distortions and not constructed
  substitutions. No conclusion about naturally occurring distortion is drawn.
- The 20 absent extraction cases and the missing-fact repair claims are not
  touched by this experiment.