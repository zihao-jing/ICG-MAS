# Sub-claim presence rule B: validation rule (frozen before any call)

Written 2026-11-14, before the build or any reference/labeller call. This
validates rule B (the pilot rule `20261113_subclaim_presence_pilot/
SUB_CLAIM_RULE.md` and its prompt, unchanged) on **fresh MuSiQue board cases**
against a stronger AI reference, then — only if it passes — applies B to the
full table set as a stricter column beside central-claim A. It does not replace
A.

## Cases

60 board-checkpoint rows from the frozen full MuSiQue presence population
(`20261113_musique_presence_full`), 30 where A gives completeness 1.000 and 30
where it does not, one row per distinct instance, chosen by
`sha256('43|bval|'+key)` within each stratum. Excluded: the 20 B-pilot
instance IDs and anything outside the frozen population. The validation rows
are therefore not the rows used to design or price B.

## Models and freezing

Reference **Gemini 3.6 Flash** and labeller **Claude Haiku 5.5**, both with the
frozen B prompt (`subclaim_prompt.json`, sha256 recorded), temperature 0,
max 8192. Reference labels are written and hashed **before** any Haiku call;
the Haiku run asserts the reference hash. The two models share the task text;
the reference is an independent stronger model, not author ground truth.

## Bar and analysis

Presence is binary: `status != absent`. Agreement with exact Clopper-Pearson
95% CI; Cohen's kappa with instance-cluster bootstrap CI (10,000 draws, seed
43). **PASS** requires point-estimate agreement >= 0.80 and kappa >= 0.60; the
kappa lower bound is reported beside the point estimate. The by-stratum
(A-complete vs not) result is reported. If it fails, B stays a pilot, the
cause is reported, and the full run is not started.

## Full run on PASS

If it passes, run B on all 2,100 frozen MuSiQue rows (estimated ~$2.88 from the
pilot price), cap $5.00, and add a `presence B (sub-claim)` column next to
central-claim A. Every B coverage cell carries the same bound wording: coverage
and critical recall are upper bounds; loss and omission are lower bounds. A is
not replaced, and no full-coverage claim is made for either.