# Prompt v3 at extraction: independent-reference validation

Rule `Per-fact-extraction-v5.md` (sha256 `a1a25cff6fab`); reference labels sha256 `9df005472b0d`, frozen before the Haiku calls. Gemini 3.6 Flash reference; Claude Haiku 5.5, prompt v3; 60 frozen MuSiQue traces, extraction pool. Spend $0.241468, cap $1.00.

**Per-fact presence agreement 161/176 = 0.915** (95% CI 0.863-0.952); kappa **0.780** (0.665-0.877) - **PASS** against 0.80/0.60.

Trace-level complete agreement 29/60 reference, 29/60 labeller; not the pass criterion (degenerate at n=60). Disagreement counts: `ref False / lab True` x 15.
