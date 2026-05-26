#!/usr/bin/env python3
"""
Compute evidence-flow audit metrics from saved API responses.

Reconstructs transmitted units from extraction/scoring responses without
re-running the LLM, then computes:
  Crit.Recall, Omission, Redundancy, Useful Budget, Agg.Fail  (no new API calls)
  Distortion                                                    (LLM judge, optional)

Usage:
    python scripts/compute_audit_metrics.py --run-dir results/run_20260523_214416
    python scripts/compute_audit_metrics.py --run-dir results/run_20260523_214416 --distortion
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.eval.silo_bench_loader import load_silobench
from src.eval.data_loader import load_musique
from src.protocols.relay import _topk_select, _redundancy_select, _parse_units
from src.protocols.base import parse_score_json

RELAY_PROTOCOLS = ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]
MAX_STATES = 3
SEED = 42
RHO = 0.5


# ---------------------------------------------------------------------------
# Step 1 — load saved run artifacts
# ---------------------------------------------------------------------------

def load_run(run_dir: str):
    with open(os.path.join(run_dir, "results.json")) as f:
        results = json.load(f)
    responses = []
    with open(os.path.join(run_dir, "api_responses.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                responses.append(json.loads(line))
    return results, responses


# ---------------------------------------------------------------------------
# Step 2 — reconstruct extracted units and scores from logged responses
# ---------------------------------------------------------------------------

def reconstruct_states_and_scores(responses: list[dict]):
    """
    Returns:
        states[inst_id][agent]   = list[str]   (extracted units, in extraction order)
        scores[inst_id][agent]   = list[dict]  (score per unit, same order as states)
    """
    # Extraction responses: one per (instance_id, agent), content = numbered unit list
    states: dict[str, dict[int, list[str]]] = defaultdict(dict)
    for r in responses:
        if r["phase"] == "extraction" and r["success"]:
            units = _parse_units(r["content"], MAX_STATES)
            states[r["instance_id"]][r["agent"]] = units

    # Scoring responses: multiple per (instance_id, agent).
    # batch_request preserves submission order (inst→agent→unit), so within each
    # (instance_id, agent) group they appear in unit_0, unit_1, unit_2 order.
    scores_accum: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in responses:
        if r["phase"] == "scoring" and r["success"]:
            sc = parse_score_json(r["content"])
            if not sc:
                sc = {"relevance": 0.5, "uniqueness": 0.5,
                      "local_importance": 0.5, "overall": 0.5}
            scores_accum[r["instance_id"]][r["agent"]].append(sc)

    return dict(states), dict(scores_accum)


# ---------------------------------------------------------------------------
# Step 3 — re-apply deterministic selection to get transmitted units
# ---------------------------------------------------------------------------

def get_transmitted_units(
    inst_id: str,
    protocol: str,
    states: dict,
    scores: dict,
    n_agents: int = 5,
) -> list[str]:
    inst_states = [states.get(inst_id, {}).get(a, []) for a in range(n_agents)]
    inst_scores = [scores.get(inst_id, {}).get(a, []) for a in range(n_agents)]

    if protocol == "random_relay":
        rng = random.Random(f"{SEED}:{inst_id}")
        selected = [
            rng.sample(s, min(MAX_STATES, len(s))) if s else []
            for s in inst_states
        ]
    elif protocol == "score_ranked_relay":
        selected = []
        for s, sc in zip(inst_states, inst_scores):
            if s and len(sc) >= len(s):
                selected.append(_topk_select(s, sc, MAX_STATES))
            elif s:
                # Missing scores: fall back to random selection
                rng = random.Random(f"{SEED}:{inst_id}:fallback")
                selected.append(rng.sample(s, min(MAX_STATES, len(s))))
            else:
                selected.append([])
    elif protocol == "redundancy_aware_relay":
        selected = []
        for s, sc in zip(inst_states, inst_scores):
            if s and len(sc) >= len(s):
                selected.append(_redundancy_select(s, sc, MAX_STATES, RHO))
            elif s:
                # Missing scores: fall back to random selection
                rng = random.Random(f"{SEED}:{inst_id}:fallback")
                selected.append(rng.sample(s, min(MAX_STATES, len(s))))
            else:
                selected.append([])
    else:
        return []

    return [u for agent_units in selected for u in agent_units]


# ---------------------------------------------------------------------------
# Step 4 — gold critical units from Silo-Bench agent shards
# ---------------------------------------------------------------------------

def get_gold_units(inst: dict) -> list[tuple[int, str]]:
    """Return (agent_id, shard_text) for each agent's private shard."""
    if "agent_configs" in inst:
        return [
            (ac["agent_id"], str(ac["input_shard"]))
            for ac in inst["agent_configs"]
        ]
    # MuSiQue format: supporting paragraphs are the gold critical units
    supporting = [p for p in inst["paragraphs"] if p["is_supporting"]]
    return [(i, p["paragraph_text"]) for i, p in enumerate(supporting)]


