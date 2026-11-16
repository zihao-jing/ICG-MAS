# Audit's own diagnosis measured on the 89 known-stage cases

Rule `AUDIT_DIAGNOSIS_RULE.md` (sha256 `e4a85b40bfe0`), matcher `matcher_config.json` (Qwen-235B, `semantic-dev-v2`, prompt `3d97341d410e`), cases `cases_v2.json`. Cohort (59): frozen Stage-2 matcher record + `diagnose_with_sharding`, zero calls. Injected (30): audit matcher rerun on the corrupted board; spend **$0.025289**, cap $0.50.

| population | known stage | n | audit correct | accuracy [95% CI] | excluded |
| --- | --- | ---: | ---: | --- | ---: |
| injected | transmission | 30 | 26 | 26/30 = 0.867 [0.693, 0.962] | 0 |
| cohort | extraction/sharding | 59 | 44 | 44/59 = 0.746 [0.616, 0.850] | 0 |

**Overall audit stage accuracy 70/89 = 0.787 [0.687, 0.866]** (excluded 0).

| known \ audit | sharding | extraction | transmission | aggregation | excluded |
| --- | ---: | ---: | ---: | ---: | ---: |
| sharding | 5 | 15 | 0 | 0 | 0 |
| extraction | 0 | 39 | 0 | 0 | 0 |
| transmission | 0 | 2 | 26 | 2 | 0 |

## Audit labels behind the stage mapping

| audit label | label count | mapped stage |
| --- | ---: | --- |
| `candidate_aggregation` | 2 | aggregation |
| `distortion` | 23 | transmission |
| `extraction_omission` | 56 | extraction |
| `partial` | 2 | transmission |
| `selection_omission` | 1 | transmission |
| `sharding_omission` | 5 | sharding |

## Errors

Injected errors (4): two cases the audit labels `candidate_aggregation` (the corrupted unit is not on the chosen support path, or an alternative faithful carrier remains), and two cases it labels `extraction_omission` (a different fact in the chosen support set is missing from the extraction pool, so the corrupted board unit is not the diagnosed fault). The audit sees only the corrupted trace; the truth is transmission by construction.

Cohort errors (15 of 20 sharding-truth cases): the audit labels them `extraction_omission` because its input-presence check uses the automatic 0.8/0.4 content-recall rule. Fourteen of the 15 are cases where the frozen cohort label is a **manual adjudication** over that automatic rule (a sentence credits the fact at >=0.8 recall but does not state the relation); the audit has no access to those adjudications. The remaining case (`2hop__342746_679190`) is automatic. This is why the cohort row is a consistency check, not independent accuracy.


Cohort note: the audit's input-presence check and the cohort truth share the same 0.8/0.4 content-recall rule, so the cohort row is a consistency check against a shared rule, not an independent accuracy estimate. The injected row is independent: the truth is set by construction and the audit sees only the corrupted trace. Errors are listed per case in `audit_results.json` (`audit_label`, `facts`).

