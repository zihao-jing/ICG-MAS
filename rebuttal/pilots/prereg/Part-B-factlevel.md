# Part B fact-level design (frozen before any call)

2026-11-15. Cap **$1.00** API-equivalent.

Label for each failed critical fact = the first checkpoint where it is missing, in order: shard (absent from the
owning agent's input), extraction pool, transmitted board, final answer. Presence at each checkpoint uses the
already validated content-recall rule (lexical recall >= 0.8 after stop-word removal).

Reference: Opus 5.5 through the local CLI, same prompt, on a stratified sample of 12 facts (3 per predicted
stage, seed 43). Agreement between the presence rule and Opus is reported; per-fact method accuracy is reported
only if that agreement supports the rule. Each method is scored per fact: correct if its named stage equals the
fact's stage. Bars on that per-fact accuracy remain .80 / .60.
