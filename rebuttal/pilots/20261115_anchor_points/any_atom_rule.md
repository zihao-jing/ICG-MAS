# Anchor roll-up rules side by side (no calls)

2026-11-15. Same 80 anchor facts, same per-atom labels from the A2 run (Haiku labeller, Gemini reference), board checkpoint. Author present = a non-absent board carrier. Three roll-ups: all atoms present (the A2 rule), any atom present, any atom carried (present or partial).

| model | rule | n | agreement [95% CI] | kappa [95% CI] |
| --- | --- | ---: | --- | --- |
| labeller_haiku | all_present | 80 | 0.487 [0.333, 0.627] | 0.150 [0.057, 0.271] |
| labeller_haiku | any_present | 80 | 0.762 [0.635, 0.867] | 0.372 [0.154, 0.596] |
| labeller_haiku | any_carried | 80 | 0.925 [0.859, 0.976] | 0.657 [0.335, 0.876] |
| reference_gemini | all_present | 80 | 0.512 [0.371, 0.643] | 0.166 [0.068, 0.286] |
| reference_gemini | any_present | 80 | 0.725 [0.597, 0.831] | 0.353 [0.166, 0.547] |
| reference_gemini | any_carried | 80 | 0.963 [0.900, 1.000] | 0.836 [0.541, 1.000] |

Cells (author / predicted):

- labeller_haiku / all_present: {'author_True_pred_False': 41, 'author_True_pred_True': 29, 'author_False_pred_False': 10}
- labeller_haiku / any_carried: {'author_True_pred_True': 67, 'author_True_pred_False': 3, 'author_False_pred_True': 3, 'author_False_pred_False': 7}
- reference_gemini / all_present: {'author_True_pred_False': 39, 'author_True_pred_True': 31, 'author_False_pred_False': 10}
- reference_gemini / any_carried: {'author_True_pred_True': 68, 'author_True_pred_False': 2, 'author_False_pred_True': 1, 'author_False_pred_False': 9}

Instance-cluster bootstrap, 2,000 draws, seed 43. Bars are not applied here: this is a zero-cost re-scoring of stored labels, not a new validation.

## Ledger
Spend $0.000000.

## Reading

The author convention is "any atom carried", not "all atoms present". Under that rule the same stored labels
pass both bars (labeller .925, kappa .657), so the A2 failure was the roll-up rule, not the label. Two
cautions: the kappa CI lower bound is .335, below the .40 wide-interval line, so this is not a headline
number; and 6 facts still disagree (3 author-present facts with no carried atom, 3 author-absent facts the
labeller calls carried), which caps agreement at .925. The reference (Gemini) agrees with the authors at .963
under the same rule.
