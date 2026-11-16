# Proxy support for the audit's stage diagnosis: pilot rule v1

2026-11-15, frozen and hashed before any call. Question: does the audit name the same stage when the critical
facts come from the paper model (Qwen3-235B) instead of the benchmark gold?

## Population

- 10 cases from `rebuttal/pilots/20261113_attribution_comparison/cases_v2.json` (frozen), stratified by the
  **gold-based audit stage** recorded in the 89-case audit (`20261113_audit_diagnosis_89/audit_results.json`):
  4 extraction, 4 transmission, 1 sharding, 1 aggregation. Within each stage, order by
  `sha256('47|proxy|' + key)` and take the first N.
  Gold-audit stage mapping: `extraction_omission` → extraction; `selection_omission`, `partial`, `distortion`
  → transmission; `sharding_omission`, `mixed_sharding_extraction` → sharding; `candidate_aggregation` →
  aggregation.
- The trace is the case's question and checkpoints; the source documents are the frozen trace package's
  `source_contexts` (each agent's shard, including distractors), not the gold supports.

## Proxy fact generation

- Prompt `proxy_facts_prompt_v1.json` (sha recorded), model `qwen/qwen3-235b-a22b-2507`, temperature 0,
  max 4096 tokens, at most 2 retries on a parse or schema failure, every attempt logged.
- Output: `facts` (fact_id, text, source_ids) and nonempty alternative `support_sets`, the same shape the
  audit's matcher produces, so the audit's own diagnosis function takes them unchanged.
- Inputs: the question and the source documents only. No gold support, no gold answer, no answer text, no
  diagnosis. The model is not told which document is gold.

## Proxy-fact validation against the benchmark gold supports

- Prompt `proxy_support_equiv_prompt_v1.json` (sha recorded), Gemini 3.6 Flash, temperature 0, one call per
  trace with all proxy facts; entries are the trace's gold support passages (`source_supports`).
- Gemini is chosen because it is independent of both the generator (Qwen) and the audit labeller (Haiku 5.5).
- Verdicts: equivalent / partial / unsupported / contradicted. **Match = equivalent.** Report the per-fact
  match rate with a 95% Clopper-Pearson interval, the counts by failure type, and one example reason per
  type. A generation or parse failure is its own failure type and is never counted as a match.

## Audit on the proxy facts

- Labeller: the frozen per-fact prompt v3 (`per_fact_prompt_v3.json`, system sha `3f7f19bb…`), Claude Haiku
  5.5, temperature 0, one call per trace per checkpoint (extraction pool, shared board), same renderer as the
  validated run. This label is already validated on MuSiQue at the extraction pool (κ .780) and as board
  carrier identification (agree .881).
- Carriers: status present or partial → one carrier object with the cited unit ids and the labeller's
  fidelity; status absent → an empty array. Fidelity classes are the prompt's own
  (faithful / partial / distorted / absent).
- Diagnosis: `src.audit.sharding_check.diagnose_with_sharding(proxy_facts, carriers, trace, correct=False)`,
  the audit's own function, unchanged. Stage mapping as above.

## Comparison and pilot output

- Proxy stage vs the gold-based audit stage of the same case: agreement with a 95% Clopper-Pearson interval
  and the exact stage matrix (proxy rows, gold columns). The case's known stage is reported beside it for
  context; it is not the comparison target.
- No pass bar for the pilot. Pilot is 10 traces, cap **$1.0**, every call logged. A full run starts only
  after review; the projection is measured unit cost × the full-run trace count.

## Scope

The comparison measures whether the stage diagnosis survives gold-free facts. It does not revalidate the
per-fact label, does not test fidelity of the board against the questions' true answer, and says nothing
about cases whose gold facts are absent from the source shards.