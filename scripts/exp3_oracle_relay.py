#!/usr/bin/env python3
"""
Experiment 3: Oracle Relay.

Runs the evidence relay pipeline using GOLD-LABEL selection instead of
LLM-scored selection. This establishes the ceiling for local importance
scoring: if the agent knew exactly which extracted units are gold-critical,
how well would relay perform?

Oracle selection: for each agent, pick the extracted unit(s) with highest
numeric overlap against that agent's input_shard (the gold critical data).

Reuses existing extraction outputs from run_qwen235b_n5 and run_qwen235b_n10
(no new extraction/scoring API calls). Only the aggregation step uses the API.

Usage:
    python scripts/exp3_oracle_relay.py
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from collections import defaultdict
from scripts.compute_audit_metrics import (
    reconstruct_states_and_scores,
    get_gold_units,
    align_gold_to_transmitted,
    aggregate_audit,
    MAX_STATES,
)
from src.eval.silo_bench_loader import load_silobench, shards_from_silobench, silobench_exact_match
from src.protocols.relay import (
    _aggregate_evidence_board_batch,
    _build_evidence_board_prompt,
    _AGGREGATION_SYSTEM,
)
from src.protocols.base import ProtocolResult
from utility.apis.openrouter_api import batch_request, setup_response_log
from utility.apis.base import APIRequest

MODEL = "qwen/qwen3-235b-a22b-2507"
MAX_TOKENS = 4096
MAX_WORKERS = 64
K = MAX_STATES  # 3

RUN_DIRS = {
    "n5": os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n5"),
    "n10": os.path.join(os.path.dirname(__file__), "..", "results", "run_qwen235b_n10"),
}

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "results", "exp3_oracle_relay"
)


# ---------------------------------------------------------------------------
# Oracle selection
# ---------------------------------------------------------------------------

def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


def oracle_select(
    states: list[str],
    gold_text: str,
    k: int,
) -> list[str]:
    """Select top-k extracted units by numeric overlap with gold shard text."""
    if not states:
        return []
    gold_nums = _numbers_in(gold_text)
    gold_toks = set(gold_text.lower().split())

    scored = []
    for unit in states:
        unit_nums = _numbers_in(unit)
        unit_toks = set(unit.lower().split())

        if gold_nums and unit_nums:
            score = len(gold_nums & unit_nums) / len(gold_nums)
        else:
            score = 0.0
        if gold_toks and unit_toks:
            denom = len(gold_toks | unit_toks)
            j = len(gold_toks & unit_toks) / denom if denom else 0.0
            score = max(score, j)
        scored.append((score, unit))

    scored.sort(key=lambda x: -x[0])
    return [u for _, u in scored[:k]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "api_responses.jsonl")
    setup_response_log(log_path)
    print(f"API log: {log_path}")

    all_instance_results = []
    all_audit_records = []

    for tier, run_dir in RUN_DIRS.items():
        n_agents_val = 5 if tier == "n5" else 10
        print(f"\n=== Oracle Relay — {tier} (n={n_agents_val}) ===")

        # Load existing api_responses
        resp_path = os.path.join(run_dir, "api_responses.jsonl")
        with open(resp_path) as f:
            responses = [json.loads(l) for l in f if l.strip()]
        print(f"  {len(responses)} existing API responses")

        states_by_id, _ = reconstruct_states_and_scores(responses)
        print(f"  {len(states_by_id)} instances with extracted units")

        instances = load_silobench(n_agents_filter=n_agents_val)
        print(f"  {len(instances)} instances")

        # Load correctness for existing protocols (to compare)
        run_results_path = os.path.join(run_dir, "results.json")
        with open(run_results_path) as f:
            run_results = json.load(f)

        # Build oracle-selected units per instance
        instances_to_run = []
        selected_per_inst = []

        for inst in instances:
            inst_id = inst["id"]
            if inst_id not in states_by_id:
                print(f"  WARNING: no states for {inst_id}")
                continue

            inst_states_by_agent = states_by_id[inst_id]
            gold_units = get_gold_units(inst)  # list of (agent_id, shard_text)

            # Build selected list: oracle selection per agent
            n_actual = len(inst["agent_configs"])
            selected = []
            for agent_idx in range(n_actual):
                agent_states = inst_states_by_agent.get(agent_idx, [])
                # Find gold text for this agent
                gold_text = ""
                for (ag_id, gt) in gold_units:
                    if ag_id == agent_idx:
                        gold_text = gt
                        break
                oracle_units = oracle_select(agent_states, gold_text, K)
                selected.append(oracle_units)

            instances_to_run.append(inst)
            selected_per_inst.append(selected)

        print(f"  Running aggregation for {len(instances_to_run)} instances...")

        # Batch aggregation
        agg_requests = []
        comm_tokens_list = []

        for inst, selected in zip(instances_to_run, selected_per_inst):
            all_flat = [u for ag_units in selected for u in ag_units]
            from src.protocols.base import count_tokens_approx
            comm_tokens_list.append(sum(count_tokens_approx(u) for u in all_flat))
            agg_requests.append(APIRequest(
                system_query=_AGGREGATION_SYSTEM,
                user_query=_build_evidence_board_prompt(selected, inst["question"]),
                model=MODEL,
                max_tokens=MAX_TOKENS,
                metadata={"instance_id": inst["id"], "phase": "oracle_relay_aggregation"},
            ))

        responses_agg = batch_request(agg_requests, max_workers=MAX_WORKERS,
                                      desc=f"oracle_relay_agg_{tier}")

        from src.protocols.relay import _parse_units
        from src.protocols.base import extract_answer

        for inst, selected, resp, comm_tok in zip(
            instances_to_run, selected_per_inst, responses_agg, comm_tokens_list
        ):
            inst_id = inst["id"]
            raw = resp.content.strip() if resp.success and resp.content.strip() else ""
            pred = extract_answer(raw) if raw else ""
            f1 = silobench_exact_match(pred, inst)
            correct = f1 >= 1.0

            # Compute audit metrics for oracle relay
            transmitted = [u for ag in selected for u in ag]
            gold_units = get_gold_units(inst)
            alignments = align_gold_to_transmitted(gold_units, transmitted)
            n_covered = sum(1 for a in alignments if a["covered"])
            n_gold = len(gold_units)
            crit_recall = n_covered / n_gold if n_gold > 0 else 1.0
            agg_fail = (not correct) and (crit_recall >= 1.0)

            all_instance_results.append({
                "protocol": "oracle_relay",
                "id": inst_id,
                "pred": pred,
                "gold": inst["answer"],
                "f1": f1,
                "correct": correct,
                "comm_tokens": comm_tok,
                "total_llm_tokens": resp.usage.get("total_tokens", 0),
            })

            all_audit_records.append({
                "inst_id": inst_id,
                "protocol": "oracle_relay",
                "n_transmitted": len(transmitted),
                "n_gold": n_gold,
                "n_covered": n_covered,
                "crit_recall": crit_recall,
                "omission": 1.0 - crit_recall,
                "redundancy": 0.0,
                "useful_budget": n_covered / len(transmitted) if transmitted else 0.0,
                "agg_fail": agg_fail,
                "correct": correct,
            })

    # ── Aggregate results ──────────────────────────────────────────────────────
    n = len(all_instance_results)
    acc = sum(r["correct"] for r in all_instance_results) / n if n > 0 else 0.0
    mean_comm = sum(r["comm_tokens"] for r in all_instance_results) / n if n > 0 else 0.0

    audit_summary = aggregate_audit(all_audit_records)

    print("\n=== Oracle Relay Results (Silo-Bench, Qwen-235B, n5+n10 combined) ===")
    print(f"  Instances: {n}")
    print(f"  Accuracy:  {acc*100:.1f}%")
    print(f"  Comm tok:  {mean_comm:.0f}")
    print(f"  CritRec:   {audit_summary.get('crit_recall', float('nan')):.3f}")
    print(f"  Omission:  {audit_summary.get('omission', float('nan')):.3f}")
    print(f"  AggFail:   {audit_summary.get('agg_fail_pct', float('nan')):.1f}%")

    print("\n=== Comparison with existing protocols ===")
    print(f"{'Protocol':<30} {'Acc%':>8} {'CommTok':>9} {'CritRec':>9} {'AggFail%':>9}")
    print("-" * 70)
    # Pull from existing results
    for name, label in [
        ("random_relay", "Random Relay"),
        ("score_ranked_relay", "Score-Ranked Relay"),
        ("redundancy_aware_relay", "Redundancy-Aware Relay"),
    ]:
        # Reload from existing results
        n5_r = json.load(open(os.path.join(RUN_DIRS["n5"], "results.json")))
        n10_r = json.load(open(os.path.join(RUN_DIRS["n10"], "results.json")))
        if name in n5_r["table"] and name in n10_r["table"]:
            a5 = n5_r["table"][name]["acc"]
            a10 = n10_r["table"][name]["acc"]
            n5 = n5_r["table"][name]["n"]
            n10 = n10_r["table"][name]["n"]
            combined_acc = (a5 * n5 + a10 * n10) / (n5 + n10)
            c5 = n5_r["table"][name]["mean_comm_tokens"]
            c10 = n10_r["table"][name]["mean_comm_tokens"]
            combined_comm = (c5 * n5 + c10 * n10) / (n5 + n10)
            print(f"{label:<30} {combined_acc*100:>8.1f} {combined_comm:>9.0f} {'  ---':>9} {'  ---':>9}")

    print(f"{'Oracle Relay':<30} {acc*100:>8.1f} {mean_comm:>9.0f} "
          f"{audit_summary.get('crit_recall', 0):>9.3f} "
          f"{audit_summary.get('agg_fail_pct', 0):>8.1f}%")

    full_r5 = json.load(open(os.path.join(RUN_DIRS["n5"], "results.json")))
    full_r10 = json.load(open(os.path.join(RUN_DIRS["n10"], "results.json")))
    if "full_sharing" in full_r5["table"] and "full_sharing" in full_r10["table"]:
        a5 = full_r5["table"]["full_sharing"]["acc"]
        a10 = full_r10["table"]["full_sharing"]["acc"]
        n5 = full_r5["table"]["full_sharing"]["n"]
        n10 = full_r10["table"]["full_sharing"]["n"]
        full_acc = (a5 * n5 + a10 * n10) / (n5 + n10)
        c5 = full_r5["table"]["full_sharing"]["mean_comm_tokens"]
        c10 = full_r10["table"]["full_sharing"]["mean_comm_tokens"]
        full_comm = (c5 * n5 + c10 * n10) / (n5 + n10)
        print(f"{'Full Evidence Sharing':<30} {full_acc*100:>8.1f} {full_comm:>9.0f} {'  1.000':>9} {'  ---':>9}")

    # ── Save ──────────────────────────────────────────────────────────────────
    out = {
        "protocol": "oracle_relay",
        "n_instances": n,
        "acc": acc,
        "mean_comm_tokens": mean_comm,
        "audit_summary": audit_summary,
        "instance_results": all_instance_results,
        "audit_records": all_audit_records,
    }
    out_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    jsonl_path = os.path.join(OUTPUT_DIR, "per_instance_results.jsonl")
    with open(jsonl_path, "w") as f:
        for r in all_instance_results:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults saved to: {OUTPUT_DIR}/")
    return out


if __name__ == "__main__":
    main()
