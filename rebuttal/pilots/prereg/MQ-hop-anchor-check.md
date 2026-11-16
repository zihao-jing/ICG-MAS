# MuSiQue 6/30 fix: hop-anchored proxy facts — frozen before any call

2026-11-15. Cap **$1.00** (hard). Pilot first: 3 traces of set A, cost and projection reported before the rest.

## Question

Does the hop-anchored proxy prompt (v4) raise agreement between the proxy-fact stage and the gold-fact stage over the
v1 result (6/30 on the failure-enriched set)?

## Pass bar

Pass: fresh failure-enriched agreement ≥ .800 **and** uniform agreement ≥ .765. Otherwise fail: the text keeps the
62/81 result only. Set A is reported but is not part of the pass bar.

## Sets (instance ids fixed by the rule, from `20261115_proxy_support_mq/population.json`, `random_relay` rows)

- **A, same 30:** the 30 traces of `20261115_q1_second_sample/results.jsonl` (the failure-enriched set that gave 6/30
  with v1 facts in `20261115_q1_validated_rerun`).
- **B, fresh failure-enriched 30:** traces that pass the second-sample filter (`q1_second_sample.population()`:
  gold support atom missing from extraction or board) and are in neither the 31 earlier Q1 traces nor set A, taken in
  ascending instance-id order, first 30.
- **C, uniform 30:** drawn from all `random_relay` rows not in A or B (the 31 earlier Q1 traces may be included),
  with `random.Random(20261115).sample` over the sorted list. Uniform means no filter on stage or answer.

## Proxy facts

- Model: Qwen-235B (`qwen/qwen3-235b-a22b-2507`), temperature 0, max tokens from the prompt file.
- Prompt: `prereg/proxy_facts_prompt_v4_hop_anchored.json` (sha256 `f0b845499d…`). It is the v1 system prompt
  (`proxy_facts_prompt_v1.json`) with one rule added, the hop-anchoring rule. The v1 user template is unchanged.
- Up to 3 attempts per trace, validated with `proxy_support_run.validate_facts`.

## Labeller and stage rule (as `q1_validated_rerun`)

- Labeller: Claude Haiku 5.5, `per_fact_points_prompt_v1.json` (sha `86d84ff6…`), `per_fact_points_run.render` and
  `parse`, temperature 0, max 4,096 output tokens. A reply is valid only if it returns labels for every atom sent.
- Gold side: first gold support, atoms split on `. ` (parts over 3 characters). Labelled against extraction and then
  board.
- Proxy side: each v4 fact's atoms, labelled against extraction and then board.
- Side stage: any atom absent at extraction → `extraction`; else any absent at board → `transmission`; else
  `aggregation`. An invalid reply leaves the side without a stage.
- Agreement per set = traces with both stages and the same stage, over traces with both stages. Wilson 95%.

## Spend

Each call is logged with model, tokens and cost in `20261115_mq_hop_anchor/calls.jsonl`. The run stops before the
cap. A skip is logged at the cap.

## Not part of this rule

The v1 results (`20261115_q1_validated_rerun`, `20261115_proxy_vs_gold_stage`) stay on record.
