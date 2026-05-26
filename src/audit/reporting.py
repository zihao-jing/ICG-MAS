"""
Export audit results to JSONL and LaTeX tables.

Outputs:
  outputs/audit/protocol_metrics.jsonl
  outputs/audit/deletion_curve.jsonl
  outputs/audit/local_importance_failure_cases.jsonl
  outputs/tables/main_protocol_audit.tex
  outputs/tables/deletion_curve.tex
  outputs/tables/local_importance_analysis.tex
"""

from __future__ import annotations

import json
import os
from typing import Any


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def write_jsonl(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Main protocol audit table (LaTeX)
# ---------------------------------------------------------------------------

_PROTOCOL_LABELS = {
    "single_local": "Single Local",
    "majority_vote": "Majority Vote",
    "free_form_debate": "Free-form Debate",
    "summary_exchange": "Summary Exchange",
    "confidence_gated": "Confidence-Gated",
    "disagreement_gated": "Disagreement-Gated",
    "random_relay": "Random Evidence Relay",
    "score_ranked_relay": "Score-Ranked Evidence Relay",
    "redundancy_aware_relay": "Redundancy-Aware Evidence Relay",
    "full_sharing": "Full Evidence Sharing",
}

_DISPLAY_ORDER = list(_PROTOCOL_LABELS.keys())


def build_main_audit_table_tex(summaries: dict[str, dict]) -> str:
    """Generate LaTeX for the main protocol audit table."""
    lines = [
        r"\begin{table*}[t]",
        r"\caption{Protocol audit results. "
        r"Critical Recall = fraction of gold critical units surviving in transmitted evidence. "
        r"Aggregation Failure = evidence present but answer wrong.}",
        r"\label{tab:main_audit}",
        r"\centering\small\setlength{\tabcolsep}{4pt}",
        r"\renewcommand{\arraystretch}{1.1}",
        r"\begin{tabular}{lrrrrrrrrr}",
        r"\toprule",
        r"\textbf{Protocol} & \textbf{Acc\,(\%)}$\uparrow$ & \textbf{Comm\,Tok}$\downarrow$ "
        r"& \textbf{Crit.\ Recall}$\uparrow$ & \textbf{Omission}$\downarrow$ "
        r"& \textbf{Distortion}$\downarrow$ & \textbf{Redundancy}$\downarrow$ "
        r"& \textbf{Useful Budget}$\uparrow$ & \textbf{Agg.\ Fail}$\downarrow$ \\",
        r"\midrule",
    ]

    order = [k for k in _DISPLAY_ORDER if k in summaries]
    order += [k for k in summaries if k not in _DISPLAY_ORDER]

    for name in order:
        s = summaries[name]
        label = _PROTOCOL_LABELS.get(name, name.replace("_", " ").title())
        row = (
            f"{label} "
            f"& {s.get('accuracy', 0)*100:.1f} "
            f"& {s.get('comm_tokens', 0):.0f} "
            f"& {s.get('critical_recall', 0):.3f} "
            f"& {s.get('omission_rate', 0):.3f} "
            f"& {s.get('distortion_rate', 0):.3f} "
            f"& {s.get('redundancy_rate', 0):.3f} "
            f"& {s.get('useful_budget_share', 0):.3f} "
            f"& {s.get('aggregation_failure', 0)*100:.1f} \\\\"
        )
        lines.append(row)

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table*}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deletion curve table (LaTeX)
# ---------------------------------------------------------------------------

