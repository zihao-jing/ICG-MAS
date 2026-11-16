# Hand check, first case: gemma31b 2hop__700093_455653, agent 0

Question: Who founded the political party of Dimuthu Bandara Abayakoon?

## Base pool (text, score composite)
- extraction:a0:u0 score 0.400: Rohana Wijeweera was the founding leader of the Janatha Vimukthi Peramuna.
- extraction:a0:u1 score 0.333: Loretta Nall founded the United States Marijuana Party in 2002.

## Duplicated pool
- extraction:a0:u0 score 0.400
- extraction:a0:u1 score 0.333
- dup:a0 score 0.400 (copy of extraction:a0:u0)
- base / score_ranked: extraction:a0:u0
- base / redundancy_aware: extraction:a0:u0
- duplicated / score_ranked: extraction:a0:u0
- duplicated / redundancy_aware: extraction:a0:u0

Check: under score_ranked the duplicated condition must select the duplicate; under redundancy_aware it must not.
