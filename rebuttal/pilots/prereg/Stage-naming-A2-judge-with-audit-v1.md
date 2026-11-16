# A2: the judge with the audit's fact table as extra input (frozen before any A2 call)

2026-11-16. Step 39, stage naming. Cap for this run **$10.00** (pilot first; the full run starts only after the pilot is priced). Scope: the 51 matched runs of the fact tables (`rebuttal/pilots/20261116_stage_naming/fact_tables.json`, rule `Stage-naming-A3-fact-named-v1.md`). Runs excluded there (no unique fact match, or no carrier record) are not in this run.

## Arms

1. **Judge alone** (existing outputs, not re-run): the judge outputs already stored for the same runs. Injected: `20261115_b5_attribution_2x2/judge_qwen.json` (Qwen) and `20261113_attribution_comparison/results_v2.json` (Gemini). Deleted: `judge_qwen` / `judge_gemini` in `20261115_injection_amendA3/results.json`. Reported on the 51 matched runs and on all 82 runs.
2. **Judge + audit evidence** (new calls): the same judge prompt (`20261113_attribution_comparison/attribution_prompt_v1.json`, system and rendered user text unchanged) with one block appended to the user text:

```
AUDIT EVIDENCE (the audit's fact table for this run; the fact below is the one the audit matched to the intended fact)
Fact: <audit fact text>
Holding agent(s): <agent ids from the audit's carriers>
Audit status: extraction <statuses>; board <statuses>
```

The block is rendered from `fact_tables.json` only. For each run the judge is the same backbone as the audit that produced the table: Qwen judge with the Qwen audit table, Gemini judge with the Gemini audit table.

Trace for each run: injected runs use `corrupted(case, accepted)` from `scripts/audit_diagnosis_89.py`; deleted-fact runs use `make_case` replayed from the logged calls (no new spend in the replay test). Both are the traces the existing judge saw.

## Outcome

Judge stage equals the known stage (injected: transmission; deleted: the injected type, extraction or sharding). Share correct per arm, Wilson 95%, paired McNemar exact for arm 1 vs arm 2 on the same runs.

## Bars

None. This is a descriptive comparison, reported in both directions.

## Pilot

5 runs per backbone (10 calls), first in the sorted order of the 51 runs. Priced from the pilot's logged cost; the full run is started only if the priced total for the remaining runs fits within the $10 cap.

## Logs

Every call is logged to `rebuttal/pilots/20261116_stage_naming/a2_calls.jsonl` with tokens and cost. No log is deleted.
