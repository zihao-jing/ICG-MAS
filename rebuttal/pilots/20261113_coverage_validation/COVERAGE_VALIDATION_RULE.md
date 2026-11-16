# Coverage prompt validation against the author labels

Frozen 2026-11-13, before any call. This validates `coverage_prompt_v1.json`
(the evidence-only prompt used in the Track 1 pilot) against the author labels
that already exist; it does not change the prompt.

## Population

The 90 E1 traces in `rebuttal/pilots/20261112_labeller/validation_150.jsonl`
whose two authors returned carrier labels (E1 anchor and dev returns under
`rebuttal/annotation/labelling_20261108/returns/`). SB is excluded: its carrier
labels are a flat unit list with no checkpoint or fidelity field, so an
author-side coverage label cannot be derived from them.

## Author-side coverage (fixed before calls)

For one author and one trace, coverage is **complete** iff every critical fact
in that author's `critical_facts_json` has at least one `carriers_json` entry
with `checkpoint == "board"` and `fidelity == "faithful"`. No critical fact
in this set lacks a board entry; a fact with only partial, distorted or absent
board carriers makes the trace incomplete. A trace is scored once per author
(180 comparisons); authors are reported separately and pooled.

## Prompt-side coverage

`coverage_prompt_v1.json`, unchanged, system sha256 recorded in
`run_manifest.json`, Claude Haiku 5.5, temperature 0, `max_tokens` 2000.
Supports and board rendered by the same function used in the Track 1 pilot.
The prompt's `complete` (every support `present` at the board) is the
statistic compared to the author-side label.

## Endpoints

Raw agreement, Cohen kappa, exact Clopper–Pearson 95% CI on agreement, prompt
and author complete rates, and every disagreement with the prompt's per-support
reason. Cap **$1**, one attempt per trace, every call logged with intent and
result. No prompt edit after seeing results; if agreement is below 0.80 the
labeller endpoints of the Track 1 report are marked **not validated** and the
lexical endpoints stand alone.

No full run, no paper edit, no commit.
