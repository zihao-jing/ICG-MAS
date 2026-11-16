# Expansion Stage 1: screening pilot

Instances: 200 unused MuSiQue dev instances x 3 models = 600 planned traces. Manifest `31c5916bc8a443cadda7a040c13e766832191bd1432842913c0267aa2546e639`. Frozen 2026-11-12; no repair arm run.

Matcher records: 600; scored ok: 597; transport failures: 3 (APIConnectionError=2, APITimeoutError=1); wrong: 366; extraction-omission candidates: 43; R3/R4 clean: 11.

## Yield

| model | scored | wrong | candidates | candidate rate | clean |
| --- | ---: | ---: | ---: | ---: | ---: |
| gemma31b | 198 | 131 | 25 | 12.6% | 6 |
| gpt4omini | 199 | 120 | 16 | 8.0% | 5 |
| qwen235b | 200 | 115 | 2 | 1.0% | 0 |
| **all** | **597** | **366** | **43** | **7.2%** | **11** |

- Candidate rate: **7.2%** (stop threshold 6%).
- Clean yield among candidates: **25.6%** (stop threshold 10%).
- Clean per screened trace: **1.84%** (the plan's central estimate was 1.90%).
- Decision: **continue to Stage 2 review**.

## Cost

| item | USD |
| --- | ---: |
| relay gemma31b | 0.1810 |
| relay gpt4omini | 0.1850 |
| relay qwen235b | 0.2234 |
| matcher | 0.4577 |
| **total** | **1.0471** |

Per-pilot cap $5.00; phase budget $100.00. Every relay call is in `api_responses.jsonl` under `relay_<model>/`; every matcher call is in `calls.jsonl` under `rebuttal/results/batch1/expansion_stage1/`.

## Candidates

| instance | model | gold | missing | candidate fact | R3 | R4 |
| --- | --- | --- | ---: | --- | --- | --- |
| 2hop__414193_176917 | gemma31b | Dougray Scott | 1 | Dougray Scott is married to Claire Forlani. | pass | pass |
| 4hop1__436202_378185_282674_759393 | gemma31b | Green Bay | 3 | Appleton, Wisconsin is located in Outagamie County. | fail | fail |
| 3hop1__127821_157828_239539 | gemma31b | Pristina | 1 | Media in Pristina is located in the capital city of Kosovo. | pass | pass |
| 3hop2__304722_397371_63959 | gemma31b | 1 December 2010 | 4 | Birmingham City beat Aston Villa 3–1 in the League Cup Final 1st leg on 23 May 1963. | fail | fail |
| 4hop1__58323_375563_161848_53331 | gemma31b | 1989 | 1 | New Zealand is near Australia. | pass | fail |
| 4hop1__89530_624859_355213_203322 | gemma31b | Cabarrus County | 1 | Gold Hill is a community in Rowan County, North Carolina, near the Cabarrus County line. | pass | fail |
| 2hop__170914_152093 | gemma31b | Fair Trade Services | 1 | Hawk Nelson signed with Fair Trade Services on December 11, 2012. | pass | pass |
| 3hop1__136129_87694_124169 | gemma31b | 1952 | 1 | Mantua Cathedral is dedicated to Saint Peter. | pass | fail |
| 2hop__475808_74481 | gemma31b | Vito Corleone | 1 | The producer of Mistress is Robert De Niro. | pass | fail |
| 2hop__619265_72380 | gemma31b | June 20, 2016 | 1 | Episode 37 "Girl with Guitar" of "Ray Donovan" aired online on June 20, 2016, and on Showtime on June 26, 2016 | pass | pass |
| 3hop1__671542_651917_47686 | gemma31b | Toronto Coach Terminal | 1 | Kevin Drew was born in Toronto, Ontario, Canada. | pass | fail |
| 2hop__82378_158266 | gemma31b | The Australian Ballet | 1 | The Australian Ballet is the top ballet company in Australia. | pass | pass |
| 3hop1__801799_547811_80702 | gemma31b | Rialto Bridge | 1 | Antonio Vivaldi was born in Venice, Italy. | pass | fail |
| 4hop1__726391_153080_159767_81096 | gemma31b | Mario Andretti | 1 | The Desert Diamond West Valley Phoenix Grand Prix is an IndyCar race held in Phoenix, Arizona. | pass | fail |
| 2hop__703493_162341 | gemma31b | nominated for an Academy Award for Best Supporting Actor | 1 | Jack Goes Boating premiered at the 26th Sundance Film Festival. | pass | fail |
| 2hop__815205_590407 | gemma31b | Bethesda | 2 | The National Human Genome Research Institute is located at the NIH main campus in Bethesda, MD. | fail | pass |
| 2hop__152229_604644 | gemma31b | 429 Records | 1 | Magic is the seventh studio album by Smash Mouth, released on September 4, 2012 through 429 Records. | pass | pass |
| 3hop1__108833_720914_27537 | gemma31b | for the conclave in Rome | 3 | Titian died in Venice. | fail | fail |
| 4hop1__199881_765799_282674_759393 | gemma31b | Green Bay | 2 | Appleton, Wisconsin is located in Outagamie County. | fail | fail |
| 4hop1__199881_378185_282674_759393 | gemma31b | Green Bay | 3 | Appleton, Wisconsin is located in Outagamie County. | fail | fail |
| 3hop1__145427_106426_157788 | gemma31b | Yamanote Line loop | 2 | Shanghai is in China. | fail | fail |
| 2hop__359312_18803 | gemma31b | trying to find a potential buyer for all of its operations in Finland | 2 | Royal Dutch Shell announced in April 2010 that it was in the process of trying to find a potential buyer for a | fail | pass |
| 3hop2__65854_88342_58657 | gemma31b | Cleveland Indians | 1 | The Chicago Cubs won the National League championship in the 2016 World Series. | pass | fail |
| 3hop1__354480_834494_33939 | gemma31b | 7,531 | 2 | Pima County, Arizona contains the city of Tucson. | fail | fail |
| 2hop__299142_347613 | gemma31b | Svante Stensson Sture | 3 | Sigrid Sture was the granddaughter of Christina Gyllenstierna. | fail | fail |
| 2hop__747758_58067 | gpt4omini | A.P.J. Abdul Kalam | 1 | A. P. J. Abdul Kalam was the 11th President of India. | pass | pass |
| 2hop__20433_157939 | gpt4omini | 1986 | 1 | Howard the Duck was created in 1973. | pass | fail |
| 4hop1__57467_53706_795904_580996 | gpt4omini | Rio Linda | 2 | Sacramento is located in California. | fail | fail |
| 3hop1__145427_106426_157788 | gpt4omini | Yamanote Line loop | 2 | Shanghai is in China. | fail | fail |
| 3hop1__491648_339990_54675 | gpt4omini | Tualatin Mountains | 1 | Mt. Adams and Mt. Rainier can also be seen from Portland on clear days. | pass | fail |
| 4hop3__220945_88460_30152_20999 | gpt4omini | The dynasty regrouped and defeated the Portuguese | 2 | The Ajuran Empire employed a new coinage following the Ottoman pattern to proclaim economic independence from  | fail | fail |
| 2hop__713299_55227 | gpt4omini | Maria Bello | 1 | Salma Hayek co-stars in the movie Here Comes the Boom. | pass | fail |
| 4hop1__344155_378185_282674_759393 | gpt4omini | Green Bay | 3 | Appleton, Minnesota is in Cottonwood County, Minnesota. | fail | fail |
| 3hop1__671542_651917_47686 | gpt4omini | Toronto Coach Terminal | 1 | Greyhound Canada operates out of the Toronto Coach Terminal. | pass | pass |
| 4hop1__161810_583746_457883_650651 | gpt4omini | NBC | 1 | The Biggest Loser Brunei is produced by the same network that created the NBC version. | pass | pass |
| 2hop__414193_176917 | gpt4omini | Dougray Scott | 1 | Dougray Scott is married to Claire Forlani. | pass | pass |
| 3hop2__132957_379231_40768 | gpt4omini | 1981 | 2 | The 1973 oil crisis occurred in 1973. | fail | fail |
| 2hop__32441_178460 | gpt4omini | Robert Roosevelt | 3 | Cornelius Roosevelt was the father of Theodore Roosevelt, Sr. and the paternal grandfather of President Theodo | fail | fail |
| 4hop1__58323_375563_161848_53331 | gpt4omini | 1989 | 1 | New Zealand is near Australia. | pass | fail |
| 3hop1__507961_160713_77246 | gpt4omini | the country of India | 1 | The Arabic term Al-Hind referred to the country of India. | pass | fail |
| 2hop__86689_728109 | gpt4omini | Oklahoma City Thunder | 1 | James Harden was drafted by the Oklahoma City Thunder. | pass | pass |
| 3hop1__104996_160713_77246 | qwen235b | the country of India | 1 | The majority religion in the area that became India is Hinduism. | pass | fail |
| 2hop__34594_160249 | qwen235b | 323–272 BC | 1 | The Battle of Beneventum, where Pyrrhus met the Roman army again, occurred in 275 BC. | pass | fail |

## Spot-check of the clean candidates

All 11 clean candidates were read against the question, gold, board and fact. Each fact either states the gold entity or value, or supplies the missing link between the question chain and a board unit that states the gold. None relies on the fact vouching for itself, and none is a board-only case (R4 rejects those). One instance, `2hop__414193_176917`, contributes two traces (gemma31b and gpt4omini) with the same fact; the other nine are distinct instances. The two long facts (`2hop__619265_72380`, `2hop__152229_604644`) contain the exact gold date and label with no rounding or negation.

R3/R4 are the zero-call lexical gates from `src/audit/e4_fix_gates.py`. R2 delivery is applied when a repair is delivered, not at screening. The conservative clean yield counts only candidates whose matcher fact passes R4; the central yield in the plan also counted two manual source-context rebuilds, which screening cannot produce.

