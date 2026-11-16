# [R1] re-implementation on the 89 known-stage cases, Qwen-235B backbone

2026-11-15. Released prompt and parser, our renderer, the stage read from the released step coordinate under the
frozen map `R1-coordinate-stage-map.md` (sha `2015e084…`), exactly as the Gemini run in `20261115_r1_full`.
Qwen-235B (`qwen/qwen3-235b-a22b-2507`), temperature 0, 4,096-token cap. Projection **$0.0671**, cap $1.00,
spend **$0.034209**, 89 calls.

| population | correct |
| --- | ---: |
| injected (n=30) | 25/30 |
| cohort (n=59) | 37/59 |
| **all (n=89)** | **62/89 = .697** |

The mode-code map is not used: the released R.1/R.2 modes describe failure type, not location, and mapping them
by hand gave 0/89 on both backbones (recorded, withdrawn). The coordinate map reproduces the Gemini run's 53/89
exactly (27 injected, 26 cohort), which is the check that the two runs are scored the same way.