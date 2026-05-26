"""SILO-BENCH Result Analysis Tool.

Analyzes experiment results across communication types, difficulty levels,
and agent scales. Computes three core metrics:
  1. Success Rate (SR)
  2. Token Efficiency
  3. Communication Density

Usage:
    uv run python -m src.analyze ./workspace
    uv run python -m src.analyze ./workspace --output results.csv
"""

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]


@dataclass
class BenchmarkResult:
    """Data class for a single experiment result."""

    communication_type: str  # p2p, bp, sfs
    model: str
    case_id: str
    case_name: str
    num_agents: int
    timestamp: str
    rounds_run: int
    success_rate: float
    token_per_round: float
    communication_density: float
    total_messages: int
    total_tokens: int


class MASBenchmarkAnalyzer:
    """Analyzer for SILO-BENCH experiment results."""

    def __init__(self, workspace_dir: str = "./workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.results: list[BenchmarkResult] = []

    def parse_directory_name(self, dirname: str) -> Optional[dict[str, str]]:
        """Parse experiment directory name into components.

        Directory format: {case_id}_{protocol}_{model}_{timestamp}
        Example: I-01-n002_p2p_grok-4-1-fast-non-reasoning_20260212235629
        """
        pattern = r"^([IVX]+-\d+(?:-n\d+)?)_(p2p|bp|sfs)_(.+?)_(\d{14})$"
        match = re.match(pattern, dirname)
        if not match:
            return None
        return {
            "case_id": match.group(1),
            "protocol": match.group(2),
            "model": match.group(3),
            "timestamp": match.group(4),
        }

    def find_experiment_directories(self) -> dict[str, dict]:
        """Find all experiment directories, selecting the latest per unique key."""
        dirs_by_key: dict[str, dict[str, dict]] = defaultdict(dict)

        for dir_path in self.workspace_dir.iterdir():
            if not dir_path.is_dir():
                continue
            parsed = self.parse_directory_name(dir_path.name)
            if not parsed:
                continue
            key = f"{parsed['case_id']}_{parsed['protocol']}_{parsed['model']}"
            dirs_by_key[key][parsed["timestamp"]] = {
                "dir_path": dir_path,
                "parsed_info": parsed,
            }

        latest_dirs = {}
        for key, ts_dict in dirs_by_key.items():
            latest_ts = max(ts_dict.keys())
            latest_dirs[key] = ts_dict[latest_ts]
            print(f"  Selected: {key} (timestamp: {latest_ts})")

        return latest_dirs

    def load_json(self, path: Path) -> dict:
        """Load a JSON file."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_final_agent_states(self, case_dir: Path, num_agents: int) -> dict[int, dict]:
        """Load the final round agent states."""
        rounds_dir = case_dir / "rounds"
        if not rounds_dir.exists():
            return {}
        round_dirs = sorted(
            d for d in rounds_dir.iterdir() if d.is_dir() and d.name.startswith("round-")
        )
        if not round_dirs:
            return {}

        final_round = round_dirs[-1]
        states = {}
        for aid in range(num_agents):
            state_path = final_round / f"agent-{aid:03d}" / "state.json"
            if state_path.exists():
                states[aid] = self.load_json(state_path)
        return states

    def analyze_single(self, case_dir: Path, parsed_info: dict) -> BenchmarkResult:
        """Analyze a single experiment case."""
        metadata = self.load_json(case_dir / "metadata.json")
        results_data = self.load_json(case_dir / "results.json")

        task_info = metadata.get("task", {})
        execution = metadata.get("execution", {})
        num_agents = task_info.get("num_agents", 0)

        agent_states = self.load_final_agent_states(case_dir, num_agents)

        # Success rate
        submissions = results_data.get("submissions", [])
        correct = sum(1 for s in submissions if s.get("correct", False))
        sr = correct / len(submissions) if submissions else 0.0

        # Token efficiency
        total_tokens = execution.get("total_output_tokens", 0)
        rounds_run = execution.get("current_round", 0)
        denominator = 100 * num_agents
        token_eff = total_tokens / denominator if denominator > 0 else 0.0

        # Communication density
        total_msgs = sum(s.get("messages_sent", 0) for s in agent_states.values())
        max_conn = num_agents * (num_agents - 1) if num_agents > 1 else 1
        comm_density = total_msgs / max_conn if max_conn > 0 else 0.0

        return BenchmarkResult(
            communication_type=parsed_info["protocol"],
            model=parsed_info["model"],
            case_id=parsed_info["case_id"],
            case_name=task_info.get("case_name", ""),
            num_agents=num_agents,
            timestamp=parsed_info["timestamp"],
            rounds_run=rounds_run,
            success_rate=sr,
            token_per_round=token_eff,
            communication_density=comm_density,
            total_messages=total_msgs,
            total_tokens=total_tokens,
        )

    def analyze_all(self):
        """Analyze all experiments and print results."""
        experiment_dirs = self.find_experiment_directories()
        if not experiment_dirs:
            print("No experiment directories found.")
            return

        print(f"Found {len(experiment_dirs)} experiment(s)\n")

        for key, dir_info in experiment_dirs.items():
            try:
                result = self.analyze_single(dir_info["dir_path"], dir_info["parsed_info"])
                self.results.append(result)
            except Exception as e:
                print(f"  Error processing {key}: {e}")

        if not self.results:
            print("No results to display.")
            return

        self._print_results()

    def _print_results(self):
        """Print analysis results."""
        if pd is None:
            # Fallback without pandas
            print(f"\n{'='*80}")
            print("Results Summary")
            print(f"{'='*80}")
            for r in self.results:
                print(
                    f"  {r.case_id} | {r.communication_type.upper()} | {r.model} | "
                    f"SR={r.success_rate:.2%} | TokenEff={r.token_per_round:.2f} | "
                    f"CommDen={r.communication_density:.4f}"
                )
            return

        df = pd.DataFrame(
            [
                {
                    "Protocol": r.communication_type.upper(),
                    "Model": r.model,
                    "Case ID": r.case_id,
                    "Case Name": r.case_name,
                    "Agents": r.num_agents,
                    "Rounds": r.rounds_run,
                    "Success Rate": f"{r.success_rate:.2%}",
                    "Token Efficiency": f"{r.token_per_round:.2f}",
                    "Comm Density": f"{r.communication_density:.4f}",
                    "Total Messages": r.total_messages,
                    "Total Tokens": r.total_tokens,
                }
                for r in self.results
            ]
        )

        print(f"\n{'='*80}")
        print("Detailed Results:")
        print(f"{'='*80}")
        print(df.to_string(index=False))

        # Summary by protocol
        print(f"\n{'='*80}")
        print("Summary by Protocol:")
        print(f"{'='*80}")
        sr_values = [r.success_rate for r in self.results]
        protocols = set(r.communication_type for r in self.results)
        for proto in sorted(protocols):
            subset = [r for r in self.results if r.communication_type == proto]
            avg_sr = sum(r.success_rate for r in subset) / len(subset)
            print(f"  {proto.upper()}: avg SR = {avg_sr:.2%} ({len(subset)} cases)")

    def export_csv(self, output_path: str):
        """Export results to CSV."""
        if pd is None:
            print("pandas is required for CSV export. Install with: uv sync --extra analysis")
            return
        if not self.results:
            print("No results to export.")
            return
        df = pd.DataFrame(
            [
                {
                    "protocol": r.communication_type,
                    "model": r.model,
                    "case_id": r.case_id,
                    "case_name": r.case_name,
                    "num_agents": r.num_agents,
                    "rounds_run": r.rounds_run,
                    "success_rate": r.success_rate,
                    "token_efficiency": r.token_per_round,
                    "communication_density": r.communication_density,
                    "total_messages": r.total_messages,
                    "total_tokens": r.total_tokens,
                    "timestamp": r.timestamp,
                }
                for r in self.results
            ]
        )
        df.to_csv(output_path, index=False)
        print(f"\nResults exported to: {output_path}")


def main():
    workspace_dir = sys.argv[1] if len(sys.argv) > 1 else "./workspace"
    output_file = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    print(f"SILO-BENCH Analysis Tool")
    print(f"Workspace: {workspace_dir}")
    print(f"{'='*80}")

    analyzer = MASBenchmarkAnalyzer(workspace_dir)
    analyzer.analyze_all()

    if output_file:
        analyzer.export_csv(output_file)

    print(f"\n{'='*80}")
    print("Analysis complete.")


if __name__ == "__main__":
    main()
