# Frozen rule: protocol comparison as repair evidence (item 3)

Written 2026-11-13 before the comparison was computed. Zero model calls; reads
the frozen distortion-audit outputs only. Stage: relay checkpoints
(transmission from an agent's shard to the board).

## Source records

- Summary Exchange: `results/distortion_audit_se/distortion_results.json`,
  `summary_all` (Qwen-235B, Silo-Bench n=5 and n=10; 390 (agent, gold-shard)
  pairs).
- Verbatim relay: `results/distortion_audit_relay/distortion_results.json`,
  `results_by_protocol` for `random_relay`, `score_ranked_relay`,
  `redundancy_aware_relay` (Qwen-235B, Silo-Bench n=5 and n=10; 315 pairs per
  protocol, 945 pooled).

The two audits use the same two-stage procedure (numeric coverage, then the
Qwen-235B judge for covered pairs); the summary audit covered 148 pairs, the
relay audits 306-307 per protocol. The pair sets are not paired one-to-one;
intervals below are independent and the gap is descriptive.

## Quantities

- **Coverage** = covered pairs / total pairs.
- **Omission** = 1 - coverage (a pair with no numeric overlap, or no candidate
  carrying a gold value).
- **Strict distortion** = DISTORTED pairs / covered pairs (a stated value is
  incorrect or contradicted). This is the paper's strict definition and is
  conditional on coverage; it is not comparable to omission without saying so.

## Intervals

Exact Clopper-Pearson 95% intervals on every proportion, computed here from
the label counts in the two JSON files. No clustering correction: the records
are (agent, shard) pairs, and the comparison is a descriptive contrast between
two protocol families, not a population estimate over instances.

## Use

If summary has higher omission and higher strict distortion than every verbatim
relay protocol, the comparison is reported as repair evidence for Answer 3:
switching the communication format (verbatim relay) reduces both omission and
distortion at the relay checkpoint. The numbers are the existing paper numbers
with intervals; no cell is replaced and no paper file is edited.