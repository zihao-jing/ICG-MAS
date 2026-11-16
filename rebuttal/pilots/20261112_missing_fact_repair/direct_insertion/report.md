# Direct-insertion pilot: report

Rule: `DIRECT_INSERTION_RULE.md`; the missing fact is supplied verbatim to the board, so it is always delivered. This is an oracle upper bound, not an achievable repair.

Rule sha256 `57eb798e76ba37b1903103c20fbfcdcddbbc6a3e7d29a3bd00f0085f6f42ccdf`; cases sha256 `bb1ccb53230393b51ee7c805a3655bec119e32e26fd0c9ae050ef58405090db0`. Spend $0.009844 against a $5.00 cap.

## Pilot (10 instances)

| arm | exact | n | exact 95% CI |
| --- | ---: | ---: | --- |
| control (board only) | 0 | 10 | 0.000-0.308 |
| insert (fact supplied) | 3 | 10 | 0.067-0.652 |

Paired: insert better in **3**, worse in **0**.

## Full cohort (59 instances)

| arm | exact | n | exact 95% CI |
| --- | ---: | ---: | --- |
| control (board only) | 0 | 59 | 0.000-0.061 |
| insert (fact supplied) | 32 | 59 | 0.408-0.673 |

Paired: insert better in **32**, worse in **0**.

Delivery: the insert arm supplies the fact in **59/59** cases by construction (no gate); the control arm adds no unit and, under the R4 diagnosis that selected this cohort, no board unit carries the targeted fact.

## Presence label: present

| arm | exact | n | exact 95% CI |
| --- | ---: | ---: | --- |
| control (board only) | 0 | 33 | 0.000-0.106 |
| insert (fact supplied) | 19 | 33 | 0.392-0.745 |

Paired: insert better in **19**, worse in **0**.

## Presence label: partial

| arm | exact | n | exact 95% CI |
| --- | ---: | ---: | --- |
| control (board only) | 0 | 6 | 0.000-0.459 |
| insert (fact supplied) | 0 | 6 | 0.000-0.459 |

Paired: insert better in **0**, worse in **0**.

## Presence label: absent

| arm | exact | n | exact 95% CI |
| --- | ---: | ---: | --- |
| control (board only) | 0 | 20 | 0.000-0.168 |
| insert (fact supplied) | 13 | 20 | 0.408-0.846 |

Paired: insert better in **13**, worse in **0**.

## Per case

