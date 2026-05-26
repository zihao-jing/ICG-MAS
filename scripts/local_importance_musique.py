#!/usr/bin/env python3
"""
Local importance scoring quality analysis on MuSiQue.
Computes AUC, Spearman, P@3, R@3 for each score component,
comparing against gold criticality labels (is_supporting=True).
Parallels the Silo-Bench local importance analysis in Figure 1 / Table 6.
"""
from __future__ import annotations
import json, os, sys
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from src.eval.data_loader import load_musique, get_supporting_paragraphs
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr

MODELS = {
    "qwen235b": os.path.join(_ROOT, "results", "run_qwen235b_musique", "api_responses.jsonl"),
    "mistrals":  os.path.join(_ROOT, "results", "run_musique_mistrals",  "api_responses.jsonl"),
    "qwen36f":   os.path.join(_ROOT, "results", "run_musique_100",        "api_responses.jsonl"),
    "qwen80bt":  os.path.join(_ROOT, "results", "run_musique_qwen80bt",  "api_responses.jsonl"),
    "gemma31b":  os.path.join(_ROOT, "results", "run_musique_gemma31b",  "api_responses.jsonl"),
}

SCORE_KEYS = ["relevance", "uniqueness", "local_importance", "joint_dependency", "overall"]

IDS_FILE = os.path.join(_ROOT, "data", "musique_100_ids.json")


def precision_recall_at_k(scores, labels, k):
    n = len(scores)
    order = np.argsort(scores)[::-1]
    top_k = order[:k]
    tp = sum(labels[i] for i in top_k)
    all_pos = sum(labels)
    p = tp / k if k > 0 else 0.0
    r = tp / all_pos if all_pos > 0 else 0.0
    return p, r


