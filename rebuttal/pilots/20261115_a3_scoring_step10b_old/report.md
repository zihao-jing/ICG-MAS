# A3 + A4 injection: kept cases and scorings

2026-11-15. $0, no model calls. Script `scripts/a3_scoring.py`; numbers in `score.json` (same folder). Sources: `rebuttal/pilots/20261115_injection_amendA3/results.json` and `..._amendA4/results.json`. Raw counts only (correct of kept cases, n); no rates or intervals. A cell is correct when its stage equals the injected type. Rule hashes: A3 `Injection-v1-amendment-A3.md` sha256 2fea3ca5…; A4 `Injection-v1-amendment-A4.md` sha256 10e16f8e…. Eight scorings: audit (word-overlap and statement rules) on Qwen and Gemini, judge on Qwen and Gemini, [R1] on Qwen and Gemini = 8 cells.

## Tried and kept (per type and model)

| type | gemma31b tried / kept | gpt4omini tried / kept | qwen235b tried / kept | total kept |
| --- | --- | --- | --- | ---: |
| extraction | 79 / 3 | 105 / 1 | 132 / 2 | 6 |
| sharding | 100 / 4 | 100 / 1 | 100 / 2 | 7 |

## Scorings (correct of kept cases, n)

| type | cell | gemma31b | gpt4omini | qwen235b | all |
| --- | --- | --- | --- | --- | --- |
| extraction | audit_qwen_old | 0 of 3 | 0 of 1 | 1 of 2 | 1 of 6 |
| extraction | audit_qwen_fix | 1 of 3 | 0 of 1 | 2 of 2 | 3 of 6 |
| extraction | audit_gemini_old | 2 of 3 | 0 of 1 | 2 of 2 | 4 of 6 |
| extraction | audit_gemini_fix | 2 of 3 | 0 of 1 | 2 of 2 | 4 of 6 |
| extraction | judge_qwen | 1 of 3 | 0 of 1 | 2 of 2 | 3 of 6 |
| extraction | judge_gemini | 1 of 3 | 1 of 1 | 1 of 2 | 3 of 6 |
| extraction | r1_qwen | 3 of 3 | 1 of 1 | 2 of 2 | 6 of 6 |
| extraction | r1_gemini | 2 of 3 | 0 of 1 | 2 of 2 | 4 of 6 |
| sharding | audit_qwen_old | 3 of 4 | 1 of 1 | 1 of 2 | 5 of 7 |
| sharding | audit_qwen_fix | 1 of 4 | 1 of 1 | 1 of 2 | 3 of 7 |
| sharding | audit_gemini_old | 4 of 4 | 1 of 1 | 1 of 2 | 6 of 7 |
| sharding | audit_gemini_fix | 4 of 4 | 1 of 1 | 1 of 2 | 6 of 7 |
| sharding | judge_qwen | 2 of 4 | 1 of 1 | 1 of 2 | 4 of 7 |
| sharding | judge_gemini | 4 of 4 | 1 of 1 | 2 of 2 | 7 of 7 |
| sharding | r1_qwen | 0 of 4 | 0 of 1 | 0 of 2 | 0 of 7 |
| sharding | r1_gemini | 0 of 4 | 0 of 1 | 0 of 2 | 0 of 7 |
