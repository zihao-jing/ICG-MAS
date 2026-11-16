# Restore comparison on the reference-gated subset

Rule `RESTORE_REFERENCE_SUBSET_RULE.md` (sha256 `b9f87f89e53a`), frozen before any new call. Subset: the **92 held-out cases** where the Gemini 3.6 Flash reference says `source_states_fact = yes` and the source sentence is verbatim (92/144 from `confirmer_validation_report.md`). 90 cases reuse the frozen full-run answer arms; 2 are reference-only and were answered here (4 calls). Spend **$0.000558**, cap $0.25. Stage: relay checkpoint (source restoration) and final aggregation (the two arms).

Control exact **0/92 = 0.0%** (0.0-3.9); restore exact **13/92 = 14.1%** (7.7-23.0); paired difference **+13** (13 improved, 0 worse, 79 same), case-bootstrap 95% CI [7, 20].

Reference-only cases (2): control 0/2, restore 0/2.

Beside the 132 figure: the confirmer gate gives 2/132 control and 20/132 restore (15.2%, 9.5-22.4). The reference gate is a stricter positive set, so the two rates are not the same denominator; both stay on record.

## Reading

The restore effect **holds** on the reference-gated subset: restore beats control by the same direction and a non-zero paired count.
The reference is an LLM, not author ground truth; this subset is reference-gated, not author-validated. The 132 remains confirmer-gated, and the 90 reused arms come from the frozen full run (no new cost). The 2 reference-only cases enter on the reference call alone and are listed above.

## Cases

