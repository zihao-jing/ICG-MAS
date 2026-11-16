# Silo-Bench extraction, point-level presence: validation run

2026-11-15. Rule `Per-fact-presence-points-v1.md` (sha `e6263584…`), amendment 1 (`e436b30a…`, reference
Gemini 3.6 Flash), prompt `per_fact_points_prompt_v1.json` (sha `86d84ff6…`), population (sha `1d1fd1af…`,
seed 47, 21 traces, 21 instances, 155 facts, 2,755 atoms). Labeller Claude Haiku 5.5; reference Gemini 3.6
Flash; identical prompt; temperature 0. Spend **$2.200761**, cap $3.5.

## Verdict

**Passes both bars at atom level and at roll-up.**

| Unit | n | Agreement [95% CI] | κ [95% CI] | Bar | Result |
|---|---:|---|---|---|---|
| Atom, present vs not | 2,755 | **.924 [.854, .985]** | **.847 [.690, .967]** | .80 / .60 | PASS |
| Fact roll-up, present vs not | 155 | **.942 [.890, .986]** | **.883 [.765, .971]** | .80 / .60 | PASS |

Instance-cluster bootstrap, 2,000 draws, seed 43, 21 instances. Fidelity of the κ interval: lower bounds .690
and .765, above the .40 wide-interval line, so neither is marked wide.

Three-class exact agreement (present/partial/absent): 2,360/2,755 = .857. Reference present share .553,
labeller .524. Roll-up cells: 64 present/present, 16 partial/partial, 56 absent/absent, 19 disagreements
(146/155 binary).

**Registered** in `rebuttal/validations/registry.json` as `silobench_extraction_presence_points` v1 at prompt
`86d84ff6…`, `passed: true`, 155 facts, 0 excluded.

## Sample and calls

- 21 traces / 21 instances drawn before any call from instances in neither the v3 nor the v4 population;
  models deepseekr1_32b (12) and geminiflashlite (9); one trace per instance. The empty-extraction-pool trace
  `pts/deepseekr1_32b/III-23_n10` (10 facts, 0 entries) stays in as an absence case; both sides labelled its
  atoms absent, so it adds agreement without flattering the result.
- 310 planned calls. All completed. 15 reference calls hit the 3,000-token cap and were re-run once at 6,000
  tokens (15 extra calls, ~$0.28); all parsed. No fact is excluded: 155/155 paired.

## The partial Opus run

Before amendment 1, six smoke calls used Opus 5.5 as the reference (4 Haiku, 2 Opus, $0.121838). They are kept
in `calls.jsonl`, are not in any score, and none of their labels is used. The amended run uses separate call
keys. The reason for the amendment: Opus is reasoning-mandatory at this endpoint and cost $0.0402 for one
30-atom call (`../prereg/Per-fact-presence-points-v1-amendment-1.md`).

## Where the remaining disagreements are

209 of 2,755 atoms differ in the binary call. They are concentrated: one instance, `III-29_n5`, holds 68 of
them (atom agreement .320 there; the median instance is 1.000). The pattern is the same definitional edge as
v3/v4, now one level down: for a task-table atom `{'id': 21, 'duration': 4}` both models cite the same entry
and agree the tuple is there, but the reference returns `present` ("explicitly listed") and the labeller
returns `partial` ("appears within the agent 1 task list"). Both are right under different readings of
"states the atom" when the entry carries more fields than the atom. This costs 3-class agreement (.857) more
than binary (.924). It is a candidate for a v2 wording fix, not a bar failure; the label passes as frozen.

## What the label covers

- Covers: atom-level presence at the Silo-Bench **extraction** checkpoint, score-ranked relay, n5/n10, on
  fresh instances.
- Does not cover: fidelity (Dist), the board checkpoint, summary exchange, or n20+ traces. Cross-model
  agreement is not author ground truth.

## Ledger

$84.681712 before this run (rule-based sum) + $2.200761 logged here = **$86.882473**. The $2.200761 includes
the $0.121838 Opus smoke. All records are in `calls.jsonl`; the run and top-up logs are `run.log` and
`run_topup.log`.