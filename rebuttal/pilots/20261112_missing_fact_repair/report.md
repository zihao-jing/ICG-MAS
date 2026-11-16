# Missing-fact repair pilot: four R4-clean cases

Frozen runner `scripts/missing_fact_repair_pilot.py`; prompts recorded in `prompt_manifest.json` before the first call (extraction system `810084ff7eca533c5c986d9e6992207e527911209fa1b6ed3dae5ded20a38dc2`, aggregation system `62f0a128fc091a679f9065ff1da671d8329dde319609d49d8c93ba7f679f0b60`). Model identifiers are the paper models, temperature 0.

## Design

R-ext re-extracts up to 3 units from the target agent's own context with the frozen relay extraction prompt. The R2 delivery gate is applied to those units before any answer call. The board-only control answers from the original board with no repair. The repair answer is run only for a delivered case, from the original board plus the extracted units. This is the repair arm as specified in README section 6; the four cases are the R4-clean cohort (two frozen facts, two rebuilt facts from `R4_rebuild.json`).

## Delivery check (run first)

Delivered **0/4**, exact 95% CI 0.000-0.602.

| case | model | recall | gate | reasons | extracted units |
| --- | --- | ---: | --- | --- | --- |
| 2hop__280583_229757 | gemma-4-31b-it | 0.000 | blocked | fact recall 0.00 < 0.8 | No evidence units were found in the provided text that identify the creator of The Mighty B or their |
| 2hop__142621_225454 | gemma-4-31b-it | 0.250 | blocked | fact recall 0.25 < 0.8 | No evidence units were found in the provided text that identify the co-writer, recording artist, or  |
| 2hop__28287_89399 | gpt-4o-mini | 0.167 | blocked | fact recall 0.17 < 0.8 | Annelids were originally animals with two separate sexes that released ova and sperm into the water  / Derek Drymon was born on November 19, 1968, and is known for his work on "SpongeBob SquarePants." / "SpongeBob SquarePants" debuted on May 1, 1999. |
| 4hop1__802394_153080_33897_81096 | qwen3-235b-a22b-2507 | 0.214 | blocked | fact recall 0.21 < 0.8 | The Desert Diamond West Valley Phoenix Grand Prix was revived by the Verizon IndyCar Series in 2016  / A Modern Jazz Symposium of Music and Poetry is an album by jazz bassist Charles Mingus. / Charles Mingus, the performer of "Mingus Plays Piano," was born in Nogales, Arizona, bu |

No repair answer was called for a blocked case, so its repair outcome does not exist to score. Reading the board-only control is reported below; it was run only after this file was written.

## Scoring check

Repair answers called: 0 (of 4 cases; delivered 0). Scored exact **0/0**. Board-only control: exact **0/4** (95% CI 0.000-0.602).

| case | arm | gold | answer | refusal | F1 | exact |
| --- | --- | --- | --- | --- | ---: | ---: |
| 2hop__280583_229757 | board_only | Will Arnett | Insufficient information. | yes | 0.000 | 0 |
| 2hop__142621_225454 | board_only | Hollywood Records | Insufficient information. | yes | 0.000 | 0 |
| 2hop__28287_89399 | board_only | Mr. Lawrence | Insufficient information. | yes | 0.000 | 0 |
| 4hop1__802394_153080_33897_81096 | board_only | Mario Andretti | Insufficient information. | yes | 0.000 | 0 |

## Wrong answers read against the gold

- `2hop__280583_229757` / board_only: gold **Will Arnett**, answer "Insufficient information.", F1 0.000 (refusal).
- `2hop__142621_225454` / board_only: gold **Hollywood Records**, answer "Insufficient information.", F1 0.000 (refusal).
- `2hop__28287_89399` / board_only: gold **Mr. Lawrence**, answer "Insufficient information.", F1 0.000 (refusal).
- `4hop1__802394_153080_33897_81096` / board_only: gold **Mario Andretti**, answer "Insufficient information.", F1 0.000 (refusal).

## Cost

New calls: $0.000888 against a $1.00 pilot cap. Calls are in `rebuttal/pilots/20261112_missing_fact_repair/calls.jsonl`; no call was made for a blocked case.

## Reading

The delivery step, not the model's use of evidence, blocks the pilot: in none of the four clean cases does re-extraction from the target agent's own context return the target fact. The repair method as specified never reaches its answer step, so the missing-fact repair experiment remains untestable in this cohort. The board-only control still shows whether the cases need the fact at all.
