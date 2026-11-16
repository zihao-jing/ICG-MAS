# Sub-claim presence rule B: 20-case pilot

Rule `SUB_CLAIM_RULE.md` (sha256 `4913c15a30c8`), prompt `subclaim_prompt.json` (sha256 `415acd95d262`). Claude Haiku 5.5, temperature 0. 20 saved MuSiQue checkpoint cases (10 where A says complete, 10 where A does not; distinct instances), 53 facts. Spend **$0.027465**, cap $5.00. Stage: relay checkpoints (extraction pool / shared board).

Price per case **$0.001373**; full-run estimate for 2,100 rows at this price **$2.88** (not run; needs approval).

| measure | count |
| --- | ---: |
| facts labelled present by B | 3 |
| facts partial by B | 38 |
| facts absent by B | 12 |
| facts A carried (present/partial) | 43 |
| atomic sub-claims split | 350 |
| sub-claims listed missing | 195 |

| key | A complete | A statuses | B statuses | sub-claims | missing |
| --- | --- | --- | --- | ---: | ---: |
| `mistrals|results/run_musique_mistrals|random_relay|2hop__31085_23241|board` | 0 | f1:present, f2:absent | f1:partial, f2:absent | 18 | 5 |
| `mistrals|results/run_musique_mistrals|random_relay|3hop2__132957_433432_40768|board` | 0 | f1:absent, f2:present, f3:present | f1:absent, f2:partial, f3:partial | 23 | 11 |
| `mistrals|results/run_musique_mistrals|redundancy_aware_relay|2hop__525581_161450|extraction` | 1 | f1:present, f2:present | f1:partial, f2:partial | 11 | 5 |
| `mistrals|results/run_musique_mistrals|redundancy_aware_relay|3hop1__404541_629431_124169|extraction` | 0 | f1:present, f2:absent, f3:present | f1:partial, f2:absent, f3:partial | 16 | 12 |
| `mistrals|results/run_musique_mistrals|redundancy_aware_relay|3hop1__64957_87694_64412|board` | 0 | f1:present, f2:present, f3:absent | f1:partial, f2:partial, f3:absent | 14 | 6 |
| `mistrals|results/run_musique_mistrals|redundancy_aware_relay|4hop1__814349_624859_355213_203322|board` | 0 | f1:present, f2:present, f3:present, f4:absent | f1:present, f2:present, f3:partial, f4:absent | 27 | 4 |
| `mistrals|results/run_musique_mistrals|score_ranked_relay|2hop__511454_120259|board` | 0 | f1:absent, f2:partial | f1:absent, f2:partial | 8 | 7 |
| `mistrals|results/run_musique_mistrals|score_ranked_relay|2hop__71755_463572|board` | 1 | f1:present, f2:present | f1:partial, f2:partial | 18 | 13 |
| `mistrals|results/run_musique_mistrals|summary_exchange|3hop1__786067_228453_86925|board` | 0 | f1:absent, f2:present, f3:present | f1:absent, f2:partial, f3:partial | 21 | 13 |
| `qwen235b|results/run_qwen235b_musique|redundancy_aware_relay|3hop1__640171_228453_86925|extraction` | 0 | f1:present, f2:present, f3:absent | f1:partial, f2:present, f3:absent | 21 | 6 |
| `qwen235b|results/run_qwen235b_musique|redundancy_aware_relay|3hop1__818422_160545_34751|extraction` | 0 | f1:absent, f2:present, f3:present | f1:absent, f2:partial, f3:partial | 12 | 10 |
| `qwen235b|results/run_qwen235b_musique|score_ranked_relay|2hop__60001_512508|board` | 1 | f1:present, f2:partial | f1:partial, f2:partial | 14 | 4 |
| `qwen235b|results/run_qwen235b_musique|summary_exchange|3hop1__106042_64399_59680|board` | 1 | f1:present, f2:present, f3:partial | f1:partial, f2:partial, f3:partial | 18 | 14 |
| `qwen36f|results/run_musique_100|random_relay|2hop__6956_192417|board` | 0 | f1:absent, f2:present | f1:absent, f2:partial | 12 | 7 |
| `qwen36f|results/run_musique_100|random_relay|3hop2__103871_20335_9331|extraction` | 1 | f1:present, f2:present, f3:present | f1:partial, f2:partial, f3:partial | 22 | 11 |
| `qwen36f|results/run_musique_100|redundancy_aware_relay|3hop1__49236_89752_49923|board` | 1 | f1:present, f2:present, f3:present | f1:partial, f2:partial, f3:partial | 22 | 18 |
| `qwen36f|results/run_musique_100|score_ranked_relay|2hop__488811_30113|extraction` | 1 | f1:partial, f2:present | f1:absent, f2:partial | 12 | 6 |
| `qwen36f|results/run_musique_100|score_ranked_relay|4hop2__71753_685934_70784_61381|extraction` | 1 | f1:present, f2:present, f3:partial, f4:present | f1:partial, f2:partial, f3:partial, f4:partial | 34 | 23 |
| `qwen36f|results/run_musique_100|summary_exchange|2hop__119423_779396|board` | 1 | f1:present, f2:partial | f1:partial, f2:absent | 10 | 9 |
| `qwen36f|results/run_musique_100|summary_exchange|2hop__284789_52835|board` | 1 | f1:partial, f2:present | f1:partial, f2:partial | 17 | 11 |

