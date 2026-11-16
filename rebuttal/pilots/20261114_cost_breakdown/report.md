# Cost breakdown by model and experiment

Source: every cost-bearing record under `rebuttal/**/*.jsonl` (documented ledger rule; the two duplicate `swaps.jsonl` files excluded). Calls are logged call attempts, including retries and failed calls. Tokens are summed prompt/completion tokens where the record has them.

## Model totals

| Model | Calls | Prompt tokens | Completion tokens | USD | Provider-billed USD | Estimated USD | Failed calls | Records without tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Opus 5.5 | 2141 | 5,721,929 | 1,170,484 | 47.175332 | 0.000000 | 47.175332 | 157 | 157 |
| Gemini 3.6 Flash | 2122 | 3,801,859 | 3,028,358 | 14.213460 | 8.106683 | 6.106777 | 46 | 98 |
| Claude Haiku 5.5 | 16632 | 30,431,760 | 11,864,515 | 8.976068 | 0.000000 | 8.976068 | 12 | 12 |
| Qwen-235B | 9801 | 16,703,324 | 2,029,915 | 3.572858 | 3.507803 | 0.065055 | 0 | 18 |
| GPT-4o-mini | 2325 | 4,125,060 | 199,205 | 0.715859 | 0.648098 | 0.067761 | 0 | 4 |
| Gemma-4-31B | 2086 | 1,628,697 | 290,758 | 0.307992 | 0.189646 | 0.118345 | 0 | 10 |
| Mistral-S | 13 | 33,648 | 4,181 | 0.007740 | 0.007740 | 0.000000 | 0 | 0 |
| Unknown | 12 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 | 12 |

**Total: 74.969308 USD** over 35132 cost-bearing records. Provider-billed 12.459970; estimated from tokens 62.509338.

## Opus 5.5

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| Board strict fidelity, full run | 1677 | 4,940,117 | 999,770 | 39.755868 | estimate | 0 |
| Board strict fidelity, pilot | 150 | 481,874 | 105,317 | 4.033836 | estimate | 0 |
| Strict-fidelity label validation v10 | 314 | 299,938 | 65,397 | 3.385628 | estimate | 157 |

## Gemini 3.6 Flash

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| batch1/E2A_wave2_screening | 219 | 630,263 | 518,833 | 2.416948 | provider | 0 |
| batch1/E1_judge_sealed | 240 | 843,183 | 423,245 | 2.211274 | provider | 0 |
| Silo-Bench presence validation | 77 | 333,624 | 197,961 | 0.992572 | estimate | 4 |
| Strict-fidelity label validation v10 | 157 | 207,132 | 189,440 | 0.865749 | estimate | 0 |
| Sub-claim validation | 59 | 59,793 | 212,230 | 0.840707 | estimate | 0 |
| batch1/E4_phase2 | 105 | 77,257 | 202,684 | 0.818008 | provider | 0 |
| batch1/E2A_wave1_screening | 68 | 179,133 | 175,767 | 0.793476 | provider | 0 |
| Label validation v9 | 120 | 159,532 | 134,497 | 0.624013 | estimate | 0 |
| batch1/E1_judge_ledger_retry | 48 | 191,266 | 117,101 | 0.582578 | provider | 0 |
| Label validation v8 | 120 | 124,300 | 125,604 | 0.564240 | estimate | 0 |
| Label validation v7 | 120 | 85,962 | 127,589 | 0.542930 | estimate | 0 |
| E2-A technical pilot | 72 | 261,101 | 88,308 | 0.526981 | provider | 0 |
| Label validation v6 | 120 | 87,130 | 121,857 | 0.522311 | estimate | 0 |
| Per-fact labeller pilot/validation | 88 | 48,400 | 87,768 | 0.365430 | estimate | 0 |
| Who&When-style stage comparison | 91 | 101,241 | 57,596 | 0.293962 | estimate | 2 |
| Restore-the-source | 148 | 30,268 | 61,963 | 0.251439 | estimate | 0 |
| Placement redo | 160 | 76,424 | 40,239 | 0.226538 | estimate | 40 |
| E2-C technical pilot | 15 | 120,415 | 29,320 | 0.200261 | provider | 0 |
| E2-C card pilot (18 calls) | 9 | 74,003 | 24,129 | 0.145986 | provider | 0 |
| batch1/E2_stage1_judge | 12 | 35,847 | 29,187 | 0.134967 | provider | 0 |
| Judge pilot | 13 | 30,325 | 24,239 | 0.113640 | provider | 0 |
| batch1/E2A_stage2_gate_judge | 6 | 15,009 | 13,244 | 0.060922 | provider | 0 |
| E4-P technical pilot | 15 | 7,028 | 7,246 | 0.032444 | provider | 0 |
| Judge pilot 2 | 5 | 15,432 | 4,904 | 0.029964 | provider | 0 |
| E4-P seed-43 source traces | 4 | 2,219 | 5,896 | 0.023774 | provider | 0 |
| MuSiQue answer equivalence | 24 | 4,119 | 3,679 | 0.016886 | estimate | 0 |
| E4 technical pilot | 5 | 1,057 | 2,494 | 0.010145 | provider | 0 |
| batch1/E4_pilot_v1 | 2 | 396 | 1,338 | 0.005314 | provider | 0 |