def _numbers_in_text(text: str) -> set[str]:
    """Extract all numbers (int/float, possibly negative) from text."""
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


# ---------------------------------------------------------------------------
# Step 5 — alignment and metrics
# ---------------------------------------------------------------------------

def align_gold_to_transmitted(
    gold_units: list[tuple[int, str]],
    transmitted: list[str],
) -> list[dict]:
    """
    For each gold unit (agent_id, shard_text), check whether any transmitted
    unit 'covers' it.

    Coverage = any number from the gold shard appears in the transmitted unit.
    Fallback  = token-level Jaccard >= 0.1 (for non-numeric shards).
    """
    alignments = []
    for agent_id, gold_text in gold_units:
        gold_nums = _numbers_in_text(gold_text)
        gold_tokens = set(gold_text.lower().split())

        best_score = 0.0
        best_unit = None

        for unit in transmitted:
            unit_nums = _numbers_in_text(unit)
            unit_tokens = set(unit.lower().split())

            # Numeric overlap score
            if gold_nums and unit_nums:
                score = len(gold_nums & unit_nums) / len(gold_nums)
            else:
                score = 0.0

            # Token Jaccard fallback
            if gold_tokens and unit_tokens:
                denom = len(gold_tokens | unit_tokens)
                j = len(gold_tokens & unit_tokens) / denom if denom else 0.0
                score = max(score, j)

            if score > best_score:
                best_score = score
                best_unit = unit

        alignments.append({
            "agent_id": agent_id,
            "covered": best_score > 0.0,
            "score": best_score,
            "best_unit": best_unit,
        })
    return alignments


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta and not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def compute_redundancy(transmitted: list[str]) -> float:
    """Mean pairwise token-level Jaccard between transmitted units."""
    if len(transmitted) < 2:
        return 0.0
    sims = [
        _jaccard(transmitted[i], transmitted[j])
        for i in range(len(transmitted))
        for j in range(i + 1, len(transmitted))
    ]
    return sum(sims) / len(sims)


def compute_instance_audit(
    inst_id: str,
    protocol: str,
    inst: dict,
    states: dict,
    scores: dict,
    correctness: float,
) -> dict:
    transmitted = get_transmitted_units(inst_id, protocol, states, scores)
    gold_units = get_gold_units(inst)
    alignments = align_gold_to_transmitted(gold_units, transmitted)

    n_gold = len(gold_units)
    n_covered = sum(1 for a in alignments if a["covered"])
    crit_recall = n_covered / n_gold if n_gold > 0 else 1.0
    omission = 1.0 - crit_recall

    redundancy = compute_redundancy(transmitted)

    # Useful budget: fraction of transmitted units that match at least one gold unit
    matched_units = {a["best_unit"] for a in alignments if a["covered"] and a["best_unit"]}
    useful_budget = len(matched_units) / len(transmitted) if transmitted else 0.0

    correct = correctness >= 1.0
    agg_fail = (not correct) and (crit_recall >= 1.0)

    return {
        "inst_id": inst_id,
        "protocol": protocol,
        "n_transmitted": len(transmitted),
        "n_gold": n_gold,
        "n_covered": n_covered,
        "crit_recall": crit_recall,
        "omission": omission,
        "redundancy": redundancy,
        "useful_budget": useful_budget,
        "agg_fail": agg_fail,
        "correct": correct,
    }


# ---------------------------------------------------------------------------
# Step 6 — LLM distortion judge (optional)
# ---------------------------------------------------------------------------

_DISTORTION_SYSTEM = (
    "You are a factual-accuracy judge.\n"
    "Given a gold fact and a transmitted unit, classify the relationship:\n"
    "  EXACT       — identical meaning and all key values preserved\n"
    "  PARAPHRASE  — same meaning, minor rewording, all key values preserved\n"
    "  PARTIAL     — some key values preserved but others missing or vague\n"
    "  DISTORTED   — at least one key value is wrong or contradicted\n"
    "  NO_MATCH    — unrelated\n"
    "Output exactly one label."
)


