# [R1] re-implementation: step-coordinate to stage map (frozen before reading any stage)

2026-11-15. Applies to the stored 30-case pilot outputs. No new calls.

## The map

The released output names an agent and a step. Our renderer (`render_trace`) emits steps in a fixed order:

- steps 1..n: extraction, one per agent (agent-0 .. agent-(n-1));
- steps n+1..2n: transmission, one per agent, same order;
- step 2n+1: the shared board (aggregator);
- step 2n+2: the final answer (aggregator).

The stage of a named step is therefore read from the renderer's own ordering:

| step coordinate | stage |
| --- | --- |
| 1 .. n | extraction |
| n+1 .. 2n | transmission |
| 2n+1, 2n+2 | aggregation |

A coordinate outside this range is `unmapped` and scores wrong. The mode code is kept but not used for the
stage; the released taxonomy's R.1/R.2 describe failure type, not location, so mapping them to a stage by hand
was the deviation that produced the earlier 0/30.

## Deviation statement (for the report)

This is still a re-implementation: released prompt and parser, our trace renderer, and the stage taken from the
released coordinate under the map above. The released benchmark's own renderer and step semantics are not used.

## Status of the earlier result

The 0/30 stands on record, labelled with the mapping error. The re-implementation result is the coordinate
reading (26/30, Wilson [.703, .947]).