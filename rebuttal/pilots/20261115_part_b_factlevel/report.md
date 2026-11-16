# Part B fact-level labels: presence rule vs Opus reference

2026-11-15. Rule `Part-B-factlevel.md` (sha `5d4192d4`), Opus 5.5 through the CLI, stratified sample of 12 facts (3 per
predicted stage, seed 43). API-equivalent **$0.603444** (CLI $0.206568), cap $1.00.

## Result: the presence rule is not validated

Presence rule vs Opus: **9/12 = .750** (Wilson [.468, .911] — wide at n = 12), below the .80 bar. The per-fact
method accuracies therefore are not reported; the attempt is a negative on the reference check, not on the methods.

The three disagreements:

| case | fact | rule | Opus |
| --- | --- | --- | --- |
| `coh/gemma31b/3hop1__662618_339990_54675` | f7 | sharding | aggregation |
| `coh/gpt4omini/3hop1__593288_720914_41132` | f3 | sharding | aggregation |
| `coh/gpt4omini/2hop__71294_494136` | f2 | extraction | sharding |

Two are the rule calling a fact sharding where the fact is present once the whole trace is read (Opus aggregation);
one is the rule calling extraction where Opus calls sharding. The first two are the whole-support lexical test
firing on a fact that the owning agent's shard restates in different words.

## Separate, from the $0 counts

On the 30 traces of the set-label validation, 18/30 = 60% have a reference set naming more than one stage
(sizes: 1 stage in 12, 2 in 11, 3 in 6, 4 in 1); on the 89 traces, 75/89 = 84% contain facts whose first missing
checkpoint differs. That is the multi-stage population description; it is not evidence about either method.

## Ledger

API-equivalent $0.603444; CLI $0.206568.
