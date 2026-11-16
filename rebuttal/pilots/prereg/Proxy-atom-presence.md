# Atom-level proxy presence (frozen before any call)

2026-11-15. Cap **$0.30**, projected $0.015 for 144 calls. The proxy stage in `Proxy-vs-gold-stage.md` was derived
from the stored checkpoint labels; this run re-derives proxy presence at atom level with the validated point
labeller, so both sides of the comparison use the same instrument.

## Population

The union of the traces in the three UEGh Q1 samples on their `random_relay` rows: 31 unique traces (samples 1 and 2
overlap in 29; samples 2 and 3 are the same 30). The Qwen proxy fact set for each row is used unchanged
(`facts.json`, status ok).

## Atoms

Each proxy fact's text is split on `. ` and parts longer than 3 characters are its atoms; atoms are numbered `a1`,
`a2`, … per fact and per call.

## Labeller and rendering

Haiku 5.5 through the OpenRouter API, frozen prompt `per_fact_points_prompt_v1.json` (sha in the build manifest),
rendered exactly as `per_fact_points_run.render`: atom lines `a1: <text>`, entries `[unit_id] (agent N) <text>`
truncated to 1,500 characters. One call labels all atoms of one fact against one checkpoint (extraction, then
board).

## Parsing

A reply is valid only if `per_fact_points_run.parse` returns labels for exactly the atom ids sent. An invalid reply
gets one retry; if it is invalid again the checkpoint is invalid for that fact.

## Fact and trace stage

Fact status at a checkpoint = absent if any atom is absent, else partial if any atom is partial, else present. The
trace stage: any fact absent at extraction gives `extraction`; otherwise any fact absent at board gives
`transmission`; otherwise `aggregation`. A trace with an invalid fact/checkpoint has no atom-level proxy stage.

## Agreement

Compared with the gold stage from the Q1 strict derivation (amendment 1 of `Proxy-vs-gold-stage.md`), per sample:
agreement = same stage / traces with both stages, Wilson 95% interval, confusion table. Reported in the same table
format as the checkpoint-label comparison. No text use.