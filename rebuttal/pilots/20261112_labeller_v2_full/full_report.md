# Full labeller run, prompt v2

Prompt version `v2`, system sha256 `585d0d453ffceffe2372169ae7d312a2fbcab9d5854e241e96244f33dfdb8e6e`, file sha256 `7f9e281669ca06e00eac86405312bb54c05cc69834eb51a732e48a669e8268c6`. Model `anthropic/claude-haiku-5.5` via OpenRouter, temperature 0. Traces 150/150 parsed; 90 E1 + 60 SB, two authors each; calls 154 records for 150 traces; spend $0.114821 against a $0.25 cap. Strict single-object parse succeeded on 149/150; 0 trace(s) emitted more than one object. Balanced-object fallback used on 1 trace(s) (SB III-26_n5). Unparsed: 0. Retried above the 800-token output budget: 4 trace(s) at 2000 tokens.

Call log: `rebuttal/pilots/20261112_labeller_v2_full/calls.jsonl` (154 records, every attempted call). Manifest: `rebuttal/pilots/20261112_labeller/validation_150.jsonl`.

## Per-trace labels

| # | task | trace | labeller | author A | author B | agrees |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | E1 | Anchor Q01 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 2 | E1 | Anchor Q01 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 3 | E1 | Anchor Q01 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 4 | E1 | Anchor Q03 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 5 | E1 | Anchor Q03 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 6 | E1 | Anchor Q03 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 7 | E1 | Anchor Q05 run 1 | CORRECT | CORRECT | CORRECT | yes |
| 8 | E1 | Anchor Q05 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 9 | E1 | Anchor Q05 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 10 | E1 | Anchor Q07 run 1 | CORRECT | CORRECT | CORRECT | yes |
| 11 | E1 | Anchor Q07 run 2 | CORRECT | CORRECT | CORRECT | yes |
| 12 | E1 | Anchor Q07 run 3 | CORRECT | CORRECT | CORRECT | yes |
| 13 | E1 | Anchor Q09 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 14 | E1 | Anchor Q09 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 15 | E1 | Anchor Q09 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 16 | E1 | Anchor Q11 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 17 | E1 | Anchor Q11 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 18 | E1 | Anchor Q11 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 19 | E1 | Anchor Q13 run 1 | DEFECT | CORRECT | CORRECT | no |
| 20 | E1 | Anchor Q13 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 21 | E1 | Anchor Q13 run 3 | CORRECT | CORRECT | CORRECT | yes |
| 22 | E1 | Anchor Q15 run 1 | CORRECT | DEFECT | DEFECT | no |
| 23 | E1 | Anchor Q15 run 2 | DEFECT | CORRECT | CORRECT | no |
| 24 | E1 | Anchor Q15 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 25 | E1 | Anchor Q17 run 1 | CORRECT | CORRECT | CORRECT | yes |
| 26 | E1 | Anchor Q17 run 2 | CORRECT | CORRECT | CORRECT | yes |
| 27 | E1 | Anchor Q17 run 3 | CORRECT | CORRECT | CORRECT | yes |
| 28 | E1 | Anchor Q19 run 1 | CORRECT | DEFECT | DEFECT | no |
| 29 | E1 | Anchor Q19 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 30 | E1 | Anchor Q19 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 31 | E1 | Anchor Q21 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 32 | E1 | Anchor Q21 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 33 | E1 | Anchor Q21 run 3 | CORRECT | CORRECT | CORRECT | yes |
| 34 | E1 | Anchor Q23 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 35 | E1 | Anchor Q23 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 36 | E1 | Anchor Q23 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 37 | E1 | Anchor Q25 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 38 | E1 | Anchor Q25 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 39 | E1 | Anchor Q25 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 40 | E1 | Anchor Q27 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 41 | E1 | Anchor Q27 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 42 | E1 | Anchor Q27 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 43 | E1 | Anchor Q29 run 1 | DEFECT | DEFECT | DEFECT | yes |
| 44 | E1 | Anchor Q29 run 2 | DEFECT | DEFECT | DEFECT | yes |
| 45 | E1 | Anchor Q29 run 3 | DEFECT | DEFECT | DEFECT | yes |
| 46 | E1 | Anchor Q02 run 1 | DEFECT |  |  | no |
| 47 | E1 | Anchor Q02 run 2 | CORRECT |  |  | yes |
| 48 | E1 | Anchor Q02 run 3 | DEFECT |  |  | yes |
| 49 | E1 | Anchor Q04 run 1 | DEFECT |  |  | yes |
| 50 | E1 | Anchor Q04 run 2 | DEFECT |  |  | yes |
| 51 | E1 | Anchor Q04 run 3 | DEFECT |  |  | yes |
| 52 | E1 | Anchor Q06 run 1 | CORRECT |  |  | yes |
| 53 | E1 | Anchor Q06 run 2 | DEFECT |  |  | yes |
| 54 | E1 | Anchor Q06 run 3 | DEFECT |  |  | yes |
| 55 | E1 | Anchor Q08 run 1 | DEFECT |  |  | yes |
| 56 | E1 | Anchor Q08 run 2 | DEFECT |  |  | yes |
| 57 | E1 | Anchor Q08 run 3 | DEFECT |  |  | yes |
| 58 | E1 | Anchor Q10 run 1 | CORRECT |  |  | yes |
| 59 | E1 | Anchor Q10 run 2 | CORRECT |  |  | yes |
| 60 | E1 | Anchor Q10 run 3 | CORRECT |  |  | yes |
| 61 | E1 | Anchor Q12 run 1 | DEFECT |  |  | yes |
| 62 | E1 | Anchor Q12 run 2 | DEFECT |  |  | yes |
| 63 | E1 | Anchor Q12 run 3 | CORRECT |  |  | yes |
| 64 | E1 | Anchor Q14 run 1 | CORRECT |  |  | yes |
| 65 | E1 | Anchor Q14 run 2 | DEFECT |  |  | yes |
| 66 | E1 | Anchor Q14 run 3 | CORRECT |  |  | yes |
| 67 | E1 | Anchor Q16 run 1 | CORRECT |  |  | yes |
| 68 | E1 | Anchor Q16 run 2 | DEFECT |  |  | yes |
| 69 | E1 | Anchor Q16 run 3 | DEFECT |  |  | yes |
| 70 | E1 | Anchor Q18 run 1 | CORRECT |  |  | no |
| 71 | E1 | Anchor Q18 run 2 | DEFECT |  |  | yes |
| 72 | E1 | Anchor Q18 run 3 | CORRECT |  |  | yes |
| 73 | E1 | Anchor Q20 run 1 | DEFECT |  |  | yes |
| 74 | E1 | Anchor Q20 run 2 | DEFECT |  |  | yes |
| 75 | E1 | Anchor Q20 run 3 | DEFECT |  |  | yes |
| 76 | E1 | Anchor Q22 run 1 | DEFECT |  |  | yes |
| 77 | E1 | Anchor Q22 run 2 | CORRECT |  |  | yes |
| 78 | E1 | Anchor Q22 run 3 | DEFECT |  |  | yes |
| 79 | E1 | Anchor Q24 run 1 | DEFECT |  |  | yes |
| 80 | E1 | Anchor Q24 run 2 | DEFECT |  |  | yes |
| 81 | E1 | Anchor Q24 run 3 | CORRECT |  |  | yes |
| 82 | E1 | Anchor Q26 run 1 | DEFECT |  |  | yes |
| 83 | E1 | Anchor Q26 run 2 | DEFECT |  |  | yes |
| 84 | E1 | Anchor Q26 run 3 | DEFECT |  |  | yes |
| 85 | E1 | Anchor Q28 run 1 | CORRECT |  |  | yes |
| 86 | E1 | Anchor Q28 run 2 | CORRECT |  |  | yes |
| 87 | E1 | Anchor Q28 run 3 | CORRECT |  |  | yes |
| 88 | E1 | Anchor Q30 run 1 | DEFECT |  |  | yes |
| 89 | E1 | Anchor Q30 run 2 | DEFECT |  |  | yes |
| 90 | E1 | Anchor Q30 run 3 | DEFECT |  |  | yes |
| 91 | SB | I-02_n10 | DEFECT | DEFECT | DEFECT | yes |
| 92 | SB | I-02_n10 | DEFECT | DEFECT | DEFECT | yes |
| 93 | SB | I-02_n10 | DEFECT | DEFECT | DEFECT | yes |
| 94 | SB | I-02_n5 | DEFECT | DEFECT | DEFECT | yes |
| 95 | SB | I-02_n5 | DEFECT | DEFECT | DEFECT | yes |
| 96 | SB | I-02_n5 | CORRECT | CORRECT | CORRECT | yes |
| 97 | SB | I-03_n10 | CORRECT | CORRECT | CORRECT | yes |
| 98 | SB | I-03_n10 | CORRECT | CORRECT | CORRECT | yes |
| 99 | SB | I-03_n10 | CORRECT | CORRECT | CORRECT | yes |
| 100 | SB | I-03_n5 | CORRECT | CORRECT | CORRECT | yes |
| 101 | SB | I-03_n5 | CORRECT | CORRECT | CORRECT | yes |
| 102 | SB | I-03_n5 | CORRECT | CORRECT | CORRECT | yes |
| 103 | SB | I-05_n5 | DEFECT | DEFECT | DEFECT | yes |
| 104 | SB | I-05_n5 | DEFECT | DEFECT | DEFECT | yes |
| 105 | SB | I-05_n5 | DEFECT | DEFECT | DEFECT | yes |
| 106 | SB | I-08_n5 | DEFECT | DEFECT | DEFECT | yes |
| 107 | SB | I-08_n5 | DEFECT | DEFECT | DEFECT | yes |
| 108 | SB | I-08_n5 | CORRECT | CORRECT | CORRECT | yes |
| 109 | SB | I-09_n10 | DEFECT | DEFECT | DEFECT | yes |
| 110 | SB | I-09_n10 | DEFECT | DEFECT | DEFECT | yes |
| 111 | SB | I-09_n10 | CORRECT | CORRECT | CORRECT | yes |
| 112 | SB | I-10_n10 | DEFECT | DEFECT | DEFECT | yes |
| 113 | SB | I-10_n10 | DEFECT | DEFECT | DEFECT | yes |
| 114 | SB | I-10_n10 | DEFECT | DEFECT | DEFECT | yes |
| 115 | SB | II-13_n10 | DEFECT | DEFECT | DEFECT | yes |
| 116 | SB | II-13_n10 | DEFECT | DEFECT | DEFECT | yes |
| 117 | SB | II-13_n10 | DEFECT | DEFECT | DEFECT | yes |
| 118 | SB | II-15_n5 | CORRECT | DEFECT | DEFECT | no |
| 119 | SB | II-15_n5 | DEFECT | DEFECT | DEFECT | yes |
| 120 | SB | II-15_n5 | CORRECT | CORRECT | CORRECT | yes |
| 121 | SB | II-17_n10 | DEFECT |  |  | yes |
| 122 | SB | II-17_n10 | DEFECT |  |  | yes |
| 123 | SB | II-17_n10 | DEFECT |  |  | yes |
| 124 | SB | II-18_n10 | DEFECT |  |  | yes |
| 125 | SB | II-18_n10 | DEFECT |  |  | yes |
| 126 | SB | II-18_n10 | DEFECT |  |  | yes |
| 127 | SB | II-18_n5 | DEFECT |  |  | yes |
| 128 | SB | II-18_n5 | DEFECT |  |  | yes |
| 129 | SB | II-18_n5 | DEFECT |  |  | yes |
| 130 | SB | III-23_n10 | DEFECT |  |  | yes |
| 131 | SB | III-23_n10 | DEFECT |  |  | yes |
| 132 | SB | III-23_n10 | DEFECT |  |  | yes |
| 133 | SB | III-23_n5 | DEFECT |  |  | yes |
| 134 | SB | III-23_n5 | DEFECT |  |  | yes |
| 135 | SB | III-23_n5 | DEFECT |  |  | yes |
| 136 | SB | III-24_n5 | DEFECT |  |  | yes |
| 137 | SB | III-24_n5 | DEFECT |  |  | yes |
| 138 | SB | III-24_n5 | DEFECT |  |  | yes |
| 139 | SB | III-26_n5 | DEFECT |  |  | yes |
| 140 | SB | III-26_n5 | DEFECT |  |  | yes |
| 141 | SB | III-26_n5 | CORRECT |  |  | yes |
| 142 | SB | III-27_n5 | DEFECT |  |  | yes |
| 143 | SB | III-27_n5 | DEFECT |  |  | yes |
| 144 | SB | III-27_n5 | DEFECT |  |  | yes |
| 145 | SB | III-29_n5 | DEFECT |  |  | yes |
| 146 | SB | III-29_n5 | DEFECT |  |  | yes |
| 147 | SB | III-29_n5 | DEFECT |  |  | yes |
| 148 | SB | III-30_n10 | DEFECT |  |  | yes |
| 149 | SB | III-30_n10 | DEFECT |  |  | yes |
| 150 | SB | III-30_n10 | DEFECT |  |  | yes |

