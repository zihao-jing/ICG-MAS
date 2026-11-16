# Exact missing-span review

The audit log does not store missing atomic spans. Its `crit_recall` compares each Silo-Bench agent's **whole input shard** with transmitted units using a permissive overlap rule, then saves only aggregate counts. It does not identify the missing number, relation, or phrase. The `coarse_audit_matches` in these sheets were reconstructed from the same rule to make the limitation visible; they are not exact labels.

- [`existing_evidence_gaps.jsonl`](existing_evidence_gaps.jsonl): the original 20-case review input (9 distinct benchmark instances).
- [`labeled_evidence_gaps.jsonl`](labeled_evidence_gaps.jsonl): completed source-to-board review. Six cases have explicit source excerpts for omitted or distorted data; 14 cases already transmit the needed data and are reclassified as aggregation gaps. Three cases also have source-verified corrections to incorrect board summaries.
- [`casebook.md`](casebook.md): readable case-by-case view of the complete task question, original source, transmitted board, decision, and selected excerpts.
- [`gemma_n5_failures.jsonl`](gemma_n5_failures.jsonl): optional audit diagnostic only. The 15 Gemma five-agent failures retain their aggregation-gap classification; no span review is required for them.

Three of the six evidence-gap cases also contain incorrect transmitted summaries: `qwen235b_n5/I-02_n5`, `qwen235b_n10/I-02_n10`, and `qwen235b_n10/I-07_n10`. The `restored_fact` arm now appends 11 explicit, source-verified correction notes after the exact source excerpts. Each note identifies the old and corrected value. The original board remains intact for the paired comparison, and the appended notes explicitly resolve its contradictory summaries.

For each case, compare `board_units` with `source_contexts`. If an answer-critical piece is absent, set `revised_diagnosis` to `evidence_gap` and fill `missing_facts` with objects of this form:

```json
{"text": "an exact substring of the cited source context", "source_context_id": "agent-0", "verified_by": "reviewer name"}
```

Also fill `reviewed_by` and `review_note`. For a wrong derived board summary, use `board_corrections` to cite the incorrect board unit, its old value, and the corrected value. The runner recalculates the correction from the cited source list before appending a correction note. If no necessary piece is missing, set `revised_diagnosis` to `aggregation_gap` and leave `missing_facts` and `board_corrections` empty. The current runner refuses evidence-gap repairs with empty or invented spans and does not add source material to aggregation-gap boards. The six-case result is in [`../results/exact_span_evidence_20260926/summary.md`](../results/exact_span_evidence_20260926/summary.md).

The labeled sheet is complete. Validated decision files have been written to [`../exact_span_decisions/`](../exact_span_decisions/). To rebuild them in a fresh directory, use:

```bash
PYTHONPATH=. .conda-env/bin/python -m scripts.finalize_exact_span_decisions \
  --output path/to/new_exact_span_decisions
```

The command checks that every cited span appears verbatim in its source before writing any decision file. It makes no API calls.
