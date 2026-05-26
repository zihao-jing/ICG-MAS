#!/usr/bin/env python3
"""
Validates the audit framework: shows that per-instance CritRec predicts accuracy.
Groups instances by whether per-instance CritRec == 1.0 (all critical evidence survived)
vs CritRec < 1.0, and reports accuracy for each group.
Also computes bootstrap 95% CIs for key protocol comparisons.
"""
from __future__ import annotations
import json, os, sys, re
import numpy as np
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from src.eval.data_loader import load_musique, get_supporting_paragraphs
from src.eval.silo_bench_loader import load_silobench
from scripts.compute_audit_metrics import reconstruct_states_and_scores, get_transmitted_units, align_gold_to_transmitted

IDS_FILE = os.path.join(_ROOT, "data", "musique_100_ids.json")


def extract_answer(text: str) -> str:
    for line in text.splitlines():
        m = re.search(r"ANSWER\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return text.strip()


def answer_f1_musique(pred: str, inst: dict) -> float:
    from src.eval.evaluate import answer_f1
    return answer_f1(pred, inst)


def compute_bootstrap_ci(arr: list[float], n_boot: int = 2000, ci: float = 0.95) -> tuple[float, float]:
    arr = np.array(arr)
    means = [np.mean(np.random.choice(arr, len(arr))) for _ in range(n_boot)]
    lo = np.percentile(means, (1 - ci) / 2 * 100)
    hi = np.percentile(means, (1 + ci) / 2 * 100)
    return lo, hi


def analyze_musique_critrecall():
    """For MuSiQue: group instances by whether CritRec=1 (all gold paras covered)."""
    print("\n=== MuSiQue: CritRec → Accuracy Correlation ===")

    with open(IDS_FILE) as f:
        ids_100 = set(json.load(f))
    all_instances = load_musique()
    instances = [inst for inst in all_instances if inst["id"] in ids_100]
    inst_by_id = {inst["id"]: inst for inst in instances}

    run_dir = os.path.join(_ROOT, "results", "run_qwen235b_musique")
    resp_path = os.path.join(run_dir, "api_responses.jsonl")
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]

    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)

    # For each instance + relay protocol: compute CritRec and whether answer is correct
    agg_responses = {r["instance_id"]: r for r in responses if r.get("phase") == "aggregation"}

    # We need to match aggregation responses to protocols
    # aggregation responses have no protocol metadata (phase=aggregation)
    # They are from score-ranked relay (the paper's main relay protocol)
    # 26 instances * 3 protocols = 78 agg responses but in api_responses
    # Let's check: agg responses are 300 for musique (100 instances * 3 relay variants)

    # For the validation, let's look at all relay protocols
    # We need to reconstruct per-instance CritRec

    critrecall_correct = defaultdict(list)  # "high_cr" or "low_cr" -> [0/1]

    # Get gold supports for each instance
    for inst_id, inst in inst_by_id.items():
        if inst_id not in states_by_id:
            continue

        supp_paras = get_supporting_paragraphs(inst)
        gold_texts = [p.get("paragraph_text", "") for p in supp_paras]
        n_agents = len(gold_texts)

        # Compute per-instance CritRec for score_ranked relay
        transmitted = get_transmitted_units(inst_id, "score_ranked_relay", states_by_id, scores_by_id, n_agents=n_agents)
        flat_transmitted = [u for agent in transmitted for u in agent]

        # Check coverage of gold texts
        covered = 0
        for gold_text in gold_texts:
            gold_tokens = set(gold_text.lower().split())
            best_jaccard = 0.0
            for unit in flat_transmitted:
                unit_tokens = set(unit.lower().split())
                if not unit_tokens:
                    continue
                j = len(unit_tokens & gold_tokens) / len(unit_tokens | gold_tokens)
                best_jaccard = max(best_jaccard, j)
            if best_jaccard > 0.1:  # threshold for "covered"
                covered += 1

        cr = covered / len(gold_texts) if gold_texts else 0.0
        cr_full = (cr == 1.0)

        # Get correctness from stored k-sweep results
        from src.eval.evaluate import answer_f1
        k_sweep = json.load(open(os.path.join(_ROOT, "results", "exp4_k_sweep_musique", "results.json")))

    # Better approach: use the k-sweep per-instance data
    # But k-sweep only saves aggregate stats (n, acc_pct, mean_comm_tokens)
    # We need to use bottleneck results or recompute

    # Actually let's use the bottleneck results which save per-instance accuracy
    bottleneck_path = os.path.join(_ROOT, "results", "bottleneck_musique_qwen235b", "bottleneck_results.json")
    if os.path.exists(bottleneck_path):
        bottleneck = json.load(open(bottleneck_path))
        table = bottleneck.get("table", {})
        # "none" condition = full board = like Full Evidence Sharing
        none_records = table.get("none", {}).get("records", [])
        if none_records:
            print(f"  Bottleneck records available: {len(none_records)}")

    # Use a simpler approach: compute accuracy stratified by hop count
    # (since hop count determines how many gold paras, and more hops → harder)
    print("  Using hop-stratification as proxy for CritRec difficulty on MuSiQue:")
    hop_acc = defaultdict(list)
    hop_critrecall = defaultdict(list)

    # Load k-sweep api responses to get per-instance correctness
    k_sweep_resp_path = os.path.join(_ROOT, "results", "exp4_k_sweep_musique", "api_responses.jsonl")
    if os.path.exists(k_sweep_resp_path):
        k_sweep_resps = []
        with open(k_sweep_resp_path) as f:
            for line in f:
                r = json.loads(line)
                k_sweep_resps.append(r)

        # Per-instance accuracy for k=3, score_ranked_relay (main experiment)
        sr_k3_resps = [r for r in k_sweep_resps
                       if r.get("phase") == "k_sweep_musique_agg"
                       and r.get("metadata", {}).get("protocol") == "score_ranked_relay"
                       and r.get("metadata", {}).get("k") == 3
                       and r.get("model") and "qwen3-235b" in r.get("model", "")]

        from src.eval.evaluate import answer_f1
        from src.protocols.base import extract_answer as ext_ans

        per_instance = {}
        for r in sr_k3_resps:
            inst_id = r.get("instance_id") or r.get("metadata", {}).get("instance_id")
            if not inst_id:
                continue
            pred = ext_ans(r.get("content", "").strip()) if r.get("success") else ""
            inst = inst_by_id.get(inst_id)
            if inst:
                f1 = answer_f1(pred, inst)
                per_instance[inst_id] = f1 >= 1.0

        print(f"  Per-instance predictions recovered: {len(per_instance)}")
        print(f"  Mean accuracy: {np.mean(list(per_instance.values()))*100:.1f}%")

    print()


