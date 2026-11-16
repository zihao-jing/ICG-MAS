# Per-fact labeller at the relay checkpoints

Rule `PER_FACT_RULE.md` (sha256 `5e91680b0256`); split `split.json` (sha256 `cd84e29ad8dc`); frozen prompt `rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json` (system sha256 `3f7f19bbb313`). Pilot cap $5.00; spend $0.231074.

Stage: relay checkpoints (extraction pool and shared board). Input: the critical-fact list (Amendment 1: the annotator `critical_facts_json` for the validation population; the first matcher-fact pass stays on record); support documents not shown. Complete coverage: every fact faithful at the board (authors' rule).

## tune — prompt v1

No comparisons.

## tune — prompt v2

Calls 78 (3 invalid). Comparisons 75: agreement 30/75 = 0.400 (95% CI 0.289-0.520); kappa 0.065 (-0.053-0.270).

## tune — prompt v3

Calls 78 (0 invalid). Comparisons 78: agreement 31/78 = 0.397 (95% CI 0.288-0.515); kappa 0.070 (-0.052-0.266).

## tune — prompt v4

Calls 78 (0 invalid). Comparisons 78: agreement 34/78 = 0.436 (95% CI 0.324-0.553); kappa 0.088 (-0.052-0.304).

## validation

Calls 48 (0 invalid). Comparisons 48: agreement 30/48 = 0.625 (95% CI 0.474-0.760); kappa 0.316 (0.072-0.714) — **FAIL**.

Disagreements (labeller complete, author complete):

- 2hop__846844_47134 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: partial/partial (author faithful)
- 2hop__846844_47134 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: partial/partial (author faithful)
- 4hop1__802394_153080_33897_81096 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: absent/absent (author faithful)
- 4hop1__802394_153080_33897_81096 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: absent/absent (author faithful)
- 3hop1__465684_160545_62931 / gpt4omini / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: partial/partial (author faithful)
- 3hop1__465684_160545_62931 / gpt4omini / board: labeller False, author True; f1: partial/partial (author faithful), f2: partial/partial (author faithful), f3: present/faithful (author faithful)
- 3hop1__640171_228453_86925 / gpt4omini / board: labeller False, author True; f1: present/faithful (author faithful), f2: present/faithful (author faithful), f3: partial/partial (author faithful)
- 3hop1__640171_228453_86925 / gpt4omini / board: labeller False, author True; f1: present/faithful (author faithful), f2: present/faithful (author faithful), f3: partial/partial (author faithful)
- 4hop1__802394_153080_33897_81096 / gpt4omini / board: labeller False, author True; f1: absent/absent (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: present/faithful (author faithful)
- 4hop1__802394_153080_33897_81096 / gpt4omini / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: present/faithful (author faithful)
- 2hop__846844_47134 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful)
- 2hop__846844_47134 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful)
- 3hop1__465684_160545_62931 / qwen235b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: partial/partial (author faithful)
- 3hop1__465684_160545_62931 / qwen235b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: partial/partial (author faithful)
- 3hop1__640171_228453_86925 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)
- 3hop1__640171_228453_86925 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)
- 4hop1__802394_153080_33897_81096 / qwen235b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: absent/absent (author faithful)
- 4hop1__802394_153080_33897_81096 / qwen235b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: present/faithful (author faithful), f4: absent/absent (author faithful)
## reserve

Calls 30 (0 invalid). Comparisons 30: agreement 14/30 = 0.467 (95% CI 0.283-0.657); kappa 0.091 (0.000-0.420) — **FAIL**.

Disagreements (labeller complete, author complete):

