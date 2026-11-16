# LLM labeller pilot

The canonical run record is `rebuttal/diagnosis/pilot_report.md`. This file is
kept only as a pointer so the pilot directory and the diagnosis directory do
not carry two versions of the same numbers.

Model `anthropic/claude-haiku-5.5` via OpenRouter; 20 traces; three attempts;
**$0.048739** total against a $0.25 cap. All calls are logged as
`calls_attempt1.jsonl`, `calls_attempt2.jsonl`, and `calls.jsonl` in this
directory. The scored run (attempt 3) parsed 20/20, agreed with the authors on
17/20 traces (raw 0.850, κ 0.634, 95% CI 0.650-1.000 and 0.211-1.000), and
failed the go/no-go. The full per-trace table, disagreement quotes, and
spot-check are in the canonical report.