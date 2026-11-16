# Frozen rule: method comparison on known-stage cases (item 6)

Written 2026-11-13 before the comparison. Zero model calls; reads frozen
matcher records, traces and the injected-distortion cases. Stages: sharding,
extraction, relay checkpoint (transmission), final aggregation.

## Cases with a known faulty stage

1. **Injected distortions** (30, `20261113_injected_distortion/accepted.json`):
   one faithful board unit was replaced by a same-class, same-shape corruption;
   the faulty stage is the **relay checkpoint** (transmission), by construction.
2. **Missing-fact cohort** (59 unique instances,
   `20261112_missing_fact_repair/presence.json`): the critical fact is absent
   from the extraction pool. The stage below that is fixed by the frozen
   presence rule: **extraction** when the fact is present or partial in the
   source shard (39 instances), **sharding** when it is absent from every
   source shard (20 instances). This is the truth used here, because item 9
   established that a fact absent from the shard cannot be an extraction loss.

The audit's prediction is its frozen diagnosis: transmission for the injected
cases (the corrupted unit is the diagnosis by construction), and the item-9
labels for the cohort. The cohort is also scored against the older truth
"extraction for all 59" to show the effect of the input check.

## Attribution baseline (proposed before building)

A **lexical checkpoint-drop** baseline: it uses the same three checkpoints and
gold supports as the audit but no critical-fact or carrier labels.

- shard coverage is 1.000 by construction (the gold supports are the shards).
- extraction coverage = mean over gold supports of the best token recall to
  any extraction unit; board coverage = the same against board units.
- drop1 = 1 - extraction coverage; drop2 = extraction coverage - board
  coverage.
- predict **extraction** if drop1 >= 0.05 and drop1 >= drop2; otherwise
  **transmission** if drop2 >= 0.05; otherwise **aggregation**.

Reference baseline: **always aggregation** (blame the final stage), the common
last-stage heuristic. Both are compared with the audit on the same cases.

The baseline cannot name **sharding** (it has no input-presence check); on the
cohort it therefore scores the 20 sharding cases wrong. That is the comparison,
not a bug.

## Reported quantities

Stage accuracy for the audit and each baseline, with exact 95% Clopper-Pearson
intervals, per case family and pooled where meaningful. The injected audit
accuracy is by construction and is labelled as such; the cohort audit accuracy
depends on the item-9 check and is labelled. No paper edit, no commit, no call.