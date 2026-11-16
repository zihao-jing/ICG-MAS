# Casebook selection v1 — rule fixed before looking at the selection

2026-11-15. Written before the selection was generated. It fixes which two cases replace the casebook
examples; the examples are not chosen to fit a result.

- Population: the 89 known-stage cases.
- Audit label: the evidence-flow audit with the Gemini 3.6 Flash carrier labeller and the statement-based
  sharding rule (`Sharding-presence-semantic-v1.md`).
- Judge label: the Who&When-style judge with Gemini 3.6 Flash (`attribution_prompt_v1.json`, stored in
  `20261113_attribution_comparison/results_v2.json`, field `judge.stage`).
- Eligible: both labels resolve to one of `sharding`, `extraction`, `transmission`, `aggregation`, and the
  labels differ.
- Order: ascending by the full case key (`population/model/instance`), plain lexicographic string order.
- Selection: the first two eligible cases in that order. No filtering on whether the audit or the judge is
  correct, and no substitution after the selection is seen.
- The selection is written with each case's audit label, judge label and known stage so the text can be
  updated under the same rule if the casebook is refreshed.