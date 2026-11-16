# Extraction-fix pilot: report

Rule: `EXTRACTION_FIX_RULE.md`; targeted extraction on the 33 present instances of the Stage 2 clean cohort. Oracle-targeted: the missing claim is given to the locator. Delivery was read and written before any answer.

## Delivery (unchanged R2 gate)

Delivered **18/33**, exact 95% CI 0.364-0.719.

| case | model | recall | gate | units |
| --- | --- | ---: | --- | --- |
| 2hop__520033_123956 | gemma-4-31b-it | 0.778 | blocked | It occurred near Palembang, on Sumatra, on 13–15 February 1942. |
| 2hop__157285_556157 | gemma-4-31b-it | 1.000 | PASS | The Mzingwane River, formerly known Umzingwane River as or Umzingwani  / It rises near Fort Usher, Matobo District, south of Bulawayo and flows |
| 2hop__804417_126089 | gemma-4-31b-it | 1.000 | PASS | The King's Commissioner of North Holland is Johan Remkes, serving sinc |
| 4hop2__9988_158985_70784_61381 | gemma-4-31b-it | 0.800 | PASS | The Kingdom of Saudi Arabia is a country situated in Southwest Asia, t / Its extensive coastlines on the Persian Gulf and Red Sea provide great |
| 2hop__88834_425488 | gemma-4-31b-it | 1.000 | PASS | Bindi the Jungle Girl is an Australian children's television nature do / Also appearing on the show are Bindi's mother Terri, her younger broth |
| 2hop__639445_567836 | gemma-4-31b-it | 1.000 | PASS | Hastings is a city and county seat of Adams County, Nebraska, United S |
| 2hop__677160_110882 | gemma-4-31b-it | 0.750 | blocked | James Cottriall (born 1 January 1986, Stratford upon Avon) is an Engli |
| 2hop__207597_73244 | gemma-4-31b-it | 0.000 | blocked | NONE |
| 2hop__765678_310556 | gemma-4-31b-it | 0.750 | blocked | Profumo was born in London, the son of former British government minis |
| 2hop__551235_310309 | gemma-4-31b-it | 0.833 | PASS | Sir Edwin Landseer Lutyens, (; ; 29 March 1869 – 1 January 1944) was a |
| 2hop__693444_220151 | gemma-4-31b-it | 0.750 | blocked | Erikson's stages of psychosocial development, as articulated in the se |
| 2hop__734582_71302 | gemma-4-31b-it | 0.500 | blocked | the prequel covers the journey of his father, Vito Corleone (De Niro), |
| 2hop__655505_110949 | gemma-4-31b-it | 0.750 | blocked | Mauro Scocco (born 11 September 1962) is a Swedish pop artist of Itali |
| 2hop__504464_708278 | gemma-4-31b-it | 0.700 | blocked | Harold Stanley (October 2, 1885 – May 14, 1963) was an American busine |
| 2hop__123148_5385 | gemma-4-31b-it | 0.714 | blocked | While not in Oklahoma City proper, other large employers within the MS |
| 2hop__95970_456836 | gemma-4-31b-it | 0.714 | blocked | The film also features La Goulette native Claudia Cardinale as herself |
| 2hop__435184_84856 | gemma-4-31b-it | 0.000 | blocked | NONE |
| 2hop__619265_45326 | gemma-4-31b-it | 0.000 | blocked | NONE |
| 2hop__810884_22402 | gemma-4-31b-it | 0.875 | PASS | The biggest university in Switzerland is the University of Zurich with |
| 3hop1__506062_792411_51423 | gemma-4-31b-it | 1.000 | PASS | Casa Loma (Spanish for ``Hill House '') is a Gothic Revival style mans |
| 2hop__788306_131879 | gemma-4-31b-it | 0.900 | PASS | Buckingham and the surrounding area has been settled for some time wit |
| 2hop__242753_658778 | gemma-4-31b-it | 0.750 | blocked | Gustav Klimt (July 14, 1862 – February 6, 1918) was an Austrian symbol |
| 3hop1__662618_339990_54675 | gemma-4-31b-it | 0.700 | blocked | To the west of the Tualatin Mountains lies the Oregon Coast Range, and |
| 4hop3__131775_29339_508306_70744 | gemma-4-31b-it | 0.000 | blocked | NONE |
| 2hop__528263_865831 | gemma-4-31b-it | 1.000 | PASS | Canyon is a city in, and the county seat of, Randall County, Texas, Un |
| 2hop__51760_602275 | gemma-4-31b-it | 1.000 | PASS | Evelyn Einstein (28 March 1941 – 13 April 2011) was the adopted daught |
| 4hop1__3496_5274_458768_33637 | gemma-4-31b-it | 0.818 | PASS | The two ethnic minorities were often viewed differently by White Ameri |
| 2hop__94507_654855 | gemma-4-31b-it | 0.800 | PASS | Eugene Victor Debs (November 5, 1855 – October 20, 1926) was an Americ |
| 3hop1__389761_567566_84283 | gpt-4o-mini | 0.857 | PASS | Warner Bros. Records Parent company Warner Music Group |
| 3hop1__593288_720914_41132 | gpt-4o-mini | 1.000 | PASS | Plague occurred in Venice 22 times between 1361 and 1528. / The plague of 1576–77 killed 50,000 in Venice, almost a third of the p / Late outbreaks in central Europe included the Italian Plague of 162 |
| 2hop__673655_316668 | gpt-4o-mini | 0.875 | PASS | "Midnight Blue is a 1963 album by Jazz guitarist Kenny Burrell featuri |
| 2hop__25396_212301 | gpt-4o-mini | 0.909 | PASS | Peel was the second son of Arthur Peel, 1st Viscount Peel, Speaker of  |
| 3hop1__274148_792411_51423 | qwen3-235b-a22b-2507 | 0.923 | PASS | Casa Loma (Spanish for ``Hill House '') is a Gothic Revival style mans |

