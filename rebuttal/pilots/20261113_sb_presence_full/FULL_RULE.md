# Full Silo-Bench presence run with the validated label (frozen before any call)

Written 2026-11-13, before the build or any call. This is the Silo-Bench half
of the piece-2 table redo. It applies the presence label validated on
Silo-Bench board cases in `20261113_sb_presence_validation` (first 24 cases
plus the 48-case expansion; combined result in `report_v2.md`) and the same
labeller prompt/system as the MuSiQue run (`per_fact_prompt_v9.json` text,
frozen; the Silo-Bench validation used the identical system text).

Population: all 1,092 Silo-Bench rows already frozen in
`20261113_main_table_presence/population.json` (3 models x 2 agent counts x 4
protocols, extraction pool and shared board; 624 board rows, 468 extraction
rows). No new relay run: traces, facts and checkpoint entries are reused. Old
columns are the frozen lexical rule on the same entries; new columns are the
per-fact presence label (Claude Haiku 5.5, temperature 0, max 4096). The
validated label is **central-claim presence**; every coverage cell carries the
qualifier "central-claim presence; lower bound on loss and omission." No full
coverage claim is made.

The label was validated against Gemini 3.6 Flash reference labels on
Silo-Bench board cases (agreement and kappa with 95% CIs reported in the
validation folder); it is not author ground truth. Fidelity/Dist is not redone
here and stays unvalidated.

Cap **$5.00**; every call logs intent and result with `cost_usd`; a hard stop
checked before each chunk. Analysis frozen: per-cell old/new critical recall,
omission, completeness and aggregation failure; pooled and per-cell 95% CIs by
instance-cluster bootstrap (2,000 draws, seed 43), instance = `instance_id`.
Rows enter the table only after the validation expansion narrowed the kappa
interval and that result is reported.