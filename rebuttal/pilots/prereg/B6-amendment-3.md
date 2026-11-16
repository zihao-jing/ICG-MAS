# B6 amendment 3: delivery-threshold sensitivity

2026-11-15. Frozen after the corrected sharding pass ($0.006097 total so far) and before the calls below.

The primary arm uses the frozen `delivery_gate` (fact recall >= 0.8). It delivered 18 of 39 extraction cases
and 0 of 20 sharding cases. Diagnosis: the gate tests near-verbatim restatement, and extraction units are
paraphrases; in most sharding cases the flagged fact is a matcher-derived claim that no supplied passage
states, so there is nothing to deliver under any threshold.

This amendment adds a **sensitivity arm only**, not a replacement: the same stored extraction units are
delivered at **recall >= 0.5** (no new extraction calls; one answer call per case that has a unit at or above
0.5). It is reported separately and labelled as a post-hoc threshold, so the primary result stays the
gate-based one. No control arm for the sensitivity cases.

Cap unchanged ($5.00), chunks of $1 or less, every call logged.