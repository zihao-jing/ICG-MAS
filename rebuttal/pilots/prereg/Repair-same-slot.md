# Audit vs judge repair, same-slot (frozen before any call)

2026-11-15. Cap **$2.00**. Same 30 injected cases.

Both arms take the identical action: quote one sentence from the corrupted agent's evidence and replace only the
corrupted board unit with that quote, then answer with the trace's own model. The arms differ only in the
instruction: the audit arm is told the missing fact; the judge arm is told only the question, since its stored
label names the stage and agent but not the fact. Same prompt shape, same call count, same slot.

Outcome: exact match; McNemar; collateral damage = facts faithful in the board before minus after, per arm, with
Clopper-Pearson intervals on the per-case loss share.
