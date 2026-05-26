"""
SILO-Bench: Multi-Agent System Benchmark Generator
Main entry point for generating benchmark cases
"""

import json
import os
from typing import Dict, List, Any, Union
from datetime import datetime

# Import paradigm generators
from paradigm_i import generate_paradigm_i_cases
from paradigm_ii import generate_paradigm_ii_cases
from paradigm_iii import generate_paradigm_iii_cases


class BenchmarkGenerator:
    """Main benchmark generator for SILO-Bench"""

    def __init__(self, num_agents: int = 5, output_dir: str = "./benchmarks"):
        """
        Initialize the benchmark generator

        Args:
            num_agents: Number of agents in the system (default: 5)
            output_dir: Directory to save generated benchmarks
        """
        self.num_agents = num_agents
        self.output_dir = output_dir
        self.system_prompt_template = self._get_system_prompt_template()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def _get_system_prompt_template(self) -> str:
        """Get placeholder system prompt - actual prompt is generated at runtime by src/utils/prompts.py"""
        return """[PLACEHOLDER] This system_prompt will be overridden at runtime by protocol-specific prompts.

The execution engine (src/engine.py) generates the actual system prompt based on the chosen communication protocol:
- msg (P2P): send_message, receive_messages, wait, submit_result
- broadcast: broadcast_message, receive_messages, list_agents, wait, submit_result
- sfs (Shared File System): list_files, read_file, write_file, delete_file, wait, submit_result

See src/utils/prompts.py for the actual runtime prompt templates.

Agent ID: {agent_id}
Total agents: {num_agents}
Max agent ID: {max_id}"""

    def _build_verification_logic(self, expected_output: Any, is_segmented: bool, float_tol: float = 0.01) -> str:
        """
        Build an executable (Python-evaluable) verification expression string.

        Assumes evaluator provides:
          - agent_outputs: List[Any] length == num_agents
          - expected_output: gold output
          - num_agents: int
        """
        if is_segmented:
            # expected_output must be List[Any] with per-agent expected values
            return (
                "len(agent_outputs) == num_agents and "
                "all(agent_outputs[i] == expected_output[i] for i in range(num_agents))"
            )

        # Global output: all agents submit the same final answer
        if isinstance(expected_output, float):
            return (
                f"len(agent_outputs) == num_agents and "
                f"all(abs(agent_outputs[i] - expected_output) <= {float_tol} for i in range(num_agents))"
            )

        return (
            "len(agent_outputs) == num_agents and "
            "all(agent_outputs[i] == expected_output for i in range(num_agents))"
        )

    def _safe_prompt_format(self, template: str, **kwargs) -> str:
        """
        Safely substitute ONLY known placeholders like {agent_id}, {num_agents}, {max_id}, {input_shard}.
        Any other {...} patterns (e.g., dictionary examples {3: 3, 7: 2}) are left unchanged.
        This avoids str.format() crashing on prompts that contain braces for examples.
        """
        out = template
        for k, v in kwargs.items():
            out = out.replace("{" + k + "}", str(v))
        return out

    def _create_case_structure(
            self,
            case_id: str,
            case_name: str,
            paradigm: str,
            leetcode_url: str,
            description: str,
            input_data: List[Any],
            expected_output: Union[Any, List[Any]],
            verification_logic: str,
            optimal_topology: str,
            optimal_message_count: str,
            output_type: str = "distributed",
            is_segmented: bool = False,
    ) -> Dict:
        """
        Create a standardized case structure.

        Args:
            output_type: Always "distributed" - all agents submit results.
            is_segmented:
                - False: GLOBAL output task, all agents submit the same expected_output
                - True : SEGMENTED output task, expected_output MUST be a list of length num_agents,
                         and each agent submits only its own segment/value.
        """

        # --- segmentation is now explicit (NO more len(expected_output)==num_agents heuristic) ---
        if is_segmented:
            if not isinstance(expected_output, list) or len(expected_output) != self.num_agents:
                raise ValueError(
                    f"Segmented task {case_id} requires expected_output as a list of length num_agents "
                    f"({self.num_agents}); got {type(expected_output)} "
                    f"len={len(expected_output) if isinstance(expected_output, list) else 'N/A'}"
                )
            per_agent_outputs = expected_output
        else:
            per_agent_outputs = [expected_output] * self.num_agents

        # Always store an executable verification expression.
        # Keep the original human-written verification_logic as a hint only.
        executable_verification_logic = self._build_verification_logic(
            expected_output=expected_output,
            is_segmented=is_segmented,
        )

        # Generate agent-specific prompts
        agent_prompts = []
        for i in range(self.num_agents):
            system_prompt = self.system_prompt_template.format(
                num_agents=self.num_agents,
                agent_id=i,
                max_id=self.num_agents - 1,
            )

            input_shard = input_data[i] if i < len(input_data) else None
            user_prompt = self._safe_prompt_format(
                description,
                agent_id=i,
                num_agents=self.num_agents,
                max_id=self.num_agents - 1,
                input_shard=input_shard,
            )

            agent_prompts.append(
                {
                    "agent_id": i,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "input_shard": input_shard,
                    "expected_output": per_agent_outputs[i],
                }
            )

        return {
            "case_id": case_id,
            "case_name": case_name,
            "paradigm": paradigm,
            "leetcode": {
                "url": leetcode_url,
                "description": "This case is inspired by the LeetCode problem. The multi-agent version tests distributed computation and communication efficiency.",
            },
            "metadata": {
                "num_agents": self.num_agents,
                "optimal_topology": optimal_topology,
                "optimal_message_count": optimal_message_count,
                "theoretical_complexity": self._get_complexity_class(paradigm),
                "output_type": "distributed",
                "is_segmented": is_segmented,
            },
            "task_description": description,
            "agent_configs": agent_prompts,
            "expected_output": {
                "type": "distributed",
                "per_agent_values": per_agent_outputs,
                "is_segmented": is_segmented,
                # store executable logic here
                "verification_logic": executable_verification_logic,
                # keep original hint for human readability/debug
                "verification_logic_hint": verification_logic,
                "format_description": "ALL agents must submit their results using submit_result(answer). "
                                      + (
                                          "Each agent submits their own portion of the result."
                                          if is_segmented
                                          else "All agents should submit the same final answer after coordination."
                                      ),
            },
            "evaluation_metrics": {
                "success_rate": "Percentage of agents that submitted correct answers over K trials",
                "round_to_completion": "Number of communication rounds needed",
                "communication_redundancy_ratio": "M_total / M_opt",
                "topological_fidelity": "Jaccard(E_empirical, E_optimal)",
            },
        }

    def _get_complexity_class(self, paradigm: str) -> str:
        """Get theoretical complexity class for a paradigm"""
        complexity_map = {
            "Paradigm I": "O(N) - MapReduce/Aggregation",
            "Paradigm II": "O(N) - Structured Mesh with Locality",
            "Paradigm III": "O(N log N) or O(N²) - Global/Shuffle"
        }
        return complexity_map.get(paradigm, "Unknown")

    def generate_all_benchmarks(self):
        """Generate all benchmark cases"""
        print(f"Generating SILO-Bench with {self.num_agents} agents...")
        print(f"Output directory: {self.output_dir}")

        all_cases = []

        # Generate Paradigm I cases (MapReduce/Aggregation)
        print("\n=== Generating Paradigm I Cases (MapReduce/Aggregation) ===")
        paradigm_i_cases = generate_paradigm_i_cases(
            self.num_agents,
            self._create_case_structure
        )
        all_cases.extend(paradigm_i_cases)
        print(f"Generated {len(paradigm_i_cases)} cases for Paradigm I")

        # Generate Paradigm II cases (Structured Mesh)
        print("\n=== Generating Paradigm II Cases (Structured Mesh) ===")
        paradigm_ii_cases = generate_paradigm_ii_cases(
            self.num_agents,
            self._create_case_structure
        )
        all_cases.extend(paradigm_ii_cases)
        print(f"Generated {len(paradigm_ii_cases)} cases for Paradigm II")

        # Generate Paradigm III cases (Unstructured/Global)
        print("\n=== Generating Paradigm III Cases (Unstructured/Global) ===")
        paradigm_iii_cases = generate_paradigm_iii_cases(
            self.num_agents,
            self._create_case_structure
        )
        all_cases.extend(paradigm_iii_cases)
        print(f"Generated {len(paradigm_iii_cases)} cases for Paradigm III")

        # Save individual cases
        for case in all_cases:
            case_file = os.path.join(self.output_dir, f"{case['case_id']}_n{self.num_agents}.json")
            with open(case_file, 'w', encoding='utf-8') as f:
                json.dump(case, f, indent=2, ensure_ascii=False)
            print(f"Saved: {case_file}")

        # Save combined benchmark
        benchmark = {
            "metadata": {
                "name": "SILO-Bench",
                "version": "1.0",
                "description": "Multi-Agent System Benchmark for Social Reasoning and Topological Adaptation",
                "num_agents": self.num_agents,
                "total_cases": len(all_cases),
                "generated_at": datetime.now().isoformat()
            },
            "cases": all_cases
        }

        combined_file = os.path.join(self.output_dir, "silo_bench_full.json")
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(benchmark, f, indent=2, ensure_ascii=False)
        print(f"\nSaved combined benchmark: {combined_file}")

        # Generate summary
        self._generate_summary(all_cases)

        print(f"\n✅ Successfully generated {len(all_cases)} benchmark cases!")
        return all_cases

    def _generate_summary(self, cases: List[Dict]):
        """Generate a summary report"""
        summary = {
            "total_cases": len(cases),
            "paradigm_i_cases": len([c for c in cases if c["paradigm"] == "Paradigm I"]),
            "paradigm_ii_cases": len([c for c in cases if c["paradigm"] == "Paradigm II"]),
            "paradigm_iii_cases": len([c for c in cases if c["paradigm"] == "Paradigm III"]),
            "num_agents": self.num_agents,
            "case_list": [
                {
                    "case_id": c["case_id"],
                    "name": c["case_name"],
                    "paradigm": c["paradigm"],
                    "optimal_topology": c["metadata"]["optimal_topology"],
                    "is_segmented": c["metadata"]["is_segmented"]
                }
                for c in cases
            ]
        }

        summary_file = os.path.join(self.output_dir, "benchmark_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Saved summary: {summary_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SILO-Bench: Multi-Agent System Benchmark"
    )
    parser.add_argument(
        "--num-agents", "-n",
        type=int,
        default=None,
        help="Number of agents (deprecated, use --agent-counts instead)"
    )
    parser.add_argument(
        "--agent-counts", "-c",
        type=int,
        nargs="+",
        default=[2, 5, 10, 20, 50, 100],
        help="List of agent counts to generate benchmarks for (default: 2 5 10 20 50 100)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="../benchmarks",
        help="Output directory for benchmark files (default: ../benchmarks)"
    )

    args = parser.parse_args()

    # Handle backward compatibility with --num-agents
    if args.num_agents is not None:
        agent_counts = [args.num_agents]
        print(f"Note: --num-agents is deprecated. Use --agent-counts instead.")
    else:
        agent_counts = args.agent_counts

    # Validate agent counts
    for count in agent_counts:
        if count < 2:
            print(f"Error: Number of agents must be at least 2, got {count}")
            return

    # Generate benchmarks for each agent count
    for count in agent_counts:
        print(f"\n{'='*60}")
        print(f"Generating benchmarks for {count} agents...")
        print(f"{'='*60}")

        generator = BenchmarkGenerator(
            num_agents=count,
            output_dir=args.output_dir
        )
        generator.generate_all_benchmarks()

    print(f"\n{'='*60}")
    print(f"All benchmarks generated successfully!")
    print(f"Output directory: {args.output_dir}")
    print(f"Agent counts: {agent_counts}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()