# B6 amendment 4: full-evidence routing for the 20 sharding cases

2026-11-15. Frozen after the corrected sharding pass ($0.008944 total so far) and before the calls below.
Cap **$1.00**, one chunk.

## Diagnosis from the logged outputs

After the corrected pass (the carrying passage as input), 0 of 20 sharding cases delivered under the frozen
gate. The logged extractions show why:

- In 15 of 20 cases the passage with the highest fact recall is the flagged agent's own passage, i.e. no
  other supplied passage scores higher.
- The flagged fact sits at recall >= 0.8 in a supplied passage in 6 of 20, at 0.5-0.8 in 10, below 0.5 in 4.
- The extracted units are short paraphrases of single sentences; even where a sentence states the fact, the
  unit restates it with different words and fails the 0.8 gate. Examples: "Dennis Quaid is married to Meg
  Ryan" is a two-hop claim across two films' passages; "The Radio Television of Kosovo has its headquarters
  in Pristina" has no passage that states it.

The matcher built these facts from gold supports and its own world knowledge, not from a sentence in the
evidence. A single-passage re-route therefore has nothing to deliver.

## The fix (gold-free)

**Full-evidence routing**: for each of the 20 cases, give the flagged agent the **concatenation of all the
instance's source supports** (title and text, in agent order) as the extraction context, with the frozen relay
extraction prompt, the trace's own model, up to 3 units. Delivered units go to the flagged agent's board and
one aggregation call follows, exactly as in the primary arm.

This uses no gold answer, reference answer, final answer, diagnosis text or fact text; only the evidence the
instance supplied. It targets the **sharding stage**: the agent lacked the rest of the evidence, not a
sentence.

Expected outcome stated in advance: if the fact is a derived claim, a multi-passage context can license it
where a single passage cannot; if it is not derivable at all, delivery stays low. Either count is the result.

## Calls and scoring

20 extraction calls (<= 3 units, 512 tokens) plus at most 20 aggregation calls (1,024 tokens), temperature 0.
Delivered count out of 20 with a Clopper-Pearson 95% interval; for delivered cases, paired exact correctness
against the same trace's baseline.

The earlier recall >= 0.5 sensitivity (amendment 3) is a **post-hoc** threshold and is reported as such, not
as part of this arm.