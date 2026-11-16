# Audit misses on the 82 known-cause runs, by cause ($0)

2026-11-16. No model calls. Sources (all read, none rescored):
- Injected (corrupted-message) runs, 30 cases x 2 backbones: `rebuttal/pilots/20261115_b5_attribution_2x2/audit_a_gemini.json` (Gemini, old rule), `rebuttal/pilots/20261115_b5_qwen_design_a/results.json` (Qwen, old rule). Known stage = transmission by construction.
- Deleted-fact runs, 11 cases x 2 backbones: `rebuttal/pilots/20261115_injection_amendA3/results.json` (`methods`, `audit_*_old`), restricted to the 11 kept cases in `rebuttal/pilots/20261115_injection_amendA3/keep_rule_decisions.md` (step 10c keep set).

Audit = old token-overlap rule, the rule used in the response's 63/82 count (injected counts are identical under the old and new rule; deleted counts use the old cells).

## Misses (19 of 82)

| Audit stage given | Known stage | Injected (of 60 runs) | Deleted (of 22 runs) | Total |
|---|---|---:|---:|---:|
| aggregation | transmission (inj) / extraction or sharding (del) | 4 | 4 | 8 |
| extraction | transmission | 5 | 0 | 5 |
| transmission | extraction (1) / sharding (2) | 0 | 3 | 3 |
| sharding | transmission | 1 | 0 | 1 |
| no stage (uncertain) | transmission | 2 | 0 | 2 |
| **Total** | | **12** | **7** | **19** |

Deleted-fact detail: extraction -> aggregation 2 (one per backbone, case 3hop2__655849); extraction -> transmission 1 (Qwen, 2hop__89403); sharding -> transmission 2 (Qwen, 3hop2__668732 and 2hop__33288); sharding -> aggregation 2 (one per backbone, 2hop__20256).

## What the classes mean

- **aggregation** (8): the audit found the fact carried to the answer stage, and the wrong answer is attributed to aggregation. This is the audit's answer-side route.
- **extraction** (5, all injected): the audit's pool check puts the corrupted fact outside the extraction pool, so the route is extraction, not transmission. This is the cost of the token-overlap presence check on corrupted text.
- **transmission** (3, all deleted): the audit found the deleted fact still on the board, so it routes to transmission.
- **sharding** (1) and **no stage** (2): one injected case routed to sharding, two Gemini cases returned no stage.

Per-case mechanism (which fact status drove each route) is not recorded in these files; the classes above are routing outcomes, not confirmed mechanisms.