## Examples of sub-claims B finds missing while A credits the fact

- `mistrals|results/run_musique_mistrals|random_relay|2hop__31085_23241|board` / f1: A=present, B=partial; missing: CIA 2001 World Factbook figures (50% Muslim, 40% Christian, 10% local religions); Association of Religion Data Archives census figures (46.5% Christian, 45.5% Muslim, 7.7% other); Attribution of the 'religion and public life' report title
- `mistrals|results/run_musique_mistrals|random_relay|3hop2__132957_433432_40768|board` / f2: A=present, B=partial; missing: Markets of sale (U.S., Canada, China); Sedan and coupe size classifications; First flagship sedan under Acura; 1996 renaming to 3.5RL; KA9 series link
- `mistrals|results/run_musique_mistrals|random_relay|3hop2__132957_433432_40768|board` / f3: A=present, B=partial; missing: Larger-car introductions and their amenities; Explicit effect of the 1981 voluntary export restraints (entry says only the opening came after them); Purpose of luxury divisions: distinguishing from mass-market brands
- `mistrals|results/run_musique_mistrals|redundancy_aware_relay|2hop__525581_161450|extraction` / f1: A=present, B=partial; missing: 2006 census population of 109,440; 22,804 families in 2006 census; Two districts: Voshmgir District and Central District; Two cities: Anbar Olum and Aqqala
- `mistrals|results/run_musique_mistrals|redundancy_aware_relay|2hop__525581_161450|extraction` / f2: A=present, B=partial; missing: Persian name استان گلستان / Ostān-e Golestān
- `mistrals|results/run_musique_mistrals|redundancy_aware_relay|3hop1__404541_629431_124169|extraction` / f1: A=present, B=partial; missing: Paenitentiam agere calls on Christians to practice penance; Paenitentiam agere considers the upcoming Second Vatican Council
- `mistrals|results/run_musique_mistrals|redundancy_aware_relay|3hop1__404541_629431_124169|extraction` / f3: A=present, B=partial; missing: No successor was appointed to the post; The post was not mentioned in the Fundamental Law of Vatican City State issued by Pope John Paul II on 26 November 2000; The Fundamental Law entered into force on 22 February 2001
- `mistrals|results/run_musique_mistrals|redundancy_aware_relay|3hop1__64957_87694_64412|board` / f1: A=present, B=partial; missing: Peter looks angry; Foreshadowing of Peter's violent reaction in Gethsemane

Pilot only: B is **not validated** against the stronger reference and is not a table column. A remains the validated label with the central-claim qualifier. The full run is not started; the estimate above is the decision input.

