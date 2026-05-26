"""
Communication protocols for the evidence-flow audit experiment.

Modules:
  base             — AgentShard, ProtocolResult, shard_instance, shared helpers
  local            — No-communication local baselines
  full_sharing     — Full evidence sharing oracle
  debate           — Free-form multi-round debate
  summary_exchange — Compressed summary exchange
  gated            — Confidence-gated and disagreement-gated communication
  relay            — Random, score-ranked, and redundancy-aware evidence relay
"""
