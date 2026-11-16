# Restore-the-source test on real-run distortion diagnoses

Rule `RESTORE_FULL_ADDENDUM.md` (sha256 `10bdfb5acd52`), frozen before the calls. Full run, 184 of 184 unique cases (`sha256('43|restore|'+instance)` order). Spend $0.043831; cap $5.00. Stages: relay checkpoint (the distorted unit) and final aggregation (the two arms).

**Validation addendum (2026-11-13).** The confirmer was validated after this run against an independent Gemini 3.6 Flash reference on 144 held-out cases: agreement 123/144 = 0.854 [0.786, 0.907], kappa 0.660 [0.524, 0.781], PASS against the frozen 0.85/0.60 rule (`confirmer_validation_report.md`). The reference is an LLM, not author ground truth, and is stricter: 109/144 confirmer-gated vs 92/144 reference-gated. The 132/184 below is therefore confirmer-gated, not author-validated. On the 92 reference-gated held-out cases the restore comparison was rerun (`RESTORE_REFERENCE_SUBSET_RULE.md`): control **0/92**, restore **13/92 = 14.1% [7.7, 23.0]**, paired **+13 [7, 20]** (13 improved, 0 worse), so the restore effect holds on the stricter subset; spend $0.000558 for 4 new calls, 90 arms reused.

## Confirmation

Cases whose source sentence was confirmed to state the fact and is verbatim in the source shard: **132/184** (71.7%, 95% CI 64.6-78.1).

