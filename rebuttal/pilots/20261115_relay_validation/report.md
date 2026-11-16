# Strict-fidelity label validated on the Qwen relay population

2026-11-15. Rule `Relay-strict-fidelity-validation-v1.md` (sha `3d7b9258…`), prompt
`strict_fidelity_pair_prompt_v1.json`. 30 relay pairs (10 per protocol, seed 47), Haiku 5.5 labeller, Opus 5.5
reference. Spend **$0.359949**, cap $0.5.

## Result: fails the kappa bar; nothing registered

| quantity | value [95% CI] |
| --- | --- |
| distorted vs not, agreement | .933 [.839, 1.000] |
| distorted vs not, kappa | .000 [-.000, .000] |
| three-class agreement | .833 |

Bars: agreement ≥ .80 and kappa ≥ .60. **FAILS**; the wide-interval rule applies.

| reference \ labeller | faithful | partial | distorted | absent |
| --- | ---: | ---: | ---: | ---: |
| faithful | 19 | 0 | 0 | 0 |
| partial | 3 | 5 | 0 | 0 |
| distorted | 1 | 1 | 0 | 0 |
| absent | 0 | 0 | 0 | 1 |

The kappa is 0 because the labeller never used the distorted class: 2 reference-distorted pairs, 0
labeller-distorted. Kappa cannot be positive without labeller positives.

## Diagnosis from the five disagreeing pairs

| pair | protocol | ref | lab | what the unit does |
| --- | --- | --- | --- | --- |
| `f6853af7…` | score-ranked | partial | faithful | restates the B-matrix in full but omits the A-row half of the fact |
| `a6c13049…` | score-ranked | partial | faithful | restates 3 of 30 values plus the last with "…" elision |
| `fb00b289…` | score-ranked | distorted | faithful | "IDs 1–19, 21–22" implies task 10, which the fact excludes |
| `221deaa0…` | redundancy | partial | faithful | "IDs 45–66" drops the gaps at 50 and 60, so the ID-to-value pairing is lost |
| `873984e2…` | redundancy | distorted | partial | lists 6 of 30 values and mistypes one digit (82.940628… → 82.940622…) |

**Cause.** On Silo-Bench relay units the critical fact is a numeric record: a list, or a list paired with an
ID range. The unit restates it compressed, with "including", "…" and ranges. Opus treats an elided middle
as dropped evidence and a changed ID set or a mistyped value as a contradiction. Haiku reads the same
compression as presentational and accepts the unit whenever the stated values match the fact. The one
partial/distorted case shows it is not only leniency: Haiku noticed the changed digit but called it partial
where the definition says distorted. The label's target — the unit carries the whole record — is not being
applied to compressed restatements, and compressed restatements are what Qwen relay units are. The low
distorted prevalence (2/30) is a consequence: the labeller has no distorted class to score, so kappa is 0 by
construction. A larger random sample would still contain mostly faithful pairs and would not fix the
misreading.

## Fix (proposed, not run)

Clarify the same prompt, not a new label: add that "including", an ellipsis and a range do not carry the
elided values (elided = missing, therefore partial), and that a stated value or an ID set that differs from
the fact is distorted (not partial).

Then revalidate on a fresh 30-pair relay sample (seed 48, 10 per protocol), Opus reference: 30 Opus + 30
Haiku calls, **about $0.37**, cap $0.5. If it passes, the relay rate can be quoted under the clarified
prompt and the old label stays registered for the four-model rates. A $1.41 120-pair re-check is needed only
if the clarified prompt is to govern both populations.

Do not retry until the fix is approved.

## Ledger

Spend $0.359949.