## Claude Haiku 5.5

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| Sub-claim presence full (B) | 2116 | 3,224,745 | 5,263,231 | 2.954090 | estimate | 0 |
| MuSiQue presence full (A) | 2108 | 4,915,215 | 1,861,687 | 1.422365 | estimate | 0 |
| Main-table redo labeller | 4800 | 6,629,834 | 1,479,366 | 1.402666 | estimate | 0 |
| Silo-Bench presence full (A) | 1113 | 4,785,094 | 1,556,417 | 1.256718 | estimate | 5 |
| v2 rescore pilot | 614 | 3,144,294 | 172,595 | 0.400727 | estimate | 0 |
| Per-fact labeller pilot/validation | 827 | 1,361,139 | 279,062 | 0.275849 | estimate | 2 |
| Injected distortion | 2064 | 681,763 | 217,995 | 0.177174 | estimate | 0 |
| Main-table presence pilot | 190 | 604,113 | 225,301 | 0.173062 | estimate | 0 |
| Coverage labeller v3 | 270 | 589,821 | 138,823 | 0.128394 | estimate | 0 |
| v2 labeller full pilot | 154 | 909,160 | 47,811 | 0.114821 | estimate | 0 |
| Answer equivalence pilot | 765 | 764,929 | 55,393 | 0.104189 | estimate | 0 |
| Coverage rescore | 147 | 319,024 | 71,661 | 0.067733 | estimate | 0 |
| Silo-Bench presence validation | 74 | 317,877 | 49,229 | 0.056402 | estimate | 1 |
| Sub-claim validation | 59 | 90,121 | 79,971 | 0.048998 | estimate | 0 |
| LLM labeller pilot | 60 | 394,253 | 18,627 | 0.048739 | estimate | 0 |
| E2-A injection screening | 121 | 320,212 | 29,026 | 0.046534 | estimate | 0 |
| Restore-the-source | 450 | 185,477 | 50,566 | 0.043831 | estimate | 0 |
| Label validation v9 | 120 | 232,412 | 36,589 | 0.041536 | estimate | 0 |
| Label validation v7 | 125 | 183,838 | 36,901 | 0.037265 | estimate | 4 |
| Coverage validation | 90 | 169,337 | 40,248 | 0.037058 | estimate | 0 |
| Label validation v8 | 120 | 180,738 | 36,000 | 0.036074 | estimate | 0 |
| Label validation v6 | 120 | 163,606 | 35,486 | 0.034104 | estimate | 0 |
| Sub-claim presence pilot | 20 | 30,334 | 48,864 | 0.027465 | estimate | 0 |
| E2-A injection screening v2 | 60 | 91,806 | 19,313 | 0.018837 | estimate | 0 |
| 20261112_repilot_v2 | 20 | 96,026 | 4,768 | 0.011987 | estimate | 0 |
| Coverage validation v2 | 25 | 46,592 | 9,585 | 0.009452 | estimate | 0 |

