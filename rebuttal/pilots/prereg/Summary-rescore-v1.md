# Summary-exchange strict fidelity re-score, v1 — frozen before any call

2026-11-15. Cap **$0.25**. Re-scores the summary-exchange distortion and omission figures with the validated
strict-fidelity prompt, so the summary figures use the same label as the relay figures.

## Population

Qwen-235B Silo-Bench summary-exchange runs, n = 5 (`results/run_qwen235b_n5`) and n = 10 (`results/run_qwen235b_n10`).
Each agent's summary is its transmitted unit. For every gold shard (agent a, shard text) in each instance:

- pair = (gold shard, best-matching summary), where the best match is the `best_unit` of
  `scripts.compute_audit_metrics.align_gold_to_transmitted` over that instance's summaries;
- if no summary matches (`best_unit` is None), pair = (gold shard, the summary of agent a itself);
- pairs with neither are counted and not labelled.

Expected 390 pairs (26 instances x (5 + 10) shards). The build prints the count; the run does not start unless it is 390.

## Label

`rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json` (sha `fc725839…`), Haiku 5.5, temperature 0, one
fact and one unit per call, two attempts per pair. Validated on relay pairs (agreement .900, kappa .791 [.466, 1.000],
`20261115_relay_validation_v3_enriched`). It has **not** been validated on summary pairs; the report says so.

## Outcomes

- Covered = label faithful, partial or distorted; absent = label absent.
- Strict distortion = distorted / covered; broad = (distorted + partial) / covered.
- **Omission = absent / all labelled pairs**, the same label. The relay figure with the same label comes from
  `20261115_relay_v2_rescore/rates.json` (absent 100 of 945).
- Intervals: Wilson 95% for proportions (stated once in the report).

## Cost

About $0.00037 per pair (relay run: 945 pairs, $0.353), so about $0.15 for 390 pairs. The cap is $0.25.