def build_deletion_curve_tex(records: list[dict]) -> str:
    """Generate LaTeX for the evidence deletion intervention table."""
    from collections import defaultdict
    # {condition: {k: [accuracy values]}}
    by_condition: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        by_condition[r["condition"]][r["k"]].append(r["accuracy"])

    ks = sorted({r["k"] for r in records})
    conditions = ["remove_critical", "remove_distractor", "remove_redundant", "remove_random"]
    condition_labels = {
        "remove_critical": "Critical units",
        "remove_distractor": "Distractor units",
        "remove_redundant": "Redundant units",
        "remove_random": "Random units",
    }

    k_headers = " & ".join(f"$k={k}$" for k in ks)
    lines = [
        r"\begin{table}[t]",
        r"\caption{Accuracy under controlled evidence deletion from oracle board.}",
        r"\label{tab:deletion_curve}",
        r"\centering\small",
        r"\begin{tabular}{l" + "r" * len(ks) + "}",
        r"\toprule",
        f"\\textbf{{Removed Evidence}} & {k_headers} \\\\",
        r"\midrule",
    ]

    for cond in conditions:
        label = condition_labels.get(cond, cond)
        cells = []
        for k in ks:
            vals = by_condition[cond].get(k, [])
            avg = sum(vals) / len(vals) * 100 if vals else 0.0
            cells.append(f"{avg:.1f}")
        lines.append(f"{label} & {' & '.join(cells)} \\\\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Local importance analysis table (LaTeX)
# ---------------------------------------------------------------------------

def build_local_importance_tex(correlation_results: list[dict], k: int = 5) -> str:
    """Generate LaTeX for the local importance failure analysis table."""
    from collections import defaultdict
    # Average across tasks
    score_keys = ["relevance", "uniqueness", "local_importance", "overall", "random"]
    agg: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for r in correlation_results:
        for key in score_keys:
            if key in r.get("correlations", {}):
                corr = r["correlations"][key]
                for metric in ["auc_vs_gold", "spearman_vs_gold", f"precision_at_{k}", f"recall_at_{k}"]:
                    agg[key][metric].append(corr.get(metric, 0.0))

    lines = [
        r"\begin{table}[t]",
        f"\\caption{{Local importance score analysis (k={k}). "
        r"AUC and Spearman measure correlation with gold criticality.}",
        r"\label{tab:local_importance}",
        r"\centering\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        f"\\textbf{{Score}} & \\textbf{{AUC}} & \\textbf{{Spearman}} "
        f"& \\textbf{{P@{k}}} & \\textbf{{R@{k}}} \\\\",
        r"\midrule",
    ]

    score_labels = {
        "relevance": "Relevance",
        "uniqueness": "Uniqueness",
        "local_importance": "Importance",
        "overall": "Average",
        "random": "Random",
    }

    for key in score_keys:
        if key not in agg:
            continue
        label = score_labels.get(key, key)

        def avg(metric: str) -> float:
            vals = agg[key].get(metric, [])
            return sum(vals) / len(vals) if vals else 0.0

        lines.append(
            f"{label} "
            f"& {avg('auc_vs_gold'):.3f} "
            f"& {avg('spearman_vs_gold'):.3f} "
            f"& {avg(f'precision_at_{k}'):.3f} "
            f"& {avg(f'recall_at_{k}'):.3f} \\\\"
        )

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full export
# ---------------------------------------------------------------------------

def export_all(
    output_dir: str,
    protocol_records: list[dict],
    deletion_records: list[dict],
    local_importance_records: list[dict],
    summaries: dict[str, dict],
) -> None:
    """Write all JSONL and LaTeX output files."""
    audit_dir = os.path.join(output_dir, "audit")
    table_dir = os.path.join(output_dir, "tables")
    os.makedirs(audit_dir, exist_ok=True)
    os.makedirs(table_dir, exist_ok=True)

    write_jsonl(os.path.join(audit_dir, "protocol_metrics.jsonl"), protocol_records)
    write_jsonl(os.path.join(audit_dir, "deletion_curve.jsonl"), deletion_records)
    write_jsonl(os.path.join(audit_dir, "local_importance_failure_cases.jsonl"), local_importance_records)

    with open(os.path.join(table_dir, "main_protocol_audit.tex"), "w") as f:
        f.write(build_main_audit_table_tex(summaries))

    if deletion_records:
        with open(os.path.join(table_dir, "deletion_curve.tex"), "w") as f:
            f.write(build_deletion_curve_tex(deletion_records))

    if local_importance_records:
        with open(os.path.join(table_dir, "local_importance_analysis.tex"), "w") as f:
            f.write(build_local_importance_tex(local_importance_records))

    print(f"[reporting] Exported to {output_dir}")
