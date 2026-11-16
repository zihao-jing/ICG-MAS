# A4: cause of each audit miss, read against the audit's fact table (frozen before classification)

2026-11-16. Step 39. Zero model calls. Scope: every audit miss on the 82 known-cause runs under the old rule (the 19 counted in `rebuttal/pilots/20261116_audit_miss_classification/REPORT.md`; injected 12 from the 2x2 pilot and the Qwen design, deleted-fact 7 from the A3 results). Each miss is read against its row in `rebuttal/pilots/20261116_stage_naming/fact_tables.json`.

## Categories (assigned in this order; first that applies)

1. **Unreadable**: the run has no fact-table row (no unique fact match, or no carrier record). Counted, not classified further.
2. **Lost fact routed past its checkpoint** (deleted-fact, known extraction or sharding): the audit's own table marks the matched fact absent at both checkpoints, but the audit named a different stage. Cause: the stage rule, not the table.
3. **Distorted fact routed away from transmission** (injected, known transmission): the table marks the matched fact distorted at the board, but the audit named extraction, sharding or uncertain. Cause: the pool presence check, not the table.
4. **Fact carried, answer still wrong** (audit names aggregation): the table marks the matched fact faithful at the board. Cause: the audit reads a correct carry as the final step's error.
5. **Other**: any miss not covered above, described in words.

Each classified miss states the audit's stage, the table statuses at extraction and board, and the category. No category is fitted after the counts are seen.
