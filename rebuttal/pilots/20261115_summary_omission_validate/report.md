# Summary-exchange board-presence label: validation (STOPPED, incomplete, no verdict)

Rule `prereg/Summary-omission-label-v1.md` (sha256 cb577da5…). Reference: Claude Opus 5.5 through `claude -p`.

## Status
- The job is not running (pid 95313 has exited). No further calls were made after the stop.
- Cap overrun: API-equivalent spend is $1.000976 against the $1.00 cap, an overrun of $0.001. The cap check ran before each call but used a per-board estimate, so the last call pushed the total over.
- Per-cost correction: average API-equivalent cost is $1.001 / 19 boards = $0.053 per board (the earlier $0.070 was one pilot board, not the average). CLI cost is $0.906 in total.
- Sample: 19 of 30 facts scored, on 19 boards. Scored by stratum: present 7, partial 4, absent 8. Unscored: partial 6, present 3, absent 2. The partial stratum is 4 of 10.
- Labeller: the stored board-presence labels being validated were produced by **anthropic/claude-haiku-5.5** (`scripts/sb_presence_full.py`, `HAIKU`; `rebuttal/pilots/20261113_sb_presence_full/calls.jsonl`, 2,227 calls with that model). The prompt file `labeller_prompt.json` names `anthropic/claude-opus-5.5` in its `model` field, but that is not the model that produced the labels. The labeller is therefore Haiku 5.5, which is not to be used. Finishing the sample would need labels from a permitted paper model, which do not exist for these boards.

## Frozen pass rule (quoted)
"PASS iff point agreement ≥ .80 and point kappa ≥ .60. The intervals are reported beside the verdict."

## How the 19 facts meet it (provisional, not a verdict)
- Agreement (present vs not present): 18/19 = .947 [.754, .991] → meets ≥ .80.
- Kappa (binary): .883, cluster bootstrap 95% [.587, 1.000] → meets the point bar ≥ .60; the lower bound is below .60.
- Three-class agreement: 17/19 = .895.
- Confusion (stored x reference): present/present 6; present/not 1; not/present 0; not/not 12.

The point bars are met on 19 of 30 facts, from a sample that does not match the frozen stratification and a labeller that is not a permitted paper model. This is not a validation pass. Summary-vs-relay omission is not rescored.
