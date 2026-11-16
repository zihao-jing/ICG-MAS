# E2-C casebook extension to 20 traces (frozen before any call)

Date: 2026-11-14. Stage: baseline attribution on the k = 1 Part B boards.
Descriptive casebook only; no pooling of backbones.

## Population and class rule

The 156 frozen Part B k = 1 traces
(`rebuttal/pilots/20261114_part_b_k1/answers.jsonl`) with their sealed E1
judge labels. Class rule unchanged from `E2-C-main.md`, applied to the judge's
carriers:

- extraction: `binary_call = lost` and a fact has no pool carrier;
- selection: `binary_call = lost`, a fact has a pool carrier and no board carrier;
- aggregation: `binary_call = reached_but_unused`.

## Casebook

The existing 7-trace casebook (`20261114_e2c_main/selection.json`) plus 13 new
traces: MuSiQue extraction 4, MuSiQue aggregation 6, Silo-Bench aggregation 3.
Combined cells: Silo-Bench extraction 3 (all eligible), Silo-Bench selection 0,
MuSiQue extraction 4, MuSiQue aggregation 8, Silo-Bench aggregation 5 = **20**.

## Selection

Within each new cell, sort the eligible pool by
`SHA-256(json([44, model, instance_id]))`, exclude the existing 7 casebook
traces, and take the first k. The exact IDs are frozen in the extension
`selection.json` before the first call. No picking after output.

## Calls

13 new traces × 3 released methods × 2 backbones (Qwen-235B and Gemini 3.6
Flash) = **78 baseline calls**. If and only if the 15-trace judge validation
passes, score the Qwen-backbone outputs (13 × 3 = 39 judge calls) with the
validated E2-C judge. The Gemini-backbone block is stored separately, marked
"judged by the same model", and never pooled with Qwen.

## Gate and status

No judge label is read before the 15-trace validation passes. If it fails, the
extension is exploratory, its labels are not used, and only the descriptive
casebook counts are reported. No coverage/CR estimate and no test are claimed.

## Budget

78 baseline calls, projected about **$1.00**; cap **$2.00**. Including the
5-trace validation completion, the E2-C extension is projected at about
**$1.30–$1.50**. Together with the selection-repair control the approved spend
is **$1.70**; the run stops before that total is exceeded.