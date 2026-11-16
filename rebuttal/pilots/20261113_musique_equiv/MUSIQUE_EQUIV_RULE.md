# Frozen rule: hand-check of the MuSiQue equivalence calls (item 2)

Written 2026-11-13 before the hand-check. No model calls; reads the logged
`answer-equiv-v1` calls and the frozen prompt's output.

## Population correction

The 150 author-labelled validation traces contain **90 E1 and 60 Silo-Bench**
traces, no MuSiQue (counted from
`rebuttal/pilots/20261112_labeller/validation_150.jsonl`). There is therefore
no MuSiQue author-labelled validation split to score. The available MuSiQue
evidence is the 400 logged main-table calls
(`rebuttal/pilots/20261112_answer_equiv/calls_main.jsonl`: 100 per protocol on
Qwen-235B, benchmark `MQ`). This check uses those calls and says so; it does
**not** claim author validation on MuSiQue.

## Agreement

Exact match (`lexical_correct`) versus the check's verdict on all 400 MuSiQue
calls: agreement and Cohen's kappa, with the 2x2 table.

## Hand-check

Every distinct (instance, gold, answer) call where exact match says wrong and
the check says EQUIVALENT is adjudicated: 113 calls, 74 distinct cases. The
hand-check is mine, reading gold and answer; the frozen verdict and reason are
read beside it. No call is re-made.

**Equivalent** if the answer names the same final answer as the gold: the same
entity, value, relation or set. Extra context is allowed when it does not
change or contradict the answer. Formatting, numeral/word form, a title,
spelling or a common abbreviation of the same entity counts as the same
answer.

**Not equivalent** if the answer omits decisive content the question asks for,
is vague or partial, gives a different answer, or contradicts the gold.

## Decision rule (fixed before the hand-check)

The check may replace the lexical cells on MuSiQue only if the hand-check
confirms **at least 0.90** of the exact-wrong / check-equivalent cases as
equivalent, with a 95% exact Clopper-Pearson interval. Otherwise the check is
not validated for MuSiQue and the lexical cells stay; the measured rate and
the errors are reported anyway.

## Cost

$0.000000 in new calls. The logged MuSiQue calls cost **$0.043771** (400 calls
in the main-table run); they are reused, not re-billed.