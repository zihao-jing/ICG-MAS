# Injected distortion rule, v2 (frozen before any answer call)

Frozen 2026-11-13, after two preview attempts under v1 and before any answer
call. v1 (`INJECTED_DISTORTION_RULE.md`) stays on record with its spent cost and
its rejections. No v1 case was accepted. Every table, sentence, and file label
still says **injected distortion**.

## What changed from v1, and why

v1 required the control editor to rewrite the original unit with **exactly the
corrupted unit's word count**. Over 80 candidates (4 attempts each) the editor
did not hit the count once: it paraphrased to 13-19 words against 11-15-word
targets, and re-asking produced the same length. The control check was
therefore impossible to pass.

v2 gets exact volume matching **by construction** instead of by asking a model
to count words:

1. The editor writes a faithful paraphrase of the original unit (no length
   request). The labeller must return `NO_CONTRADICTION` for
   (original, paraphrase). This paraphrase is the **control**.
2. The corruption is applied to the **control** text, not to the original:
   replace the first whole-token occurrence of the gold answer with a
   same-type, same-normalized-token-count, same-raw-word-count distractor. This
   leaves the word count unchanged, so corrupt and control have identical
   length and differ in exactly one span. The labeller must return
   `CONTRADICTION` for (control, corrupt).
3. The **repair** arm restores the original verbatim unit, as before.

The control and corrupt arms now differ only in the value, and the paraphrase
effect is absorbed by the control arm, which makes corrupt-vs-control the tight
manipulation check. corrupt-vs-repair measures restoration of the original
verbatim unit and also carries the paraphrase difference; both are reported.

## Pool

Unchanged from v1: all Stage 2 traces (800 instances x 3 models, 2,400 traces; the full cohort pool, not only the 59 extraction-omission cases). A candidate needs:

- matcher status `ok` and the trace's recorded answer exact (`answer_correct`);
- exactly one board unit whose text contains the gold answer as an exact
  whole-token substring (so corruption cannot leave the true value elsewhere on
  the board);
- a `faithful` board carrier for that unit in the matcher record.

Candidates are deduplicated by (instance, model, unit id) and ordered by
`digest([43, instance, model, unit_id])`. The seed 43 is fixed for this
experiment.

## Control (faithful paraphrase)

The frozen editor rewrites the target unit so that it states the same claim,
keeps the gold answer verbatim, adds no fact, and changes no value. Deterministic
checks before use:

- the gold appears as a whole-token exact substring;
- the paraphrase differs from the original text;
- the frozen labeller returns `NO_CONTRADICTION` for (original, paraphrase).

No length requirement is imposed on the paraphrase.

## Corruption (deterministic, injected, applied to the control)

Replace the first whole-token occurrence of the gold in the **control** text
with a **distractor value from the same pool**:

- same surface type (number, date, or other text);
- same normalized token count and same raw word count as the gold;
- different normalized tokens from the gold.

The rest of the control text is copied verbatim; the word count is unchanged by
construction. The corrupted control is used only if the frozen contradiction
labeller returns `CONTRADICTION` for (control, corrupt).

## Arms

- **base**: the trace's recorded answer, no call.
- **corrupt**: the board with the target unit text replaced by the corrupted
  control text.
- **control**: the board with the target unit text replaced by the control
  (faithful paraphrase).
- **repair**: the board with the target unit restored to the original verbatim
  text, as in v1.

Answer calls use the frozen relay aggregation system prompt, `max_tokens=1024`,
`temperature=0`, and the trace's own model. Scoring is the frozen exact rule
`answer_f1 == 1.0` with the instance's aliases. No judge and no re-scoring of
main tables.

## Preview and pilot

- Build the first 10 accepted cases and show original, control, and corrupted
  text with both labeller verdicts. **No answer call is made before this
  preview exists.**
- Then pilot the four arms on those 10 cases under a $5 cap.
- Then extend to at least 30 accepted cases from fresh candidates under this
  same rule; the extension is reported with the pilot.
- Every call is logged with a call id, model, token usage, and cost. The cap is
  enforced before each call.

## Reporting

- Counts of cases accepted and rejected, with reasons.
- Exact answers for base, corrupt, control, and repair, each with exact
  Clopper-Pearson 95% intervals; paired corrupt-vs-repair and corrupt-vs-control
  comparisons.
- Per-case table with the original, control, and corrupted text and the answers.
- Cost by stage (preview generation/labelling, pilot answers, extension).

## Interpretation fixed in advance

- A drop from control/repair to corrupt, with corrupt-vs-control isolated to one
  value, is evidence that the injected contradiction changed the answer.
- A corrupt answer that stays exact is not a failure of the manipulation by
  itself; the labeller already confirmed the contradiction. It means the
  answerer did not use the corrupted unit.
- These are injected corruptions, not observed distortions and not constructed
  substitutions. No conclusion about naturally occurring distortion is drawn.
- The 20 absent extraction cases and the missing-fact repair claims are not
  touched by this experiment.