| key | instance | model | source | control | restore |
| --- | --- | --- | --- | --- | --- |
| `3cb0be696f83` | 2hop__547045_131879 | gemma31b | reused | wrong | wrong |
| `411587a72062` | 3hop1__559908_42197_18397 | gpt4omini | reused | wrong | wrong |
| `4597aff354ed` | 4hop1__88342_49853_128008_92225 | gemma31b | reused | wrong | wrong |
| `481e9d703600` | 3hop1__475351_160713_77246 | gpt4omini | reused | wrong | wrong |
| `49f62e8d6de3` | 2hop__462179_643013 | gemma31b | reused | wrong | wrong |
| `4a8dca3b0b17` | 2hop__198459_61845 | qwen235b | reused | wrong | wrong |
| `4e0b90a474f0` | 4hop3__373573_132409_223216_35031 | gpt4omini | reused | wrong | wrong |
| `51041702bcd6` | 2hop__33288_157788 | gpt4omini | reused | wrong | wrong |
| `51efd6e05402` | 3hop2__326964_846_7713 | gemma31b | reused | wrong | wrong |
| `522d3d5b721c` | 3hop1__71549_486583_84283 | gpt4omini | reused | wrong | wrong |
| `52fce7e33d0e` | 2hop__487706_40501 | gemma31b | reused | wrong | wrong |
| `552691661b6f` | 2hop__274110_413723 | gemma31b | reused | wrong | exact |
| `5551158483c0` | 2hop__385392_756039 | gemma31b | reused | wrong | wrong |
| `559e2e0353c3` | 2hop__446324_620302 | gemma31b | reused | wrong | exact |
| `565f46cecca4` | 4hop1__399219_765799_282674_759393 | gemma31b | new | wrong | wrong |
| `58ca215e1e47` | 3hop1__6362_14336_21111 | gemma31b | reused | wrong | wrong |
| `59e7c0c55da3` | 3hop1__131783_131926_87157 | gemma31b | reused | wrong | wrong |
| `604f2a38375e` | 3hop1__418091_15840_36014 | gemma31b | reused | wrong | wrong |
| `606bd4747249` | 2hop__109242_113442 | gemma31b | reused | wrong | exact |
| `61a2dbce68b4` | 3hop1__103197_214799_259594 | gemma31b | reused | wrong | wrong |
| `631b7235ac2a` | 2hop__765180_123956 | gemma31b | reused | wrong | exact |
| `64918062ef96` | 2hop__128945_47686 | gemma31b | reused | wrong | wrong |
| `6576beb50bbf` | 2hop__472486_97805 | gemma31b | reused | wrong | wrong |
| `6e5ddfbb383c` | 2hop__66_59409 | gpt4omini | reused | wrong | wrong |
| `6f895c3c31b0` | 2hop__207597_73244 | gpt4omini | reused | wrong | wrong |
| `6f8c1e797f9f` | 2hop__635187_861533 | gemma31b | reused | wrong | wrong |
| `73a390791cbf` | 4hop1__690653_378185_282674_759393 | gemma31b | reused | wrong | wrong |
| `73b300a3f0e2` | 4hop1__343844_17130_70784_79935 | gemma31b | reused | wrong | wrong |
| `74a99d6da47f` | 3hop2__573858_326964_7713 | gemma31b | reused | wrong | wrong |
| `76891e9ac747` | 2hop__494659_5385 | gemma31b | reused | wrong | exact |
| `7717e36ff113` | 2hop__507528_139339 | gemma31b | reused | wrong | wrong |
| `77a3eb367ed3` | 2hop__669160_139339 | gemma31b | reused | wrong | wrong |
| `77a8039aa857` | 2hop__497191_129669 | gemma31b | reused | wrong | exact |
| `77c6e1809a90` | 3hop1__617062_127905_46748 | gemma31b | reused | wrong | wrong |
| `78210b512fb6` | 2hop__510860_22402 | gemma31b | reused | wrong | wrong |
| `7a1654a30e75` | 2hop__796221_18803 | gemma31b | reused | wrong | wrong |
| `7b3f00558e97` | 2hop__38828_89399 | gpt4omini | reused | wrong | wrong |
| `7e85e5824dc5` | 2hop__132909_33564 | gpt4omini | reused | wrong | wrong |
| `7f880cb94ad6` | 2hop__485221_544917 | gemma31b | reused | wrong | exact |
| `8177d5cd79b4` | 4hop1__391525_49925_13759_736921 | qwen235b | new | wrong | wrong |
| `83ba3eb019c5` | 2hop__231890_595414 | gemma31b | reused | wrong | wrong |
| `85133e74a693` | 4hop1__638988_17130_70784_79935 | gemma31b | reused | wrong | wrong |
| `8ad07fb9072d` | 2hop__169443_83769 | gpt4omini | reused | wrong | wrong |
| `8aef0fc80540` | 2hop__301011_820181 | gemma31b | reused | wrong | wrong |
| `8b45a71b0077` | 3hop2__132957_52222_40768 | gpt4omini | reused | wrong | wrong |
| `8c4721ea4f7d` | 3hop1__131110_39743_24526 | gemma31b | reused | wrong | wrong |
| `8c51dc4bd25c` | 3hop1__285585_538202_84283 | gemma31b | reused | wrong | wrong |
| `8e81dcaaccef` | 2hop__450608_373421 | gemma31b | reused | wrong | wrong |
| `926001a85d6f` | 2hop__171254_383727 | gemma31b | reused | wrong | wrong |
| `96f8bdc9d7c6` | 2hop__78756_198548 | gpt4omini | reused | wrong | wrong |
| `97ccbd34449a` | 3hop2__30152_105895_20999 | gpt4omini | reused | wrong | wrong |
| `987d6ca8408d` | 3hop1__354480_834494_34053 | gemma31b | reused | wrong | wrong |
| `992857928dcd` | 3hop1__79039_131926_13165 | gpt4omini | reused | wrong | wrong |
| `9f8e00912069` | 2hop__849534_122868 | gemma31b | reused | wrong | exact |
| `aa18c6c6e6be` | 4hop2__71753_73205_70784_79935 | gemma31b | reused | wrong | wrong |
| `aa31ad62a81c` | 2hop__123166_47134 | gemma31b | reused | wrong | exact |
| `ac0baba4b7d1` | 2hop__149862_108549 | gemma31b | reused | wrong | wrong |
| `b07c7145635e` | 2hop__411091_625230 | gemma31b | reused | wrong | wrong |
| `b0a50ac56a3e` | 2hop__37765_85990 | qwen235b | reused | wrong | wrong |
| `b1675885d91e` | 3hop1__816887_127905_80286 | gemma31b | reused | wrong | wrong |
| `b4894f425e5c` | 2hop__728969_131890 | gemma31b | reused | wrong | wrong |
| `b658d01aab24` | 3hop2__132957_132798_40768 | gpt4omini | reused | wrong | wrong |
| `b8f5d65e32fc` | 2hop__157251_556157 | gemma31b | reused | wrong | wrong |
| `b90bccb30fdc` | 2hop__693157_131890 | gemma31b | reused | wrong | wrong |
| `bb59fafc1ff5` | 2hop__442175_56873 | gpt4omini | reused | wrong | wrong |
| `bc932a57af32` | 4hop2__161602_426860_88460_18966 | gpt4omini | reused | wrong | wrong |
| `bcddb2076c03` | 2hop__7906_78851 | gemma31b | reused | wrong | wrong |
| `bd9a2042c86d` | 2hop__157339_156796 | gemma31b | reused | wrong | wrong |
| `be4f0e1dfacc` | 3hop1__222497_309482_80702 | gemma31b | reused | wrong | exact |
| `c1b28ce2a97f` | 2hop__20256_74481 | gpt4omini | reused | wrong | wrong |
| `cbeee0ba3c01` | 2hop__203985_524737 | gemma31b | reused | wrong | wrong |
| `cc34320c4488` | 2hop__394720_120259 | gemma31b | reused | wrong | wrong |
| `cce3a2876b91` | 2hop__840174_78851 | qwen235b | reused | wrong | wrong |
| `cd10fd989927` | 3hop1__129675_39743_24526 | gemma31b | reused | wrong | wrong |
| `cd92a7892f48` | 2hop__739909_807845 | gemma31b | reused | wrong | exact |
| `d0f5e2f26480` | 2hop__776377_857193 | gemma31b | reused | wrong | wrong |
| `d1c77d14a170` | 2hop__829358_754719 | gemma31b | reused | wrong | wrong |
| `d38aed77c1cd` | 2hop__53937_92673 | gemma31b | reused | wrong | wrong |
| `d4a0ecc5c2f4` | 2hop__175175_347233 | gemma31b | reused | wrong | exact |
| `d8af39dbc9fa` | 2hop__481809_184805 | qwen235b | reused | wrong | wrong |
| `d90b61b72938` | 2hop__814671_82341 | gemma31b | reused | wrong | wrong |
| `dc162e7bab08` | 3hop2__92991_89854_76291 | gemma31b | reused | wrong | wrong |
| `dc9179f25710` | 3hop1__694534_160088_49779 | gemma31b | reused | wrong | wrong |
| `df5dde97381e` | 2hop__650138_22402 | gemma31b | reused | wrong | wrong |
| `e0aa00d7b5e8` | 2hop__155781_155922 | gemma31b | reused | wrong | wrong |
| `e4f42fc65657` | 2hop__705035_152093 | gemma31b | reused | wrong | exact |
| `e684450980e7` | 2hop__95172_152907 | gemma31b | reused | wrong | wrong |
| `e843b7ecd1e6` | 3hop1__354480_834494_34109 | gemma31b | reused | wrong | wrong |
| `f173315d2495` | 2hop__130668_126089 | gemma31b | reused | wrong | wrong |
| `f3ce435e192e` | 3hop1__23058_20608_36327 | gemma31b | reused | wrong | wrong |
| `f6693b4f41fc` | 2hop__9512_36630 | gemma31b | reused | wrong | wrong |
| `f75f0a5a1e1c` | 3hop1__23444_160713_77246 | gpt4omini | reused | wrong | wrong |
