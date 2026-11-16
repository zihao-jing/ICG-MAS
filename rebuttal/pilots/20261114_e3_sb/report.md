# E3 Silo-Bench routes (exploratory)

51 Silo-Bench qwen235b traces, random_relay, k = 3 labels from `20261113_sb_presence_full`; $0, no model calls.

**Exploratory.** The Silo-Bench extraction presence label is unvalidated (prompt v3 failed at kappa .127; fixed prompt v4 also failed at kappa .553, cluster CI [0.000, 1.000]). The board carrier label is unvalidated for Silo-Bench, fidelity/distortion is unvalidated, and these labels are random_relay, not the score-ranked relay of the MuSiQue E3 run. No row here is a validated correction.

| route | n |
|---|---:|
| aggregation | 19 |
| correct | 4 |
| distortion | 2 |
| selection | 26 |

| removed | changed | share [95% CI] |
|---|---:|---|
| pool | 0/51 | 0.000 [0.000, 0.070] |
| fidelity | 2/51 | 0.039 [0.011, 0.132] |
| aggregation | 19/51 | 0.373 [0.253, 0.510] |
| all_three | 51/51 | 1.000 [0.930, 1.000] |
