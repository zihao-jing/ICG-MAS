# Expansion Stage 2: screening

Instances: 800 unused MuSiQue dev instances x 3 models = 2400 planned traces. Manifest `5663d338c7055760045ef91cdbb2cae5af1c6e7dcc2c83712aa3b11aee187c7d`; Stage 1 manifest `695a28cf4bf1fdd897c8037721b045c23b02b6aee441f3965108bc5d64b10004`. Frozen 2026-11-12; no repair arm run.

Matcher records: 2400; scored ok: 2400; transport failures: 0 (none); wrong: 1524; extraction-omission candidates: 216; R3/R4 clean: 69 (59 unique).

## Yield by model

| model | scored | wrong | candidates | candidate rate | clean | distortion | selection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma31b | 800 | 525 | 126 | 15.8% | 44 | 101 | 0 |
| gpt4omini | 800 | 516 | 57 | 7.1% | 16 | 40 | 3 |
| qwen235b | 800 | 483 | 33 | 4.1% | 9 | 35 | 3 |
| **all** | **2400** | **1524** | **216** | **9.0%** | **69** | **176** | **6** |

## Diagnoses

| diagnosis | traces | unique instances |
| --- | ---: | ---: |
| candidate_aggregation | 955 | 516 |
| correct_control | 875 | 439 |
| extraction_omission | 216 | 162 |
| distortion | 176 | 150 |
| partial | 167 | 145 |
| selection_omission | 6 | 6 |
| uncertain | 5 | 4 |

## Per-experiment clean counts

| experiment | Stage 2 alone | Stage 1 + Stage 2 | reaches 30? |
| --- | ---: | ---: | --- |
| Extraction | 69 traces / 59 unique | 80 traces / 69 unique | yes |
| Direct insertion | same cohort | same cohort | yes |
| Distortion, diagnosed | 176 traces / 150 unique | 214 traces / 184 unique | yes |
| Distortion, swaps at 1/4 yield | about 44 | about 46 | yes |

The distortion swap counts are the plan's quarter-yield estimate; swaps are generated separately by the labeller and must pass R6 before they count.

## Cost

| item | USD |
| --- | ---: |
| relay gemma31b | 0.7371 |
| relay gpt4omini | 0.7384 |
| relay qwen235b | 0.8870 |
| matcher shard_00 | 0.2314 |
| matcher shard_01 | 0.2379 |
| matcher shard_02 | 0.2321 |
| matcher shard_03 | 0.2351 |
| matcher shard_04 | 0.2400 |
| matcher shard_05 | 0.2515 |
| matcher shard_06 | 0.2410 |
| matcher shard_07 | 0.2372 |
| **total** | **4.2688** |

Per-pilot cap $5.00. Every relay call is in `api_responses.jsonl` under `relay_<model>/`; every matcher call is in each shard's `calls.jsonl` under `rebuttal/results/batch1/expansion_stage2/matcher_shard_*`.

## Clean extraction candidates

