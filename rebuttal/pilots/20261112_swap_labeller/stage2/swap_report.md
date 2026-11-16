# Distortion swap generation, swap-v1

Prompt `swap-v1` (labeller-v2), file sha256 `f2499ad68780e5ba147aec6d6586d9e74a439ac1b11ee72137ab35beb27fe095`, system sha256 `f6edc28eb401888d808ab64c861089416358a2a471dadef128638637ad31ef3e`, model `anthropic/claude-haiku-5.5`, temperature 0. Cases 176; calls 176; spend $0.038218 against a $0.50 cap.

Call log: `rebuttal/pilots/20261112_swap_labeller/stage2/calls.jsonl`; case list: `rebuttal/pilots/20261112_swap_labeller/stage2/swap_cases.jsonl` (1a98fac097c5082dc1e947025b0cc585c3307b8dd4bd6ee8d094676469fe43b2); swap records: `rebuttal/pilots/20261112_swap_labeller/stage2/swaps.jsonl`.

## Gate results

- Accepted: **6** of 176.
- Rejected: **170**.
- Gate: span verbatim in the source context; `distortion_gate` swap recall >= 0.8 and replaced-unit recall >= 0.5; `delivery_reasons` clear (not question, header, refusal or data list; recall >= 0.8).

| reason | cases |
| --- | ---: |
| swap or replaced unit misses the distorted fact | 153 |
| labeller returned no span | 17 |
| fact recall 0.67 < 0.8 | 9 |
| fact recall 0.50 < 0.8 | 7 |
| span is not a verbatim substring of the source context | 6 |
| fact recall 0.43 < 0.8 | 4 |
| fact recall 0.75 < 0.8 | 4 |
| fact recall 0.56 < 0.8 | 4 |
| fact recall 0.62 < 0.8 | 4 |
| fact recall 0.57 < 0.8 | 4 |
| fact recall 0.29 < 0.8 | 3 |
| fact recall 0.40 < 0.8 | 3 |
| fact recall 0.25 < 0.8 | 3 |
| fact recall 0.60 < 0.8 | 3 |
| fact recall 0.38 < 0.8 | 2 |
| fact recall 0.17 < 0.8 | 2 |
| fact recall 0.46 < 0.8 | 2 |
| fact recall 0.64 < 0.8 | 2 |
| fact recall 0.18 < 0.8 | 2 |
| fact recall 0.33 < 0.8 | 2 |
| fact recall 0.30 < 0.8 | 2 |
| fact recall 0.71 < 0.8 | 2 |
| fact recall 0.78 < 0.8 | 2 |
| fact recall 0.36 < 0.8 | 2 |
| fact recall 0.54 < 0.8 | 1 |
| fact recall 0.45 < 0.8 | 1 |
| fact recall 0.79 < 0.8 | 1 |
| fact recall 0.69 < 0.8 | 1 |
| fact recall 0.59 < 0.8 | 1 |
| fact recall 0.73 < 0.8 | 1 |
| fact recall 0.11 < 0.8 | 1 |
| fact recall 0.27 < 0.8 | 1 |
| fact recall 0.21 < 0.8 | 1 |
| fact recall 0.42 < 0.8 | 1 |
| fact recall 0.58 < 0.8 | 1 |
| fact recall 0.77 < 0.8 | 1 |
| fact recall 0.23 < 0.8 | 1 |
| fact recall 0.00 < 0.8 | 1 |
| fact recall 0.12 < 0.8 | 1 |
| document header | 1 |
| fact recall 0.14 < 0.8 | 1 |
| fact recall 0.20 < 0.8 | 1 |
| fact recall 0.53 < 0.8 | 1 |
| fact recall 0.08 < 0.8 | 1 |
| fact recall 0.37 < 0.8 | 1 |

## Accepted swaps

### 3hop1__129675_39743_24526 / gpt4omini / board:a2:u0

Question: What is the average daytime temperature in the region where Richmond is found, in the state where WGCK-FM is located?  
Gold: `upper 40s–lower 50s °F`  
Span: `In winter, the Piedmont is colder than the coast, with temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C) during the day and often dropping below the freezing point at night.`  
Fact: f3 — `The Piedmont region has winter daytime temperatures averaging in the upper 40s–lower 50s °F (8–12 °C).`  
Swap recall: {'f3': 0.812}; replaced recall: {'f3': 0.875}.

### 3hop1__390489_502967_84283 / gpt4omini / board:a2:u0

Question: Who is the owner of the record label of the performer of Flamenco a Go-Go?  
Gold: `Warner Music Group`  
Span: `Warner Bros. Records Parent company Warner Music Group`  
Fact: f4 — `Warner Music Group is the parent company of Warner Bros. Records.`  
Swap recall: {'f4': 0.8}; replaced recall: {'f4': 1.0}.

### 3hop1__131110_39743_24526 / gemma31b / board:a0:u0

Question: In the state that includes Walnut Spring, what's the typical winter daytime temperature range in the region of Richmond?  
Gold: `upper 40s–lower 50s °F`  
Span: `In winter, the Piedmont is colder than the coast, with temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C) during the day and often dropping below the freezing point at night.`  
Fact: f3 — `In winter, the Piedmont region has daytime temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C).`  
Swap recall: {'f3': 0.833}; replaced recall: {'f3': 1.0}.

### 3hop1__131110_39743_24526 / gpt4omini / board:a0:u0

Question: In the state that includes Walnut Spring, what's the typical winter daytime temperature range in the region of Richmond?  
Gold: `upper 40s–lower 50s °F`  
Span: `In winter, the Piedmont is colder than the coast, with temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C) during the day and often dropping below the freezing point at night.`  
Fact: f3 — `In winter, the Piedmont region has daytime temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C).`  
Swap recall: {'f3': 0.833}; replaced recall: {'f3': 0.833}.

### 3hop1__131110_39743_24526 / qwen235b / board:a0:u1

Question: In the state that includes Walnut Spring, what's the typical winter daytime temperature range in the region of Richmond?  
Gold: `upper 40s–lower 50s °F`  
Span: `In winter, the Piedmont is colder than the coast, with temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C) during the day and often dropping below the freezing point at night.`  
Fact: f3 — `In winter, the Piedmont region has daytime temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C).`  
Swap recall: {'f3': 0.833}; replaced recall: {'f3': 0.833}.

### 3hop1__129675_39743_24526 / qwen235b / board:a2:u0

Question: What is the average daytime temperature in the region where Richmond is found, in the state where WGCK-FM is located?  
Gold: `upper 40s–lower 50s °F`  
Span: `In winter, the Piedmont is colder than the coast, with temperatures usually averaging in the upper 40s–lower 50s °F (8–12 °C) during the day and often dropping below the freezing point at night.`  
Fact: f3 — `The Piedmont region has winter daytime temperatures averaging in the upper 40s–lower 50s °F (8–12 °C).`  
Swap recall: {'f3': 0.812}; replaced recall: {'f3': 0.875}.

## Rejected swaps

The rejected spans and their reasons are in `swaps.jsonl`.

