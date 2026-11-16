# Distortion-confirmer validation against an independent reference

Rule `CONFIRMER_RULE.md` (sha256 `1ffa11efabf8`), frozen before any call; reference prompt `confirmer_reference_prompt.json` (sha256 `d4ebfe7002f4`) is a copy of the confirmer's system text. Reference **Gemini 3.6 Flash**; confirmer **Claude Haiku 5.5**. Held-out 144 of the 144 cases reserved from validation (the 40 pilot cases excluded from the 184). Spend $0.250881, cap $2.00. Stage: relay checkpoint (the candidate source sentence and the distorted board unit); the answer arms are not used.

**Agreement on `source_states_fact`: 123/144 = 0.854 (95% CI 0.786-0.907); kappa 0.660 (0.524-0.781) - PASS** against the frozen rule (agreement >= 0.85, kappa >= 0.60).

Confusion: confirmer yes / reference no 19; confirmer no / reference yes 2; both yes 90; both no 33.

Gate on the held-out cases (verbatim is mechanical and identical for both): confirmer confirmed **109/144 = 0.757** (0.679-0.824); reference confirmed **92/144 = 0.639** (0.555-0.717).

## What this means

The confirmer's `source_states_fact` call **agrees with the reference** at the frozen point-estimate bar: 0.854 clears 0.85, but the 95% CI lower bound 0.786 does not, so the PASS is a point-estimate pass, not an interval-level one. The 132 figure remains a confirmer count on all 184 cases; this run validates the semantic call on the 144 held-out cases, not the truth of that count.

The reference is an LLM applying the same written prompt, not author ground truth. No author labels exist for this confirmation task. The held-out cases were fixed before the reference calls; no case was selected on its label.

## Per-case reference labels

