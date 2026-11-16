# E2-A proxy technical supplement — 2026-11-08

Before proxy outcome calls. Same five reserved IDs/action manifest as E2-A-technical; never final labels. Pilot both card variants P-q/P-a without choosing or freezing either. Qwen generates facts; P-a uses three full-shard samples from the original base model, temperature .7, seed42, lowercased exact-answer majority with lexical tie-break. All shards, no gold answer/support flags, human labels, audit verdicts or baseline predictions enter proxy generation. Empty/invalid fact schema fails rather than inventing supports. Two schema retries maximum, every attempt logged. Both variants match the injected checkpoints with dev-v2 Qwen. Maximum75 calls. E1 gold-support matcher is the separate existing postcheck. This supplement tests the optional E6 dependency; no full E6 run.

Config SHA256: 1a7e603f8430d837091df5a29888a1a44a062aa381ff43ebc95f8eecc689b190
Script SHA256: f726cab50ec05077fa910c0c708034b4dc08c2b953914b2c5b3018af524b5315
