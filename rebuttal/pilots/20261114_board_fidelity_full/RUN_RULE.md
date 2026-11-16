# Board strict-fidelity full run (frozen before the first full call)

Written 2026-11-14, before the full run. Applies the V10 strict-fidelity label
to all **1,824 board rows** of the frozen piece-2 population (MuSiQue 1,200,
Silo-Bench 624), in stages capped at **$5 per invocation**. The 150-row pilot
(`20261114_board_fidelity_pilot`) is reused for the same keys because the
label, model, prompt and settings are identical; its $4.033836 is part of the
total. Projection from the pilot: **$43.92** (MuSiQue $21.59, Silo-Bench
$22.34). If the running total would pass **$50**, stop and report instead of
continuing.

Label: Claude Opus 5.5, `per_fact_prompt_v10.json`, temperature 0, max 2500,
reasoning enabled. Validation record: natural board cases **158/163 = .969
[.930, .990]**, kappa **.721 [.429, .930]**; constructed all-37 **.946
[.818, .993]**, kappa **.641**, constructed interval **wide**; secondary
"distorted vs not" on constructed **.865**, kappa **.467**, and **Dist stays
unvalidated**. Every fidelity cell carries this caveat.

Parse failures are retried at most 3 attempts, then excluded and listed. No
label repair. Coverage and critical recall remain upper bounds; loss and
omission lower bounds wherever presence is reported.