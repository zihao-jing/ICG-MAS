# Answer-equivalence beside exact match

Prompt `answer-equiv-v1` (frozen; see `rebuttal/pilots/20261112_answer_equiv/`). **Not validated on MuSiQue-style answers**: the validation set was Silo-Bench author labels, and both cohorts here are MuSiQue (Stage 2). Exact match stays the primary number; the equivalence counts are descriptive and flagged wherever they differ.

## Direct insertion (59 cases)

| arm | n | exact | 95% CI | exact or equivalent | 95% CI | equivalent-only |
| --- | ---: | ---: | --- | ---: | --- | ---: |
| control | 59 | 0 | 0.000-0.061 | 1 | 0.000-0.091 | 1 |
| insert | 59 | 32 | 0.408-0.673 | 39 | 0.526-0.779 | 7 |

Right content under equivalence, exact-match miss (8):

| case | model | arm | gold | answer | equivalence |
| --- | --- | --- | --- | --- | --- |
| 2hop__304852_758385 | gemma-4-31b-it | insert | Hubbard County | Hubbard County, Minnesota | EQUIVALENT |
| 2hop__554145_88622 | gemma-4-31b-it | control | ADM Michael S. Rogers | ADM Michael S. Rogers USN | EQUIVALENT |
| 2hop__554145_88622 | gemma-4-31b-it | insert | ADM Michael S. Rogers | ADM Michael S. Rogers USN | EQUIVALENT |
| 2hop__810884_22402 | gemma-4-31b-it | insert | nearly 25,000 | Nearly 25,000 students. | EQUIVALENT |
| 3hop1__389761_567566_84283 | gpt-4o-mini | insert | Warner Music Group | Warner Music Group owns Warner Bros. Records, | EQUIVALENT |
| 3hop1__454441_55349_651302 | gemma-4-31b-it | insert | Denver | Denver, Colorado | EQUIVALENT |
| 3hop1__593288_720914_41132 | gpt-4o-mini | insert | 22 | 22 times. | EQUIVALENT |
| 4hop1__3496_5274_458768_33637 | gemma-4-31b-it | insert | two | 2 | EQUIVALENT |

## Extraction fix (33 present cases)

| arm | n | exact | 95% CI | exact or equivalent | 95% CI | equivalent-only |
| --- | ---: | ---: | --- | ---: | --- | ---: |
| board_only | 33 | 0 | 0.000-0.106 | 0 | 0.000-0.106 | 0 |
| repair | 18 | 6 | 0.133-0.590 | 8 | 0.215-0.692 | 2 |

Right content under equivalence, exact-match miss (2):

| case | model | arm | gold | answer | equivalence |
| --- | --- | --- | --- | --- | --- |
| 2hop__810884_22402 | gemma-4-31b-it | repair | nearly 25,000 | Nearly 25,000 students. | EQUIVALENT |
| 3hop1__593288_720914_41132 | gpt-4o-mini | repair | 22 | 22 times. | EQUIVALENT |

## Insertion and repair on the same 18 delivered cases

18 cases where the extraction-fix repair was delivered and an insertion answer exists (0 without an insertion answer). Denominator is the same for both.

| arm | n | exact | 95% CI | exact or equivalent |
| --- | ---: | ---: | --- | ---: |
| insert | 18 | 7 | 0.173-0.643 | 11 |
| repair | 18 | 6 | 0.133-0.590 | 8 |
| insertion control | 18 | 0 | 0.000-0.185 | 0 |
| board-only control | 18 | 0 | 0.000-0.185 | 0 |

Reading: this paired table is the like-for-like comparison. The 19/33 insertion figure counts present cases the repair gate delivered only 18 of; 0/18 of the repair-paired control answers are exact.
