# Frozen rule: input-presence (sharding) check in the audit diagnosis

Written 2026-11-13 before the check was run. Zero model calls: the check reads
frozen traces, matcher records and presence labels only. The instrument is the
frozen presence rule in
`rebuttal/pilots/20261112_missing_fact_repair/PRESENCE_RULE.md` (Amendments 1
and 2); no threshold, tokenizer or stop list is changed here.

## What changes

The audit's existing diagnosis (`src.audit.semantic_matcher.diagnose`) labels a
fact `extraction_omission` when the extraction pool carries no version of it.
That label assumes the fact was available in the agent's input shard. This rule
adds the missing check: before an `extraction_omission` label stands, test
whether the fact was present in the input shard of the agent(s) that should
have extracted it.

- **sharding_omission**: no source shard contains the fact (content recall
  absent in every source-agent context). The loss happened before extraction;
  no extraction from that input could have recovered it.
- **extraction_omission** (unchanged): at least one source shard contains the
  fact (present or partial). The fact was available to extraction and did not
  reach the pool.
- **mixed_sharding_extraction**: the chosen support set has several
  `extraction_omission` facts and they split between the two labels. Reported
  separately, never pooled into either.

Only `extraction_omission` moves. `selection_omission`, `distortion`,
`partial`, `uncertain`, `candidate_aggregation` and `correct_control` are not
touched. The old diagnoses stay on record and the old `diagnose` function is
not edited; the check is a new function that wraps it.

## Populations

1. **Missing-fact cohort** (extraction stage): the Stage 2 clean
   extraction-omission cohort, 69 traces over 59 unique instances. For each
   trace the targeted fact and target agent are those already frozen in
   `presence.json`; the label is `label_final` (the content rule plus the
   manual read recorded in `presence_check.md`). Old diagnosis:
   `extraction_omission` for every trace (that is the cohort definition).
2. **Main-table diagnoses** (E1 anchor, 30 instances x 3 models, 84 valid
   matcher records): every trace whose existing `diagnosis` is
   `extraction_omission`. The targeted facts are the facts in the chosen
   minimum support set that the matcher labelled `extraction_omission` (the
   same facts `diagnose` used). A fact's source shards are the
   `source_contexts` entries whose `context_id` is listed in its `source_ids`
   (the `gold:` prefix is stripped). All source shards of the fact are read;
   the fact is in-shard if any one of them contains it.

**Amendment 1 (written before the 2,400-trace run; the E1 anchor and cohort
runs above are unchanged).** Population 2 is extended with the full Stage 2
main-run matcher set (`rebuttal/results/batch1/expansion_stage2/matcher/`,
2,400 traces over three models): every trace whose frozen `diagnosis` is
`extraction_omission` (216 traces). Facts, source shards and presence test are
identical to population 2 above. This is the diagnosis set behind the
main-table audit rows; the 69-trace missing-fact cohort is contained in it,
so the two reports overlap by design and are not pooled. No model call.

## Presence test

Exactly the frozen presence rule: split the shard at `.`, `!`, `?` or newline;
drop the question line, `You hold the following evidence:` lines and
`[Document: ...]` lines; for each remaining sentence compute content recall
(the fact and sentence normalised, the frozen STOP set removed). The shard
label is **present** if the best sentence reaches 0.8, **partial** if it
reaches 0.4, **absent** below 0.4. For several source shards, the fact is
**present** if any shard is present, else **partial** if any shard is partial,
else **absent**.

No manual adjudication is applied to the E1 anchor; the content rule governs,
and its known tendency to read co-located tokens as presence makes the
sharding count conservative (it understates sharding losses). The manual read
in the missing-fact cohort is already recorded in `presence_check.md` and is
part of the frozen presence rule for that cohort.

## Reported quantities

Old versus new diagnoses side by side, at trace and instance level, with exact
Clopper-Pearson 95% intervals on the moved share. For the E1 anchor also the
per-fact split (present / partial / absent in shard) and the number of facts
moved. Every number names its source file. Spend is $0.000000 (no calls).

## Limits fixed before the run

- The check reads lexical presence, not entailment; the cast-sentence failure
  in `presence_check.md` shows the rule can call a fact present when it is not
  stated. Sharding moves are therefore a lower bound.
- Only facts the matcher already called `extraction_omission` are checked; a
  fact cannot move from `selection_omission` or `distortion`.
- The main-table re-run is the E1 anchor matcher set, the diagnosis set the
  paper's stage table uses; no new matcher call is made.