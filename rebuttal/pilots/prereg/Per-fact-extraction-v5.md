# Prompt v3 at extraction: independent-reference validation (frozen before any call)

Date: 2026-11-14. The board checkpoint was validated separately (per-fact
carrier agreement .881 [.823, .925]). This rule validates the same prompt v3
at the **extraction pool**, which E3 uses and which has no validation yet.

## Population

The 60 MuSiQue traces of `20261113_per_fact_labeller/population_v5.json`
(never used in labeller development, one model per instance by
`sha256('43|v5|model|instance')`). Same instances and models, same matcher
fact list; the checkpoint is the **extraction pool** instead of the board.
Population is rewritten and hashed before any call.

## Reference and labeller

Reference: Gemini 3.6 Flash, new frozen prompt
`extraction_reference_prompt.json` (the board prompt with the checkpoint name
changed to the extraction pool; system hash recorded before the first call).
It is blind to the labeller. Reference labels are written and hashed before
the first Haiku call.

Labeller: Claude Haiku 5.5, prompt v3 unchanged, one call per trace.

## Outcome

Unit of analysis is the **fact**, not the trace: for every fact, reference
carried = any cited extraction unit; labeller carried = `status != absent`.
Agreement and Cohen's kappa on that binary, with exact Clopper-Pearson
interval for agreement and instance-cluster bootstrap for kappa (seed 43,
10,000 draws). Pass: agreement >= 0.80 and kappa >= 0.60.

Trace-level complete agreement is reported beside it but is not the pass
criterion, because 60 traces make it degenerate.

## Cost

At most 60 reference and 60 labeller calls. Hard cap **$1.00**, every call
logged. Stop and report at the cap.