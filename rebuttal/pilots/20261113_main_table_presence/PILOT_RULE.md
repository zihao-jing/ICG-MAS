# Piece 2 pilot rule: presence-based main-table columns (frozen before any call)

Written 2026-11-13, before the pilot call. Piece 2 redoes the paper's main
table (`iclr2027_paper/items/tables/tab_audit_combined.tex`) with the
validated per-fact **presence** label. The fidelity column is **not** redone
and stays marked unvalidated; V10 is testing that label separately.

## Stage and scope

- Stage: relay checkpoints (extraction pool and shared board).
- Models: Qwen-235B, Mistral-S, Qwen-3.6-Flash, the three models in the paper's
  main table.
- Benchmarks: Silo-Bench (26 n=5 + 26 n=10 traces) and MuSiQue (100 traces).
- Protocols: summary exchange, random relay, score-ranked relay,
  redundancy-aware relay, plus full evidence sharing by construction
  (CR=1, omission=0, complete coverage=1; not sent to the labeller).
- Runs: `results/run_qwen235b_{n5,n10,musique}`, `results/run_mistrals`,
  `results/run_mistrals_n10`, `results/run_musique_mistrals`,
  `results/run_20260523_214416`, `results/run_silobench_n10`,
  `results/run_musique_100`.

## Facts and labels

The fact list is the audit's gold critical units (`source_supports`): MuSiQue
supporting paragraphs and Silo-Bench agent shards, the same units the old
lexical rule scores. The new label is the V9 per-fact presence label (Claude
Haiku 5.5, `per_fact_prompt_v9.json`), validated at extraction (0.968, kappa
0.857) and at the board (carrier 0.952, kappa 0.796) in V9. **Silo-Bench facts
are numeric shard rows and were not part of that validation; its new rows are
exploratory, not validated replacements.**

Old columns are the frozen lexical rule recomputed on the same traces from the
same checkpoints (`align_gold_to_transmitted`: any number/token overlap). Both
instruments see the same facts at the same checkpoint.

## Columns

- critical recall (CR) = facts carried / facts; carried = status present or
  partial. Omission = 1 - CR.
- complete coverage = traces with every fact carried / traces.
- aggregation failure (AF) = complete coverage AND a non-perfect answer /
  traces. The answer is held fixed from the saved run.
- fidelity is reported old-only and marked not validated.

## Pilot and cap

Pilot: two instances per (model, benchmark, n_agents) by hash order
`sha256('43|pres|'+instance)`, all four communication protocols and both
checkpoints. Every call logs intent and result with `cost_usd`; cap **$5.00**.
The report gives old and new columns per cell, the pilot spend, and the
full-run estimate (3 models x 152 traces x (3 relay protocols x 2
checkpoints + summary exchange x 1 board checkpoint) = 3,192 calls). **No
full run starts without approval.**

## CIs

Per-cell proportions get exact Clopper-Pearson 95% CIs in the full run; the
pilot reports counts and rates with small-n caveats. Instance-cluster
bootstrap CIs (seed 43, 2,000 draws) are used for pooled comparisons in the
full run.