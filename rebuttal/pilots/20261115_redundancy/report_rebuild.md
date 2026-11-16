# Redundancy rebuild: protection and crowding-out at k = 3

2026-11-15. 30 MuSiQue traces re-extracted at up to 5 units per agent (k = 3 now strictly below the unit count);
re-extraction spend **$0.01056**, cap $0.20. Selection uses the paper's lexical Jaccard penalty (rho = .5).

| protocol | Red [95% CI] | UB [95% CI] |
|---|---:|---:|
| random | .200 [.168, .232] | .061 [.029, .094] |
| score-ranked | .217 [.185, .248] | .050 [.019, .081] |
| redundancy-aware | .185 [.163, .207] | .044 [.014, .075] |

**No protection claim.** The intervals overlap across all three protocols; the only statement the data support is
the point ordering: redundancy-aware has the lowest mean Red, score-ranked the highest, random in between. A
difference of this size at n = 30 is not established.

**Crowding-out fails.** Useful budget by Red quartile is .033, .056, .033, .067 — no decline with redundancy.

**Deviation.** Per-unit relevance scores were replaced by a lexical question-overlap score so the rebuild stayed
inside the $0.20 cap; the paper's LLM scorer was not called. Selection therefore differs from the paper's in its
score term as well as in the rebuilt unit set. The earlier k = 2 run on stored units is exploratory.

## Ledger
$0.01056.