## Agreement

- Raw agreement: **0.953** (286 of 300 author comparisons).
- Cohen kappa: **0.878**.
- 95% CI: agreement **0.913-0.987**, kappa **0.760-0.965** (cluster bootstrap, 50 clusters, 2,000 draws, seed 42).
- Disagreements: 7 traces.

### E1 Anchor Q13 run 1

Gold: `[1000, 1000, 999, 997, 995, 994, 994, 993, 993, 984]`  
Answer: `[1000, 999, 997, 995, 994, 993, 984, 982, 981, 980]`  
exact token-F1: 0.700 (stricter than the authors).  
Labeller: DEFECT — The final answer differs from the gold: it omits the second 1000, second 994 and second 993 that the gold requires, and adds 982, 981 and 980 in their place. The faithful value 1000 from agent 7 (board:a7:u0) was on the board but did not reach the final list, so the loss is at the board checkpoint.  
Authors: A=CORRECT, B=CORRECT

### E1 Anchor Q15 run 1

Gold: `1981`  
Answer: `By the early 1980s`  
exact token-F1: 0.000 (more lenient than the authors).  
Labeller: CORRECT — The gold answer '1981' is not stated in the final answer 'By the early 1980s', so the answers differ after normalization (tokens '1981' vs 'by early 1980s'). However, the rule requires me to check for a checkpoint defect: the fact that Honda, Toyota and Nissan opened US assembly plants in the early 1980s, tied to the 1981 voluntary export restraints, is faithfully carried in extraction:a2:u0 and board:a2:u0, and the 1981 year appears in the source for agent-2 without distortion. The answer is imprecise rather than distorted at any checkpoint, so no pool or board defect is identifiable.  
Authors: A=DEFECT, B=DEFECT

