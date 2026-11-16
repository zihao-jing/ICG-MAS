# Injection screening with a labeller gate — rule frozen before any call

Date frozen: 2026-11-13. Pilot only; no full run until review.

## Question

Before an injection experiment, every base trace must be defect-free and every
injected fault must actually be present. This pilot tests whether the frozen
evidence-flow labeller can serve as that gate.

## Population

- **Bases.** The 219 wave-2 MuSiQue bases in
  `rebuttal/pilots/20261110_e2a_wave2/judge_input_traces.jsonl` (seed 43/44,
  three model families). Pilot sample: 8 per (seed, family) cell, 48 total,
  chosen by ascending `sha256("43|item_id")` within each cell.
- **Injected pairs.** The six built before/after items in
  `rebuttal/annotation/packets_20261110/E2A_wave2_spot/packet.jsonl`
  (`declared_edit` names the injected fault).

## Gate

Frozen prompt `labeller_prompt_v2.json` (sha256 recorded in its manifest;
Claude Haiku 5.5, temperature 0), rendered by `scripts.pilot_llm_labeller.render`.

- A base passes when the labeller returns `CORRECT` (no critical fact absent
  or distorted at the pool or board). `DEFECT` or unparsed output fails.
- An injected pair passes when the before trace is `CORRECT` and the after
  trace is `DEFECT`. A before trace that is already `DEFECT` fails the base
  check; an after trace that stays `CORRECT` fails the fault check.

The label is evidence flow only. The base's exact-match correctness is known
by construction and is not re-scored here.

## Spot-check

One base per cell (6) and all six pairs (12 items) are read by hand against the
rendered content. For each item the hand label is recorded (`defect_free` /
`defect_present` with the unit or fact that shows it), and agreement with the
labeller is reported. The spot-check is a sample check, not a second full run.

## Endpoints

- base pass rate, exact Clopper–Pearson 95% CI;
- pairs: before and after verdicts, pass count;
- spot-check agreement on the 12 items, disagreements listed;
- cost, every call logged with intent and result.

## Guardrails

Pilot cap **$5**, hard stop before any call that would exceed it; one attempt
per item; temperature 0; prompt, rule and sample hashed into
`run_manifest.json` before the first call. No injections are generated here,
no base is repaired, and no full run or paper edit is made.