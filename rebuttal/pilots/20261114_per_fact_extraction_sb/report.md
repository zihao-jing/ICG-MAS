# Prompt v3 at the Silo-Bench extraction pool

Rule `Per-fact-extraction-sb.md` (sha256 `12a96b0d8487`); reference labels `f1370635505f`, frozen before the Haiku calls. Gemini 3.6 Flash reference; Claude Haiku 5.5 prompt v3; 30 fresh Silo-Bench traces, 250 facts. Spend $0.417768, cap $1.00.

**Per-fact presence agreement 215/250 = 0.860** (95% CI 0.811-0.901); kappa **0.127** (0.000-0.270) - **FAIL** against 0.80/0.60.

Disagreements: `ref False / lab True` x 35.