def analyze_model(model_key: str, resp_path: str, instances: list[dict]) -> dict:
    print(f"\n=== {model_key} ===")
    if not os.path.exists(resp_path):
        print(f"  Missing: {resp_path}")
        return {}

    # Load scoring responses
    scoring = []
    with open(resp_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("phase") == "scoring" and r.get("success") and r.get("content"):
                try:
                    sc = json.loads(r["content"])
                    scoring.append({
                        "instance_id": r["instance_id"],
                        "agent": r.get("agent", 0),
                        "scores": sc,
                    })
                except Exception:
                    pass

    if not scoring:
        print(f"  No scoring responses found.")
        return {}

    print(f"  {len(scoring)} scoring responses")

    # Build gold labels: for each instance+agent, which unit index is critical?
    # For MuSiQue, each agent holds one supporting paragraph
    # The paragraph is "critical" if it's a gold supporting paragraph
    # We know each agent's shard = one supporting paragraph (from get_supporting_paragraphs)
    # So all extracted units from an agent with a gold supporting shard are "critical"
    # and units from an agent with a distractor shard are "non-critical"

    inst_by_id = {inst["id"]: inst for inst in instances}

    # For MuSiQue: agent_i holds shard_i = supporting_paragraphs[i]
    # All paragraphs in get_supporting_paragraphs are gold supporting (is_supporting=True)
    # But the extraction also gets distractor paragraphs sometimes?
    # Actually in the MuSiQue setup: each agent gets one paragraph (from all_paragraphs)
    # and the gold ones are those flagged is_supporting=True

    # Let's determine: how many agents per instance have gold paragraphs?
    # From get_supporting_paragraphs, we get paragraphs where is_supporting=True
    # The agent assignments map: agent i → supporting_paragraphs[i] (all gold)
    # Wait, actually in the distributed MuSiQue setup:
    # - n_agents = len(supporting_paragraphs) = number of hop chains
    # - Each agent gets exactly one supporting paragraph
    # - So ALL agents have gold paragraphs → all extracted units are "gold"?!

    # Let me check this more carefully
    sample_inst = instances[0]
    supp_paras = get_supporting_paragraphs(sample_inst)
    print(f"  Sample instance has {len(supp_paras)} supporting paragraphs")
    print(f"  n_agents = {len(supp_paras)} (each agent gets one supporting paragraph)")

    # If each agent always gets a gold paragraph, then all units are "critical"
    # and AUC would be undefined. This is different from Silo-Bench where 
    # there are both critical and non-critical facts within each shard.

    # On MuSiQue, the extraction_recall question is: does the agent extract 
    # the supporting paragraph's key content?
    # The "gold label" should be at the unit level, not shard level.
    # Since we don't have unit-level gold labels for MuSiQue, we need a proxy.

    # Proxy approach: use "is this extracted unit aligned to the supporting paragraph?"
    # via Jaccard similarity. Units with high Jaccard to the supporting text are "critical".

    # Actually, let's use a simpler approach:
    # On MuSiQue, CritRec=1.0 for relay with k=3, meaning at k=3, all gold content is covered.
    # The local importance failure question becomes: at k=1, does the top-ranked unit
    # contain the critical content?
    # We can approximate: among extracted units per agent, the unit most similar 
    # (by token overlap) to the gold supporting paragraph text is the "true critical" unit.

    # Load instances and compute per-agent gold text
    results_per_component = {k: {"scores": [], "labels": []} for k in SCORE_KEYS + ["random"]}

    from scripts.compute_audit_metrics import reconstruct_states_and_scores
    with open(resp_path) as f:
        responses = [json.loads(l) for l in f if l.strip()]
    states_by_id, scores_by_id = reconstruct_states_and_scores(responses)

    # Also get extraction responses to map units
    extract_by_id_agent = {}  # (inst_id, agent) → list of units
    with open(resp_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("phase") == "extraction" and r.get("success") and r.get("content"):
                inst_id = r["instance_id"]
                agent = r.get("agent", 0)
                # Parse units
                units = []
                for ln in r["content"].splitlines():
                    ln = ln.strip()
                    if ln and (ln[0].isdigit() or ln.startswith("-")):
                        import re
                        unit = re.sub(r"^\d+[\.\)]\s*", "", ln).strip()
                        if unit:
                            units.append(unit)
                extract_by_id_agent[(inst_id, agent)] = units

    n_processed = 0
    for inst in instances:
        inst_id = inst["id"]
        if inst_id not in inst_by_id:
            continue
        supp_paras = get_supporting_paragraphs(inst)
        n_agents = len(supp_paras)

        for agent_id in range(n_agents):
            # Gold text = the supporting paragraph text for this agent
            gold_text = supp_paras[agent_id].get("paragraph_text", "")
            gold_tokens = set(gold_text.lower().split())

            # Get extracted units for this agent
            units = states_by_id.get(inst_id, {}).get(agent_id, [])
            agent_scores = scores_by_id.get(inst_id, {}).get(agent_id, [])

            if not units or len(units) != len(agent_scores):
                continue

            # Compute Jaccard similarity of each unit to gold text
            unit_jaccard = []
            for unit in units:
                unit_tokens = set(unit.lower().split())
                if not unit_tokens or not gold_tokens:
                    unit_jaccard.append(0.0)
                else:
                    unit_jaccard.append(len(unit_tokens & gold_tokens) / len(unit_tokens | gold_tokens))

            # Label: top-Jaccard unit is "critical", others are not
            # (at least 1 unit must have overlap > 0)
            max_jac = max(unit_jaccard)
            if max_jac == 0:
                continue

            gold_labels = [1 if j == max_jac else 0 for j in unit_jaccard]

            for sc_key in SCORE_KEYS:
                sc_vals = [sc.get(sc_key, 0.5) for sc in agent_scores]
                results_per_component[sc_key]["scores"].extend(sc_vals)
                results_per_component[sc_key]["labels"].extend(gold_labels)

            # Random baseline
            import random
            rand_vals = [random.random() for _ in units]
            results_per_component["random"]["scores"].extend(rand_vals)
            results_per_component["random"]["labels"].extend(gold_labels)
            n_processed += 1

    print(f"  {n_processed} (agent, shard) pairs processed")

    if n_processed == 0:
        return {}

    # Compute metrics
    print(f"\n  {'Score':<20} {'AUC':>6} {'Spearman':>10} {'P@1':>6} {'R@1':>6}")
    print(f"  {'-'*55}")

    results = {}
    for sc_key in SCORE_KEYS + ["random"]:
        sc_arr = np.array(results_per_component[sc_key]["scores"])
        lb_arr = np.array(results_per_component[sc_key]["labels"])

        if lb_arr.sum() == 0 or lb_arr.sum() == len(lb_arr):
            continue

        try:
            auc = roc_auc_score(lb_arr, sc_arr)
        except Exception:
            auc = float("nan")

        rho, _ = spearmanr(sc_arr, lb_arr)

        # P@1 R@1 globally (treat each agent as independent)
        # Regroup by agent
        # Use the stored per-agent data
        p1_vals, r1_vals = [], []
        p3_vals, r3_vals = [], []
        # Recompute per-agent
        for inst in instances:
            inst_id = inst["id"]
            if inst_id not in inst_by_id:
                continue
            supp_paras = get_supporting_paragraphs(inst)
            for agent_id in range(len(supp_paras)):
                units = states_by_id.get(inst_id, {}).get(agent_id, [])
                agent_scores = scores_by_id.get(inst_id, {}).get(agent_id, [])
                if not units or len(units) != len(agent_scores):
                    continue
                gold_text = supp_paras[agent_id].get("paragraph_text", "")
                gold_tokens = set(gold_text.lower().split())
                unit_jaccard = []
                for unit in units:
                    unit_tokens = set(unit.lower().split())
                    unit_jaccard.append(len(unit_tokens & gold_tokens) / len(unit_tokens | gold_tokens) if unit_tokens and gold_tokens else 0.0)
                max_jac = max(unit_jaccard)
                if max_jac == 0:
                    continue
                gold_labels_agent = [1 if j == max_jac else 0 for j in unit_jaccard]
                if sc_key == "random":
                    import random
                    sc_vals_agent = [random.random() for _ in units]
                else:
                    sc_vals_agent = [sc.get(sc_key, 0.5) for sc in agent_scores]
                p1, r1 = precision_recall_at_k(sc_vals_agent, gold_labels_agent, 1)
                p3, r3 = precision_recall_at_k(sc_vals_agent, gold_labels_agent, 3)
                p1_vals.append(p1)
                r1_vals.append(r1)
                p3_vals.append(p3)
                r3_vals.append(r3)

        p1m = np.mean(p1_vals) if p1_vals else float("nan")
        r1m = np.mean(r1_vals) if r1_vals else float("nan")
        p3m = np.mean(p3_vals) if p3_vals else float("nan")
        r3m = np.mean(r3_vals) if r3_vals else float("nan")
        print(f"  {sc_key:<20} {auc:>6.3f} {rho:>10.3f} {p1m:>6.3f} {r1m:>6.3f}")
        results[sc_key] = {"auc": auc, "spearman": rho, "p1": p1m, "r1": r1m, "p3": p3m, "r3": r3m}

    return results


def main():
    with open(IDS_FILE) as f:
        ids_100 = set(json.load(f))
    all_instances = load_musique()
    instances = [inst for inst in all_instances if inst["id"] in ids_100]
    print(f"Loaded {len(instances)} MuSiQue instances")

    all_results = {}
    for model_key, resp_path in MODELS.items():
        res = analyze_model(model_key, resp_path, instances)
        all_results[model_key] = res

    out_path = os.path.join(_ROOT, "results", "local_importance_musique.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
