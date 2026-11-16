# Per-fact carrier-target fresh check (original labels)

Rule `PER_FACT_RULE_V4.md` (sha256 `0bc7d8c69cb6`), frozen before the calls. Validation is against the authors' original labels. 64 board comparisons (24 anchor + 40 dev); spend $0.028203, cap $5.00.

## Validation against the authors' original labels

Agreement **47/64 = 0.734** (95% CI 0.609-0.837); kappa **0.279** (0.000-0.577) - **FAIL** against 0.80/0.60. Per-fact **255/298**. The labeller stays unvalidated even for carrier identification.

## Post-hoc corrected-label audit (not a validation)

Against `corrected_labels.json` (sha256 `f79e20fbff47`), audited after the calls: agreement **64/64 = 1.000** (95% CI 0.944-1.000); kappa **1.000** (1.000-1.000); per-fact **289/298**. This is not a validation: the references were corrected after the labeller output was seen, and 40 of the 64 rows are E1 dev rows used in labeller development.

| key | source | labeller | author | corrected |
| --- | --- | --- | --- | --- |
| anchor/gemma31b/I-02_n5/A | anchor | True | True | True |
| anchor/gemma31b/I-02_n5/B | anchor | True | True | True |
| anchor/gemma31b/II-13_n10/A | anchor | True | True | True |
| anchor/gemma31b/II-13_n10/B | anchor | True | True | True |
| anchor/gemma31b/III-24_n5/A | anchor | True | True | True |
| anchor/gemma31b/III-24_n5/B | anchor | True | True | True |
| anchor/gemma31b/III-27_n5/A | anchor | True | True | True |
| anchor/gemma31b/III-27_n5/B | anchor | True | True | True |
| anchor/gpt4omini/I-02_n5/A | anchor | True | True | True |
| anchor/gpt4omini/I-02_n5/B | anchor | True | True | True |
| anchor/gpt4omini/II-13_n10/A | anchor | True | True | True |
| anchor/gpt4omini/II-13_n10/B | anchor | True | True | True |
| anchor/gpt4omini/III-24_n5/A | anchor | True | True | True |
| anchor/gpt4omini/III-24_n5/B | anchor | True | True | True |
| anchor/gpt4omini/III-27_n5/A | anchor | True | True | True |
| anchor/gpt4omini/III-27_n5/B | anchor | True | True | True |
| anchor/qwen235b/I-02_n5/A | anchor | True | True | True |
| anchor/qwen235b/I-02_n5/B | anchor | True | True | True |
| anchor/qwen235b/II-13_n10/A | anchor | True | True | True |
| anchor/qwen235b/II-13_n10/B | anchor | False | False | True |
| anchor/qwen235b/III-24_n5/A | anchor | False | False | True |
| anchor/qwen235b/III-24_n5/B | anchor | False | False | True |
| anchor/qwen235b/III-27_n5/A | anchor | True | True | True |
| anchor/qwen235b/III-27_n5/B | anchor | True | True | True |
| dev/dev/Dev run 07/A | dev | False | True | False |
| dev/dev/Dev run 07/B | dev | False | True | False |
| dev/dev/Dev run 11/A | dev | True | True | False |
| dev/dev/Dev run 11/B | dev | False | True | False |
| dev/dev/Dev run 04/C | dev | True | True | False |
| dev/dev/Dev run 04/D | dev | False | True | False |
| dev/dev/Dev run 14/A | dev | False | True | False |
| dev/dev/Dev run 14/B | dev | False | True | False |
| dev/dev/Dev run 08/A | dev | True | True | False |
| dev/dev/Dev run 08/B | dev | True | True | False |
| dev/dev/Dev run 16/A | dev | True | True | True |
| dev/dev/Dev run 16/B | dev | True | True | True |
| dev/dev/Dev run 18/C | dev | True | True | True |
| dev/dev/Dev run 18/D | dev | True | True | True |
| dev/dev/Dev run 10/C | dev | False | False | False |
| dev/dev/Dev run 10/D | dev | False | False | False |
| dev/dev/Dev run 01/A | dev | True | True | True |
| dev/dev/Dev run 01/B | dev | True | True | True |
| dev/dev/Dev run 17/C | dev | True | True | True |
| dev/dev/Dev run 17/D | dev | True | True | True |
| dev/dev/Dev run 20/A | dev | True | True | True |
| dev/dev/Dev run 20/B | dev | True | True | True |
| dev/dev/Dev run 03/A | dev | False | True | False |
| dev/dev/Dev run 03/B | dev | False | True | False |
| dev/dev/Dev run 06/C | dev | True | True | True |
| dev/dev/Dev run 06/D | dev | True | True | True |
| dev/dev/Dev run 02/C | dev | False | True | False |
| dev/dev/Dev run 02/D | dev | False | True | False |
| dev/dev/Dev run 15/C | dev | False | True | False |
| dev/dev/Dev run 15/D | dev | False | True | False |
| dev/dev/Dev run 05/A | dev | True | True | True |
| dev/dev/Dev run 05/B | dev | True | True | True |
| dev/dev/Dev run 12/A | dev | False | True | False |
| dev/dev/Dev run 12/B | dev | False | True | False |
| dev/dev/Dev run 09/C | dev | True | True | False |
| dev/dev/Dev run 09/D | dev | False | True | False |
| dev/dev/Dev run 13/A | dev | False | True | False |
| dev/dev/Dev run 13/B | dev | False | True | False |
| dev/dev/Dev run 19/A | dev | True | True | True |
| dev/dev/Dev run 19/B | dev | True | True | True |

## What this covers, and what it does not

The target is carrier identification: whether the labeller returns the board units that state each critical fact. It is not semantic fidelity or coverage, and the main-table columns stay lexical or matcher. The 24 anchor rows were not used before; the 40 dev rows were used in labeller development, so this set cannot be a clean validation of the prompt.

Composition: all 64 comparisons are Silo-Bench, not MuSiQue - 24 from four unused synthetic E1 anchor instances (I-02, II-13, III-24, III-27) and 40 from the 20 E1 dev runs. The reserve failures that motivated the audit were MuSiQue. No unused MuSiQue author labels remain, so MuSiQue carrier identification stays unvalidated; the pass above covers Silo-Bench carrier identification only.

The corrected labels are ours, audited from the board text under `PER_FACT_RULE_V4.md` and `author_citation_audit.md`; the authors' original labels are reported beside them and stay on record. Because the audit was made after the fresh calls and on a candidate set the labeller also saw, a row where author and labeller are wrong in the same way is not corrected and counts as agreement. The audited label is read from the text, not copied from the labeller, but this is not an independent author re-annotation.
