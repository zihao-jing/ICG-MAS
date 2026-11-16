# Audit's own diagnosis measured on the 89 known-stage cases (frozen before any call)

Written 2026-11-13, before the build or any matcher call. This replaces the
definitional audit rows in `scripts/method_comparison.py`, which assumed the
audit's answer (`audit = transmission` on injected cases and `audit_new` copied
from the cohort truth). The audit row here is a measured run of the audit's own
diagnosis (`src.audit.sharding_check.diagnose_with_sharding`) on the same 89
cases the Gemini judge is being run on (`cases_v2.json`).

## Cases

`rebuttal/pilots/20261113_attribution_comparison/cases_v2.json`, frozen:
30 injected distortions (known stage transmission) + 59 missing-fact instances
(39 extraction, 20 sharding by the frozen presence rule).

## Cohort cases (59), zero model calls

For each case, load the frozen Stage-2 matcher record for its
`(model, instance_id)` from `rebuttal/results/batch1/expansion_stage2/matcher/`
(the `semantic-dev-v2` matcher record already used by the audit) and run

    diagnose_with_sharding(rec['facts'], rec['carriers'],
                           packages(model)[instance_id], correct=False)

with the package's unchanged clean trace. No new model call: the matcher record
is a frozen audit artefact, and the diagnosis function is the same one the
audit uses. The truth for these cases is the frozen presence rule. The audit's
input-presence check implements the same 0.8/0.4 content-recall rule, so this
cohort row is a **consistency check against a shared rule**, not an independent
accuracy estimate; it is still measured per case, not copied.

## Injected cases (30), matcher calls

Take the frozen package for `(model, instance_id)`; replace the text of the
accepted `unit_id` with the accepted corrupt text in the **board** and the
corresponding **transmission** unit; leave sources and question unchanged. Run
the audit's own matcher end to end:

    match_trace(ledger, key, adapt(corrupted_trace),
                'qwen/qwen3-235b-a22b-2507')

(`src.audit.matcher_v2`, temperature 0, max 4096, at most 2 retries per logical
call, all attempts logged by `CallLedger`), then

    diagnose_with_sharding(result['facts'], result['carriers'],
                           corrupted_trace, correct=False)

The truth is transmission by construction (the accepted case corrupted a
faithful board unit); the audit must reach it from the corrupted trace alone.
No gold answer is shown to the matcher, and no label is repaired.

## Frozen stage mapping

| audit label | stage |
| --- | --- |
| `extraction_omission` | extraction |
| `sharding_omission` | sharding |
| `mixed_sharding_extraction` | sharding |
| `selection_omission` | transmission |
| `partial` | transmission |
| `distortion` | transmission |
| `candidate_aggregation` | aggregation |
| `correct_control` | excluded (no failure stage) |
| `uncertain` | excluded (no stage decided) |

`mixed_sharding_extraction` is mapped to sharding because at least one chosen
fact is absent from the input shard; the mixed label is also counted and shown
separately in the confusion table. Excluded cases are removed from the
denominator and reported.

## Caps and reporting

Matcher cap **$0.50** (estimated $0.05 for 60 calls at Qwen-235B prices), hard
stop checked after every case; every call logs intent and result with
`cost_usd`. Report per population and overall accuracy with exact
Clopper-Pearson 95% CIs, known-stage x audit-stage confusion, exclusions, and
cost. The Gemini judge row is reported beside it from its own frozen run; the
lexical checkpoint-drop baseline stays as a measured baseline.