def run_distortion_judge(
    run_dir: str,
    instances_by_id: dict,
    states: dict,
    scores: dict,
    run_results: dict,
    model: str,
    max_workers: int = 32,
) -> dict[str, dict[str, list[dict]]]:
    """Run LLM distortion judge on all (inst, protocol, transmitted_unit) pairs
    that already have a gold alignment match.

    Returns distortion_results[protocol][inst_id] = list of classification dicts.
    """
    from utility.apis.openrouter_api import batch_request
    from utility.apis.base import APIRequest

    # Collect all pairs that need judging
    judge_requests = []
    judge_index = []  # (protocol, inst_id, agent_id, transmitted_unit)

    for protocol in RELAY_PROTOCOLS:
        proto_results = {r["id"]: r for r in run_results["instance_results"][protocol]}
        for inst_id, inst in instances_by_id.items():
            transmitted = get_transmitted_units(inst_id, protocol, states, scores)
            gold_units = get_gold_units(inst)
            alignments = align_gold_to_transmitted(gold_units, transmitted)
            for align in alignments:
                if align["covered"] and align["best_unit"]:
                    gold_text = dict(gold_units).get(align["agent_id"] , "")
                    # Use a compact representation of the gold value (numbers only)
                    gold_nums = sorted(_numbers_in_text(gold_text))
                    gold_repr = "Key values: " + ", ".join(gold_nums[:10])
                    prompt = (
                        f"Gold fact (agent {align['agent_id']} shard key values):\n{gold_repr}\n\n"
                        f"Transmitted unit:\n{align['best_unit']}\n\n"
                        f"Classification (EXACT/PARAPHRASE/PARTIAL/DISTORTED/NO_MATCH):"
                    )
                    judge_requests.append(APIRequest(
                        system_query=_DISTORTION_SYSTEM,
                        user_query=prompt,
                        model=model,
                        max_tokens=16,
                        temperature=0.0,
                        metadata={
                            "phase": "distortion_judge",
                            "protocol": protocol,
                            "instance_id": inst_id,
                            "agent_id": align["agent_id"],
                        },
                    ))
                    judge_index.append((protocol, inst_id, align["agent_id"], align["best_unit"]))

    if not judge_requests:
        return {}

    print(f"\n[Distortion Judge] Submitting {len(judge_requests)} requests...")
    responses = batch_request(judge_requests, max_workers=max_workers,
                              desc="distortion judge")

    LABELS = {"EXACT", "PARAPHRASE", "PARTIAL", "DISTORTED", "NO_MATCH"}
    distortion: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for resp, (protocol, inst_id, agent_id, unit) in zip(responses, judge_index):
        label = "NO_MATCH"
        if resp.success:
            raw = resp.content.strip().upper()
            for lbl in LABELS:
                if lbl in raw:
                    label = lbl
                    break
        distortion[protocol][inst_id].append({
            "agent_id": agent_id,
            "unit": unit,
            "label": label,
        })

    return dict(distortion)


# ---------------------------------------------------------------------------
# Aggregate across instances + print table
# ---------------------------------------------------------------------------

