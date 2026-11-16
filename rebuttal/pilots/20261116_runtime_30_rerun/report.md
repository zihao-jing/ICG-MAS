# Run-time 30-failure rerun (rule: prereg/Runtime-30-rerun-v1.md, hash 251e02fa…, recorded before any call)

Spend $0.0816 of $2.00: 26 Gemini equivalence calls, one per scoreable trace (5 pilot, 21 run). `calls.jsonl` logs every call with tokens and cost. 26 scoreable traces; 4 not scoreable (2hop__284789_52835, 2hop__525242_52835, 2hop__81659_52835, 3hop1__131820_59747_48534).

## Figures (26 traces, Wilson 95%)

| Measure | New: matched granularity (merged) | Same traces, unmerged | Earlier: answer-bearing gold, unmerged (`20261116_gold_answer_bearing`) | Earlier: first-support gold, 30 traces (`20261115_q1_second_sample`) |
|---|---|---|---|---|
| Agreement with gold stage | 18/26 = 69% (50–84) | 18/26 = 69% (50–84) | 18/26 | 6/30 = 20% (10–37) |
| Alarms (run-time names extraction or transmission) | 4 | 4 | – | – |
| Alarm real (gold also extraction or transmission) | 1/4 = 25% (5–70) | 1/4 = 25% (5–70) | – | – |
| Catch (gold extraction, run-time extraction) | 1/6 = 17% (3–56) | 1/6 = 17% (3–56) | – | – |

Gold stage on 26: aggregation 20, extraction 6, transmission 0.

## Notes

- The merge changed no trace's stage (merged = unmerged on all 26). Equivalence verdicts: 27 equivalent, 5 partial, 70 unsupported (of 102 facts; 26 calls, all valid).
- The 4 alarms are 2hop__433694_20273, 3hop1__132795_40769_64047, 3hop1__251085_831637_91775, 3hop1__41865_55331_34700; only 3hop1__41865_55331_34700 is a real early loss.
- The 6 early losses: 2hop__458672_20057, 3hop1__389955_132457_47686, 3hop1__389955_132457_51423, 3hop1__398232_326948_59893, 3hop1__41865_55331_34700 (caught), 3hop1__49236_89752_49923 (missed; its stored facts are all present at run time).
- Trace 3hop1__49236_89752_49923: stored facts kept (valid, status ok, 3 facts); not regenerated.
- These figures use 4 alarms and 6 early losses. Intervals are wide; the rates are descriptive.
- The earlier "1 of 4" alarm and "1 of 6" catch figures are reproduced here (same traces, same labels), so they now have a source file.
