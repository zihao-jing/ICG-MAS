# Silo-Bench presence validation (rule frozen before any call)

Written 2026-11-13, before the build or any call. The Silo-Bench rows of the
main table stay out until this passes: the V9 presence label was validated on
MuSiQue text facts only, and the piece-2 pilot showed Silo-Bench completeness
jumping to 1.000, which may be over-crediting.

## Population

Silo-Bench traces from the three main-table models (`run_qwen235b_n5`,
`run_qwen235b_n10`, `run_mistrals`, `run_mistrals_n10`,
`run_20260523_214416`, `run_silobench_n10`) and the four communication
protocols. One trace per (model, n_agents, protocol) chosen by hash order
`sha256('43|sbval|'+model+'|'+n_agents+'|'+protocol+'|'+instance)` among
instances not used in the piece-2 pilot (II-15_n5, II-18_n10, II-19_n5,
III-23_n10) and not in the 30-instance E1 anchor. This gives **24 board cases**
(5 facts for n=5, 10 for n=10). Population is frozen in `population.json` and
the build manifest before the first reference call.

## Facts and label

A fact is one agent's shard (a numeric table row), the same unit the old
lexical rule scores. The prompt text is the V9 label text (V10 prompt
versions); the question is shown. Only the **board checkpoint** is validated
(the stage the table reports). Presence = status present or partial.

## Runs

- Reference: Gemini 3.6 Flash, `reference_prompt.json`, temperature 0,
  reasoning enabled, max 8192, cap **$2.00**. Labels freeze to
  `reference_labels.json` before any Haiku call; hash in the reference
  manifest.
- Labeller: Claude Haiku 5.5, `labeller_prompt.json`, temperature 0,
  max 4096, cap **$0.50**. Every call logs intent and result with cost.

## Bar

Presence agreement >= **0.80** and Cohen kappa >= **0.60**, each with a 95% CI
(exact Clopper-Pearson for agreement; instance-cluster bootstrap for kappa,
seed 43, 10,000 draws). A failure keeps Silo-Bench out of the table and is
reported with its cause.