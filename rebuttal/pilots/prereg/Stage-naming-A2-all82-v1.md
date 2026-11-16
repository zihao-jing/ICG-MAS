# A2 on all 82 known-cause runs: judge plus audit evidence (frozen before any call)

2026-11-16. Step 46, stage naming. Cap for this step **$1.00** (pilot first: 10 calls, 5 per backbone; the remaining runs start only after the pilot is priced and the priced total fits the cap). Spend is logged to a new ledger, `rebuttal/pilots/20261116_stage_naming/a2_calls_all82.jsonl`; no existing log is deleted.

## Scope

The 82 known-cause runs: 41 cases (30 injected, 11 deleted-fact) × 2 backbones (Qwen judge with the Qwen audit table; Gemini judge with the Gemini audit table). Cohort runs are not in scope.

- **Already done (kept, not re-run):** the 51 runs in `rebuttal/pilots/20261116_stage_naming/a2_results.jsonl` (inputs `a2_inputs.json`, hash in `a2_build_manifest.json`). They are not called again.
- **New in this step:** the remaining 31 runs. These are the 29 runs that the audit did not match (no unique fact at content recall ≥ 0.8, or no carrier record) and the runs whose audit-matched fact appears only in the strict fact table.

## Judge and prompt

Identical to the earlier judge-plus-audit run (rule `Stage-naming-A2-judge-with-audit-v1.md`):
- system prompt and rendered user text from `20261113_attribution_comparison/attribution_prompt_v1.json` (renderer `scripts/b5_attribution_2x2.render_judge`), unchanged;
- the judge is the same backbone as the audit that produced the fact table: Qwen 3 235B (`qwen/qwen3-235b-a22b-2507`) or Gemini 3.6 Flash (`google/gemini-3.6-flash`), both through OpenRouter. No Opus call is made in this step.
- temperature 0, max tokens 2048 (as in the earlier run).

## Audit evidence block

The fact table is whatever the audit produced for the run, taken from `fact_tables_strict.json` (the parser-fixed table, 53 matched runs). The block is appended to the user text:

- **Matched run:** the same block as the earlier run:
  ```
  AUDIT EVIDENCE (the audit's fact table for this run; the fact below is the one the audit matched to the intended fact)
  Fact: <matched audit fact text>
  Holding agent(s): <agent ids from the audit's carriers>
  Audit status: extraction <statuses>; board <statuses>
  ```
- **No matched run (no audit fact matched the intended fact, or no carrier record; the audit's fact table is empty for this purpose):** the block reads
  ```
  AUDIT EVIDENCE (the audit's fact table for this run; the audit matched no fact to the intended fact)
  Fact: none
  Holding agent(s): none
  Audit status: none
  ```

The 51 runs already done used `fact_tables.json` (the earlier table). Any run whose matched fact differs between the two tables is reported with its own note; it is not re-run.

## Outcome and scoring

Judge stage equals the known stage: injected runs known as transmission; deleted runs known as the injected type (extraction or sharding). Share correct over the 82 runs, Wilson 95%.

Reported in one table on the 82 runs: audit (existing, 63/82), LLM judge alone (existing, 68/82), [R1] (existing, 55/82), judge plus audit evidence (51 done + 31 new). Column "names the correct lost fact": audit on the 53 matched runs (49/53, from `a3_score_strict.json`); "No" for the other three methods.

## Bars

None. Descriptive comparison.

## Pilot

10 new calls (the first 5 new Qwen runs and the first 5 new Gemini runs, in sorted order). The full run starts only if the priced remainder fits the $1.00 cap. Every call's cost is logged.
