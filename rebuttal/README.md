# Experiment records

Run all commands here from the repository root. Each folder under `pilots/` is
one experiment and is kept as an archive: use a fresh output directory for every
new condition or retry.

## What each folder holds

| File | Purpose |
| --- | --- |
| `pilots/prereg/*.md`, `*prompt*.json` | Rule and prompt, written and hashed before the run |
| `report.md`, `*score*.json`, `*summary*` | Results, with the source file of every number |
| `RUN_RECORD.md`, `handcheck.md` | Run notes and manual checks, where a run has them |

Raw API call logs (`calls.jsonl`), model traces and large result files are not
part of the release because of their size; each report names them, and
re-running the listed script regenerates them in a new folder.

The main README lists which folder supports each reported result. The repair
studies are under `iclr2027_paper/experiments/repair/`.

## Offline checks

```bash
./run.sh python -m pytest tests/ -q
./run.sh python -m src.eval.run_experiment --help
./run.sh python -m scripts.run_frozen_repair --help
```

Recompute threshold sensitivity without API calls; choose a new output name:

```bash
./run.sh python -m scripts.exp_rebuttal_threshold \
  --sb-run results/run_qwen235b_n5 \
  --mq-run results/run_qwen235b_musique \
  --output rebuttal/results/new_threshold_check.json
```

The required cached runs must be present locally. MuSiQue raw data belongs at
`data/musique/musique_ans_v1.0_dev.jsonl`; Silo-Bench inputs are under
`data/silo-bench/benchmarks/`. A fresh Git clone does not include the ignored
MuSiQue data or baseline results.

## Plan a frozen repair run

This example validates an existing reviewed cohort and writes a call plan.
Without `--execute`, it makes no API calls. The output directory must not exist.

```bash
./run.sh python -m scripts.run_frozen_repair run \
  --manifest iclr2027_paper/experiments/repair/qwen235b_silobench_n5_review.jsonl \
  --decisions iclr2027_paper/experiments/repair/exact_span_decisions/qwen235b_silobench_n5_decisions.jsonl \
  --output rebuttal/results/new_qwen_n5_plan
```

For a new cohort, prepare and review its own manifest and decisions using the
[repair-study instructions](../iclr2027_paper/experiments/repair/README.md).
Evidence-gap decisions require verified literal source spans. Keep the sample,
condition definitions, and model choices fixed before observing new responses.

To execute a reviewed plan, repeat its arguments with a **different, fresh**
output directory and add `--execute --max-calls N`, where `N` covers the
printed call count. Check the provider's current model availability and rates
first. The count cap is not a monetary budget. Use `--retry-from` for failed
arms; keep retry artifacts separate from the original run.

## New baseline experiments

The main runner uses `--dataset silobench` or `--dataset musique`.
The separate evidence-flow audit runner uses `--benchmark silo_bench` or
`--benchmark musique`. These spellings are different.

For a small live baseline run, explicitly choose the provider's model ID:

```bash
export REBUTTAL_MODEL='your-provider-model-id'
./run.sh python -m src.eval.run_experiment \
  --dataset silobench --n-agents 5 --protocols score_ranked_relay \
  --provider openrouter --model "$REBUTTAL_MODEL" \
  --limit 2 --max-workers 2 \
  --output rebuttal/results/new_silobench_smoke
```

This makes paid API calls. `--test` on experiment runners also uses live APIs;
it is not equivalent to the mocked test suite. Configure the API key in the
ignored root `.env`, as described in the main README.

## Record and report

Use names such as `YYYYMMDD_question_model_dataset_condition`. Keep the exact
command, code commit, model ID, dataset IDs, seed, prompts, provider responses,
failed calls, and inclusion/exclusion decisions with each run. Preserve the
original baseline caches and separate experimental conditions when summarizing.

Lexical coverage is a diagnostic proxy, not proof that all required facts are
present. The stage-swap study compares model placement under a one-upgrade-call
budget; it does not by itself establish causal attribution. Report MuSiQue F1
and Silo-Bench exact match separately, with sample sizes and uncertainty.

Before sharing a reproducible snapshot, inspect `git status`: the current paper
and many repair scripts originated as untracked local files. Include intended
source files and reviewed artifacts in a versioned checkpoint; keep credentials,
local environments, and disposable build files out. No automatic commit or
artifact relocation is performed by these workflows.

Build the current manuscript with:

```bash
./iclr2027_paper/build.sh
```

The output is `iclr2027_paper/build/main.pdf`.