## Qwen-235B

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| batch1/expansion_stage2 | 4815 | 9,635,159 | 918,262 | 1.906256 | provider | 0 |
| batch1/expansion_stage1 | 1204 | 2,392,676 | 228,487 | 0.458453 | provider | 0 |
| batch1/E4_pool_matcher | 507 | 1,379,016 | 363,120 | 0.437891 | provider | 0 |
| batch1/E1_matcher_anchor | 178 | 488,639 | 128,486 | 0.152535 | provider | 0 |
| batch1/E4P_seed43 | 1079 | 523,703 | 99,291 | 0.131901 | provider | 0 |
| batch1/Paper_evaluators_full_v11 | 852 | 292,880 | 69,069 | 0.076322 | provider | 0 |
| batch1/E4_phase2 | 195 | 164,603 | 56,990 | 0.065103 | provider | 0 |
| batch1/E4_phase1 | 85 | 217,270 | 45,784 | 0.060124 | provider | 0 |
| E2-A technical pilot | 71 | 246,374 | 9,052 | 0.039874 | provider | 0 |
| Placement pilot | 30 | 346,564 | 8,232 | 0.039346 | estimate | 0 |
| batch1/E4_phase1b | 78 | 167,199 | 15,569 | 0.029425 | provider | 0 |
| Audit diagnosis on 89 cases | 60 | 120,047 | 11,276 | 0.025289 | provider | 0 |
| 20261108_e1_v2 | 60 | 91,626 | 9,534 | 0.018822 | provider | 0 |
| E2-C technical pilot | 15 | 112,317 | 2,677 | 0.017408 | provider | 0 |
| 20261108_e1 | 108 | 79,824 | 8,143 | 0.015684 | provider | 0 |
| E4 technical pilot | 47 | 58,818 | 5,266 | 0.011605 | provider | 0 |
| E2-C card pilot (18 calls) | 9 | 67,867 | 1,349 | 0.010825 | provider | 0 |
| Swap labeller | 44 | 67,636 | 6,335 | 0.009931 | estimate | 0 |
| 20261108_e2_a_proxy | 26 | 43,771 | 5,131 | 0.009598 | provider | 0 |
| batch1/E1_matcher_anchor_topup | 12 | 32,711 | 5,258 | 0.007944 | provider | 0 |
| E4-P seed-43 source traces | 52 | 31,688 | 4,942 | 0.007098 | provider | 0 |
| 20261108_e1_calibration | 62 | 21,612 | 3,551 | 0.005090 | provider | 0 |
| Placement redo | 32 | 11,617 | 4,073 | 0.004885 | estimate | 0 |
| batch1/E4_direct_insertion | 8 | 5,879 | 4,695 | 0.004568 | provider | 0 |
| batch1/Paper_evaluators_pilot | 48 | 15,114 | 3,975 | 0.004304 | provider | 0 |
| batch1/E4_pilot_v1 | 21 | 19,680 | 1,939 | 0.004112 | provider | 0 |
| Injected distortion | 20 | 7,431 | 2,086 | 0.002709 | estimate | 0 |
| 20261108_r1_structural | 5 | 17,355 | 483 | 0.002672 | provider | 0 |
| Placement v2 | 4 | 8,828 | 1,736 | 0.002625 | estimate | 0 |
| Constructed distortion | 5 | 0 | 0 | 0.002486 | estimate | 0 |
| Missing-fact repair | 14 | 6,105 | 1,129 | 0.001758 | estimate | 0 |
| batch1/E4_manifest | 17 | 8,291 | 964 | 0.001678 | provider | 0 |
| batch1/E2A_stage2_spot | 4 | 7,032 | 481 | 0.001342 | provider | 0 |
| Answer-equivalence beside | 8 | 5,738 | 1,481 | 0.001314 | estimate | 0 |
| E4-P technical pilot | 14 | 2,960 | 659 | 0.000849 | provider | 0 |
| 20261108_control_pilot | 3 | 2,789 | 71 | 0.000444 | provider | 0 |
| batch1/E2A_stage2_spot_v4 | 6 | 1,330 | 206 | 0.000351 | provider | 0 |
| batch1/E2A_stage2_spot_v3 | 3 | 1,175 | 133 | 0.000236 | provider | 0 |