### E1 Anchor Q15 run 2

Gold: `1981`  
Answer: `Acura Legend's maker (Honda) opened US assembly plants in the early 1980s, Lexus's maker (Toyota) opened US assembly plants around the same time, and Nissan opened US assembly plants shortly after, affected by the 1981 voluntary export restraints.`  
exact token-F1: 0.053 (stricter than the authors).  
Labeller: DEFECT — The gold answer is 1981, a specific year, but the final answer gives only 'early 1980s' and 'shortly after' with no year. The critical fact that the plants opened in 1981 (the year of the voluntary export restraints) is never extracted precisely: extraction:a2:u0 states the opening only as 'a decade after the 1973 oil crisis' and omits the 1981 date from the source's 'affected by the 1981 voluntary export restraints' phrasing, so the pool carries a partial fact and the answer fails to reach the required year.  
Authors: A=CORRECT, B=CORRECT

### E1 Anchor Q19 run 1

Gold: `in the north-east of the country south of the Caspian Sea`  
Answer: `In the north-east of Iran, south of the Caspian Sea.`  
exact token-F1: 0.889 (more lenient than the authors).  
Labeller: CORRECT — Normalized gold tokens are 'in north east of country south of caspian sea'; the final answer 'In the north-east of Iran, south of the Caspian Sea' differs by the added word 'Iran' and the omitted 'country', so by the stated rule the token lists are not identical and this is a DEFECT rather than CORRECT. Checkpoint: the critical fact (north-east, south of Caspian Sea) is present and faithfully carried in pool unit extraction:a1:u0 and board unit board:a1:u0, so the defect lies in the final answer's wording rather than in an evidence checkpoint.  
Authors: A=DEFECT, B=DEFECT

