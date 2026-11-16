# Board strict-fidelity pilot (frozen before any call)

Written 2026-11-14, before the build or any labeller call. This is a **cost and
output pilot** for applying the validated strict-fidelity label at the shared
board on the main table. It is not a new validation and it does not replace
the V10 validation record.

## Label and validation record

The strict-fidelity label is the V10 per-fact labeller: Claude Opus 5.5,
`per_fact_prompt_v10.json` text, temperature 0, max 2500, reasoning enabled
(the 2500 deviation from V10's stated 1200 is already disclosed in the V10
report). V10 validation, natural board cases: **158/163 = .969 [.930, .990]**,
kappa **.721 [.429, .930]**; constructed all-37: **.946 [.818, .993]**, kappa
**.641**; the "distorted vs not" secondary on constructed is **.865**, kappa
**.467** and stays **unvalidated**, with a wide constructed interval. These
figures are carried into the pilot report; the pilot adds no new validation
claim.

## Population

150 board-checkpoint rows from the frozen piece-2 population
(`20261113_main_table_presence/population.json`): 75 MuSiQue and 75 Silo-Bench,
stratified by model and protocol, selected by
`sha256('43|bfid|'+key)` within each benchmark. Disjoint from the V10
validation cases (none of the main-table board rows overlap the V10
population). Traces, facts and board entries are reused; no relay call.

## Run and reporting

Cap **$5.00**; every call logs intent and result with `cost_usd`. Report:
valid-parse rate, price per case, projected cost for all 1,824 board rows,
fidelity distribution, per-fact output examples, the V10 natural-case kappa and
the constructed/Dist caveats. The full run is not started until the pilot is
reviewed; after approval it runs in stages of at most $5 each, within the
approved ~$32 total. Every fidelity cell in the table carries the strict-label
meaning and the natural-case kappa; Dist stays unvalidated.