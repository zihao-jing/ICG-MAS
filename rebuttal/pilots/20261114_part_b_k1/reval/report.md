# Part B judge v2 revalidation: fails; fallback to option A

Prompt v2: `rebuttal/judge/E2-judge-v2.json`, system SHA-256
`830249e0da005bc06644d3075abf6793d5835afc5caeb1a7e7d0d7a7c1920bbe`, frozen
before any call. The four class rules were written from the six v1
disagreements (`../disagreements.md`) before the prompt was changed.

## Validation set

30 fresh wrong k = 1 traces: 84 fresh traces built (64 that were correct at
k = 3, plus the 20 wrong traces left after the 126 + 30 draw); 47 were wrong
at k = 1, and 30 were drawn by SHA. Disjoint from the 126 main, the 30 earlier
validation traces, the 89 known-stage cases and the 7-trace E2-C casebook.

## Result

Opus 5.5: 30/30 valid, **$1.046256** (cap $2.00). Gemini 3.6 Flash: 30/30
valid, **$0.277310**.

| Quantity | Value |
|---|---|
| Agreement | **.800 [.667, .933]** |
| Cohen's kappa | **.545 [.225, .831]** |
| Bar | agreement ≥ .80, kappa ≥ .60 |
| Verdict | **fails (kappa)** |

The first Gemini attempt used `max_tokens=1500` and truncated 18 of 30
outputs ($0.256130); it is an engineering failure, not a prompt result, and
was rerun at 2500 without changing the prompt.

## Fallback: option A

Part B is reported as **agreement with an unvalidated judge**. The kappa and
its CI are shown, and the Part B claim is left out of the headline. No further
Part B spend. Batch 1 labels stay on record, labelled **unvalidated**; they
are not relabelled and batches 2 and 3 are not run.