| instance | model | gold | missing | candidate fact | R3 | R4 |
| --- | --- | --- | ---: | --- | --- | --- |
| 2hop__520033_123956 | gemma31b | 15 February 1942 | 1 | The Battle of Palembang occurred on 13–15 February 1942. | pass | pass |
| 2hop__304852_758385 | gemma31b | Hubbard County | 1 | Park Rapids is located in Hubbard County, Minnesota. | pass | pass |
| 2hop__157285_556157 | gemma31b | Limpopo River | 1 | The Mzingwane River is a tributary of the Limpopo River. | pass | pass |
| 2hop__804417_126089 | gemma31b | Johan Remkes | 1 | The King's Commissioner of North Holland is Johan Remkes, serving since 2010. | pass | pass |
| 4hop2__9988_158985_70784_61381 | gemma31b | 1932 | 1 | Saudi Arabia borders the Persian Gulf. | pass | pass |
| 2hop__96411_47902 | gemma31b | Matt Damon | 1 | Matt Damon plays Jason Bourne in the Bourne film series. | pass | pass |
| 2hop__88834_425488 | gemma31b | Terri Irwin | 1 | Bindi Irwin is the daughter of Terri Irwin. | pass | pass |
| 3hop1__454441_55349_651302 | gemma31b | Denver | 1 | Trey Parker was born in Denver, Colorado. | pass | pass |
| 2hop__639445_567836 | gemma31b | Adams County | 1 | Hastings is the county seat of Adams County, Nebraska. | pass | pass |
| 3hop1__637555_339990_15538 | gemma31b | 1984 | 1 | New York reinstated the death penalty in 1984. | pass | pass |
| 2hop__677160_110882 | gemma31b | 1 January 1986 | 1 | James Cottriall was born on 1 January 1986. | pass | pass |
| 2hop__50068_494136 | gemma31b | Meg Ryan | 1 | Dennis Quaid is married to Meg Ryan. | pass | pass |
| 2hop__128342_375952 | gemma31b | Santa Barbara County | 1 | Los Alamos, New Mexico is located in Los Alamos County. | pass | pass |
| 2hop__207597_73244 | gemma31b | Thaba Putsoa | 1 | The source of the Orange River is at Thaba Putsoa in the Maloti Mountains (Drakensberg), Lesotho. | pass | pass |
| 4hop1__37608_32392_823060_610794 | gemma31b | Richland County | 1 | Forest Acres shares a border with Columbia, South Carolina. | pass | pass |
| 2hop__765678_310556 | gemma31b | John Profumo | 1 | John Profumo was married to actress Valerie Hobson. | pass | pass |
| 2hop__551235_310309 | gemma31b | Edwin Landseer Lutyens | 1 | Sir Edwin Landseer Lutyens was an English architect born on 29 March 1869. | pass | pass |
| 2hop__64537_482364 | gemma31b | Aeson | 1 | Aeson is the father of Jason. | pass | pass |
| 2hop__693444_220151 | gemma31b | Joan Erikson | 1 | Erik Erikson collaborated with Joan Erikson on his stages of psychosocial development. | pass | pass |
| 2hop__342746_679190 | gemma31b | Garson Kanin | 1 | Ruth Gordon was married to Garson Kanin. | pass | pass |
| 2hop__734582_71302 | gemma31b | Vito Corleone | 1 | Robert De Niro played Vito Corleone in The Godfather Part II. | pass | pass |
| 2hop__655505_110949 | gemma31b | 11 September 1962 | 1 | Mauro Scocco was born on 11 September 1962. | pass | pass |
| 2hop__504464_708278 | gemma31b | Harold Stanley | 1 | Morgan Stanley was co-founded by Harold Stanley in 1935. | pass | pass |
| 2hop__123148_5385 | gemma31b | 11,900 | 1 | The University of Oklahoma employs 11,900 people. | pass | pass |
| 2hop__95970_456836 | gemma31b | La Goulette | 1 | Claudia Cardinale is a native of La Goulette. | pass | pass |
| 2hop__435184_84856 | gemma31b | January 20, 2017 | 1 | The new season of Real Time with Bill Maher starts on January 20, 2017. | pass | pass |
| 2hop__619265_45326 | gemma31b | 12 | 1 | Season 5 of "Ray Donovan" has 12 episodes. | pass | pass |
| 2hop__810884_22402 | gemma31b | nearly 25,000 | 1 | The University of Zurich has nearly 25,000 students. | pass | pass |
| 3hop1__506062_792411_51423 | gemma31b | Casa Loma | 1 | Toronto is in Canada. | pass | pass |
| 2hop__788306_131879 | gemma31b | River Great Ouse | 1 | Buckingham has evidence of Roman settlement near the River Great Ouse. | pass | pass |
| 2hop__554145_88622 | gemma31b | ADM Michael S. Rogers | 1 | The head of the National Security Agency is the Director of the NSA. | pass | pass |
| 2hop__242753_658778 | gemma31b | Vienna Secession | 1 | Gustav Klimt is a member of the Vienna Secession movement. | pass | pass |
| 3hop1__662618_339990_54675 | gemma31b | Tualatin Mountains | 1 | The Cascade Range is east of the Tualatin Mountains near Portland, Oregon. | pass | pass |
| 4hop3__131775_29339_508306_70744 | gemma31b | University of South Carolina | 1 | University of South Carolina has 10 national championships. | pass | pass |
| 3hop1__715607_792411_51423 | gemma31b | Casa Loma | 1 | Toronto is a city in Canada. | pass | pass |
| 2hop__528263_865831 | gemma31b | Randall County | 1 | Canyon is a city in Randall County, Texas. | pass | pass |
| 2hop__723404_58556 | gemma31b | Food Safety Modernization Act (FSMA) | 1 | The FDA has a food safety system known as the Food Safety Modernization Act (FSMA). | pass | pass |
| 2hop__46213_494136 | gemma31b | Meg Ryan | 1 | Dennis Quaid is married to Meg Ryan in the film Flesh and Bone. | pass | pass |
| 2hop__51760_602275 | gemma31b | Hans Albert Einstein | 1 | Hans Albert Einstein was the son of Albert Einstein. | pass | pass |
| 4hop1__3496_5274_458768_33637 | gemma31b | two | 1 | The two ethnic minorities who were viewed differently are Japanese and Chinese. | pass | pass |
| 2hop__323534_810083 | gemma31b | Scranton | 1 | Tom Flannery was born in Scranton, Pennsylvania, United States. | pass | pass |
| 2hop__94507_654855 | gemma31b | Socialist Party of America | 1 | Eugene V. Debs was a member of the Socialist Party of America. | pass | pass |
| 3hop1__462125_538202_84283 | gemma31b | Warner Music Group | 1 | Mercury Nashville Records is a record label. | pass | pass |
| 4hop1__58323_375563_161848_44231 | gemma31b | Michael Joseph Savage | 1 | Australia is near New Zealand. | pass | pass |
| 4hop1__28352_53706_795904_580996 | gpt4omini | Rio Linda | 1 | Sacramento, California shares a border with Rio Linda. | pass | pass |
| 3hop1__389761_567566_84283 | gpt4omini | Warner Music Group | 1 | Warner Music Group owns Warner Bros. Records. | pass | pass |
| 3hop1__593288_720914_41132 | gpt4omini | 22 | 1 | Plague occurred in Venice 22 times between 1361 and 1528. | pass | pass |
| 2hop__71294_494136 | gpt4omini | Meg Ryan | 1 | Meg Ryan is the spouse of Dennis Quaid. | pass | pass |
| 3hop1__462125_538202_84283 | gpt4omini | Warner Music Group | 1 | Mercury Nashville Records is a record label. | pass | pass |
| 4hop3__661103_698586_91248_54362 | gpt4omini | Confederate Gen. John Bell Hood | 1 | Shawty Lo died in a car accident in Atlanta on September 21, 2016. | pass | pass |
| 2hop__342746_679190 | gpt4omini | Garson Kanin | 1 | Ruth Gordon and Garson Kanin were spouses. | pass | pass |
| 2hop__673655_316668 | gpt4omini | conga | 1 | Ray Barretto played conga on the album Midnight Blue. | pass | pass |
| 2hop__25396_212301 | gpt4omini | Arthur Peel | 1 | Sidney Peel was the youngest son of Prime Minister Sir Robert Peel. | pass | pass |
| 2hop__128342_375952 | gpt4omini | Santa Barbara County | 1 | Los Alamos, New Mexico is located in Los Alamos County. | pass | pass |
| 3hop1__702699_792411_51423 | gpt4omini | Casa Loma | 1 | Toronto is the birth city of Jane Siberry. | pass | pass |
| 2hop__47808_198548 | gpt4omini | Katharine Ross | 1 | Katharine Ross is the wife of Sam Elliott. | pass | pass |
| 2hop__55032_786853 | gpt4omini | Amy Poehler | 1 | The spouse of Will Arnett is Amy Poehler. | pass | pass |
| 2hop__50068_494136 | gpt4omini | Meg Ryan | 1 | Dennis Quaid is married to Meg Ryan. | pass | pass |
| 3hop1__127837_157828_239539 | gpt4omini | Pristina | 1 | The Radio Television of Kosovo has its headquarters in Pristina. | pass | pass |
| 3hop1__127716_157828_239539 | gpt4omini | Pristina | 1 | The Radio Television of Kosovo is headquartered in Pristina. | pass | pass |
| 3hop1__274148_792411_51423 | qwen235b | Casa Loma | 1 | Casa Loma is a historic house museum and landmark located in Toronto, Ontario, Canada. | pass | pass |
| 3hop1__454441_55349_651302 | qwen235b | Denver | 1 | Trey Parker was born in Denver, Colorado. | pass | pass |
| 4hop1__473563_309800_355213_203322 | qwen235b | Cabarrus County | 1 | Rowan County shares a border with Cabarrus County. | pass | pass |
| 4hop1__89632_32392_823060_610794 | qwen235b | Richland County | 1 | The city sharing a border with the state capital of the US state where The Patriot was filmed is Forest Acres. | pass | pass |
| 3hop1__127837_157828_239539 | qwen235b | Pristina | 1 | The headquarters of Radio Television of Kosovo is in Pristina. | pass | pass |
| 2hop__50068_494136 | qwen235b | Meg Ryan | 1 | Dennis Quaid is married to Meg Ryan. | pass | pass |
| 4hop1__58323_375563_161848_44231 | qwen235b | Michael Joseph Savage | 1 | Australia is near New Zealand. | pass | pass |
| 3hop1__715607_792411_51423 | qwen235b | Casa Loma | 1 | Toronto is a city in Canada. | pass | pass |
| 2hop__435184_84856 | qwen235b | January 20, 2017 | 1 | The new season of Real Time with Bill Maher starts on January 20, 2017. | pass | pass |

## Distortion cases for swap generation

176 diagnosed traces, 150 unique instances. The case list with source text is in `distortion_cases.jsonl`.

## Qwen

Qwen stays in the pool pending review of its per-model yield above (9 clean, 35 distortion diagnoses).