| instance | model | source states fact | board contradicts | confirmed |
| --- | --- | --- | --- | --- |
| 4hop1__145494_698949_157828_162309 | gemma31b | no | no | no |
| 4hop1__580153_49925_13759_736921 | gemma31b | no | no | no |
| 2hop__557411_652060 | gemma31b | no | no | no |
| 2hop__757497_78606 | gpt4omini | yes | yes | yes |
| 2hop__124807_135019 | gemma31b | yes | no | yes |
| 2hop__156658_155922 | gemma31b | yes | no | yes |
| 4hop2__71753_648517_70784_61381 | gemma31b | no | yes | no |
| 4hop1__88342_49853_128008_46894 | qwen235b | yes | yes | yes |
| 2hop__632870_22402 | gemma31b | yes | no | yes |
| 2hop__351275_75487 | gemma31b | yes | no | yes |
| 4hop2__161602_426860_88460_126088 | qwen235b | yes | no | yes |
| 3hop2__28476_14777_9331 | gpt4omini | yes | no | yes |
| 2hop__123509_5385 | gemma31b | yes | yes | yes |
| 3hop1__68732_39743_24526 | gemma31b | yes | no | yes |
| 3hop1__145924_131905_41948 | qwen235b | no | no | no |
| 4hop1__344155_378185_282674_759393 | qwen235b | no | no | no |
| 4hop2__161602_426860_88460_21062 | qwen235b | no | no | no |
| 4hop2__9988_261673_70784_79935 | gemma31b | no | no | no |
| 4hop2__71753_729371_70784_79935 | gemma31b | no | no | no |
| 3hop1__831499_228453_10972 | gemma31b | no | no | no |
| 4hop1__370129_621192_10659_42311 | gpt4omini | yes | no | yes |
| 4hop1__636860_49925_13759_736921 | gemma31b | no | no | no |
| 2hop__124932_278133 | gemma31b | yes | no | yes |
| 3hop1__127821_157828_239539 | qwen235b | no | no | no |
| 2hop__839126_472799 | gemma31b | yes | no | yes |
| 4hop1__163763_49925_13759_736921 | gemma31b | no | no | no |
| 4hop1__813171_153080_159767_81096 | qwen235b | yes | no | yes |
| 2hop__810411_159673 | gemma31b | yes | no | yes |
| 2hop__673655_316668 | gemma31b | yes | no | yes |
| 2hop__756620_127399 | gemma31b | yes | no | yes |
| 2hop__107548_124896 | gemma31b | yes | no | yes |
| 2hop__280451_84616 | gemma31b | yes | no | yes |
| 3hop1__529164_567566_84283 | gemma31b | yes | no | yes |
| 3hop1__159737_160713_77246 | qwen235b | no | no | no |
| 3hop1__617062_127905_92225 | gpt4omini | no | no | no |
| 2hop__142198_152093 | gemma31b | yes | no | yes |
| 3hop1__462960_160545_34754 | gpt4omini | no | no | no |
| 3hop1__469478_15840_36002 | gemma31b | yes | no | yes |
| 2hop__86689_728109 | gemma31b | no | no | no |
| 2hop__286_574195 | gemma31b | yes | no | yes |
| 2hop__547045_131879 | gemma31b | yes | no | yes |
| 2hop__156085_436709 | qwen235b | no | no | no |
| 3hop1__559908_42197_18397 | gpt4omini | yes | no | yes |
| 4hop1__436202_378185_282674_759393 | gpt4omini | no | no | no |
| 4hop1__88342_49853_128008_92225 | gemma31b | yes | no | yes |
| 4hop3__220945_88460_30152_20999 | qwen235b | yes | no | yes |
| 3hop1__475351_160713_77246 | gpt4omini | yes | no | yes |
| 2hop__462179_643013 | gemma31b | yes | no | yes |
| 2hop__198459_61845 | qwen235b | yes | no | yes |
| 4hop2__160585_14670_8987_8529 | gpt4omini | yes | no | yes |
| 4hop3__373573_132409_223216_35031 | gpt4omini | yes | yes | yes |
| 2hop__33288_157788 | gpt4omini | yes | no | yes |
| 3hop2__326964_846_7713 | gemma31b | yes | no | yes |
| 3hop1__71549_486583_84283 | gpt4omini | yes | no | yes |
| 2hop__487706_40501 | gemma31b | yes | no | yes |
| 2hop__274110_413723 | gemma31b | yes | no | yes |
| 2hop__385392_756039 | gemma31b | yes | no | yes |
| 2hop__446324_620302 | gemma31b | yes | no | yes |
| 3hop1__312146_720914_41132 | gpt4omini | no | no | no |
| 4hop1__399219_765799_282674_759393 | gemma31b | no | no | no |
| 3hop1__6362_14336_21111 | gemma31b | yes | no | yes |
| 4hop2__71753_158985_70784_79935 | gemma31b | no | yes | no |
| 3hop1__131783_131926_87157 | gemma31b | yes | no | yes |
| 3hop1__222497_309482_27537 | gemma31b | yes | no | yes |
| 2hop__196348_150107 | gemma31b | no | no | no |
| 3hop1__602329_792411_51423 | gemma31b | no | no | no |
| 2hop__64537_482364 | gpt4omini | no | no | no |
| 3hop1__418091_15840_36014 | gemma31b | yes | no | yes |
| 2hop__109242_113442 | gemma31b | yes | yes | yes |
| 3hop1__103197_214799_259594 | gemma31b | yes | no | yes |
| 2hop__765180_123956 | gemma31b | yes | no | yes |
| 2hop__128945_47686 | gemma31b | yes | no | yes |
| 2hop__472486_97805 | gemma31b | yes | no | yes |
| 4hop1__777217_32392_823060_610794 | gemma31b | no | no | no |
| 3hop2__304722_747004_63959 | gemma31b | no | no | no |
| 2hop__39063_212301 | gpt4omini | yes | no | yes |
| 2hop__66_59409 | gpt4omini | yes | yes | yes |
| 4hop1__94201_642284_131926_90707 | gemma31b | no | no | no |
| 2hop__207597_73244 | gpt4omini | yes | no | yes |
| 2hop__635187_861533 | gemma31b | yes | no | yes |
| 4hop1__145087_32392_823060_610794 | gemma31b | yes | no | yes |
| 4hop1__690653_378185_282674_759393 | gemma31b | yes | no | yes |
| 4hop1__343844_17130_70784_79935 | gemma31b | yes | no | yes |
| 3hop2__573858_326964_7713 | gemma31b | yes | no | yes |
| 2hop__494659_5385 | gemma31b | yes | no | yes |
| 2hop__507528_139339 | gemma31b | yes | no | yes |
| 2hop__669160_139339 | gemma31b | yes | no | yes |
| 2hop__497191_129669 | gemma31b | yes | no | yes |
| 3hop1__617062_127905_46748 | gemma31b | yes | no | yes |
| 2hop__510860_22402 | gemma31b | yes | no | yes |
| 4hop1__606685_508773_85832_745702 | gpt4omini | yes | no | yes |
| 2hop__796221_18803 | gemma31b | yes | no | yes |
| 2hop__38828_89399 | gpt4omini | yes | no | yes |
| 2hop__82669_768138 | gpt4omini | no | no | no |
| 2hop__132909_33564 | gpt4omini | yes | no | yes |
| 2hop__485221_544917 | gemma31b | yes | no | yes |
| 2hop__43776_162341 | gemma31b | yes | no | yes |
| 4hop1__391525_49925_13759_736921 | qwen235b | no | no | no |
| 2hop__231890_595414 | gemma31b | yes | no | yes |
| 4hop1__638988_17130_70784_79935 | gemma31b | yes | no | yes |
| 3hop1__92788_648104_13493 | gpt4omini | no | no | no |
| 2hop__169443_83769 | gpt4omini | yes | no | yes |
| 2hop__301011_820181 | gemma31b | yes | no | yes |
| 3hop2__132957_52222_40768 | gpt4omini | yes | no | yes |
| 3hop1__131110_39743_24526 | gemma31b | yes | no | yes |
| 3hop1__285585_538202_84283 | gemma31b | yes | no | yes |
| 2hop__450608_373421 | gemma31b | yes | no | yes |
| 2hop__171254_383727 | gemma31b | yes | no | yes |
| 2hop__55966_162341 | gemma31b | no | yes | no |
| 2hop__78756_198548 | gpt4omini | yes | no | yes |
| 3hop2__30152_105895_20999 | gpt4omini | yes | no | yes |
| 3hop1__354480_834494_34053 | gemma31b | yes | no | yes |
| 3hop1__79039_131926_13165 | gpt4omini | yes | no | yes |
| 2hop__527400_159673 | gemma31b | yes | no | yes |
| 2hop__849534_122868 | gemma31b | yes | no | yes |
| 3hop2__851134_326964_7713 | gpt4omini | no | no | no |
| 4hop1__726391_153080_159767_81096 | qwen235b | no | no | no |
| 4hop2__71753_73205_70784_79935 | gemma31b | yes | no | yes |
| 2hop__123166_47134 | gemma31b | yes | no | yes |
| 4hop1__58323_375563_161848_44231 | gpt4omini | no | no | no |
| 2hop__603598_25719 | gpt4omini | yes | no | yes |
| 2hop__422295_8311 | gemma31b | no | no | no |
| 2hop__149862_108549 | gemma31b | yes | no | yes |
| 4hop3__531933_836463_161616_77103 | gemma31b | no | no | no |
| 3hop1__174833_650651_7262 | gpt4omini | no | no | no |
| 2hop__55032_786853 | qwen235b | no | yes | no |
| 2hop__411091_625230 | gemma31b | yes | no | yes |
| 2hop__37765_85990 | qwen235b | yes | no | yes |
| 3hop1__816887_127905_80286 | gemma31b | yes | no | yes |
| 4hop3__507819_88460_30152_20999 | gemma31b | no | no | no |
| 2hop__728969_131890 | gemma31b | yes | no | yes |
| 3hop2__132957_132798_40768 | gpt4omini | yes | no | yes |
| 2hop__157251_556157 | gemma31b | yes | no | yes |
| 2hop__693157_131890 | gemma31b | yes | no | yes |
| 2hop__442175_56873 | gpt4omini | yes | no | yes |
| 4hop2__161602_426860_88460_18966 | gpt4omini | yes | no | yes |
| 2hop__7906_78851 | gemma31b | yes | no | yes |
| 2hop__227791_75487 | gemma31b | no | no | no |
| 2hop__157339_156796 | gemma31b | yes | no | yes |
| 3hop1__222497_309482_80702 | gemma31b | yes | no | yes |
| 2hop__20256_74481 | gpt4omini | yes | no | yes |
| 3hop2__304722_781203_63959 | gemma31b | no | no | no |
| 2hop__203985_524737 | gemma31b | yes | no | yes |
| 2hop__394720_120259 | gemma31b | yes | no | yes |
| 2hop__840174_78851 | qwen235b | yes | no | yes |
| 3hop1__129675_39743_24526 | gemma31b | yes | no | yes |
| 2hop__739909_807845 | gemma31b | yes | no | yes |
| 2hop__776377_857193 | gemma31b | yes | no | yes |
| 2hop__829358_754719 | gemma31b | yes | no | yes |
| 3hop1__145427_106426_157788 | qwen235b | yes | no | yes |
| 3hop1__765565_326948_78782 | gemma31b | no | no | no |
| 3hop2__88342_93066_47738 | qwen235b | no | no | no |
| 2hop__53937_92673 | gemma31b | yes | no | yes |
| 4hop1__131002_53706_795904_580996 | qwen235b | no | no | no |
| 2hop__175175_347233 | gemma31b | yes | no | yes |
| 2hop__481809_184805 | qwen235b | yes | yes | yes |
| 2hop__814671_82341 | gemma31b | yes | no | yes |
| 2hop__70584_198548 | gemma31b | no | no | no |
| 3hop2__92991_89854_76291 | gemma31b | yes | no | yes |
| 3hop1__694534_160088_85460 | qwen235b | no | no | no |
| 3hop1__694534_160088_49779 | gemma31b | yes | no | yes |
| 2hop__458131_174974 | gemma31b | no | no | no |
| 4hop2__567956_14670_8987_8529 | gpt4omini | yes | no | yes |
| 3hop1__390489_502967_84283 | gpt4omini | yes | yes | yes |
| 2hop__650138_22402 | gemma31b | yes | no | yes |
| 2hop__132469_533882 | gemma31b | yes | no | yes |
| 2hop__155781_155922 | gemma31b | yes | no | yes |
| 2hop__557284_160249 | gemma31b | yes | no | yes |
| 2hop__705035_152093 | gemma31b | yes | no | yes |
| 3hop1__178435_547811_41132 | gpt4omini | no | no | no |
| 2hop__95172_152907 | gemma31b | yes | no | yes |
| 3hop1__354480_834494_34109 | gemma31b | yes | no | yes |
| 3hop2__30152_105395_20999 | gemma31b | yes | no | yes |
| 2hop__130668_126089 | gemma31b | yes | no | yes |
| 3hop1__23058_20608_36327 | gemma31b | yes | no | yes |
| 3hop1__66872_709625_84283 | gpt4omini | yes | yes | yes |
| 2hop__9512_36630 | gemma31b | yes | no | yes |
| 2hop__734582_71302 | qwen235b | no | yes | no |
| 3hop1__23444_160713_77246 | gpt4omini | yes | no | yes |
| 2hop__24661_81961 | gemma31b | yes | no | yes |
| 3hop1__483634_720378_15538 | gemma31b | no | no | no |
| 2hop__779424_75487 | gemma31b | no | no | no |
| 2hop__267938_92763 | gemma31b | yes | no | yes |
| 3hop2__304722_466316_63959 | gemma31b | yes | no | yes |

## Answer arms (confirmed cases)

Control exact **2/132**; restore exact **20/132** (15.2%, 95% CI 9.5-22.4). Mean F1 control 0.051, restore 0.326. Paired: 18 improved, 0 worse, 114 same.

## Reading

Only 132 of 184 cases have a source sentence that the labeller confirms states the fact and is verbatim in the shard. The remainder are distortion diagnoses whose target unit is not a near-copy of a source fact (refusals, headers, unrelated text), so the audit's distortion label is not restorable from the source. On the confirmed cases the restore arm is reported above; the sample is descriptive.

The confirming labeller is **Claude Haiku 5.5** with the frozen prompt in `RESTORE_RULE.md`, temperature 0. It had **not been validated for this confirmation task** at the time of this report; the validation addendum at the top records the later held-out PASS. The verbatim-substring test is mechanical, but the states-the-fact judgement is unvalidated. The 132 count is therefore a labeller-gated count, not an author-validated one.
