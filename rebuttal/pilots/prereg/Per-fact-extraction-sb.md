# Prompt v3 at the Silo-Bench extraction pool (frozen before any call)

Date: 2026-11-14. The MuSiQue extraction validation passed (176 facts,
agreement .915 [.863, .952], kappa .780 [.665, .877]). Silo-Bench is a
separate domain and is not covered by that record.

## Population

30 fresh Silo-Bench traces: all base-model traces on the fresh instances,
ordered by `sha256('43|extract-sb|model|instance')`, first 30. Only 16 fresh
instances remain after the exclusions, so model traces, not instances, are the
sampling unit. Excluded: the 69 Silo-Bench presence
validation cases, the E1 anchor, E1 dev/calibration, and the Part B Silo-Bench
traces. Fact list is each agent's gold support shard (`source_supports`).
Checkpoint is the extraction pool. Population hashed before any call.

## Reference and labeller

Reference Gemini 3.6 Flash with the frozen extraction-pool prompt
(`extraction_reference_prompt.json`); labels written and hashed before the
Haiku calls. Labeller Claude Haiku 5.5, prompt v3 unchanged.

## Outcome

Per-fact presence: reference carried = any cited extraction unit; labeller
carried = `status != absent`. Agreement and Cohen's kappa with Clopper-Pearson
and instance-cluster bootstrap CIs (seed 43, 10,000 draws). Pass: agreement
>= 0.80 and kappa >= 0.60. If it fails, the Silo-Bench extraction rows are
exploratory and unvalidated.

## Cost

At most 30 reference and 30 labeller calls. Hard cap **$1.00**.