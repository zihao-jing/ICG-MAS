# Proxy-support granularity fix: before/after on 20 Silo-Bench traces

2026-11-15. Rule `Proxy-support-granularity-fix-v1.md` (sha `f8eae783...`), amended caps (facts 8,000, equivalence 8,000). Both arms use the same rows and the same equivalence prompt; only the facts prompt differs (`proxy_facts_prompt_v1.json` vs `proxy_facts_prompt_v2.json`). Cap $1.5 for the step; spend $0.482973.

| arm | truncated | truncation [95% CI] | equivalence [CP 95% CI] | facts/trace (mean) | facts scored | spend |
| --- | --- | --- | --- | ---: | ---: | ---: |
| before | 1/19 | 5% [0%, 26%] | 0.946 [0.915, 0.967] | 17.4 | 331 | $0.310077 |
| after | 0/19 | 0% [0%, 18%] | 0.991 [0.949, 1.000] | 5.6 | 106 | $0.172896 |

Validation under the frozen rule: **VALIDATES**.

| bar | result |
| --- | --- |
| truncation_after_le_2pct | pass |
| equivalence_non_inferior_5pt | pass |
| equivalence_ci_lower_ge_65 | pass |

## Sample defect, disclosed

The frozen rule said 20 traces (10 that truncated, 10 that did not). The two candidate pools overlap on one row, `summary_exchange|I-05_n5`: it truncated in the old-rule run (equivalence at 2,996 tokens) and was clean under the amended rule in the amended-cap pilot, so it entered both sets. The population therefore holds **19 unique rows**, not 20, and each arm measured it once. The build manifest lists 20 selection slots because the duplicate was not removed when the sets were concatenated. The bars are evaluated on 19 traces.

## What the fix did

- **Granularity**: mean facts per trace fell from 17.4 to 5.6; the largest fact list fell from 98 to 10. The per-element enumeration is gone: the fixed prompt emits one fact per record (an agent array or edge list) instead of one per element.
- **Failure**: the before arm lost 3 of 19 fact sets and 3 equivalence checks; the after arm lost none of either.
- **Equivalence** rose from 0.946 to 0.991. This is the fact the gold check was measuring: with one fact per record against a support that holds the same record, the check almost always returns equivalent. The before rate was diluted by per-element facts that the gold support did not single out.

**Caveat that matters for the population run.** Zero truncation in 19 traces cannot establish a rate at or below 2%: the Clopper-Pearson upper bound is 17.6%. The before arm truncated only 1 of 19 on re-run, because most of its candidate rows had truncated under the old 4,096-token cap, not under the amended one; of its 3 fact-set failures, 2 are parser/shape rejections, not truncation. The amended-cap truncators from the 20-trace pilot (III-22, III-24, II-19) were not all in this draw. So the before/after contrast is clean on granularity and equivalence, and weak on truncation: it takes a population run to estimate that rate.

## Decision

The frozen rule was met on all three bars, so Silo-Bench may run under the fixed proxy as its own population rate, inside the remaining line cap. The truncation bar should be re-checked at the first chunk of that run, on more traces, before the full 208.

## Ledger
Before arm $0.310077, after arm $0.172896, step total $0.482973.