- 3hop1__106042_64399_59680 / gemma31b / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful), f3: partial/partial (author faithful)
- 3hop1__106042_64399_59680 / gemma31b / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful), f3: partial/partial (author faithful)
- 3hop2__132957_433432_40768 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)
- 3hop2__132957_433432_40768 / gemma31b / board: labeller False, author True; f1: partial/partial (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)
- 2hop__135822_46621 / gpt4omini / board: labeller False, author True; f1: present/faithful (author faithful), f2: present/partial (author faithful)
- 3hop1__106042_64399_59680 / gpt4omini / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful), f3: present/faithful (author faithful)
- 3hop1__106042_64399_59680 / gpt4omini / board: labeller False, author True; f1: present/faithful (author faithful), f2: partial/partial (author faithful), f3: present/faithful (author faithful)
- 3hop2__132957_433432_40768 / gpt4omini / board: labeller False, author True; f1: partial/partial (author faithful), f2: partial/partial (author faithful), f3: absent/absent (author faithful)
- 3hop2__132957_433432_40768 / gpt4omini / board: labeller False, author True; f1: partial/partial (author faithful), f2: partial/partial (author faithful), f3: absent/absent (author faithful)
- III-30_n10 / gpt4omini / board: labeller False, author True; f_a0: present/faithful (author faithful), f_a1: present/faithful (author faithful), f_a2: present/faithful (author faithful), f_a3: present/faithful (author faithful), f_a4: present/faithful (author faithful), f_a5: present/faithful (author faithful), f_a6: present/faithful (author faithful), f_a7: partial/partial (author faithful), f_a8: present/faithful (author faithful), f_a9: present/faithful (author faithful)
- 2hop__486314_544665 / qwen235b / board: labeller False, author True; f1: partial/distorted (author faithful), f2: absent/absent (author faithful)
- 2hop__486314_544665 / qwen235b / board: labeller False, author True; f1: partial/distorted (author faithful), f2: absent/absent (author faithful)
- 3hop1__106042_64399_59680 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: absent/absent (author faithful), f3: present/faithful (author faithful)
- 3hop1__106042_64399_59680 / qwen235b / board: labeller False, author True; f1: present/faithful (author faithful), f2: absent/absent (author faithful), f3: present/faithful (author faithful)
- 3hop2__132957_433432_40768 / qwen235b / board: labeller False, author True; f1: absent/absent (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)
- 3hop2__132957_433432_40768 / qwen235b / board: labeller False, author True; f1: absent/absent (author faithful), f2: present/faithful (author faithful), f3: absent/absent (author faithful)

## Decision

Validation **fail** under the frozen rule (agreement >= 0.80 and kappa >= 0.60). The labeller is not validated on the semantic target; lexical coverage remains the reported figure. The carrier-target n=48 result is exploratory (`revalidation.md`); the fresh reserve check under `PER_FACT_RULE_V3.md` FAILS (20/30, kappa 0.194), so the labeller is not validated for carrier identification either. The semantic FAIL stays on record beside it.

## Diagnosis

Validation confusion (labeller complete, author complete): both true 20, labeller false / author true 18, both false 10, labeller true / author false 0. Every disagreement in this validation is the labeller calling a trace incomplete that the authors call complete. At the fact level the authors label 158 of 168 board carriers faithful; the labeller labels 125 faithful. The author label is near constant, and its carrier records mark facts faithful whose cited board units do not state them.

Examples from the validation disagreements:
- 2hop__846844_47134 / gemma31b / C: author complete; f1: board board:a0:u0, board:a0:u1 -> labeller partial/partial; f2: board board:a1:u0 -> labeller partial/partial
- 2hop__846844_47134 / gemma31b / D: author complete; f1: board board:a0:u0, board:a0:u1 -> labeller partial/partial; f2: board board:a1:u0 -> labeller partial/partial
- 4hop1__802394_153080_33897_81096 / gemma31b / C: author complete; f1: board board:a0:u0 -> labeller partial/partial; f4: board none -> labeller absent/absent

The clearest case is 2hop__28287_89399 / gemma31b / C: the author lists "It is thought that annelids were originally animals with two separate sexes, which released ova and sperm into the water via their nephridia" and marks it faithful with board:a1:u0, whose text is "Annelid fertilized eggs develop into trochophore larvae, which live as plankton." That unit does not state the listed fact. A labeller that reproduces this label would have to call an unsupported carrier faithful.

Prompt revisions tried on the tune split: matcher-fact v1 0.603 (47/78, kappa 0.221); author-fact v2 0.400; decisive-content v3 0.397; question-relevance v4 0.436. The change from the audit matcher facts to the annotator list (Amendment 1) did not raise agreement, and neither wording change did, because the remaining gap is the reference label, not the prompt. The reserve split is held unused: the rule allows it only for re-validation after a cause is fixed, and no labeller-side fix addresses a reference that marks unsupported carriers faithful.
