# Causes of proxy-vs-gold stage disagreements (frozen before the diagnosis)

2026-11-15. $0: read from stored labels only, no calls.

## Population

Every trace of the three Q1 samples for which the atom-level proxy stage (`Proxy-atom-presence.md`) and the gold
stage (`Proxy-vs-gold-stage.md`, amendment 1) are both present and **differ**.

## What is compared

Gold's failing checkpoint: extraction if any gold atom is absent at extraction, else board. For each gold atom that
the gold labeller marks absent at that checkpoint, report:

- the atom text;
- whether the gold-side checkpoint entries carry it: lexical recall of the atom's tokens (normalize, stop-list
  removed) against the concatenated checkpoint entry texts;
- the proxy fact whose atoms are closest to it (best lexical recall of any of that fact's atom texts against the
  gold atom) and that fact's wording;
- whether that proxy fact's atom was labelled present at the same checkpoint by the atom-level proxy labeller.

## One cause per atom

1. **gold labeller error** — recall ≥ .8 against the gold-side entries: the atom's own words are in the entries and
   the gold labeller still called it absent.
2. **wording mismatch** — otherwise, if a proxy fact atom labelled present matches the gold atom at recall ≥ .5: a
   close variant was accepted on the proxy side and rejected on the gold side (the two prompts apply different
   standards).
3. **proxy fact does not carry the atom** — no proxy fact atom reaches .5 against the gold atom: the proxy fact set
   simply does not express it, so the proxy audit sees nothing missing.

Atom-key mismatch cannot be assigned here: a trace with a checkpoint that fails the frozen parser has no gold stage
and is outside the population. Its count is reported beside the table.

## One cause per trace

The cause held by the majority of the trace's listed absent atoms; on a tie, the cause of the first absent atom at
the failing checkpoint. The atom-level list is reported with the trace-level assignment so a different reading is
visible.

## Output

Per sample and overall: traces by disagreement direction, then traces by cause, then the atom-level table. No rates
and no interval; this is a description of the disagreements, not a new estimate.