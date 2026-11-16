# Injected distortion: pilot report

Rule: `INJECTED_DISTORTION_RULE_V2.md`. All cases are **injected distortions**: one faithful board unit was corrupted in place with a same-type, same-length wrong value, confirmed by the frozen labeller; the control is a volume-matched faithful rewrite, also labeller-confirmed. This is not observed distortion and not a constructed substitution.

Accepted 30 cases from the Stage 2 pool; 35 candidate attempts rejected. Spend $0.185914 against the cap. This is the approved ≥30-case set (30 cases).

## Exact answers by arm

| arm | exact | n | 95% CI |
| --- | ---: | ---: | --- |
| base (recorded, no call) | 30 | 30 | 0.884-1.000 |
| corrupt | 0 | 30 | 0.000-0.116 |
| control | 23 | 30 | 0.577-0.901 |
| repair | 24 | 30 | 0.614-0.923 |

Paired comparisons:

| pair | better | worse | same |
| --- | ---: | ---: | ---: |
| repair vs corrupt | 24 | 0 | 6 |
| control vs corrupt | 23 | 0 | 7 |
| repair vs control | 2 | 1 | 27 |

## Per case

| case | model | gold | original unit | corrupted unit | control unit | base | corrupt | control | repair |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 3hop1__275261_443779_52195 | gemma31b | Francisco Guterres | The President of the Democratic Republic of Timor-Leste | Xanana Gusmão holds the office of President of the Demo | Francisco Guterres holds the office of President of the | 1 | 0 | 1 | 1 |
| 3hop1__488744_443779_52195 | gemma31b | Francisco Guterres | The president of the Democratic Republic of Timor-Leste | Xanana Gusmão holds the presidency of the Democratic Re | Francisco Guterres holds the presidency of the Democrat | 1 | 0 | 1 | 1 |
| 3hop1__773623_87694_124169 | qwen235b | 1952 | Marchese Camillo Serafini served as Governor of Vatican | Until his death in 1948, Marchese Camillo Serafini held | Until his death in 1952, Marchese Camillo Serafini held | 1 | 0 | 1 | 1 |
| 2hop__84847_21969 | gpt4omini | 1786 | Warren Hastings was impeached in 1786 after years of ef | Edmund Burke pushed for years, and in 1792 Warren Hasti | Edmund Burke pushed for years, and in 1786 Warren Hasti | 1 | 0 | 1 | 1 |
| 2hop__446324_620302 | qwen235b | University of Toronto | Matt Cohen studied political economy at the University  | At the University of Cambridge, Matt Cohen pursued a co | At the University of Toronto, Matt Cohen pursued a cour | 1 | 0 | 1 | 1 |
| 2hop__804417_126089 | gpt4omini | Johan Remkes | The King's Commissioner of North Holland is Johan Remke | Serving since 2010, Harry Borghouts holds the post of K | Serving since 2010, Johan Remkes holds the post of King | 1 | 0 | 1 | 1 |
| 3hop1__64694_34179_23375 | qwen235b | 1948 | Stalin published "Falsifiers of History" in response to | In reaction to the U.S. State Department's release of N | In reaction to the U.S. State Department's release of N | 1 | 0 | 1 | 1 |
| 3hop1__617062_127905_80286 | gemma31b | Pete Rose | Pete Rose holds the Major League record for most career | With 4,256 career hits, Babe Ruth owns the Major League | With 4,256 career hits, Pete Rose owns the Major League | 1 | 0 | 1 | 1 |
| 3hop1__773623_87694_124169 | gpt4omini | 1952 | The post of Governor of Vatican City was held by Marche | Marchese Camillo Serafini served as Governor of Vatican | Marchese Camillo Serafini served as Governor of Vatican | 1 | 0 | 1 | 1 |
| 3hop1__254856_400692_51423 | gemma31b | Casa Loma | Casa Loma is a Gothic Revival style mansion and garden  | Located in midtown Toronto, Ontario, Canada, Spadina Ho | Located in midtown Toronto, Ontario, Canada, Casa Loma  | 1 | 0 | 0 | 0 |
| 2hop__734582_71302 | gpt4omini | Vito Corleone | Robert De Niro stars as Vito Corleone in The Godfather  | In The Godfather Part II, Snapper Foster is portrayed o | In The Godfather Part II, Vito Corleone is portrayed on | 1 | 0 | 1 | 1 |
| 2hop__814671_82341 | qwen235b | in Northern Florida | Ocala is a city located in Northern Florida. | Situated central Atlantic Ocean, the city of Ocala is f | Situated in Northern Florida, the city of Ocala is foun | 1 | 0 | 0 | 0 |
| 4hop1__429751_32392_823060_610794 | gemma31b | Richland County | Forest Acres is a city in Richland County, South Caroli | Forest Acres is a municipality located within Maricopa  | Forest Acres is a municipality located within Richland  | 1 | 0 | 0 | 0 |
| 4hop1__93963_170667_443779_52195 | gpt4omini | Francisco Guterres | The president of the Democratic Republic of Timor-Leste | Lana Wood holds the office of President of the Democrat | Francisco Guterres holds the office of President of the | 1 | 0 | 1 | 1 |
| 3hop1__488744_443779_52195 | gpt4omini | Francisco Guterres | The President of the Democratic Republic of Timor-Leste | Chris Harrison holds the presidency of the Democratic R | Francisco Guterres holds the presidency of the Democrat | 1 | 0 | 1 | 1 |
| 3hop1__144439_443779_52195 | qwen235b | Francisco Guterres | Francisco Guterres is the President of Timor-Leste. | Timor-Leste's President is George Benson. | Timor-Leste's President is Francisco Guterres. | 1 | 0 | 0 | 1 |
| 2hop__739909_807845 | gpt4omini | Digital First Media | Media News Group merged to become Digital First Media i | In December 2013, Media News Group combined with anothe | In December 2013, Media News Group combined with anothe | 1 | 0 | 1 | 1 |
| 4hop1__151903_5274_458768_33677 | gemma31b | 2013 | Santa Monica received the Bicycle Friendly Community Aw | The League of American Bicyclists granted Santa Monica  | The League of American Bicyclists granted Santa Monica  | 1 | 0 | 1 | 1 |
| 4hop1__606685_508773_85832_745702 | gemma31b | Sebastian Cabot | Sebastian Cabot was the son of Italian explorer John Ca | John Cabot (Giovanni Caboto), an Italian explorer, fath | John Cabot (Giovanni Caboto), an Italian explorer, fath | 1 | 0 | 1 | 0 |
| 3hop1__5544_34179_23375 | gpt4omini | 1948 | In 1948, Stalin published "Falsifiers of History" in re | Responding to the State Department's release of the sec | Responding to the State Department's release of the sec | 1 | 0 | 1 | 1 |
| 2hop__51074_75184 | gemma31b | Claudia Wells | Claudia Wells played the character of Marty's girlfrien | In Back to the Future, the part of Marty's girlfriend,  | In Back to the Future, the part of Marty's girlfriend,  | 1 | 0 | 1 | 1 |
| 3hop1__742780_567566_84283 | gemma31b | Warner Music Group | Warner Bros. Records' parent company is Warner Music Gr | The corporate owner of Warner Bros. Records is Qatar St | The corporate owner of Warner Bros. Records is Warner M | 1 | 0 | 1 | 1 |
| 2hop__17455_21567 | gpt4omini | John Kukuzelis | John Kukuzelis was a prominent reformer of Orthodox Chu | During the first half of the 14th century, Phil Hansero | During the first half of the 14th century, John Kukuzel | 1 | 0 | 1 | 1 |
| 3hop1__17192_78396_157843 | gpt4omini | 1853 | Lower Burma was annexed by the British in 1853 as a res | As a consequence of the Second Anglo-Burmese War, the B | As a consequence of the Second Anglo-Burmese War, the B | 1 | 0 | 0 | 1 |
| 2hop__6827_86319 | gemma31b | Brian Thomas Moynihan | Brian Thomas Moynihan is the chairman and CEO of Bank o | Bank of America is led by Katharina von Bora, who serve | Bank of America is led by Brian Thomas Moynihan, who se | 1 | 0 | 1 | 1 |
| 2hop__835710_7298 | qwen235b | Michael Bublé | Michael Bublé started out as an adult contemporary arti | Lech Wałęsa began his career as an artist within the ad | Michael Bublé began his career as an artist within the  | 1 | 0 | 1 | 1 |
| 2hop__95172_152907 | gpt4omini | La Goulette | Claudia Cardinale was born in La Goulette, a neighborho | On 15 April 1938, Claudia Cardinale came into the world | On 15 April 1938, Claudia Cardinale came into the world | 1 | 0 | 0 | 0 |
| 2hop__316374_82341 | gpt4omini | in Northern Florida | Ocala is a city located in Northern Florida. | Ocala is a city situated central Atlantic Ocean. | Ocala is a city situated in Northern Florida. | 1 | 0 | 0 | 0 |
| 2hop__373544_66723 | gemma31b | James Howard Meredith | James Howard Meredith became the first African-American | In 1962, the University of Mississippi welcomed its fir | In 1962, the University of Mississippi welcomed its fir | 1 | 0 | 1 | 1 |
| 2hop__15416_58040 | gpt4omini | Fort Davis | Fort Davis has the highest elevation above sea level of | Among all Texas county seats, Citrus Heights sits at th | Among all Texas county seats, Fort Davis sits at the gr | 1 | 0 | 1 | 1 |

## Cost by stage

- answer: $0.008740
- preview_class: $0.050222
- preview_classmatch: $0.006631
- preview_control: $0.100646
- preview_label: $0.019675

## Reading

A drop from base/repair to corrupt with the control near base is the injected-distortion effect. A corrupt answer that stays exact means the answerer did not use the corrupted unit.

One case (3hop1__254856_400692_51423, Casa Loma) refused ("Insufficient information") on all three arms, control and repair included, although its base answered correctly. Its corrupt failure is therefore an edit/volume effect on that trace, not evidence that the corruption changed the answer; read the arms on the other 29 cases for the injected-distortion effect.
