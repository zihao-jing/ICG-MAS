# Baseline scoring v4 — released scorer determines primary

2026-11-08. Supersedes v3 prospectively; rescoring existing technical pilots is retrospective. Decision is based on released code, not comparative performance. Pinned commit: 14369dcb079c7cdf86ed2924145d5a28ff5c73b2. Both source files were fetched at this commit and verified byte-identical to the inspected evaluation cache; hashes in review4/r1_scorer_source_check.json.

`whowhen_eval/parse.py` lines169–170:
```python
if code in known:
    return code, None
```
`whowhen_eval/score.py` line152:
```python
"mode": bool(pm) and pm in ok_modes,
```
The parser extracts the first recognised taxonomy code, independent of a mode name; the scorer compares that code. **It accepts code-only answers. Code-only released scoring is therefore primary; strict code+name scoring is sensitivity.** No released prompt/taxonomy changes. Per-axis scoring is independent in score.py lines145–153: an invalid mode does not erase a correct agent/step. Missing/invalid predictions score wrong on that axis and stay in the denominator. Full-output invalidity is reported additionally, not used to erase independently valid axes.

For relay traces, native renderer coordinates map to stages as before; exact agent, native step and released mode are scored independently. Family type is primary, mode secondary under the frozen 17-mode mapping. Strict sensitivity requires the matching code+name pair for type validity; report legacy all-fields-strict joint scores additionally when comparing to old pilots. Neither scorer invents a missing name or remaps an invalid code. Show primary and sensitivity side by side with invalid rates in every E2-C/E2 result table. Disclose the Qwen/Gemini family reversal observed in pilots. W&W and MAST keep their released method-specific scoring; no invented mode axis for W&W.
