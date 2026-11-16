# Gate-version pilots: report

Frozen rules: `GATE_V2A_RULE.md` (content-token recall) and `TABLE_PROMPT_RULE.md` (tabular locator). v1 (`EXTRACTION_FIX_RULE.md`) is unchanged and reported beside both.

## v1 on record (33 present instances)

- Delivery 18/33, CI 0.364-0.719.
- Repair exact 6/18 (v1-delivered cases only), CI 0.133-0.590.
- Board-only control on those same 18 cases: 0/18, CI 0.000-0.185.

## v2a: content-token recall (same extraction, new gate)

| version | delivered | 95% CI | repair exact (delivered set) | pair control exact |
| --- | ---: | --- | --- | --- |
| v1 | 18/33 | 0.364-0.719 | 6/18 | 0/18 |
| v2a | 25/33 | 0.577-0.889 | 10/25 (0.211-0.613) | 0/25 |

Newly delivered by v2a: 8 (2hop__242753_658778, 2hop__520033_123956, 2hop__655505_110949, 2hop__677160_110882, 2hop__693444_220151, 2hop__765678_310556, 2hop__95970_456836, 3hop1__662618_339990_54675); lost: 1 (2hop__94507_654855). New answer calls: 8; spend $0.000671.

| case | v1 recall | v2a recall | v1 | v2a | v2a answer | exact |
| --- | ---: | ---: | --- | --- | --- | ---: |
| 2hop__123148_5385 | 0.714 | 0.667 | blocked | blocked | — | 0 |
| 2hop__157285_556157 | 1.000 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 2hop__207597_73244 | 0.000 | 0.000 | blocked | blocked | — | 0 |
| 2hop__242753_658778 | 0.750 | 0.833 | blocked | PASS | The creator of Judith and the Head of Holofernes, Gusta | 0 |
| 2hop__25396_212301 | 0.909 | 0.889 | PASS | PASS | Sidney Peel | 0 |
| 2hop__435184_84856 | 0.000 | 0.000 | blocked | blocked | — | 0 |
| 2hop__504464_708278 | 0.700 | 0.714 | blocked | blocked | — | 0 |
| 2hop__51760_602275 | 1.000 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 2hop__520033_123956 | 0.778 | 0.857 | blocked | PASS | 15 February 1942 | 1 |
| 2hop__528263_865831 | 1.000 | 1.000 | PASS | PASS | Randall County | 1 |
| 2hop__551235_310309 | 0.833 | 0.900 | PASS | PASS | Insufficient information. | 0 |
| 2hop__619265_45326 | 0.000 | 0.000 | blocked | blocked | — | 0 |
| 2hop__639445_567836 | 1.000 | 1.000 | PASS | PASS | Adams County | 1 |
| 2hop__655505_110949 | 0.750 | 1.000 | blocked | PASS | 11 September 1962 | 1 |
| 2hop__673655_316668 | 0.875 | 0.857 | PASS | PASS | Conga. | 1 |
| 2hop__677160_110882 | 0.750 | 1.000 | blocked | PASS | 1 January 1986 | 1 |
| 2hop__693444_220151 | 0.750 | 0.875 | blocked | PASS | Joan Erikson | 1 |
| 2hop__734582_71302 | 0.500 | 0.500 | blocked | blocked | — | 0 |
| 2hop__765678_310556 | 0.750 | 0.833 | blocked | PASS | John Profumo | 1 |
| 2hop__788306_131879 | 0.900 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 2hop__804417_126089 | 1.000 | 1.000 | PASS | PASS | Johan Remkes (King's Commissioner of North Holland) | 0 |
| 2hop__810884_22402 | 0.875 | 1.000 | PASS | PASS | Nearly 25,000 students. | 0 |
| 2hop__88834_425488 | 1.000 | 1.000 | PASS | PASS | Terri Irwin | 1 |
| 2hop__94507_654855 | 0.800 | 0.714 | PASS | blocked | — | 0 |
| 2hop__95970_456836 | 0.714 | 1.000 | blocked | PASS | Claudia Cardinale, who acted in the film, was born in L | 0 |
| 3hop1__274148_792411_51423 | 0.923 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 3hop1__389761_567566_84283 | 0.857 | 0.857 | PASS | PASS | Warner Music Group | 1 |
| 3hop1__506062_792411_51423 | 1.000 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 3hop1__593288_720914_41132 | 1.000 | 1.000 | PASS | PASS | 22 times. | 0 |
| 3hop1__662618_339990_54675 | 0.700 | 0.857 | blocked | PASS | Insufficient information. | 0 |
| 4hop1__3496_5274_458768_33637 | 0.818 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 4hop2__9988_158985_70784_61381 | 0.800 | 1.000 | PASS | PASS | Insufficient information. | 0 |
| 4hop3__131775_29339_508306_70744 | 0.000 | 0.000 | blocked | blocked | — | 0 |

Right-content, exact-fail answers under v2a (normalized gold is a substring of the answer; scored 0 by the frozen rule, listed separately):
| case | gold | answer |
| --- | --- | --- |
| 2hop__242753_658778 | Vienna Secession | The creator of Judith and the Head of Holofernes, Gustav Klimt, was a member of the Vienna Secession movement. |
| 2hop__804417_126089 | Johan Remkes | Johan Remkes (King's Commissioner of North Holland) |
| 2hop__810884_22402 | nearly 25,000 | Nearly 25,000 students. |
| 2hop__95970_456836 | La Goulette | Claudia Cardinale, who acted in the film, was born in La Goulette. |
| 3hop1__593288_720914_41132 | 22 | 22 times. |


## Tabular locator prompt (unchanged v1 gate)

| version | delivered | 95% CI | repair exact (delivered set) | pair control exact |
| --- | ---: | --- | --- | --- |
| v1 | 18/33 | 0.364-0.719 | 6/18 | 0/18 |
| tabular prompt | 18/33 | 0.364-0.719 | 5/18 (0.097-0.535) | 0/18 |

Newly delivered: 1 (4hop3__131775_29339_508306_70744); lost: 1 (2hop__673655_316668). Spend $0.006853.

| tabular case | v1 delivery | new delivery | new units |
| --- | --- | --- | --- |
| 2hop__435184_84856 | blocked | blocked | Season Episodes Originally aired First aired Last aired 20 F |
| 2hop__619265_45326 | blocked | blocked | 5 12 August 6, 2017 (2017 - 08 - 06) October 29, 2017 (2017  |
| 4hop3__131775_29339_508306_70744 | blocked | PASS | College comparison Clemson University University of South Ca |

| case | new delivery | v1 delivery | new answer | exact |
| --- | --- | --- | --- | ---: |
| 2hop__123148_5385 | blocked | blocked | — | 0 |
| 2hop__157285_556157 | PASS | PASS | Insufficient information. | 0 |
| 2hop__207597_73244 | blocked | blocked | — | 0 |
| 2hop__242753_658778 | blocked | blocked | — | 0 |
| 2hop__25396_212301 | PASS | PASS | Sidney Peel | 0 |
| 2hop__435184_84856 | blocked | blocked | — | 0 |
| 2hop__504464_708278 | blocked | blocked | — | 0 |
| 2hop__51760_602275 | PASS | PASS | Insufficient information. | 0 |
| 2hop__520033_123956 | blocked | blocked | — | 0 |
| 2hop__528263_865831 | PASS | PASS | Randall County | 1 |
| 2hop__551235_310309 | PASS | PASS | Insufficient information. | 0 |
| 2hop__619265_45326 | blocked | blocked | — | 0 |
| 2hop__639445_567836 | PASS | PASS | Adams County | 1 |
| 2hop__655505_110949 | blocked | blocked | — | 0 |
| 2hop__673655_316668 | blocked | PASS | — | 0 |
| 2hop__677160_110882 | blocked | blocked | — | 0 |
| 2hop__693444_220151 | blocked | blocked | — | 0 |
| 2hop__734582_71302 | blocked | blocked | — | 0 |
| 2hop__765678_310556 | blocked | blocked | — | 0 |
| 2hop__788306_131879 | PASS | PASS | Insufficient information. | 0 |
| 2hop__804417_126089 | PASS | PASS | Johan Remkes has been the King's Commissioner of North  | 0 |
| 2hop__810884_22402 | PASS | PASS | Nearly 25,000 students. | 0 |
| 2hop__88834_425488 | PASS | PASS | Terri Irwin | 1 |
| 2hop__94507_654855 | PASS | PASS | Socialist Party of America | 1 |
| 2hop__95970_456836 | blocked | blocked | — | 0 |
| 3hop1__274148_792411_51423 | PASS | PASS | Insufficient information. | 0 |
| 3hop1__389761_567566_84283 | PASS | PASS | Warner Music Group owns the record label of the Another | 0 |
| 3hop1__506062_792411_51423 | PASS | PASS | Insufficient information. | 0 |
| 3hop1__593288_720914_41132 | PASS | PASS | 22 times. | 0 |
| 3hop1__662618_339990_54675 | blocked | blocked | — | 0 |
| 4hop1__3496_5274_458768_33637 | PASS | PASS | Insufficient information. | 0 |
| 4hop2__9988_158985_70784_61381 | PASS | PASS | Insufficient information. | 0 |
| 4hop3__131775_29339_508306_70744 | PASS | blocked | University of South Carolina | 1 |

Right-content, exact-fail answers under the tabular prompt (listed separately; scored 0 by the frozen rule):
| case | gold | answer |
| --- | --- | --- |
| 2hop__804417_126089 | Johan Remkes | Johan Remkes has been the King's Commissioner of North Holland since 2010. |
| 2hop__810884_22402 | nearly 25,000 | Nearly 25,000 students. |
| 3hop1__389761_567566_84283 | Warner Music Group | Warner Music Group owns the record label of the Another Page performer. |
| 3hop1__593288_720914_41132 | 22 | 22 times. |

## Reading

Both versions keep v1 on record; neither replaces it. v2a isolates the gate term on identical extraction output. The tabular prompt changes the locator only, with the v1 gate and scoring held fixed. Exact scoring remains the outcome; delivery is a gate result.