### E1 Anchor Q02 run 1

Gold: `fleur - de-lis`  
Answer: `The symbol is called the fleur-de-lis.`  
exact token-F1: 0.667 (stricter than the authors).  
Labeller: DEFECT — The final answer adds words ('symbol is called') so its normalized tokens differ from the gold 'fleur de lis'. The critical fact that Blanton's manufacturer (Sazerac Company) is headquartered in New Orleans is not supported by any source text; it first appears as unsupported pool extractions (extraction:a0:u1, extraction:a2:u2).  
Authors: C=CORRECT, D=CORRECT

### E1 Anchor Q18 run 1

Gold: `GDR`  
Answer: `East Germany`  
exact token-F1: 0.000 (more lenient than the authors).  
Labeller: CORRECT — The final answer 'East Germany' normalizes to the same tokens as the gold 'GDR' only if treated as equivalent; under the strict token rule, 'east germany' does not equal 'gdr', so this is a difference in naming rather than a value. However, the gold answer is the abbreviation for the same country, and the comparison rule requires identical token lists, which fails here, so the verdict should be DEFECT with the pool/board carrying the fact that the country is East Germany (GDR) faithfully.  
Authors: C=DEFECT, D=DEFECT

### SB II-15_n5

Gold: `7`  
Answer: `28`  
Silo-Bench exact match: 0.000 (more lenient than the authors).  
Labeller: CORRECT — All five string segments and the A...B...C pattern definition are faithfully restated in both the pool and the board, so no critical fact is absent or distorted at any checkpoint; the wrong final answer (28 vs gold 7) arises from the computation step rather than evidence flow.  
Authors: A=DEFECT, B=DEFECT

