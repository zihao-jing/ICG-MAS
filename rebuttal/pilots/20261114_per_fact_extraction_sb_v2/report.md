# Prompt v4 at the Silo-Bench extraction pool

Rule `Per-fact-extraction-sb-v2.md` (sha256 `ae322beb91ca`); reference labels `40de34043b7b`, frozen before the Haiku calls. Prompt v4 (system `47cd9e47…`). 30 fresh Silo-Bench traces, 18 instances, 210 facts. Spend $0.361262, cap $1.00.

**Per-fact presence agreement 197/210 = 0.938** (instance-cluster 95% CI 0.850-1.000); kappa **0.553** (cluster 95% CI 0.000-1.000) - **FAIL** against 0.80/0.60.

CIs resample the 18 instances, not the 30 traces.
