# W3 log-only judge, rule v1 (frozen before any call; 2026-11-16)

## Purpose

Test whether a Who&When-style judge that sees only the run log (no checkpoint snapshots) names the failing stage
on the 89 known-stage cases, and whether its errors pile onto the last agent. Descriptive comparison; the audit is
not re-run and no stored label is changed.

## Judge

- Model: `google/gemini-3.6-flash` (same model as the existing W3 judge row, `attribution_prompt_v1.json`).
- Temperature 0; reasoning enabled (as in the existing judge); max output 8192 tokens.
- One call per case. Hard stop: before each call the estimated cost (input characters / 4 at the listed prompt
  price, plus 8192 output tokens at the completion price) is added to the spend so far; if the sum would exceed the
  cap, the call is not made and is logged as skipped.

## Input view: log only

The judge sees the question and a chronological log. Each agent contributes three entries, then the aggregator
contributes one entry per board unit it received and one final entry:

| Log line shown to the judge | Source (not shown) | Stage the judge's entry maps to |
|---|---|---|
| `agent a received its input: <shard text>` | the agent's source shard | sharding |
| `agent a produced: <text>` | the agent's extraction units | extraction |
| `agent a sent: <text>` | the agent's transmitted units | transmission |
| `aggregator received from agent a: <text>` | the board units | transmission |
| `aggregator final answer: <text>` | the final answer | aggregation |

Entries are numbered `[1]`, `[2]`, … in that order (agents in index order, then the aggregator's board entries, then the
final answer). Each text is truncated at 500 characters, as in `attribution_prompt_v1.json`. No section headings
(extraction pool, transmitted evidence, shared board) and no stage names are shown. The entry type is used only
after the call, for the mapping above.

## System prompt (sent verbatim)

```
You are a failure-attribution judge for a multi-agent question-answering run. You see the run as a numbered log in time order; each line names the agent that acted. The final answer is known to be incorrect. Name the earliest log entry at which the failure was introduced: the first entry where the evidence needed for the answer was missing, lost or altered. Judge only the log shown; do not use outside knowledge. Return strict JSON only:
{"entry": <entry number>, "agent": <agent integer or null>, "reason": "one short sentence"}
```

## Scoring

- Stage of a case = the mapping of the named entry's type (table above). Correct = mapped stage equals the stored
  `known_stage` in `20261113_attribution_comparison/cases_v2.json` (extraction or sharding for the 59 cohort cases;
  transmission for the 30 injected cases).
- A reply that cannot be parsed, or names an entry that does not exist, is scored as wrong and counted.
- Accuracy: Wilson 95% interval from the counts (agreement convention).
- Comparator: the existing full-trace judge (`20261113_attribution_comparison/results_v2.json`, `judge.stage`) on the
  same cases; its accuracy is 67/89 on all 89 cases.
- Last agent: for each case, the highest agent index in the case. Share of named agents that equal the last agent,
  compared with the share of true owners that are the last agent. True owner: the injected unit's `agent_id`
  (`20261113_injected_distortion/accepted.json`) for injected cases; the `gold:agent-N` source of the flagged fact
  (`20261115_b6_repairs/cases.json`) for cohort cases.

## Pass criteria (fixed before the run)

- **Accuracy drop:** log-only accuracy on the 89 cases is more than 10 points below the full-trace judge (67/89 =
  .753), i.e. below 57/89.
- **Pile-on:** the judge names the last agent for more than 50% of the cases that it names an agent for, or that
  share exceeds the share of true owners that are the last agent by 15 points or more.
- **Outcome:** if either criterion is met, the W3 verdict follows the wording set in the review sheet. If neither is met, W3
  rests on the extra output: one side-by-side example giving the fact and the checkpoint.

## Run plan

- Pilot: 15 cases, the first 15 in ascending order of `sha256(key)`, cap $1.00.
- Full run: the remaining 74 cases, only after the pilot is reviewed; total cap $5.00 including the pilot.
- Every call is logged with intent and result, including `cost_usd`.

## Amendment log

### Amendment 1 (recorded 2026-11-16, after the full run; rule text above unchanged)

- Departure: the Outcome bullet's pile-on criterion is not used for the W3 verdict. The verdict is set by the accuracy criterion alone, as the user instructed on 2026-11-16 after the pilot. Pile-on is reported descriptively.
- Why: the pile-on criterion measures which agent the judge names, not whether it names the right stage. Had the criterion been applied, it would not have been met on the full set (named-last 37/89 = .416, not above .50; gap 10.1 points, below 15), so the departure does not change the outcome.
- Pile-on figures (descriptive): named agent is the last agent 37/89 = .416; true owner is the last agent 46/89 = .517.
- Verdict basis: log view 68/89 = .764 [.666, .840] against 67/89 for the full-trace judge on the same cases; the drop threshold (57/89) is not reached. W3 rests on the side-by-side example.
- The run recorded rule sha256 b036321785e39fc5e0108fd967080ffabdc0d36313d06a769d9b88e2e389623c (the file before this entry was appended). Results: `rebuttal/pilots/20261116_w3_log_only_judge/score.json` (spend $0.324135).
