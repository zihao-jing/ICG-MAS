# B7e: sentence-format insertion run with Gemini 3.6 Flash

2026-11-15. Frozen rule `B7e` (derived from `B7d-paper-model-aggregator.md`; same 59 cases, boards and inserted
facts, Gemini 3.6 Flash in both arms, sentence-format system prompt). Spend **$0.329423**, cap $1.00.

## Result

| arm | Gemini sentence | Gemini bare (B7d) | earlier model sentence | earlier model bare (B7c) | Opus bare (B7b) |
| --- | ---: | ---: | ---: | ---: | ---: |
| insert | **33/59** | 32/59 | 32/59 | 30/59 | 43/59 |
| control | 0/59 | 1/59 | 0/59 | 0/59 | 5/59 |

Paired, per case, exact match; 2,000-draw case bootstrap, seed 43:

| effect | difference [95% CI] |
| --- | --- |
| format at Gemini (sentence minus bare) | +.017 [−.034, +.085] |
| model at sentence (Gemini minus earlier) | +.017 [−.034, +.085] |
| model at bare (Gemini minus earlier) | +.034 [−.051, +.119] |
| model at bare (Opus minus Gemini) | +.186 [+.085, +.288] |
| format at Opus (bare minus sentence) | +.356 [+.237, +.475] |
| model at sentence (Opus minus earlier) | −.169 [−.305, −.034] |

**Paper-model effects are null in every cell.** Format does not move answers for either paper model, and the
two paper models do not differ from each other. The large effects belong to Opus alone, in both directions,
which is why the Opus runs are marked not usable as paper-subject evidence.

Within the Gemini run, insert minus control is +.559 [+.441, +.678].

## Ledger

$0.329423, cap $1.00.

## Transport

All calls through OpenRouter; Gemini 3.6 Flash, `google/gemini-3.6-flash`.