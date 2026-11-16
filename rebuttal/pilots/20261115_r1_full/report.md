# [R1] re-implementation on the 89 known-stage cases

2026-11-15. Released all-at-once prompt and parser; our renderer; stage read from the released step coordinate under the hashed map `2015e084` (`R1-coordinate-stage-map.md`). The paper defines no stage taxonomy, so the stage map comes from the released taxonomy plus the renderer coordinate; stated once. Gemini 3.6 Flash. Spend **$0.870774** (projected $0.75, under the $1.00 cap).

| population | R1 stage correct | audit Gemini | audit Qwen | judge Gemini | judge Qwen |
| --- | ---: | ---: | ---: | ---: | ---: |
| injected (n=30) | 27/30 | 21 | 27 | 24 | 27 |
| cohort (n=59) | 26/59 | 40 | 30 | 43 | 29 |
| **all (n=89)** | **53/89 = .596** | **61** | **57** | **67** | **56** |

R1 does not beat the audit (53 against 57 on the Qwen backbone and 61 on Gemini), so no verification of a win is needed. The row is labelled a re-implementation: released prompt and parser, our renderer, and the released coordinate for the stage. The 30-case pilot is inside this 89 and not reported separately.

The earlier score that mapped mode codes to stages (0/89) is withdrawn; it used a hand map that the taxonomy does not support.

## Ledger
$0.870774.
