# E2-C card pilot: 3 reserved k=1 traces, released methods

Rule `rebuttal/pilots/prereg/E2-C-card-pilot.md`, sha256
`63d3d2de992c…`; frozen before the first call. Technical pilot only, no
scoring and no casebook selection. 3 reserved calibration traces, one per
SHA order; 3 released methods x 2 backbones = **18 calls, 18 parsed, 0
failed, $0.156811**, cap $1.00.

**Rule-hash check.** The 8 November technical pilot's prereg is
`131904da48…`; the card pilot rule is `63d3d2de99…`. They do not match, so
the old pilot is not counted and this run is the card pilot.

## Qwen-235B backbone

| Method | Calls | Parsed |
|---|---:|---:|
| Who&When all-at-once (MIT) | 3 | 3 |
| Who&When-Pro `all_at_once`, 17-mode taxonomy | 3 | 3 |
| MAST (`definitions.txt` order) | 3 | 3 |

## Gemini 3.6 Flash backbone — **judged by the same model**

| Method | Calls | Parsed |
|---|---:|---:|
| Who&When all-at-once (MIT) | 3 | 3 |
| Who&When-Pro `all_at_once`, 17-mode taxonomy | 3 | 3 |
| MAST (`definitions.txt` order) | 3 | 3 |

The two blocks are stored separately in `results.json` by `backbone` and are
never pooled. Traces:
`qwen/qwen3-235b-a22b-2507·3hop1__273571_834494_33939`,
`qwen/qwen3-235b-a22b-2507·2hop__532383_768138`,
`openai/gpt-4o-mini·3hop1__273571_834494_33939`.

External files were re-fetched from the pinned MAST commit `a70542e`
(`taxonomy_definitions_examples/definitions.txt`,
`taxonomy_definitions_examples/examples.txt`, `llm_judge_pipeline.ipynb`) and
added to `rebuttal/external/MANIFEST.json`; `verify_external()` returns clean.