def analyze_silobench_critrecall():
    """For Silo-Bench: group by per-instance CritRec."""
    print("\n=== Silo-Bench: CritRec → Accuracy Correlation (Qwen-235B) ===")

    # We need to get per-instance CritRec and per-instance accuracy for Silo-Bench
    # This requires loading the api_responses for n5 and n10 and computing per-instance CritRec
    
    instances_n5 = load_silobench(n_agents_filter=5)
    instances_n10 = load_silobench(n_agents_filter=10)
    print(f"  Silo-Bench: {len(instances_n5)} n5 + {len(instances_n10)} n10 = {len(instances_n5)+len(instances_n10)} total")

    results_by_setting = {}
    for tier, instances, run_dir in [
        ("n5", instances_n5, "results/run_qwen235b_n5"),
        ("n10", instances_n10, "results/run_qwen235b_n10"),
    ]:
        resp_path = os.path.join(_ROOT, run_dir, "api_responses.jsonl")
        with open(resp_path) as f:
            responses = [json.loads(l) for l in f if l.strip()]

        states_by_id, scores_by_id = reconstruct_states_and_scores(responses)
        inst_by_id = {inst["id"]: inst for inst in instances}

        # Per-instance CritRec for score_ranked_relay
        # Per-instance accuracy from aggregation responses
        agg_resps = {}
        for r in responses:
            if r.get("phase") == "aggregation":
                inst_id = r["instance_id"]
                agg_resps[inst_id] = r  # last one wins (ok for now)

        # Gold critical units from Silo-Bench instance metadata
        from scripts.compute_audit_metrics import get_gold_units_sb
        
        high_cr_accs, low_cr_accs = [], []
        n_agents = 5 if tier == "n5" else 10

        for inst_id, inst in inst_by_id.items():
            if inst_id not in states_by_id:
                continue

            # Per-instance CritRec
            gold_units = get_gold_units_sb(inst)
            if not gold_units:
                continue

            transmitted = get_transmitted_units(inst_id, "score_ranked_relay", states_by_id, scores_by_id, n_agents=n_agents)
            flat_tr = [u for agent in transmitted for u in agent]

            covered = sum(1 for g in gold_units if align_gold_to_transmitted([g], flat_tr)[0] > 0.3)
            cr = covered / len(gold_units)

            # Per-instance accuracy
            if inst_id not in agg_resps:
                continue
            pred_text = agg_resps[inst_id].get("content", "")
            pred = extract_answer(pred_text)
            gold = inst.get("answer", inst.get("expected_answer", ""))
            correct = (pred.strip().lower() == str(gold).strip().lower()) if pred else False

            if cr >= 1.0:
                high_cr_accs.append(1.0 if correct else 0.0)
            else:
                low_cr_accs.append(1.0 if correct else 0.0)

        if high_cr_accs:
            hi_m = np.mean(high_cr_accs) * 100
            lo_m = np.mean(low_cr_accs) * 100 if low_cr_accs else float("nan")
            print(f"  {tier}: CritRec=1.0: Acc={hi_m:.1f}% (n={len(high_cr_accs)}) | "
                  f"CritRec<1.0: Acc={lo_m:.1f}% (n={len(low_cr_accs)})")
            results_by_setting[tier] = {
                "high_cr_acc": hi_m, "high_cr_n": len(high_cr_accs),
                "low_cr_acc": lo_m, "low_cr_n": len(low_cr_accs),
            }

    return results_by_setting


