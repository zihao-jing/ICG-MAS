# Distortion swap generation, swap-v1

Prompt `swap-v1` (labeller-v2), file sha256 `f2499ad68780e5ba147aec6d6586d9e74a439ac1b11ee72137ab35beb27fe095`, system sha256 `f6edc28eb401888d808ab64c861089416358a2a471dadef128638637ad31ef3e`, model `anthropic/claude-haiku-5.5`, temperature 0. Cases 25; calls 25; spend $0.005423 against a $0.50 cap.

Call log: `rebuttal/pilots/20261112_swap_labeller/calls.jsonl`; case list: `rebuttal/pilots/20261112_swap_labeller/swap_cases.jsonl` (1e21e0658f6875684eca5262b6e6bfc22dc8ef79a3974eb0be65c686302a1382); swap records: `rebuttal/pilots/20261112_swap_labeller/swaps.jsonl`.

## Gate results

- Accepted: **1** of 25.
- Rejected: **24**.
- Gate: span verbatim in the source context; `distortion_gate` swap recall >= 0.8 and replaced-unit recall >= 0.5; `delivery_reasons` clear (not question, header, refusal or data list; recall >= 0.8).

| reason | cases |
| --- | ---: |
| swap or replaced unit misses the distorted fact | 20 |
| labeller returned no span | 4 |
| fact recall 0.50 < 0.8 | 3 |
| fact recall 0.44 < 0.8 | 1 |
| fact recall 0.71 < 0.8 | 1 |
| fact recall 0.61 < 0.8 | 1 |
| fact recall 0.48 < 0.8 | 1 |
| fact recall 0.57 < 0.8 | 1 |
| fact recall 0.00 < 0.8 | 1 |

## Accepted swaps

### 4hop3__152056_698586_91248_54362 / openai/gpt-4o-mini / board:a1:u1

Question: Who burned down the city where Dunn Dunn's artist died in the war after which the government got involved in healthcare?  
Gold: `Confederate Gen. John Bell Hood`  
Span: `On September 1, 1864, Confederate Gen. John Bell Hood evacuated Atlanta, after a five - week siege mounted by Union Gen. William Sherman, and ordered all public buildings and possible Confederate assets destroyed.`  
Fact: f8 — `After evacuating Atlanta, Gen. John Bell Hood ordered all public buildings and possible Confederate assets destroyed.`  
Swap recall: {'f8': 0.938}; replaced recall: {'f8': 0.625}.

## Rejected swaps

The rejected spans and their reasons are in `swaps.jsonl`.