### Why delivery failed

- Verbatim sentence just below the gate (0.70-0.79): 10 cases (2hop__520033_123956, 2hop__677160_110882, 2hop__765678_310556, 2hop__693444_220151, 2hop__655505_110949, 2hop__504464_708278, 2hop__123148_5385, 2hop__95970_456836, 2hop__242753_658778, 3hop1__662618_339990_54675). The locator returned the stating sentence, but the R2 full-token recall includes function words ('was born on' vs '(born'), so a correct sentence is blocked.
- Sentence found but low recall: 1 cases (2hop__734582_71302).
- Locator returned NONE: 4 cases (2hop__207597_73244, 2hop__435184_84856, 2hop__619265_45326, 4hop3__131775_29339_508306_70744); 3 of these are tabular evidence, which is not sentence-shaped.

## Scoring (frozen exact answer_f1)

- Board-only control: **0/33** exact, 95% CI 0.000-0.106.
- Repair arm: **6/18** exact, 95% CI 0.133-0.590 (called only for delivered cases).
- Board-only control restricted to those same 18 cases: **0/18** exact, 95% CI 0.000-0.185. This is the paired control for the repair arm.
- Paired: repair better in **6** cases, worse in **0**.

### Right content, failed exact match (reported separately)

These answers state the gold (the normalized gold is a substring of the answer) but carry extra words, so the frozen exact rule scores them 0. They are not repair failures and are excluded from the failure count; they are scored exactly as the frozen rule requires and shown here beside it. Found: 3.

| case | gold | answer | paired control |
| --- | --- | --- | --- |
| 2hop__804417_126089 | Johan Remkes | Johan Remkes (King's Commissioner of North Holland) | Insufficient information. |
| 2hop__810884_22402 | nearly 25,000 | Nearly 25,000 students. | Insufficient information. |
| 3hop1__593288_720914_41132 | 22 | 22 times. | Insufficient information. |

| case | gold | board-only answer | exact | repair answer | exact |
| --- | --- | --- | ---: | --- | ---: |
| 2hop__520033_123956 | 15 February 1942 | Insufficient information. | 0 | — | 0 |
| 2hop__157285_556157 | Limpopo River | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__804417_126089 | Johan Remkes | Insufficient information. | 0 | Johan Remkes (King's Commissioner of North Holland) | 0 |
| 4hop2__9988_158985_70784_61381 | 1932 | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__88834_425488 | Terri Irwin | Insufficient information. | 0 | Terri Irwin | 1 |
| 2hop__639445_567836 | Adams County | Insufficient information. | 0 | Adams County | 1 |
| 2hop__677160_110882 | 1 January 1986 | Insufficient information. | 0 | — | 0 |
| 2hop__207597_73244 | Thaba Putsoa | Insufficient information. | 0 | — | 0 |
| 2hop__765678_310556 | John Profumo | Insufficient information. | 0 | — | 0 |
| 2hop__551235_310309 | Edwin Landseer Lutyens | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__693444_220151 | Joan Erikson | Insufficient information. | 0 | — | 0 |
| 2hop__734582_71302 | Vito Corleone | Insufficient information. | 0 | — | 0 |
| 2hop__655505_110949 | 11 September 1962 | Insufficient information. | 0 | — | 0 |
| 2hop__504464_708278 | Harold Stanley | Morgan Stanley | 0 | — | 0 |
| 2hop__123148_5385 | 11,900 | Insufficient information. | 0 | — | 0 |
| 2hop__95970_456836 | La Goulette | Insufficient information. | 0 | — | 0 |
| 2hop__435184_84856 | January 20, 2017 | Insufficient information. | 0 | — | 0 |
| 2hop__619265_45326 | 12 | Insufficient information. | 0 | — | 0 |
| 2hop__810884_22402 | nearly 25,000 | Insufficient information. | 0 | Nearly 25,000 students. | 0 |
| 3hop1__506062_792411_51423 | Casa Loma | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__788306_131879 | River Great Ouse | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__242753_658778 | Vienna Secession | Insufficient information. | 0 | — | 0 |
| 3hop1__662618_339990_54675 | Tualatin Mountains | Insufficient information. | 0 | — | 0 |
| 4hop3__131775_29339_508306_70744 | University of South Carolina | Clemson University | 0 | — | 0 |
| 2hop__528263_865831 | Randall County | Insufficient information. | 0 | Randall County | 1 |
| 2hop__51760_602275 | Hans Albert Einstein | Insufficient information. | 0 | Insufficient information. | 0 |
| 4hop1__3496_5274_458768_33637 | two | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__94507_654855 | Socialist Party of America | Eugene V. Debs (the person the novel is based on) is associa | 0 | Socialist Party of America | 1 |
| 3hop1__389761_567566_84283 | Warner Music Group | Warner Bros. Records owns the record label of Christopher Cr | 0 | Warner Music Group | 1 |
| 3hop1__593288_720914_41132 | 22 | Insufficient information. | 0 | 22 times. | 0 |
| 2hop__673655_316668 | conga | Insufficient information. | 0 | Conga. | 1 |
| 2hop__25396_212301 | Arthur Peel | Sidney Peel | 0 | Sidney Peel | 0 |
| 3hop1__274148_792411_51423 | Casa Loma | Insufficient information. | 0 | Insufficient information. | 0 |

## Cost

Spend $0.009024 against a $5.00 cap. Every intent and result is in `calls.jsonl`.

## Reading

The delivery rate says how often a targeted pass recovers the stated claim. The board-only/repair pair is the frozen scoring result, not a claim about the model's general evidence use.
