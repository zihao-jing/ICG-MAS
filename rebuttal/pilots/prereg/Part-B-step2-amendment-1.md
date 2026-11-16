# Part B step 2, amendment 1: cap raised to $2.50 API-equivalent

2026-11-15. Written before calls 7 onward. Everything in `Part-B-step2-truth-rule.md` stands except the cap.

## Why

The first six calls reached $0.435 API-equivalent ($0.264 CLI charge). The local CLI adds about 14,000
prompt tokens of harness context per call (input 342 + cache creation 2.4k–13.2k + cache read 10.8k), so at
API prices a call costs about $0.07, not the $0.009 the direct API path cost on the same traces. Thirty calls
therefore need about $2.2, not $0.50.

## Change

Cap **$2.50 API-equivalent** (prompt and completion tokens at $4/M and $20/M). Calls 1–6 stay on record and
are not repeated; the run resumes at call 7. The CLI's own charge is recorded beside the API-equivalent figure.
No prompt, population or scoring change.