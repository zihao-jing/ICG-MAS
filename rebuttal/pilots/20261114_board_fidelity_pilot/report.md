# Board strict-fidelity pilot

Rule `PILOT_RULE.md` (sha256 `0c79240e6867`); prompt `per_fact_prompt_v10.json` (sha256 `94ade327ceea`); Claude Opus 5.5, max 2500, reasoning enabled. Pilot stopped at 150 of 150 sampled rows (all sampled); 150 parsed, 754 fact labels; spend **$4.033836**, cap $5.00. Stage: shared board.

Price per case **$0.026892**; projection for all 1824 board rows **$43.92**, which is **above the approved ~$32** (per-benchmark: MuSiQue 1,200 rows ~$21.59, Silo-Bench 624 rows ~$22.34). The full run is not started; stages would be at most $5 each.

| fidelity | facts |
| --- | ---: |
| faithful | 571 |
| partial | 109 |
| distorted | 22 |
| absent | 52 |

## Validation record carried into this pilot

- Natural board cases (V10): **158/163 = .969 [.930, .990]**, kappa **.721 [.429, .930]**.
- Constructed distortions, all 37: **.946 [.818, .993]**, kappa **.641**; the constructed interval is **wide**.
- The secondary "distorted vs not" label on constructed cases is **.865**, kappa **.467**, and **Dist stays unvalidated**.

The pilot adds no new validation claim. The full board run starts only after review; every fidelity cell will carry the natural-case kappa and the unvalidated-Dist caveat. Coverage and critical recall remain upper bounds, loss and omission lower bounds wherever presence labels are reported.

