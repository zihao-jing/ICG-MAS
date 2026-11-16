# Selection repair, volume-matched targeted request

2026-11-15. Rule `Selection-repair-volume-matched.md` (sha `a7a83c75...`). Board unit count held constant: the first target request unit replaces the last board unit of the same agent. Spend $0.005452, cap $0.50.

| arm | exact | n | paired difference vs rerun [95% CI] | volume-matched |
| --- | ---: | ---: | --- | ---: |
| R-sel-replace | 13 | 52 | -0.019 [-0.115, +0.058] | 49 |
| plain rerun | 14 | 52 | — | — |

Case bootstrap over pairs, 2,000 draws, seed 43. Exact match against the gold answer.

The earlier targeted-request arm (R-sel, append up to two units) scored 16/52 against the same
rerun's 14/52, +.038 [+.000, +.098], while its board volume matched the rerun in only 14 of 52
cases; within those 14 the effect was 0. This arm holds the unit count constant and matches
volume in 49 of 52, and the effect is null. At n = 52 the paired CI half-width here is about
.09, so an effect of roughly 5 cases or more would have shown; the observed difference is
-1 case. The null is therefore a volume explanation of the earlier gain, not an underpowered
test of a large effect.

## Ledger
Spend $0.005452.
