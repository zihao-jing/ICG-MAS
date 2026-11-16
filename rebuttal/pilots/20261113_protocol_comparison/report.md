# Protocol comparison as repair evidence (item 3)

Rule `COMPARISON_RULE.md`, frozen before the comparison. Stage: relay
checkpoints. Zero model calls; the audits are existing outputs
(`results/distortion_audit_se/`, `results/distortion_audit_relay/`), spend
$0.000000 here.

Population: Qwen-235B, Silo-Bench n=5 and n=10; 390 (agent, gold-shard) pairs
for Summary Exchange, 315 per verbatim relay protocol. Intervals are exact
Clopper-Pearson; the two pair sets are not paired, so the gaps are
descriptive.

Bound reading: a pair counts as covered on **any numeric overlap**, so the
coverage rates are **upper bounds** on true coverage and the omission rates are
**lower bounds** on true omission. Every table and answer that quotes these
numbers states both sides.

## Omission (no numeric overlap with the agent's own shard)

| protocol | n | omitted | omission (95% CI) |
| --- | ---: | ---: | ---: |
| Summary Exchange | 390 | 242 | **62.1%** (57.0-66.9) |
| Random relay | 315 | 9 | **2.9%** (1.3-5.4) |
| Score-ranked relay | 315 | 8 | **2.5%** (1.1-4.9) |
| Redundancy-aware relay | 315 | 8 | **2.5%** (1.1-4.9) |
| Relay pooled | 945 | 25 | **2.6%** (1.7-3.9) |

## Strict distortion among covered pairs

| protocol | covered | distorted | strict distortion (95% CI) |
| --- | ---: | ---: | ---: |
| Summary Exchange | 148 | 13 | **8.8%** (4.8-14.5) |
| Random relay | 306 | 2 | **0.7%** (0.1-2.3) |
| Score-ranked relay | 307 | 1 | **0.3%** (0.0-1.8) |
| Redundancy-aware relay | 307 | 0 | **0.0%** (0.0-1.2) |
| Relay pooled | 920 | 3 | **0.3%** (0.1-1.0) |

## Reading

At the relay checkpoint, the communication format moves both failure modes in
the same direction. Summary Exchange omits the numeric evidence in 62.1% of
(agent, shard) pairs, against 2.6% for verbatim relay, and when it does carry a
value it states it incorrectly in 8.8% of covered pairs, against 0.3% for
relay. Every relay protocol is below every summary interval on both
quantities; the strict-distortion comparison is conditional on coverage, and
summary covers far fewer pairs, so the 8.8%-versus-0.3% gap understates the
total amount of bad evidence: summary also fails to transmit 62% of the pairs
that relay carries. This is the repair evidence for Answer 3's relay branch: a
verbatim re-request or a verbatim relay protocol addresses distortion and
omission together, not by re-prompting the same summary format. It does not
test a deployed repair, and it does not touch final aggregation.