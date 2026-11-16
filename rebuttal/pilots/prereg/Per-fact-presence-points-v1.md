# Per-fact presence at the point level, Silo-Bench extraction: frozen rule v1

2026-11-15. Frozen before any call. No API call has been made under this rule. Supersedes prompt v3 and
v4 for the Silo-Bench extraction checkpoint only.

## Why

Prompts v3 and v4 failed validation because Silo-Bench facts are lists (task tables, coordinate lists,
user vectors) and the two sides of the comparison placed the "how much of the list counts as present"
threshold differently: 30 of v3's 35 disagreements sit in four list-heavy instances, and v4's reasons say
"this list-valued fact is incomplete" while returning `present`. The unit was wrong, not only the prompt.
This rule removes the threshold by labelling each point and rolling up deterministically.

## Unit

Each source support is split into claim atoms by `scripts/per_fact_points_build.py`, before any call:

1. A support that parses as a JSON or Python literal list with more than one element: **one atom per element**
   (a coordinate pair, a table row or a list item is one atom).
2. A support that parses as a dict with more than one key: **one atom per key**, carrying that key's value.
3. Any other support: **one atom per sentence**; a single-sentence support is one atom.

Atom ids are `f<fact>.<atom>`, facts numbered `f1…` in the order of the source supports. The split is
recorded in `population.json` and is not changed after the first call.

## Statuses

- **present** — an entry states the atom with the same entities, values, direction, qualifiers and units.
  Word order, formatting and paraphrase are allowed.
- **partial** — an entry states the atom but changes a value, entity, number, date, direction or qualifier,
  or states only an incomplete fragment of it.
- **absent** — no entry states the atom or any altered version of it.

Only the extraction entries may be used. No outside knowledge.

## Roll-up

- Atom critical recall = present atoms / all atoms.
- A fact is **present** iff all its atoms are present; **partial** iff at least one atom is present and not all
  are; **absent** iff no atom is present.
- No other threshold exists. The old fact-level threshold is not used.

## Prompt and models

- One prompt for both sides: `rebuttal/pilots/prereg/per_fact_points_prompt_v1.json`, identical text for the
  labeller and the reference. Only the model changes.
- Labeller: `anthropic/claude-haiku-5.5`. Reference: `anthropic/claude-opus-5.5`. Temperature 0.
- One call per (trace, fact). Each request carries the question, the source fact as context, that fact's
  atom list, and the trace's extraction entries.
- Output is one JSON object as specified in the prompt. The parser strips one leading/trailing code fence;
  a call with invalid JSON gets exactly one retry, then is excluded and reported.

## Sample

- Drawn by `scripts/per_fact_points_build.py` with seed 47 before any call; recorded in `population.json`
  with its sha256 in `build_manifest.json`.
- **21 traces, 21 instances, one trace per instance**, from instances that appear in neither the v3 nor the
  v4 population. Models are `deepseekr1_32b` and `geminiflashlite` (neither was used to design the rule),
  `score_ranked_relay`, n5 or n10; the per-instance model is chosen by the seeded hash.
- The 21-instance ceiling is the benchmark's: only 52 Silo-Bench instances exist at n5/n10, and 31 were used
  by v3 or v4. The sample cannot be widened without reusing instances.

## Validation and bars

- Unit of agreement: the atom. Binary outcome: present vs not present (partial and absent collapse). The
  three-class confusion is reported alongside.
- Agreement ≥ **.80** and Cohen's κ ≥ **.60**.
- Both are reported with 95% CIs by instance-cluster bootstrap, 21 instances, 2,000 draws, seed 43,
  percentile interval. κ is recomputed inside each resample.
- **Pass** requires both point estimates to meet the bars. If κ's CI lower bound is below .40, the label is
  marked wide-interval and is not used for a headline claim even if the point estimate passes.

## Cost

- Cap **$3.5** for the whole run (155 facts × 2 models = 310 calls, ~2,755 atoms). The pre-call projection
  is recorded in `build_manifest.json`; if the running spend would exceed $3.5 the run stops and reports to
  the lead. No second sample under this rule.

## Outcome handling

- **Pass**: the atom-level presence label replaces the lexical Silo-Bench extraction rows; old rows stay on
  record beside it. Fidelity and the board checkpoint are not covered by this rule.
- **Fail**: the label stays out of the headline, the disagreements are read and reported with the cause,
  and any new prompt version needs a new fresh sample. No threshold or prompt tuning on this sample.