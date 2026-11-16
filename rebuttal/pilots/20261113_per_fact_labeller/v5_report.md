# V5 independent-reference validation of the per-fact labeller

Design `PER_FACT_RULE_V5.md` (sha256 `27f981d81207`); reference labels `reference_labels_v5.json` (sha256 `319e87302616`), frozen before the Haiku calls. Reference labeller **Gemini 3.6 Flash**; labeller under test **Claude Haiku 5.5**, prompt v3. 60 MuSiQue boards never used in labeller development; spend $0.382002, cap $5.00.

**Per-fact carrier agreement 155/176 = 0.881** (95% CI 0.823-0.925). The 21 disagreements are **all over-credits**: the reference lists no carrier and the labeller returns a unit - 9 x `reference no carrier, labeller partial` (first: `v5/gpt4omini/4hop3__39836_29339_508306_70744/f3`); 12 x `reference no carrier, labeller present` (first: `v5/qwen235b/4hop1__105688_17130_70784_79935/f1`). There are no misses of a reference carrier and no wrong-unit-only cases.

Board-level complete agreement is **60/60 = 1.000** (95% CI 0.940-1.000); kappa **1.000** (1.000-1.000) - **PASS** against 0.80/0.60; reference complete 26/60, labeller complete 26/60. The board-level figure hides the per-fact over-credits and is not the headline.

## What this validates

Carrier identification at the board checkpoint: whether the Haiku labeller returns the board units a different model, applying the same written rubric blind, marks as stating each fact. The reference is independent of the labeller under test and of the assistant that wrote the rubric, and its labels were hashed before the Haiku calls. It is an LLM reference, not author ground truth, so this is cross-model agreement on MuSiQue, not semantic fidelity or coverage. This run is the labeller's **validation record** for that one label and stage (`VALIDATION_RECORD.md`). The earlier author-label run failed because all 10 reserve disagreements were author-citation errors, not labeller misses (`author_citation_audit.md`); the corrected-label 30/30 is a post-hoc audit, not a validation. Fidelity, coverage and extraction-pool labels remain unvalidated.
