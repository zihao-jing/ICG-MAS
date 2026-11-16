# [R1] on our traces: released prompt path, our renderer, frozen mode map (pilot)

2026-11-15. Cap **$0.80**. 30 injected cases (known stage: transmission). Paper model: Gemini 3.6 Flash.
This is a **re-implementation using the released prompt and parser**, not the released method run as shipped:
the released code is vendored (`rebuttal/external/whowhen_eval/`, pinned in `MANIFEST.json`), but its expected
trace format is ALFWorld/GAIA, and our traces are relay states.

## What is taken unchanged from the release

The all-at-once prompt (`whowhen_eval.prompts.all_at_once` with `user_msg`, taxonomy from
`rebuttal/external/taxonomy.yaml`), the 17 mode codes and names, and the official parser (`parse_all_at_once`,
`_FIELD_RE`). No prompt text is edited.

## Deviations from the paper's description

1. **Trace rendering.** The release reads its own benchmark history; our trace is rendered by
   `src/audit/pilot_common.render_trace` (per-agent extraction, transmission, then the board and the wrong
   answer) and then passed through the released renderer interface. This is not the ALFWorld/GAIA renderer.
2. **Stage map.** The released taxonomy has 17 modes; our audit has 4 stages. The map below is ours, frozen
   before calls, and is the main deviation: it converts the released mode into our vocabulary rather than
   scoring the released mode directly.
3. **Backbone.** Gemini 3.6 Flash, chosen as a paper model; the release's own experiments did not use it.

## Frozen mode -> stage map

| mode | stage |
| --- | --- |
| P.1 Visual misidentification | extraction |
| P.2 Spatial/grounding error | extraction |
| R.1 Hallucination | aggregation |
| R.2 Reasoning error | aggregation |
| R.3 Numerical/calculation error | aggregation |
| R.4 Task misunderstanding | aggregation |
| PL.1 Ineffective Planning | aggregation |
| PL.2 Goal drift | aggregation |
| A.1 Tool parameter/invocation error | extraction |
| A.2 Output format/syntax error | extraction |
| A.3 Premature termination | aggregation |
| A.4 Repetitive/looping behavior | aggregation |
| V.1 Context/memory loss | transmission |
| V.2 Inadequate or incorrect verification | aggregation |
| C.1 Delegation/orchestration error | aggregation |
| C.2 Communication failure | transmission |
| C.3 Over-reliance on other agents | aggregation |

Unparsed or invalid modes score wrong and are counted separately.

## Outcome

Stage accuracy on the 30 injected cases with a Clopper-Pearson interval, the mode distribution, and the share
of outputs whose stage is transmission. Pilot result decides whether the full 89-case run is proposed.