## GPT-4o-mini

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| Who&When sanity | 368 | 2,819,457 | 39,947 | 0.446887 | provider | 0 |
| batch1/E4P_seed43 | 1066 | 483,678 | 75,621 | 0.117924 | provider | 0 |
| batch1/E4_phase2 | 190 | 130,927 | 33,249 | 0.039588 | provider | 0 |
| Placement pilot | 30 | 345,854 | 6,697 | 0.038176 | estimate | 0 |
| GPT-4o-mini k=1 rebuild | 152 | 76,740 | 9,750 | 0.017361 | provider | 0 |
| Swap labeller | 44 | 68,448 | 6,454 | 0.010072 | estimate | 0 |
| batch1/E4_phase1 | 44 | 25,305 | 2,522 | 0.005309 | provider | 0 |
| Placement redo | 72 | 22,447 | 3,148 | 0.005256 | estimate | 0 |
| 20261108_e1_calibration | 61 | 20,700 | 2,958 | 0.004880 | provider | 0 |
| Answer-equivalence beside | 32 | 22,912 | 4,417 | 0.004500 | estimate | 0 |
| Missing-fact repair | 46 | 19,462 | 2,246 | 0.004267 | estimate | 0 |
| 20261108_e1 | 54 | 16,316 | 2,494 | 0.003944 | provider | 0 |
| Injected distortion | 42 | 14,261 | 2,136 | 0.003421 | estimate | 0 |
| 20261108_crosscheck_pilot | 5 | 12,195 | 888 | 0.002362 | provider | 0 |
| E4 technical pilot | 26 | 8,623 | 1,544 | 0.002220 | provider | 0 |
| 20261108_e2_a_proxy | 6 | 8,724 | 958 | 0.001461 | provider | 0 |
| Constructed distortion | 3 | 0 | 0 | 0.001375 | estimate | 0 |
| batch1/E4_phase1b | 12 | 5,174 | 744 | 0.001223 | provider | 0 |
| batch1/E2A_stage2_spot_v4 | 18 | 3,698 | 792 | 0.001030 | provider | 0 |
| E4-P technical pilot | 16 | 3,596 | 716 | 0.000969 | provider | 0 |
| batch1/E4_manifest | 6 | 3,725 | 374 | 0.000783 | provider | 0 |
| batch1/E2A_stage2_spot_v3 | 10 | 3,058 | 533 | 0.000779 | provider | 0 |
| Placement v2 | 4 | 3,780 | 214 | 0.000695 | estimate | 0 |
| batch1/E4_direct_insertion | 8 | 3,134 | 332 | 0.000669 | provider | 0 |
| E2-A technical pilot | 8 | 1,838 | 338 | 0.000478 | provider | 0 |
| 20261108_e4_donor_v2 | 2 | 1,008 | 133 | 0.000231 | provider | 0 |

## Gemma-4-31B

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| batch1/E4P_seed43 | 1081 | 588,987 | 142,222 | 0.126153 | provider | 0 |
| Placement pilot | 30 | 389,016 | 9,443 | 0.044476 | estimate | 0 |
| batch1/E4_phase2 | 140 | 150,893 | 65,809 | 0.039050 | provider | 0 |
| Swap labeller | 113 | 161,780 | 14,920 | 0.023638 | estimate | 0 |
| Missing-fact repair | 213 | 83,237 | 11,520 | 0.021255 | estimate | 0 |
| Answer-equivalence beside | 129 | 91,902 | 12,268 | 0.015324 | estimate | 0 |
| batch1/E4_phase1 | 72 | 42,654 | 13,279 | 0.009408 | provider | 0 |
| Placement redo | 56 | 19,518 | 3,600 | 0.005344 | estimate | 0 |
| Injected distortion | 35 | 12,312 | 2,287 | 0.003377 | estimate | 0 |
| 20261108_e1_calibration | 48 | 18,592 | 2,657 | 0.003261 | provider | 0 |
| Placement v2 | 4 | 11,460 | 2,225 | 0.003182 | estimate | 0 |
| batch1/E4_direct_insertion | 18 | 9,609 | 3,317 | 0.003148 | provider | 0 |
| 20261108_e1 | 44 | 15,003 | 2,328 | 0.002717 | provider | 0 |
| Constructed distortion | 4 | 0 | 0 | 0.001748 | estimate | 0 |
| batch1/E4_phase1b | 36 | 9,091 | 1,884 | 0.001650 | provider | 0 |
| batch1/E4_manifest | 17 | 10,944 | 829 | 0.001641 | provider | 0 |
| batch1/E4_pilot_v1 | 13 | 3,393 | 530 | 0.000834 | provider | 0 |
| E4 technical pilot | 13 | 3,422 | 552 | 0.000594 | provider | 0 |
| E4-P technical pilot | 9 | 2,016 | 438 | 0.000390 | provider | 0 |
| 20261108_e2_a_proxy | 3 | 2,806 | 145 | 0.000370 | provider | 0 |
| E2-A technical pilot | 4 | 854 | 212 | 0.000175 | provider | 0 |
| batch1/E2A_stage2_spot_v3 | 2 | 698 | 148 | 0.000138 | provider | 0 |
| batch1/E2A_stage2_spot_v4 | 2 | 510 | 145 | 0.000117 | provider | 0 |

## Mistral-S

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| Judge pilot | 8 | 18,433 | 3,415 | 0.004879 | provider | 0 |
| Judge pilot 2 | 5 | 15,215 | 766 | 0.002862 | provider | 0 |

## Unknown

| Experiment | Calls | Prompt tokens | Completion tokens | USD | Provider / estimate | Failed |
|---|---:|---:|---:|---:|---|---:|
| Constructed distortion | 12 | 0 | 0 | 0.000000 | provider | 0 |

