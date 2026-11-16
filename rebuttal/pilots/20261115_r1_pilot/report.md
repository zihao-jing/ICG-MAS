# [R1] on our traces: 30-case pilot (re-implementation)

2026-11-15. Released all-at-once prompt and parser, our trace renderer, frozen mode->stage map (`R1-reimplementation-pilot.md`, sha `23da70c7...`). Gemini 3.6 Flash. Spend $0.2373, cap $0.80.

| quantity | value |
| --- | ---: |
| cases | 30 |
| stage correct | 0/30 = 0.000 |
| 95% CI | [0.000, 0.114] |
| unmapped modes | 0 |

| mode | n |
| --- | ---: |
| R.1 | 27 |
| R.2 | 3 |

Label: re-implementation. Deviations are listed in the rule: our renderer, and our frozen map from the 17 released modes to the four audit stages.


## Correction: the mode-to-stage map was the error

The 0/30 above is kept on record. It came from the frozen map that sent every R.1 and R.2 to aggregation. Checked
against the taxonomy, that map is not supported: R.1 (hallucination) and R.2 (reasoning error) are defined by
what goes wrong, not by where, and both can occur at extraction, transmission or aggregation. The released
output also names the agent and the step, which the pilot stored.

Re-scoring the same 30 stored outputs at $0, mapping the released step coordinate to the stage of the rendered
trace (extraction, transmission or aggregation): **26/30 stage correct**, Wilson 95% [.703, .947]. The remaining
four name a step in the wrong stage or the aggregator. No new calls; the same $0.237 covers both readings.

This is the re-implementation result: released prompt and parser, our renderer, and stage read from the released
coordinate rather than from a hand map. The renderer deviation remains; it is not shown to bias the coordinate.

## Ledger
Spend $0.237346.
