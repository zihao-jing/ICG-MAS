# A4 summary: causes of the 19 audit misses on the 82 runs (old rule)

Rule: prereg/Stage-naming-A4-miss-causes-v1.md (hash 1951d8c8…). Source rows: a4_misses.json (original table), a4_misses_strict.json (rebuilt table, build-bug correction per prereg/Stage-naming-A3-fact-named-v1-amendment-1.md, sha256 4abe17da…). No model calls.

## Counts (19 misses): original and rebuilt

| Category | Original (fact_tables.json) | Rebuilt (fact_tables_strict.json) |
|---|---:|---:|
| Unreadable, no fact at 0.8 | 6 | 6 |
| Unreadable, no carrier record | 4 | 3 |
| Lost fact routed past its checkpoint | 4 | 4 |
| Distorted fact routed away from transmission | 2 | 3 |
| Other (deletion read as distortion) | 3 | 3 |
| Total | 19 | 19 |

Only one item changes category: gemini inj/gemma31b/3hop1__617062 (unreadable → distorted fact routed away from transmission; table: extraction faithful, board distorted; audit said extraction).

## The 9 unreadable misses (rebuilt table)

| Run | Audit stage | Reason no row | Status after rebuild |
|---|---|---|---|
| gemini inj/qwen235b/2hop__835710_7298 | aggregation | no fact at 0.8 (best 0.67) | unchanged |
| qwen inj/qwen235b/2hop__835710_7298 | aggregation | same case, no fact at 0.8 | unchanged |
| gemini inj/gpt4omini/2hop__17455_21567 | extraction | no fact at 0.8 (best 0.56) | unchanged |
| gemini inj/gemma31b/4hop1__606685_508773_85832_745702 | sharding | no fact at 0.8 (best 0.56) | unchanged |
| gemini inj/gemma31b/3hop1__254856_400692_51423 | aggregation | no fact at 0.8 (best 0.36) | unchanged |
| qwen inj/gemma31b/3hop1__254856_400692_51423 | aggregation | same case, no fact at 0.8 | unchanged |
| gemini inj/qwen235b/3hop1__144439_443779_52195 | extraction | no carrier record | still unreadable: attempt 1 truncated; attempt 3 parses but the frozen rule uses attempt 1 only. Decision A (2026-11-16): stays unmatched and is reported as such; no selection rule added |
| gemini inj/gpt4omini/4hop1__93963_170667_443779_52195 | none (uncertain) | no carrier record | still unreadable: all three attempts truncated |
| gemini inj/gemma31b/4hop1__151903_5274_458768_33677 | none (uncertain) | no carrier record | still unreadable: all three attempts fail strict_parse |

The original table counted 4 "no carrier record" (617062, 144439, 93963, 151903). The fenced-JSON parser bug explains only 617062 (now readable). 144439 is still unreadable because its attempt-1 output is truncated.

Note: the parser correction also adds gpt4omini 2hop__804417 (gemini) to the matched runs; it is not a miss, so it is not in this table.

## The readable misses (one line each, rebuilt table)

- gemini inj/gemma31b/4hop1__429751 → extraction: fact faithful at extraction, distorted at board; routed to extraction. Distorted fact routed away from transmission.
- qwen inj/gpt4omini/4hop1__93963 → extraction: fact faithful at extraction, distorted at board. Same category.
- gemini inj/gemma31b/3hop1__617062 → extraction: faithful at extraction, distorted at board. Same category (new in rebuilt table).
- gemini and qwen case/extraction/gemma31b/3hop2__655849 → aggregation (2 runs): deleted fact absent at both checkpoints; audit names aggregation. Lost fact routed past its checkpoint.
- gemini and qwen case/sharding/qwen235b/2hop__20256 → aggregation (2 runs): deleted fact absent at both; same category.
- qwen case/extraction/gemma31b/2hop__89403 → transmission: deleted fact read as distorted at extraction, empty board. Other: deletion read as distortion.
- qwen case/sharding/gemma31b/3hop2__668732 → transmission: deleted fact distorted at extraction and board. Other.
- qwen case/sharding/gemma31b/2hop__33288 → transmission: deleted fact distorted at extraction and board. Other.