| case | model | presence | gold | control answer | exact | insert answer | exact |
| --- | --- | --- | --- | --- | ---: | --- | ---: |
| 2hop__123148_5385 | gemma-4-31b-it | present | 11,900 | Insufficient information. | 0 | 11,900 | 1 |
| 2hop__128342_375952 | gemma-4-31b-it | absent | Santa Barbara County | Insufficient information. | 0 | KABG is a radio station licensed to Los Alamos, New Mex | 0 |
| 2hop__157285_556157 | gemma-4-31b-it | present | Limpopo River | Insufficient information. | 0 | Mzingwane River | 0 |
| 2hop__207597_73244 | gemma-4-31b-it | present | Thaba Putsoa | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__242753_658778 | gemma-4-31b-it | present | Vienna Secession | Insufficient information. | 0 | Gustav Klimt, the creator of Judith and the Head of Hol | 0 |
| 2hop__25396_212301 | gpt-4o-mini | present | Arthur Peel | Sidney Peel | 0 | Sidney Peel | 0 |
| 2hop__304852_758385 | gemma-4-31b-it | absent | Hubbard County | Park Rapids, Minnesota | 0 | Hubbard County, Minnesota | 0 |
| 2hop__323534_810083 | gemma-4-31b-it | partial | Scranton | Insufficient information. | 0 | Scranton, Pennsylvania, United States | 0 |
| 2hop__342746_679190 | gemma-4-31b-it | absent | Garson Kanin | Insufficient information. | 0 | Garson Kanin | 1 |
| 2hop__435184_84856 | gemma-4-31b-it | present | January 20, 2017 | Insufficient information. | 0 | January 20, 2017 | 1 |
| 2hop__46213_494136 | gemma-4-31b-it | absent | Meg Ryan | Insufficient information. | 0 | Meg Ryan | 1 |
| 2hop__47808_198548 | gpt-4o-mini | absent | Katharine Ross | Insufficient information. | 0 | Katharine Ross | 1 |
| 2hop__50068_494136 | gemma-4-31b-it | absent | Meg Ryan | Insufficient information. | 0 | Meg Ryan | 1 |
| 2hop__504464_708278 | gemma-4-31b-it | present | Harold Stanley | Morgan Stanley | 0 | Harold Stanley | 1 |
| 2hop__51760_602275 | gemma-4-31b-it | present | Hans Albert Einstein | Insufficient information. | 0 | Hans Albert Einstein | 1 |
| 2hop__520033_123956 | gemma-4-31b-it | present | 15 February 1942 | Insufficient information. | 0 | 15 February 1942 | 1 |
| 2hop__528263_865831 | gemma-4-31b-it | present | Randall County | Insufficient information. | 0 | Randall County | 1 |
| 2hop__55032_786853 | gpt-4o-mini | absent | Amy Poehler | Insufficient information. | 0 | Amy Poehler | 1 |
| 2hop__551235_310309 | gemma-4-31b-it | present | Edwin Landseer Lutyens | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__554145_88622 | gemma-4-31b-it | absent | ADM Michael S. Rogers | ADM Michael S. Rogers USN | 0 | ADM Michael S. Rogers USN | 0 |
| 2hop__619265_45326 | gemma-4-31b-it | present | 12 | Insufficient information. | 0 | 12 | 1 |
| 2hop__639445_567836 | gemma-4-31b-it | present | Adams County | Insufficient information. | 0 | Adams County | 1 |
| 2hop__64537_482364 | gemma-4-31b-it | absent | Aeson | Insufficient information. | 0 | Aeson | 1 |
| 2hop__655505_110949 | gemma-4-31b-it | present | 11 September 1962 | Insufficient information. | 0 | 11 September 1962 | 1 |
| 2hop__673655_316668 | gpt-4o-mini | present | conga | Insufficient information. | 0 | Conga | 1 |
| 2hop__677160_110882 | gemma-4-31b-it | present | 1 January 1986 | Insufficient information. | 0 | 1 January 1986 | 1 |
| 2hop__693444_220151 | gemma-4-31b-it | present | Joan Erikson | Insufficient information. | 0 | Joan Erikson | 1 |
| 2hop__71294_494136 | gpt-4o-mini | absent | Meg Ryan | Insufficient information. | 0 | Meg Ryan | 1 |
| 2hop__723404_58556 | gemma-4-31b-it | partial | Food Safety Modernization Act (FSMA) | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__734582_71302 | gemma-4-31b-it | present | Vito Corleone | Insufficient information. | 0 | Vito Corleone | 1 |
| 2hop__765678_310556 | gemma-4-31b-it | present | John Profumo | Insufficient information. | 0 | John Profumo | 1 |
| 2hop__788306_131879 | gemma-4-31b-it | present | River Great Ouse | Insufficient information. | 0 | Insufficient information. | 0 |
| 2hop__804417_126089 | gemma-4-31b-it | present | Johan Remkes | Insufficient information. | 0 | Johan Remkes | 1 |
| 2hop__810884_22402 | gemma-4-31b-it | present | nearly 25,000 | Insufficient information. | 0 | Nearly 25,000 students. | 0 |
| 2hop__88834_425488 | gemma-4-31b-it | present | Terri Irwin | Insufficient information. | 0 | Terri Irwin | 1 |
| 2hop__94507_654855 | gemma-4-31b-it | present | Socialist Party of America | Eugene V. Debs (the person the novel is based on) is as | 0 | Socialist Party of America | 1 |
| 2hop__95970_456836 | gemma-4-31b-it | present | La Goulette | Insufficient information. | 0 | La Goulette | 1 |
| 2hop__96411_47902 | gemma-4-31b-it | partial | Matt Damon | Insufficient information. | 0 | Insufficient information. | 0 |
| 3hop1__127716_157828_239539 | gpt-4o-mini | absent | Pristina | Belgrade, Serbia | 0 | Pristina | 1 |
| 3hop1__127837_157828_239539 | gpt-4o-mini | absent | Pristina | Insufficient information. | 0 | Pristina | 1 |
| 3hop1__274148_792411_51423 | qwen3-235b-a22b-2507 | present | Casa Loma | Insufficient information. | 0 | Insufficient information. | 0 |
| 3hop1__389761_567566_84283 | gpt-4o-mini | present | Warner Music Group | Warner Bros. Records owns the record label of the Anoth | 0 | Warner Music Group owns Warner Bros. Records, the label | 0 |
| 3hop1__454441_55349_651302 | gemma-4-31b-it | absent | Denver | Insufficient information. | 0 | Denver, Colorado | 0 |
| 3hop1__462125_538202_84283 | gemma-4-31b-it | partial | Warner Music Group | Insufficient information. | 0 | Insufficient information. | 0 |
| 3hop1__506062_792411_51423 | gemma-4-31b-it | present | Casa Loma | Insufficient information. | 0 | Insufficient information. | 0 |
| 3hop1__593288_720914_41132 | gpt-4o-mini | present | 22 | Insufficient information. | 0 | 22 times. | 0 |
| 3hop1__637555_339990_15538 | gemma-4-31b-it | absent | 1984 | Insufficient information. | 0 | 1984 | 1 |
| 3hop1__662618_339990_54675 | gemma-4-31b-it | present | Tualatin Mountains | Insufficient information. | 0 | Insufficient information. | 0 |
| 3hop1__702699_792411_51423 | gpt-4o-mini | absent | Casa Loma | Insufficient information. | 0 | Casa Loma | 1 |
| 3hop1__715607_792411_51423 | gemma-4-31b-it | partial | Casa Loma | Insufficient information. | 0 | Insufficient information. | 0 |
| 4hop1__28352_53706_795904_580996 | gpt-4o-mini | absent | Rio Linda | Insufficient information. | 0 | Insufficient information. | 0 |
| 4hop1__3496_5274_458768_33637 | gemma-4-31b-it | present | two | Insufficient information. | 0 | 2 | 0 |
| 4hop1__37608_32392_823060_610794 | gemma-4-31b-it | absent | Richland County | Insufficient information. | 0 | Richland County | 1 |
| 4hop1__473563_309800_355213_203322 | qwen3-235b-a22b-2507 | partial | Cabarrus County | Lake County, Geauga County, Summit County, and Medina C | 0 | Lake County, Geauga County, Summit County, and Medina C | 0 |
| 4hop1__58323_375563_161848_44231 | gemma-4-31b-it | absent | Michael Joseph Savage | Insufficient information. | 0 | Michael Joseph Savage | 1 |
| 4hop1__89632_32392_823060_610794 | qwen3-235b-a22b-2507 | absent | Richland County | United States | 0 | United States | 0 |
| 4hop2__9988_158985_70784_61381 | gemma-4-31b-it | present | 1932 | Insufficient information. | 0 | Insufficient information. | 0 |
| 4hop3__131775_29339_508306_70744 | gemma-4-31b-it | present | University of South Carolina | Clemson University | 0 | University of South Carolina | 1 |
| 4hop3__661103_698586_91248_54362 | gpt-4o-mini | absent | Confederate Gen. John Bell Hood | Gen. John Bell Hood burned down Atlanta. | 0 | Gen. John Bell Hood burned down Atlanta, where Shawty L | 0 |

## Reading

The insert arm is the board answerer with the fact guaranteed. The difference from the extraction-fix repair arm is the cost of re-extraction and the R2 gate. On the 20 absent instances it is only an oracle bound; those cases stay recorded as misdiagnosed.
