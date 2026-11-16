# Redundancy injection under a fixed budget, v1 — frozen before any call

2026-11-15. Cap **$2.00**. Tests whether duplicated content displaces critical content when the message budget is tight,
and whether the paper's redundancy-aware selection protects against it.

## Population

MuSiQue, `score_ranked_relay` base records of the three paper models (gemma31b, gpt4omini, qwen235b) with the base
eligibility of `Injection-v1.md` (matcher status ok, answer correct, every carrier at extraction and board faithful).
First **30 eligible instances per model** in the order of `Injection-v1.md` (sha256 of `injection-v1|20261115|<model>|<instance>`).
90 cases.

## Budget and selection

- Each agent transmits **k = 2** units (budget of two messages per agent). Each agent's extraction pool holds its
  stored units (K = 3 per agent) with their stored scores.
- Score-ranked selection: the top k units by stored score (ties in stored order), as `selected_with_ids`.
- Redundancy-aware selection: the paper's `_redundancy_select` (src/protocols/relay.py) with rho = 0.5 and k = 2.

## Conditions

For each case and each agent:

1. **Base**: the stored pool, unchanged.
2. **Duplicated**: the pool plus one exact copy of the agent's highest-scored unit, with a new unit id
   (`dup:a<agent>`) and the same stored score.

Protocol x condition = 2 x 2. Both selection rules run on both conditions. The agent's other units, the scores and the
aggregation prompt and model are unchanged. No extraction or scoring call is made.

## Verification before any result is read

1. In the duplicated condition, each agent's pool contains its duplicate (asserted in code; count reported).
2. One hand-checked trace is printed in full: the pool, the score-ranked selection and the redundancy-aware selection,
   under both conditions. The two selections must differ under the duplicated condition, and the duplicate must be
   selected by score ranking and not by redundancy-aware selection.

## Outcomes

- **Answer F1** against gold after the unchanged aggregation prompt and model (primary).
- **Gold answer string in the transmitted board** (lexical, secondary; labelled as lexical).

Per protocol and per condition: mean F1 and count of cases with F1 = 1.0, with Wilson 95% intervals for proportions.
Paired difference (duplicated minus base) per protocol with the count of cases that drop, rise or stay.

## Calls

One aggregation call per case, condition and protocol: 90 x 2 x 2 = 360 calls, logged with cost in
`calls.jsonl`. The run stops at the cap.
