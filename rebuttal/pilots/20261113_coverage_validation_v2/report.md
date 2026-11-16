# Coverage prompt v2 — held-out validation

Rule `COVERAGE_VALIDATION_RULE_V2.md` (sha256 `c202a5efa206`), prompt `coverage_prompt_v2.json` (sha256 `868fcd089f46`). 25 traces, 60 held-out author comparisons; spend $0.009452.

Agreement: **18/60** (30.0%, exact Clopper-Pearson 95% CI 18.8-43.2%); Cohen kappa **0.060** (bootstrap 95% CI 0.019-0.128).

Pass rule fixed before the run: agreement >= 0.80 **and** kappa >= 0.60. Verdict: **FAIL**.

The coverage labeller is **not validated**. The lexical rule remains the reported coverage figure, and no prompt edit follows this result.

| k | n | rate | 95% CI |
| ---: | ---: | ---: | --- |
| 18 | 60 | 30.0% | 18.8-43.2% |

Prompt complete: 8/60; author complete: 50/60.

## Per item

| item | prompt | authors | agreement |
| --- | ---: | --- | ---: |
| Calibration run 1 | False | [False, False, False, False] | 4/4 |
| Calibration run 2 | False | [True, True, True, True] | 0/4 |
| Calibration run 3 | False | [False, False, False, False] | 4/4 |
| Calibration run 4 | False | [True, True, True, True] | 0/4 |
| Calibration run 5 | False | [True, True, True, True] | 0/4 |
| Dev run 01 | False | [True, True] | 0/2 |
| Dev run 02 | False | [True, True] | 0/2 |
| Dev run 03 | False | [True, True] | 0/2 |
| Dev run 04 | False | [True, True] | 0/2 |
| Dev run 05 | False | [True, True] | 0/2 |
| Dev run 06 | False | [True, True] | 0/2 |
| Dev run 07 | False | [True, True] | 0/2 |
| Dev run 08 | False | [True, True] | 0/2 |
| Dev run 09 | False | [True, True] | 0/2 |
| Dev run 10 | False | [False, False] | 2/2 |
| Dev run 11 | False | [True, True] | 0/2 |
| Dev run 12 | False | [True, True] | 0/2 |
| Dev run 13 | False | [True, True] | 0/2 |
| Dev run 14 | False | [True, True] | 0/2 |
| Dev run 15 | False | [True, True] | 0/2 |
| Dev run 16 | True | [True, True] | 2/2 |
| Dev run 17 | True | [True, True] | 2/2 |
| Dev run 18 | True | [True, True] | 2/2 |
| Dev run 19 | False | [True, True] | 0/2 |
| Dev run 20 | True | [True, True] | 2/2 |

## Disagreements

| item | author | prompt | support statuses (id: status) |
| --- | ---: | ---: | --- |
| Calibration run 2 | A (True) | False | s1: partial; s2: partial |
| Calibration run 2 | B (True) | False | s1: partial; s2: partial |
| Calibration run 2 | C (True) | False | s1: partial; s2: partial |
| Calibration run 2 | D (True) | False | s1: partial; s2: partial |
| Calibration run 4 | A (True) | False | s1: present; s2: partial; s3: present |
| Calibration run 4 | B (True) | False | s1: present; s2: partial; s3: present |
| Calibration run 4 | C (True) | False | s1: present; s2: partial; s3: present |
| Calibration run 4 | D (True) | False | s1: present; s2: partial; s3: present |
| Calibration run 5 | A (True) | False | s1: partial; s2: partial; s3: present |
| Calibration run 5 | B (True) | False | s1: partial; s2: partial; s3: present |
| Calibration run 5 | C (True) | False | s1: partial; s2: partial; s3: present |
| Calibration run 5 | D (True) | False | s1: partial; s2: partial; s3: present |
| Dev run 01 | A (True) | False | s1: present; s2: partial |
| Dev run 01 | B (True) | False | s1: present; s2: partial |
| Dev run 02 | C (True) | False | s1: distorted; s2: partial |
| Dev run 02 | D (True) | False | s1: distorted; s2: partial |
| Dev run 03 | A (True) | False | s1: partial; s2: partial |
| Dev run 03 | B (True) | False | s1: partial; s2: partial |
| Dev run 04 | C (True) | False | s1: absent; s2: partial |
| Dev run 04 | D (True) | False | s1: absent; s2: partial |
| Dev run 05 | A (True) | False | s1: partial; s2: partial |
| Dev run 05 | B (True) | False | s1: partial; s2: partial |
| Dev run 06 | C (True) | False | s1: partial; s2: present |
| Dev run 06 | D (True) | False | s1: partial; s2: present |
| Dev run 07 | A (True) | False | s1: partial; s2: present |
| Dev run 07 | B (True) | False | s1: partial; s2: present |
| Dev run 08 | A (True) | False | s1: present; s2: partial |
| Dev run 08 | B (True) | False | s1: present; s2: partial |
| Dev run 09 | C (True) | False | s1: partial; s2: partial |
| Dev run 09 | D (True) | False | s1: partial; s2: partial |
| Dev run 11 | A (True) | False | s1: partial; s2: absent; s3: present |
| Dev run 11 | B (True) | False | s1: partial; s2: absent; s3: present |
| Dev run 12 | A (True) | False | s1: present; s2: partial; s3: present |
| Dev run 12 | B (True) | False | s1: present; s2: partial; s3: present |
| Dev run 13 | A (True) | False | s1: partial; s2: absent; s3: partial; s4: partial |
| Dev run 13 | B (True) | False | s1: partial; s2: absent; s3: partial; s4: partial |
| Dev run 14 | A (True) | False | s1: partial; s2: partial; s3: partial; s4: partial |
| Dev run 14 | B (True) | False | s1: partial; s2: partial; s3: partial; s4: partial |
| Dev run 15 | C (True) | False | s1: partial; s2: partial; s3: partial; s4: partial |
| Dev run 15 | D (True) | False | s1: partial; s2: partial; s3: partial; s4: partial |
| Dev run 19 | A (True) | False | s1: absent; s2: present; s3: absent; s4: present; s5: present; s6: present; s7: present; s8: present; s9: present; s10: present |
| Dev run 19 | B (True) | False | s1: absent; s2: present; s3: absent; s4: present; s5: present; s6: present; s7: present; s8: present; s9: present; s10: present |
