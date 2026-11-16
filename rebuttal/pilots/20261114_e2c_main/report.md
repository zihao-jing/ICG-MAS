# E2-C main run: 7 of the carded 12 traces

Selected before any baseline call, SHA order within class, from the 156
frozen k = 1 traces and their E1 judge labels.

| Cell | Carded | Ran | Traces |
|---|---:|---:|---|
| Silo-Bench extraction | 4 | 3 | `II-18_n10` (qwen, gemma), `III-24_n5` (qwen) |
| Silo-Bench selection | 4 | **0** | none eligible |
| MuSiQue aggregation | 2 | 2 | `3hop2__92991_28727_76291`, `3hop2__106842_30645_84681` |
| Silo-Bench aggregation | 2 | 2 | `III-23_n10` (gpt4omini), `I-09_n10` (qwen) |
| **Total** | **12** | **7** | |

**No selection claim is made.** The k = 3 judge labels contain no selection
omissions (at k = 3 every extracted unit is transmitted), so the selection
cell is empty. The table reports 7 of 12 and the shortfall; nothing was
relabelled or refilled.

Calls: 3 released methods × 2 backbones × 7 traces = **42 calls, 0 failed,
$0.408542** (cap 72 calls / $2.00). Gemini-backbone rows are stored separately
and marked "judged by the same model"; they are not pooled with Qwen.

## E2-C judge validation

20 baseline outputs (10 traces × 2 methods), Opus 5.5 reference then Gemini
3.6 Flash, frozen reference `01d4a921…`. **17 of 20 valid pairs; 3 Gemini
outputs were excluded because they were not valid JSON** (format failures,
not substantive labels). Agreement **1.000 [1.000, 1.000]**, Cohen's kappa
**1.000 [1.000, 1.000]**. The bar (agreement ≥ .80, kappa ≥ .60) passes, so
the E2-C judge label may be used; the exclusion of 3/20 format failures is
reported beside it. No E2-C judge label had been written before this record.

**Small-sample caveat.** This is a small-sample pass on 17 items. The
intervals are degenerate at 1.000 because every included pair agreed; they do
not establish strong agreement, and the point estimate should be read with
the 3 excluded format failures beside it.

**Selection label.** The E2-C casebook classes come from the E1 judge, which
was validated against the authors' labels at kappa .676 [.526, .804]. The
author labels are the validation reference only; no author label is an input
to the casebook.