## Held-out check

20 of the 150 traces are the v1 pilot, which was used to design the v2 prompt. Excluding them, the held-out 130 traces score agreement **0.954** (248 of 260; 95% CI 0.907-0.992) and kappa **0.881** (95% CI 0.756-0.976); 6 of the 7 disagreements are in the held-out set. The full-set and held-out scores are effectively the same.

## Go / no-go

Requirement: lower CI bound at least 0.80 agreement and kappa at least 0.60. **Passed.**

## Caveat

The v2 dev re-pilot sample was author-unanimous, so its 0.950/0.900 score tested agreement with a consensus label, not disagreement resolution. The 150-trace set has no traces where the two authors differ, so it does not test disagreement resolution either; both scores measure agreement against consensus labels. The 7 disagreements are labeller-vs-authors, not author-vs-author.

Of the 7 disagreements, 4 are the labeller returning CORRECT on an answer the authors call DEFECT: E1 Anchor Q15 run 1, E1 Anchor Q19 run 1, E1 Anchor Q18 run 1, SB II-15_n5. Two of those rationales argue the evidence flow is faithful, which the prompt treats as CORRECT when the answer is wrong only at computation; two (Q18 run 1 and Q19 run 1) state the strict token rule gives DEFECT and then return CORRECT anyway. The other disagreements are the labeller applying the strict token rule where the authors were lenient. The pass is therefore against unanimous authors; the lenient class is a prompt-definition boundary, and the two explicit contradictions are genuine prompt-following errors.

