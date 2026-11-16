# Frozen presence rule (zero-cost check)

Written 2026-11-12 before the check was run. No model calls; this rule reads
frozen text only.

## Cohort

The Stage 2 clean extraction-omission cohort: every matcher record whose
`diagnosis == 'extraction_omission'` and whose R3+R4 flags pass, recomputed
from `rebuttal/results/batch1/expansion_stage2/matcher/*.json` exactly as
`scripts/run_expansion_stage2.py --report` does. That is 69 traces over 59
unique instances.

## Targeted fact

For each clean trace, the targeted fact is the first missing fact id in the
matcher's carrier record, i.e. the same `candidate_fact` that the Stage 2
report prints (R3 guarantees exactly one missing fact per trace).

## Target agent and its own context

The target agent is the E4-v7 `extraction_omission` target: the fact's support
agents (parsed from the matcher's `source_ids`) sorted by
`digest([42, instance, agent])`, first element. The agent's own context is its
`source_contexts` entry in the Stage 2 trace package. No other agent's context
and no full document pool is read.

## Presence label

The context is split at `.`, `!`, `?` or a newline (the same split as
`spans()` in `scripts/build_e4_manifest.py`). **Amendment 1 (before any paid
call):** the question line and document headers are not evidence and are
dropped before scoring, mirroring the R2 gate's question/header reasons. A
sentence is dropped if it starts with `Question:` or `You hold the following
evidence:`, if its normalized text equals the normalized question, or if it is
a `[Document: ...]` line. For each remaining sentence `s`:

- `full(s)` = token-multiset recall of the fact in `s`
  (`src/audit/e4_fix_gates.py::recall`).
- `content(s)` = the same recall computed after removing the frozen `STOP`
  set from both the fact and the sentence.

`rmax` is the highest `full(s)`; ties go to the earliest sentence in document
order.

- **present**: at least one sentence has `full >= 0.8` and `content >= 0.8`.
- **partial**: the remaining evidence shares at least one fact token with the
  fact, but no sentence is present.
- **absent**: no remaining sentence shares any fact token with the fact.

**Amendment 1 (before any paid call):** "present" is any sentence meeting both
thresholds, not only the highest-`full` sentence; the reported best sentence is
the highest-`full` supporting sentence, earliest in document order on ties.

**Amendment 2 (before any paid call):** the final label is content-based,
because function words are not evidence: a fact is stated with "was born"
against "born" or "on 1 January" against "(born 1 January)" and the full-token
recall penalises that. Definitions used for the split and for pilot
eligibility:

- **present**: best sentence content recall `>= 0.8` (the fact's content
  tokens are co-located in one sentence).
- **partial**: best sentence content recall `>= 0.4` but no sentence reaches
  0.8.
- **absent**: best sentence content recall `< 0.4`.

Both splits (Amendment-1 full-token rule and the content rule) are printed.
Every present and partial case is printed with its best sentence; a manual
read may move a case only with the sentence and reason recorded here, before
any paid call. The content rule governs eligibility.

The 0.8 threshold is the R2 delivery threshold, so "present" means a single
context sentence already carries what the delivery gate would demand from an
extracted unit.

The best-matching sentence is printed for every non-present case. A manual
read may override a label only before any paid call and only with the sentence
and reason recorded in `presence_check.md`; every override is listed there.

## Instance level

Each trace is labelled. For the 59 unique instances, the instance label is the
label of the first trace in the frozen model order
`gemma31b, gpt4omini, qwen235b`; if the traces for one instance disagree, the
disagreement is reported as well. The split is reported at both levels
(traces and instances).

## Use

Only **present** cases are eligible for the extraction-fix pilot. **Absent**
cases are a design finding and are not repaired. **Partial** cases are not
piloted; they are reported with their best sentence.