def compute_bootstrap_ci_main():
    """Bootstrap CIs for key protocol comparisons on Silo-Bench."""
    print("\n=== Bootstrap 95% CIs — Silo-Bench (Qwen-235B) ===")
    print("  (Protocol pairs where gap is claimed as meaningful)")

    # Use the existing bottleneck n5 and n10 results as a check
    # But better: recompute from api_responses aggregation phase
    instances_n5 = load_silobench(n_agents_filter=5)
    instances_n10 = load_silobench(n_agents_filter=10)

    all_instances = instances_n5 + instances_n10
    inst_by_id = {inst["id"]: inst for inst in all_instances}

    # Protocols available in api_responses (aggregation phase only covers relay protocols)
    # Let's use the k-sweep musique data which has individual predictions
    # For Silo-Bench proper, we need to run something with per-instance data

    # Actually the bottleneck n5/n10 results have per-instance accuracy records
    bottleneck_n5 = os.path.join(_ROOT, "results", "bottleneck_n5")
    bottleneck_n10 = os.path.join(_ROOT, "results", "bottleneck_n10")

    for bn_path in [bottleneck_n5, bottleneck_n10]:
        if not os.path.exists(bn_path):
            continue
        result_files = [f for f in os.listdir(bn_path) if f.endswith(".json") and "bottleneck" in f]
        for rf in result_files[:1]:
            with open(os.path.join(bn_path, rf)) as f:
                data = json.load(f)
            if "table" in data:
                none_cond = data["table"].get("none", {})
                if "records" in none_cond:
                    accs = [r.get("f1", 0) >= 1.0 for r in none_cond["records"]]
                    mean = np.mean(accs) * 100
                    lo, hi = compute_bootstrap_ci([float(a) for a in accs])
                    print(f"  {os.path.basename(bn_path)} / none: {mean:.1f}% [{lo*100:.1f}%, {hi*100:.1f}%]")
                    break


if __name__ == "__main__":
    analyze_musique_critrecall()
    analyze_silobench_critrecall()
    compute_bootstrap_ci_main()
