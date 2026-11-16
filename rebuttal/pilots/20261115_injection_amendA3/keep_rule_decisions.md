# Keep rule check, step 10b (kept A3 cases, 14 at 2026-11-15)

Rule: keep only if exactly one critical fact is removed, at the intended stage, with no surviving copy.
Mechanical test: `scripts/a3_keep_rule.py` -> `keep_rule.json`. Its coverage test (content tokens, >= 0.5) gives false
positives when a remaining sentence shares an entity with the fact (for example "Natalie Wood" in f1 counts toward
"Lana Wood is the sister of Natalie Wood"). Decisions below are from reading the remaining text.

| model | instance | type | intended | facts removed (reading) | decision |
|---|---|---|---|---|---|
| qwen235b | 2hop__189094_612080 | extraction | f1 | f1 and f2 (a0:u0 states both) | FAIL |
| gpt4omini | 2hop__826864_17335 | extraction | f1 | f1 only; f1 not in support set | DROP (your decision) |
| gemma31b | 2hop__434218_29898 | extraction | f1 | f1 and f2 (a0:u1 is the only f2 unit) | DROP (your decision) |
| gemma31b | 3hop2__655849_223623_162182 | extraction | f1 | f1 only | PASS |
| gemma31b | 2hop__89403_602275 | extraction | f1 | f1 only (a0:u1 is a related but not critical statement) | PASS |
| qwen235b | 2hop__301587_233146 | extraction | f1 | f1 and f2 (a0:u0 f1, a0:u1 f2) | FAIL |
| gemma31b | 3hop2__668732_223623_162182 | sharding | f1 | f1 only | PASS |
| qwen235b | 2hop__30905_213732 | sharding | f2 | f2 only (remaining agent-1 sentence is not a copy) | PASS |
| gpt4omini | 2hop__646493_5385 | sharding | f2 | f2 only | PASS |
| qwen235b | 2hop__20256_74481 | sharding | f1 | f1 only | PASS |
| gemma31b | 4hop3__31333_29339_508306_70744 | sharding | f2 | f2 only; remaining text is the question echo, which does not state the fact | PASS (note) |
| gemma31b | 2hop__82270_177869 | sharding | f2 | f2 only | PASS |
| gemma31b | 2hop__312223_144857 | sharding | f1 | f1 only | PASS |
| gemma31b | 2hop__89764_827343 | sharding | f2 | f2 only (survivor flagged by name overlap with f1) | PASS |

Kept after step 10b: extraction 2 (655849, 89403); sharding 8. Total 10.

## Step 10c additions (sharding to 360; 3 new kept cases, 2026-11-15)

| model | instance | type | intended | facts removed (reading) | decision |
|---|---|---|---|---|---|
| gemma31b | 2hop__33288_157788 | sharding | f2 | f2 only; no surviving copy | PASS |
| gemma31b | 3hop2__88342_93066_90766 | sharding | f2 | f3 also removed (f3 has no surviving copy); not the intended fact only | FAIL |
| qwen235b | 3hop1__163654_503371_21711 | sharding | f1 | f1 and f2: the deleted agent-0 sentence "Martin the Humane (29 July 1356 – 31 May 1410) ... King of Aragon ..." is the only statement of f2 (death 31 May 1410) | FAIL |

Step 10c keep set after drops: 11 cases (extraction 2, sharding 9). Dropped: 2hop__826864_17335 (your decision), 2hop__434218_29898 (your decision), 2hop__189094_612080, 2hop__301587_233146, 3hop2__88342_93066_90766, 3hop1__163654_503371_21711.
