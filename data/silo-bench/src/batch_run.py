"""Batch runner: execute multiple cases across task/protocol/model combinations.

Task files in benchmarks/ follow the naming convention:
    {LEVEL}-{TASK_ID}-n{NUM_AGENTS}.json
    e.g. I-01-n002.json, II-15-n050.json, III-21-n100.json

Usage:
    uv run python -m src.batch_run \
        --task-dir benchmarks/ \
        --protocols msg broadcast sfs \
        --workspace workspace/ \
        --max-rounds 100 \
        --workers 4

    # Filter by level and agent count:
    uv run python -m src.batch_run \
        --levels I II \
        --agent-counts 2 5 10 \
        --protocols msg
"""

import argparse
import glob
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from src.engine import DEFAULT_API_KEY, DEFAULT_MODEL, DEFAULT_MODEL_URL, init_case, run_round
from src.utils.config import load_config

# Regex for parsing task filenames: {LEVEL}-{TASK_ID}_n{NUM_AGENTS}.json
# Supports both underscore and dash separator before 'n': I-01_n2 or I-01-n002
TASK_FILENAME_RE = re.compile(r"^(I{1,3})-(\d+)[-_]n(\d+)$")


def _parse_task_stem(stem: str) -> tuple[str, str, int] | None:
    """Parse a task filename stem into (level, task_id, num_agents).

    Returns None if the filename doesn't match the expected pattern.
    """
    m = TASK_FILENAME_RE.match(stem)
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def _filter_task_files(
    task_files: list[str],
    levels: list[str] | None,
    agent_counts: list[int] | None,
    task_ids: list[str] | None,
) -> list[str]:
    """Filter task files by level, agent count, and/or specific task IDs."""
    filtered = []
    for tf in task_files:
        stem = Path(tf).stem
        parsed = _parse_task_stem(stem)
        if parsed is None:
            # Non-standard filename — skip when any filter is active
            if levels or agent_counts or task_ids:
                continue
            filtered.append(tf)
            continue
        level, tid, n_agents = parsed
        if levels and level not in levels:
            continue
        if agent_counts and n_agents not in agent_counts:
            continue
        if task_ids and stem not in task_ids:
            continue
        filtered.append(tf)
    return filtered


def run_single_case(
    task_file: str,
    protocol: str,
    model: str,
    api_base: str,
    api_key: str,
    max_rounds: int,
    workspace: str,
) -> dict:
    """Run a single case from init through completion."""
    case_dir = init_case(
        task_file=task_file,
        protocol=protocol,
        model=model,
        api_base=api_base,
        api_key=api_key,
        max_rounds=max_rounds,
        workspace=workspace,
    )

    # Run rounds until done
    for _ in range(max_rounds):
        done = run_round(case_dir)
        if done:
            break

    return {"case_dir": case_dir, "task_file": task_file, "protocol": protocol, "model": model}


def main():
    parser = argparse.ArgumentParser(description="Batch run SILO-BENCH cases")
    parser.add_argument("--task-dir", default="benchmarks", help="Directory with task JSONs")
    parser.add_argument(
        "--protocols",
        nargs="+",
        default=["msg"],
        choices=["msg", "broadcast", "sfs"],
        help="Protocols to run",
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        choices=["I", "II", "III"],
        default=None,
        help="Filter by task level (e.g. --levels I II)",
    )
    parser.add_argument(
        "--agent-counts",
        nargs="+",
        type=int,
        default=None,
        help="Filter by agent count (e.g. --agent-counts 2 5 10)",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Filter by specific task IDs (e.g. --task-ids I-01-n002 II-15-n050)",
    )
    parser.add_argument("--models", nargs="+", default=None, help="Models to run")
    parser.add_argument("--api-base", default=None, help="API base URL")
    parser.add_argument("--api-key", default=None, help="API key")
    parser.add_argument("--profile", default="default", help="Config profile name from configs/config.yaml")
    parser.add_argument("--max-rounds", type=int, default=100, help="Max rounds per case")
    parser.add_argument("--workspace", default="workspace", help="Workspace directory")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers")
    args = parser.parse_args()

    # Load config from profile, then override with CLI args
    cfg = load_config(args.profile)
    if args.api_base is None:
        args.api_base = cfg["api_base"]
    if args.api_key is None:
        args.api_key = cfg["api_key"]
    if args.models is None:
        args.models = [cfg["model"]] if cfg["model"] else [DEFAULT_MODEL]

    # Collect all task files
    task_files = sorted(glob.glob(str(Path(args.task_dir) / "*.json")))
    if not task_files:
        print(f"No task files found in {args.task_dir}")
        return

    # Apply filters
    task_files = _filter_task_files(task_files, args.levels, args.agent_counts, args.task_ids)
    if not task_files:
        print("No task files match the specified filters.")
        return

    # Build all combinations
    jobs = []
    for task_file in task_files:
        for protocol in args.protocols:
            for model in args.models:
                jobs.append((task_file, protocol, model))

    print(f"Total jobs: {len(jobs)} ({len(task_files)} tasks x {len(args.protocols)} protocols x {len(args.models)} models)")

    if args.workers <= 1:
        # Sequential execution
        for i, (task_file, protocol, model) in enumerate(jobs):
            print(f"[{i + 1}/{len(jobs)}] {Path(task_file).stem} | {protocol} | {model}")
            result = run_single_case(
                task_file=task_file,
                protocol=protocol,
                model=model,
                api_base=args.api_base,
                api_key=args.api_key,
                max_rounds=args.max_rounds,
                workspace=args.workspace,
            )
            print(f"  -> {result['case_dir']}")
    else:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for task_file, protocol, model in jobs:
                future = executor.submit(
                    run_single_case,
                    task_file=task_file,
                    protocol=protocol,
                    model=model,
                    api_base=args.api_base,
                    api_key=args.api_key,
                    max_rounds=args.max_rounds,
                    workspace=args.workspace,
                )
                futures[future] = (task_file, protocol, model)

            completed = 0
            for future in as_completed(futures):
                completed += 1
                task_file, protocol, model = futures[future]
                try:
                    result = future.result()
                    print(f"[{completed}/{len(jobs)}] Done: {result['case_dir']}")
                except Exception as e:
                    print(f"[{completed}/{len(jobs)}] FAILED: {Path(task_file).stem} | {protocol} | {model}: {e}")

    print("Batch run complete.")


if __name__ == "__main__":
    main()
