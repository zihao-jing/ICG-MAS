# Published-style stage attribution on known-stage cases

Rule `ATTRIBUTION_RULE_V2.md` (sha256 `dc7414b4875d`), prompt `attribution_prompt_v1.json` (sha256 `acdf6da0a7e7`), Gemini 3.6 Flash. 89 of 89 cases scored; spend **$0.293962**, caps $0.50 pilot / $2.00 full.

| population | known stage | n | judge correct | accuracy [95% CI] |
| --- | --- | ---: | ---: | --- |
| injected | transmission | 30 | 24 | 24/30 = 0.800 [0.614, 0.923] |
| cohort | extraction/sharding | 59 | 43 | 43/59 = 0.729 [0.597, 0.836] |

**Overall judge stage accuracy 67/89 = 0.753 [0.650, 0.838]**.

| known \ judge | sharding | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: | ---: |
| sharding | 19 | 0 | 0 | 1 |
| extraction | 15 | 24 | 0 | 0 |
| transmission | 6 | 0 | 24 | 0 |

## Comparison (measured on the same 89 cases)

| method | injected (n=30) | cohort (n=59) | overall (n=89) |
| --- | --- | --- | --- |
| Who&When-style judge (Gemini 3.6 Flash) | 24/30 = 0.800 [0.614, 0.923] | 43/59 = 0.729 [0.597, 0.836] | 67/89 = 0.753 [0.650, 0.838] |
| audit, measured (Qwen-235B matcher + diagnosis) | 26/30 = 0.867 [0.693, 0.962] | 44/59 = 0.746 [0.616, 0.850] | 70/89 = 0.787 [0.687, 0.866] |
| lexical checkpoint-drop baseline | 0/30 = 0.000 [0.000, 0.116] | 39/59 = 0.661 [0.526, 0.779] | 39/89 = 0.438 [0.333, 0.547] |

The audit row is a **real run** of the audit's own diagnosis: for the 59 cohort cases, `diagnose_with_sharding` on the frozen Stage-2 matcher records (zero calls); for the 30 injected cases, the audit matcher (`matcher_v2`, Qwen-235B) rerun on the corrupted board plus the same diagnosis (spend $0.025289, cap $0.50). The earlier definitional audit row (30/30, 59/59) is dropped; always-aggregation is dropped as definitional.

Caveat: the cohort truth is the frozen input-presence rule and the audit uses the same 0.8/0.4 content-recall check, so its 44/59 cohort figure is a consistency check against a shared rule, not independent accuracy; 14 of its 15 cohort errors are cases where the frozen label is a manual adjudication over that rule. The injected 26/30 row is independent: truth by construction, audit sees only the corrupted trace.

The judge is an LLM with a frozen prompt, not the published method's released code; the stage vocabulary is the audit's, extended with sharding. The comparison is descriptive.