| key | instance | model | confirmer | reference | verbatim |
| --- | --- | --- | --- | --- | --- |
| `3cb0be696f83` | 2hop__547045_131879 | gemma31b | yes | yes | yes |
| `3db66b2055fe` | 2hop__156085_436709 | qwen235b | no | no | yes |
| `411587a72062` | 3hop1__559908_42197_18397 | gpt4omini | yes | yes | yes |
| `441f6d264769` | 4hop1__436202_378185_282674_759393 | gpt4omini | no | no | yes |
| `4597aff354ed` | 4hop1__88342_49853_128008_92225 | gemma31b | yes | yes | yes |
| `45a49dc737d3` | 4hop3__220945_88460_30152_20999 | qwen235b | yes | no | yes |
| `481e9d703600` | 3hop1__475351_160713_77246 | gpt4omini | yes | yes | yes |
| `49f62e8d6de3` | 2hop__462179_643013 | gemma31b | yes | yes | yes |
| `4a8dca3b0b17` | 2hop__198459_61845 | qwen235b | yes | yes | yes |
| `4b93d8df8272` | 4hop2__160585_14670_8987_8529 | gpt4omini | yes | no | yes |
| `4e0b90a474f0` | 4hop3__373573_132409_223216_35031 | gpt4omini | yes | yes | yes |
| `51041702bcd6` | 2hop__33288_157788 | gpt4omini | yes | yes | yes |
| `51efd6e05402` | 3hop2__326964_846_7713 | gemma31b | yes | yes | yes |
| `522d3d5b721c` | 3hop1__71549_486583_84283 | gpt4omini | yes | yes | yes |
| `52fce7e33d0e` | 2hop__487706_40501 | gemma31b | yes | yes | yes |
| `552691661b6f` | 2hop__274110_413723 | gemma31b | yes | yes | yes |
| `5551158483c0` | 2hop__385392_756039 | gemma31b | yes | yes | yes |
| `559e2e0353c3` | 2hop__446324_620302 | gemma31b | yes | yes | yes |
| `5655a6047a44` | 3hop1__312146_720914_41132 | gpt4omini | no | no | yes |
| `565f46cecca4` | 4hop1__399219_765799_282674_759393 | gemma31b | no | yes | yes |
| `58ca215e1e47` | 3hop1__6362_14336_21111 | gemma31b | yes | yes | yes |
| `59a6965e0755` | 4hop2__71753_158985_70784_79935 | gemma31b | no | no | yes |
| `59e7c0c55da3` | 3hop1__131783_131926_87157 | gemma31b | yes | yes | yes |
| `5ad604ff4316` | 3hop1__222497_309482_27537 | gemma31b | yes | no | yes |
| `5b659d19ae76` | 2hop__196348_150107 | gemma31b | no | no | yes |
| `5cc6bb3ca62c` | 3hop1__602329_792411_51423 | gemma31b | no | no | yes |
| `5e6bb96ed00f` | 2hop__64537_482364 | gpt4omini | no | no | yes |
| `604f2a38375e` | 3hop1__418091_15840_36014 | gemma31b | yes | yes | yes |
| `606bd4747249` | 2hop__109242_113442 | gemma31b | yes | yes | yes |
| `61a2dbce68b4` | 3hop1__103197_214799_259594 | gemma31b | yes | yes | yes |
| `631b7235ac2a` | 2hop__765180_123956 | gemma31b | yes | yes | yes |
| `64918062ef96` | 2hop__128945_47686 | gemma31b | yes | yes | yes |
| `6576beb50bbf` | 2hop__472486_97805 | gemma31b | yes | yes | yes |
| `66b2041db3e8` | 4hop1__777217_32392_823060_610794 | gemma31b | no | no | yes |
| `68a21a8e02ac` | 3hop2__304722_747004_63959 | gemma31b | no | no | yes |
| `6a45e9dec071` | 2hop__39063_212301 | gpt4omini | yes | no | yes |
| `6e5ddfbb383c` | 2hop__66_59409 | gpt4omini | yes | yes | yes |
| `6f5c332691ac` | 4hop1__94201_642284_131926_90707 | gemma31b | no | no | yes |
| `6f895c3c31b0` | 2hop__207597_73244 | gpt4omini | yes | yes | yes |
| `6f8c1e797f9f` | 2hop__635187_861533 | gemma31b | yes | yes | yes |
| `70c172db7465` | 4hop1__145087_32392_823060_610794 | gemma31b | yes | no | yes |
| `73a390791cbf` | 4hop1__690653_378185_282674_759393 | gemma31b | yes | yes | yes |
| `73b300a3f0e2` | 4hop1__343844_17130_70784_79935 | gemma31b | yes | yes | yes |
| `74a99d6da47f` | 3hop2__573858_326964_7713 | gemma31b | yes | yes | yes |
| `76891e9ac747` | 2hop__494659_5385 | gemma31b | yes | yes | yes |
| `7717e36ff113` | 2hop__507528_139339 | gemma31b | yes | yes | yes |
| `77a3eb367ed3` | 2hop__669160_139339 | gemma31b | yes | yes | yes |
| `77a8039aa857` | 2hop__497191_129669 | gemma31b | yes | yes | yes |
| `77c6e1809a90` | 3hop1__617062_127905_46748 | gemma31b | yes | yes | yes |
| `78210b512fb6` | 2hop__510860_22402 | gemma31b | yes | yes | yes |
| `78e09a59ff1b` | 4hop1__606685_508773_85832_745702 | gpt4omini | yes | no | yes |
| `7a1654a30e75` | 2hop__796221_18803 | gemma31b | yes | yes | yes |
| `7b3f00558e97` | 2hop__38828_89399 | gpt4omini | yes | yes | yes |
| `7dab26b81bcf` | 2hop__82669_768138 | gpt4omini | no | no | yes |
| `7e85e5824dc5` | 2hop__132909_33564 | gpt4omini | yes | yes | yes |
| `7f880cb94ad6` | 2hop__485221_544917 | gemma31b | yes | yes | yes |
| `8049b17c0d78` | 2hop__43776_162341 | gemma31b | yes | no | yes |
| `8177d5cd79b4` | 4hop1__391525_49925_13759_736921 | qwen235b | no | yes | yes |
| `83ba3eb019c5` | 2hop__231890_595414 | gemma31b | yes | yes | yes |
| `85133e74a693` | 4hop1__638988_17130_70784_79935 | gemma31b | yes | yes | yes |
| `87048f2253a1` | 3hop1__92788_648104_13493 | gpt4omini | no | no | yes |
| `8ad07fb9072d` | 2hop__169443_83769 | gpt4omini | yes | yes | yes |
| `8aef0fc80540` | 2hop__301011_820181 | gemma31b | yes | yes | yes |
| `8b45a71b0077` | 3hop2__132957_52222_40768 | gpt4omini | yes | yes | yes |
| `8c4721ea4f7d` | 3hop1__131110_39743_24526 | gemma31b | yes | yes | yes |
| `8c51dc4bd25c` | 3hop1__285585_538202_84283 | gemma31b | yes | yes | yes |
| `8e81dcaaccef` | 2hop__450608_373421 | gemma31b | yes | yes | yes |
| `926001a85d6f` | 2hop__171254_383727 | gemma31b | yes | yes | yes |
| `92c9a561b90a` | 2hop__55966_162341 | gemma31b | no | no | yes |
| `96f8bdc9d7c6` | 2hop__78756_198548 | gpt4omini | yes | yes | yes |
| `97ccbd34449a` | 3hop2__30152_105895_20999 | gpt4omini | yes | yes | yes |
| `987d6ca8408d` | 3hop1__354480_834494_34053 | gemma31b | yes | yes | yes |
| `992857928dcd` | 3hop1__79039_131926_13165 | gpt4omini | yes | yes | yes |
| `9c31947644dc` | 2hop__527400_159673 | gemma31b | yes | no | yes |
| `9f8e00912069` | 2hop__849534_122868 | gemma31b | yes | yes | yes |
| `a8b56664bf6c` | 3hop2__851134_326964_7713 | gpt4omini | no | no | yes |
| `a9a5bc396dd7` | 4hop1__726391_153080_159767_81096 | qwen235b | no | no | yes |
| `aa18c6c6e6be` | 4hop2__71753_73205_70784_79935 | gemma31b | yes | yes | yes |
| `aa31ad62a81c` | 2hop__123166_47134 | gemma31b | yes | yes | yes |
| `aa95585cdc2f` | 4hop1__58323_375563_161848_44231 | gpt4omini | no | no | yes |
| `aaf1cdf8c52a` | 2hop__603598_25719 | gpt4omini | yes | no | yes |
| `ab3dbc60f333` | 2hop__422295_8311 | gemma31b | no | no | yes |
| `ac0baba4b7d1` | 2hop__149862_108549 | gemma31b | yes | yes | yes |
| `ae361b758d01` | 4hop3__531933_836463_161616_77103 | gemma31b | no | no | yes |
| `ae3a7dc70816` | 3hop1__174833_650651_7262 | gpt4omini | no | no | yes |
| `aee2ff3f6484` | 2hop__55032_786853 | qwen235b | no | no | yes |
| `b07c7145635e` | 2hop__411091_625230 | gemma31b | yes | yes | yes |
| `b0a50ac56a3e` | 2hop__37765_85990 | qwen235b | yes | yes | yes |
| `b1675885d91e` | 3hop1__816887_127905_80286 | gemma31b | yes | yes | yes |
| `b2e2ed7844e0` | 4hop3__507819_88460_30152_20999 | gemma31b | no | no | yes |
| `b4894f425e5c` | 2hop__728969_131890 | gemma31b | yes | yes | yes |
| `b658d01aab24` | 3hop2__132957_132798_40768 | gpt4omini | yes | yes | yes |
| `b8f5d65e32fc` | 2hop__157251_556157 | gemma31b | yes | yes | yes |
| `b90bccb30fdc` | 2hop__693157_131890 | gemma31b | yes | yes | yes |
| `bb59fafc1ff5` | 2hop__442175_56873 | gpt4omini | yes | yes | yes |
| `bc932a57af32` | 4hop2__161602_426860_88460_18966 | gpt4omini | yes | yes | yes |
| `bcddb2076c03` | 2hop__7906_78851 | gemma31b | yes | yes | yes |
| `bd6cc5b2079f` | 2hop__227791_75487 | gemma31b | no | no | yes |
| `bd9a2042c86d` | 2hop__157339_156796 | gemma31b | yes | yes | yes |
| `be4f0e1dfacc` | 3hop1__222497_309482_80702 | gemma31b | yes | yes | yes |
| `c1b28ce2a97f` | 2hop__20256_74481 | gpt4omini | yes | yes | yes |
| `c4f0b35529f9` | 3hop2__304722_781203_63959 | gemma31b | no | no | yes |
| `cbeee0ba3c01` | 2hop__203985_524737 | gemma31b | yes | yes | yes |
| `cc34320c4488` | 2hop__394720_120259 | gemma31b | yes | yes | yes |
| `cce3a2876b91` | 2hop__840174_78851 | qwen235b | yes | yes | yes |
| `cd10fd989927` | 3hop1__129675_39743_24526 | gemma31b | yes | yes | yes |
| `cd92a7892f48` | 2hop__739909_807845 | gemma31b | yes | yes | yes |
| `d0f5e2f26480` | 2hop__776377_857193 | gemma31b | yes | yes | yes |
| `d1c77d14a170` | 2hop__829358_754719 | gemma31b | yes | yes | yes |
| `d2386044bf88` | 3hop1__145427_106426_157788 | qwen235b | yes | no | yes |
| `d267fc37189f` | 3hop1__765565_326948_78782 | gemma31b | no | no | yes |
| `d29b1cbd1ae5` | 3hop2__88342_93066_47738 | qwen235b | no | no | yes |
| `d38aed77c1cd` | 2hop__53937_92673 | gemma31b | yes | yes | yes |
| `d461d2886840` | 4hop1__131002_53706_795904_580996 | qwen235b | no | no | yes |
| `d4a0ecc5c2f4` | 2hop__175175_347233 | gemma31b | yes | yes | yes |
| `d8af39dbc9fa` | 2hop__481809_184805 | qwen235b | yes | yes | yes |
| `d90b61b72938` | 2hop__814671_82341 | gemma31b | yes | yes | yes |
| `db827aace5cf` | 2hop__70584_198548 | gemma31b | no | no | yes |
| `dc162e7bab08` | 3hop2__92991_89854_76291 | gemma31b | yes | yes | yes |
| `dc1a8979156e` | 3hop1__694534_160088_85460 | qwen235b | no | no | yes |
| `dc9179f25710` | 3hop1__694534_160088_49779 | gemma31b | yes | yes | yes |
| `dd10ac05bbe5` | 2hop__458131_174974 | gemma31b | no | no | yes |
| `dedd747fbd80` | 4hop2__567956_14670_8987_8529 | gpt4omini | yes | no | yes |
| `df43f419687e` | 3hop1__390489_502967_84283 | gpt4omini | yes | no | yes |
| `df5dde97381e` | 2hop__650138_22402 | gemma31b | yes | yes | yes |
| `df86576950ee` | 2hop__132469_533882 | gemma31b | yes | no | yes |
| `e0aa00d7b5e8` | 2hop__155781_155922 | gemma31b | yes | yes | yes |
| `e4e43b1ed441` | 2hop__557284_160249 | gemma31b | yes | no | yes |
| `e4f42fc65657` | 2hop__705035_152093 | gemma31b | yes | yes | yes |
| `e50535b44eb6` | 3hop1__178435_547811_41132 | gpt4omini | no | no | yes |
| `e684450980e7` | 2hop__95172_152907 | gemma31b | yes | yes | yes |
| `e843b7ecd1e6` | 3hop1__354480_834494_34109 | gemma31b | yes | yes | yes |
| `ef901c5e9c58` | 3hop2__30152_105395_20999 | gemma31b | yes | no | yes |
| `f173315d2495` | 2hop__130668_126089 | gemma31b | yes | yes | yes |
| `f3ce435e192e` | 3hop1__23058_20608_36327 | gemma31b | yes | yes | yes |
| `f5f9694fc628` | 3hop1__66872_709625_84283 | gpt4omini | yes | no | yes |
| `f6693b4f41fc` | 2hop__9512_36630 | gemma31b | yes | yes | yes |
| `f75c6ba9aefe` | 2hop__734582_71302 | qwen235b | no | no | yes |
| `f75f0a5a1e1c` | 3hop1__23444_160713_77246 | gpt4omini | yes | yes | yes |
| `f7974bbaf6fd` | 2hop__24661_81961 | gemma31b | yes | no | yes |
| `f917067f900c` | 3hop1__483634_720378_15538 | gemma31b | no | no | yes |
| `f99b0b55d20c` | 2hop__779424_75487 | gemma31b | no | no | yes |
| `fbd5ecd44956` | 2hop__267938_92763 | gemma31b | yes | no | yes |
| `fde711b3d06e` | 3hop2__304722_466316_63959 | gemma31b | yes | no | yes |
