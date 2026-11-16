# Silo-Bench presence validation, expansion stage (frozen before any call)

Written 2026-11-13, after the first 24-case validation (`report.md`, agreement
0.906, kappa 0.702 with a wide kappa interval 0.242-0.940). This stage adds
**two fresh board cases per (model, n_agents, protocol) cell**, chosen by the
same hash order after the first case, disjoint from the first 24, the E1 anchor
and the piece-2 pilot. Target: 24 + 48 = 72 cases, three per cell.

Everything else is unchanged: same `RULE.md` presence definition, same
`reference_prompt.json` (Gemini 3.6 Flash, reasoning enabled, max 8192,
temperature 0), same `labeller_prompt.json` (Claude Haiku 5.5, max 4096,
temperature 0), reference labels frozen and hashed before the Haiku calls.
The original population, labels, calls and report stay on record unchanged;
the expansion writes `_v2` files and a combined `report_v2.md`.

Analysis fixed before the calls: presence agreement (fact not `absent`) with
exact Clopper-Pearson CIs, Cohen's kappa with instance-cluster bootstrap CI
(10,000 draws, seed 43), the same PASS bar 0.80 agreement / 0.60 kappa, and the
same by-`n_agents` breakdown. The combined 72-case result is reported beside
the original 24-case result; the original is not replaced.

Caps: reference **$1.50**, labeller **$0.30**; combined with the first stage
($0.343) the total stays under $5. Every call logs intent and result with
`cost_usd`. If the reference cap is hit the run stops and the achieved n is
reported.