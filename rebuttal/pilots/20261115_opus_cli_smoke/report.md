# Opus CLI smoke test (transport check, three calls)

2026-11-15. Three judge calls through `claude -p` from an empty temporary directory (`/var/folders/.../opus_cli_smoke_*`),
with `--system-prompt-file` (the frozen `rebuttal/judge/E2-judge-v2.json` system text, sha recorded per call),
`--exclude-dynamic-system-prompt-sections`, `--output-format json`, `--model claude-opus-5-5`, tools disabled
(`--disallowedTools` on Bash, Edit, Write, Read, Glob, Grep, WebFetch, WebSearch, Task, NotebookEdit, TodoWrite,
Agent, Skill, Workflow, Monitor). Trace and user text are byte-identical to the three validation traces the API
path used. Spend **$0.185220**, including a first three-call pass that sent the QA message instead of the judge
prompt ($0.075404, discarded, kept in `calls.jsonl`).

## Result

**All three judge calls parse to the API's label shape under the API parser, with no CLI chatter in the result.**

| call | returncode | strict JSON | API parser | class | input tok | cache create | cache read | output tok | CLI cost |
| --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | yes | yes | multiple | 348 | 5,599 | 9,985 | 801 | $0.047404 |
| 2 | 0 | yes | yes | single | 348 | 2,105 | 10,832 | 617 | $0.026423 |
| 3 | 0 | no (json fence) | yes | single | 348 | 3,538 | 10,832 | 737 | $0.035988 |

Call 3 wrapped its object in a ```` ```json ```` fence. The API path's own parser (first `{` to last `}`) accepts
it unchanged, so the format difference is cosmetic and already handled by the parser used in every judge run.
The `result` field contains only the judge object; CLI bookkeeping stays in the JSON envelope, not in the text.

## Transport deviation (record in every report that uses this route)

The CLI route is not the OpenRouter route the other calls used, so each report that uses it must say so:

- Usage comes back as `input_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens`, not
  `prompt_tokens`; thinking tokens are reported separately. The API-path token accounting does not map one to
  one. Cost here is the CLI's own `total_cost_usd`, not a price-table recomputation.
- Prompt caching is active on this route (first call creates 5,599, later calls read ~10,150), so per-call cost
  is lower than the same prompt through the API without caching. Comparing costs across the two routes by
  per-call dollars would misstate the difference.
- Model string differs: `claude-opus-5-5` here, `anthropic/claude-opus-5.5` through OpenRouter. Same model,
  different transport.

## Status

Because this route differs from the API route, Part B results that use it are marked "transport: claude-cli"
in their call logs and in the report header. Opus remains labeller/reference only, never the subject.

## Ledger

$0.185220 total for this test ($0.109816 judge calls + $0.075404 discarded first pass).