# E2-C card pilot rule (frozen before the run)

Date: 2026-11-14. Technical pilot only, not the casebook evaluation. Three
reserved calibration traces stored at k = 1, drawn by ascending SHA-256 of
canonical JSON `["E2-C-card-pilot", 43, model, instance_id]`.

## Methods and backbones

Three released methods, unchanged: Who&When all-at-once (MIT),
Who&When-Pro `all_at_once` with the released 17-mode `taxonomy.yaml`, and
MAST (`definitions.txt`, notebook order mapped to the definitions). Two
backbones: `qwen/qwen3-235b-a22b-2507` and `google/gemini-3.6-flash`.
One call per method per backbone per trace; 3 x 3 x 2 = **18 calls**.

The Gemini-backbone outputs are stored in a separate block and marked
"judged by the same model"; they are never pooled with Qwen.

## What the pilot checks

Renderer, released-prompt loading, parser success and measured cost. No
scoring against labels and no casebook selection: those belong to the main
run. Cap **$1.00**.

## Frozen inputs

Pinned external files are verified against `rebuttal/external/MANIFEST.json`
before the first call. Trace ids and the rule hash are frozen in
`run_identity.json` before dispatch.