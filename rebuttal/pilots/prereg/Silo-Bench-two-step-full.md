# Silo-Bench two-step full population run

2026-11-15. Frozen before any call of this run. Cap **$4.00**, chunks of $1 or less. Same prompt version as the
pilot (`proxy_facts_prompt_v3_two_step.json`, sha recorded), same rule for the two steps.

## Population

All 208 Silo-Bench traces of the fixed proxy population. The 20 pilot traces
(`20261115_sb_twostep_pilot/results.jsonl`) are reused unchanged, not re-run; the other 188 are run here.

## Method

Identical to the pilot: selection call, then the frozen v2 facts prompt applied to the selected entries only,
then the frozen equivalence check against gold supports. Audit labels are produced with the frozen per-fact
labeller, as in the v2 population run, so this population's stage rate is comparable to the MuSiQue rate.

## Bars and stop rule

- Truncation: a call reaching its token cap counts as truncated; the run stops when the truncated share
  exceeds **2%**.
- Granularity: mean facts per trace <= 1.2 x the mean gold supports, no trace above 30 facts, no generation
  failure.
- Reported as its own population rate, with Clopper-Pearson intervals, and never pooled with MuSiQue.

## Budget

About $2.4 projected from the pilot ($0.227 for 20 traces). Hard cap $4.00 with call-level enforcement.