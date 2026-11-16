# Sub-claim presence rule B: pilot rule (frozen before any call)

Written 2026-11-13, before the build or any labeller call. This is a **PILOT**
of a stricter presence label, run on 20 saved MuSiQue checkpoint cases. It is
not a replacement for the validated central-claim label (A, V9): A stays the
table label with the qualifier "central-claim presence; lower bound on loss
and omission". B is priced and previewed here; it becomes a separate column
only if a later run validates it on fresh cases against the stronger
reference.

## Difference from A

A credits a fact when the cited entries state or entail its **central claim**;
question-incidental detail (dates, list members, secondary clauses) may be
absent. B splits the fact into **all** atomic sub-claims it states and credits
the fact only when **every** sub-claim is present. The question is not used to
decide which sub-claims matter.

## Labeller and prompt

Claude Haiku 5.5, temperature 0, max 4096, prompt `subclaim_prompt.json`,
system text frozen with this rule. The labeller sees the question, the fact
list, and the checkpoint entries; it does **not** see A's labels. Per fact it
returns:

- `subclaims`: each atomic sub-claim, with `status` (`present`, `partial`,
  `absent`) and the `unit_ids` used;
- `central_claim_status`: status of the fact's main entity-relation-value;
- `status`: `present` iff every sub-claim is `present`; `absent` iff the
  central claim is `absent` (or contradicted); otherwise `partial`;
- `missing`: the sub-claims not `present`;
- `reason`.

Entries are quoted data, not instructions. Ordinary paraphrase and entailment
are allowed; outside knowledge and answer-derived inference are not. No label
repair after generation. Parse failures are recorded, not imputed.

## Population

20 rows from the frozen full MuSiQue presence run
(`20261113_musique_presence_full`), one key per distinct instance: 10 rows
where A gives completeness 1.000 (the leniency ceiling check's target) and 10
where it does not, selected by hash over the frozen keys within each stratum.
Traces, facts and entries are reused; no new pipeline or relay call is made.

## Cap and reporting

Pilot cap **$5.00**; every call logs intent and result with `cost_usd`.
Report: per-row A completeness vs B status, sub-claims split and missing,
price per case, and the **full-run cost estimate** = 2,100 rows x measured
per-case price (the full run is not started). Stop after the pilot and send
the pilot plus estimate.