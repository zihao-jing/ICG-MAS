"""
Evidence-flow audit package.

Modules:
  evidence_units          — EvidenceUnit dataclass, gold support loader, extraction
  alignment               — Align transmitted units to gold critical units
  metrics                 — Evidence-flow metrics (recall, omission, distortion, …)
  interventions           — Controlled evidence deletion experiments
  local_importance_analysis — Correlation between local scores and true criticality
  reporting               — Export JSONL and LaTeX tables
"""