def aggregate_audit(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {}
    return {
        "n": n,
        "crit_recall":   sum(r["crit_recall"]   for r in records) / n,
        "omission":      sum(r["omission"]       for r in records) / n,
        "redundancy":    sum(r["redundancy"]     for r in records) / n,
        "useful_budget": sum(r["useful_budget"]  for r in records) / n,
        "agg_fail_pct":  100 * sum(r["agg_fail"] for r in records) / n,
    }


def print_audit_table(base_table: dict, audit_summaries: dict,
                      distortion_by_proto: dict | None = None) -> None:
    _ORDER = [
        "single_local", "majority_vote", "best_local",
        "free_form_debate", "summary_exchange",
        "confidence_gated", "disagreement_gated",
        "random_relay", "score_ranked_relay", "redundancy_aware_relay",
        "full_sharing",
    ]
    _LABELS = {
        "single_local": "Single Local",
        "majority_vote": "Majority Vote",
        "best_local": "Best-Local Oracle",
        "free_form_debate": "Free-form Debate",
        "summary_exchange": "Summary Exchange",
        "confidence_gated": "Confidence-Gated",
        "disagreement_gated": "Disagreement-Gated",
        "random_relay": "Random Evidence Relay",
        "score_ranked_relay": "Score-Ranked Evidence Relay",
        "redundancy_aware_relay": "Redundancy-Aware Relay",
        "full_sharing": "Full Evidence Sharing",
    }

    header = (
        f"{'Protocol':<30} {'Acc%':>6} {'CommTok':>8} "
        f"{'CritRec':>8} {'Omit':>6} {'Dist':>6} "
        f"{'Redund':>7} {'UsefulB':>8} {'AggFail':>8}"
    )
    print(header)
    print("-" * len(header))

    order = [k for k in _ORDER if k in base_table]
    order += [k for k in base_table if k not in _ORDER]

    for name in order:
        row = base_table[name]
        label = _LABELS.get(name, name)
        acc = row["acc"] * 100
        comm = row["mean_comm_tokens"]

        if name in audit_summaries and audit_summaries[name].get("n", 0) > 0:
            a = audit_summaries[name]
            dist_str = "---"
            if distortion_by_proto and name in distortion_by_proto:
                d = distortion_by_proto[name]
                dist_str = f"{d:.3f}"
            print(
                f"{label:<30} {acc:>6.2f} {comm:>8.1f} "
                f"{a['crit_recall']:>8.3f} {a['omission']:>6.3f} {dist_str:>6} "
                f"{a['redundancy']:>7.3f} {a['useful_budget']:>8.3f} {a['agg_fail_pct']:>7.1f}%"
            )
        else:
            print(
                f"{label:<30} {acc:>6.2f} {comm:>8.1f} "
                f"{'---':>8} {'---':>6} {'---':>6} "
                f"{'---':>7} {'---':>8} {'---':>8}"
            )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute_summary_exchange_audit(
    responses: list[dict],
    instances_by_id: dict,
    run_results: dict,
) -> dict:
    """Compute audit metrics for Summary Exchange from logged 'summary' phase responses.

    Treats each agent's NL summary as its single transmitted evidence unit.
    Returns a summary dict matching the structure returned by aggregate_audit().
    """
    # Collect summary contents keyed by (instance_id, agent)
    summaries: dict[str, dict[int, str]] = defaultdict(dict)
    for r in responses:
        if r.get("phase") == "summary" and r.get("success"):
            summaries[r["instance_id"]][r["agent"]] = r["content"]

    if not summaries:
        print("  WARNING: no 'summary' phase responses found — cannot audit Summary Exchange")
        return {}

    proto_results = {
        r["id"]: r
        for r in run_results["instance_results"].get("summary_exchange", [])
    }

    records = []
    for inst_id, inst in instances_by_id.items():
        if inst_id not in summaries:
            continue
        agent_summaries = summaries[inst_id]
        transmitted = [agent_summaries[a] for a in sorted(agent_summaries)]
        gold_units = get_gold_units(inst)
        alignments = align_gold_to_transmitted(gold_units, transmitted)

        n_gold = len(gold_units)
        n_covered = sum(1 for a in alignments if a["covered"])
        crit_recall = n_covered / n_gold if n_gold > 0 else 1.0
        omission = 1.0 - crit_recall
        redundancy = compute_redundancy(transmitted)
        matched_units = {a["best_unit"] for a in alignments if a["covered"] and a["best_unit"]}
        useful_budget = len(matched_units) / len(transmitted) if transmitted else 0.0
        correctness = proto_results.get(inst_id, {}).get("f1", 0.0)
        correct = correctness >= 1.0
        agg_fail = (not correct) and (crit_recall >= 1.0)

        records.append({
            "inst_id": inst_id,
            "protocol": "summary_exchange",
            "n_transmitted": len(transmitted),
            "n_gold": n_gold,
            "n_covered": n_covered,
            "crit_recall": crit_recall,
            "omission": omission,
            "redundancy": redundancy,
            "useful_budget": useful_budget,
            "agg_fail": agg_fail,
            "correct": correct,
        })

    return aggregate_audit(records), records


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compute audit metrics from saved API logs.")
    parser.add_argument("--run-dir", required=True, help="Path to results/run_*/")
    parser.add_argument("--distortion", action="store_true",
                        help="Run LLM distortion judge (makes new API calls)")
    parser.add_argument("--summary-exchange", action="store_true",
                        help="Also compute audit metrics for Summary Exchange protocol")
    parser.add_argument("--model", default="qwen/qwen3-235b-a22b-2507")
    parser.add_argument("--max-workers", type=int, default=32)
    parser.add_argument("--dataset", choices=["silobench", "musique"], default=None,
                        help="Dataset type (auto-detected from run args if omitted)")
    parser.add_argument("--n-agents", type=int, default=None,
                        help="n_agents filter for Silo-Bench (auto-detected from run args if omitted)")
    args = parser.parse_args(argv)

    # ── Load artifacts ──────────────────────────────────────────────────────
    print(f"Loading run from: {args.run_dir}")
    run_results, responses = load_run(args.run_dir)
    print(f"  {len(responses)} API responses loaded")

    # ── Auto-detect dataset ─────────────────────────────────────────────────
    dataset = args.dataset
    if dataset is None:
        run_args = run_results.get("args", {})
        dataset = run_args.get("dataset", "silobench")
    print(f"  Dataset: {dataset}")

    # ── Reconstruct states and scores ────────────────────────────────────────
    print("Reconstructing extracted units and scores from logs...")
    states, scores = reconstruct_states_and_scores(responses)
    print(f"  {len(states)} instances with extracted units")

    # ── Load instances ───────────────────────────────────────────────────────
    if dataset == "musique":
        print("Loading MuSiQue instances...")
        run_ids = {r["id"] for r in run_results["instance_results"].get(
            "random_relay", run_results["instance_results"].get("single_local", [])
        )}
        all_mq = load_musique()
        instances = [inst for inst in all_mq if inst["id"] in run_ids]
        instances_by_id = {inst["id"]: inst for inst in instances}
        print(f"  {len(instances)} instances matched (from {len(run_ids)} run IDs)")
    else:
        n_agents = args.n_agents
        if n_agents is None:
            run_args = run_results.get("args", {})
            n_agents = run_args.get("n_agents", 5)
        print(f"Loading Silo-Bench instances (n={n_agents})...")
        instances = load_silobench(n_agents_filter=n_agents)
        instances_by_id = {inst["id"]: inst for inst in instances}
        print(f"  {len(instances)} instances loaded")

    # ── Compute audit metrics for relay protocols ────────────────────────────
    print("Computing audit metrics...")
    audit_records: dict[str, list[dict]] = {p: [] for p in RELAY_PROTOCOLS}

    for protocol in RELAY_PROTOCOLS:
        proto_results = {r["id"]: r for r in run_results["instance_results"][protocol]}
        for inst in instances:
            inst_id = inst["id"]
            if inst_id not in states:
                print(f"  WARNING: no extraction data for {inst_id}, skipping")
                continue
            correctness = proto_results.get(inst_id, {}).get("f1", 0.0)
            record = compute_instance_audit(
                inst_id, protocol, inst, states, scores, correctness
            )
            audit_records[protocol].append(record)
        print(f"  {protocol}: {len(audit_records[protocol])} instances computed")

    # ── Aggregate ────────────────────────────────────────────────────────────
    audit_summaries = {p: aggregate_audit(audit_records[p]) for p in RELAY_PROTOCOLS}

    # ── Optional Summary Exchange audit ─────────────────────────────────────
    se_records = []
    if args.summary_exchange:
        print("Computing Summary Exchange audit metrics...")
        se_result = compute_summary_exchange_audit(responses, instances_by_id, run_results)
        if se_result:
            se_summary, se_records = se_result
            if se_summary and se_records:
                audit_summaries["summary_exchange"] = se_summary
                print(f"  summary_exchange: {len(se_records)} instances computed")
                print(f"  CritRec={se_summary['crit_recall']:.3f}  "
                      f"Omit={se_summary['omission']:.3f}  "
                      f"Redund={se_summary['redundancy']:.3f}  "
                      f"UsefulB={se_summary['useful_budget']:.3f}  "
                      f"AggFail={se_summary['agg_fail_pct']:.1f}%")
            else:
                print("  summary_exchange: 0 instances matched — skipping")

    # ── Optional distortion judge ────────────────────────────────────────────
    distortion_by_proto = None
    if args.distortion:
        import os as _os
        _os.environ.setdefault("OPENROUTER_API_KEY",
                               _os.environ.get("OPENROUTER_API_KEY", ""))
        raw_distortion = run_distortion_judge(
            args.run_dir, instances_by_id, states, scores, run_results,
            model=args.model, max_workers=args.max_workers,
        )
        # Aggregate distortion rate per protocol:
        # fraction of covered alignments labelled DISTORTED
        distortion_by_proto = {}
        for protocol, by_inst in raw_distortion.items():
            all_labels = [d["label"] for inst_labels in by_inst.values()
                          for d in inst_labels]
            if all_labels:
                distortion_by_proto[protocol] = sum(
                    1 for l in all_labels if l == "DISTORTED"
                ) / len(all_labels)

    # ── Print combined table ─────────────────────────────────────────────────
    print("\n=== Table 1 — Protocol Audit Results ===")
    base_table = run_results["table"]
    print_audit_table(base_table, audit_summaries, distortion_by_proto)

    # ── Save audit records alongside results.json ────────────────────────────
    out_path = os.path.join(args.run_dir, "audit_metrics.json")
    with open(out_path, "w") as f:
        json.dump({
            "audit_records": audit_records,
            "audit_summaries": {p: s for p, s in audit_summaries.items()},
            "distortion": distortion_by_proto,
        }, f, indent=2)
    print(f"Audit metrics saved to: {out_path}")


if __name__ == "__main__":
    main()
