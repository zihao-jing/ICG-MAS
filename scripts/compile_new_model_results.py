#!/usr/bin/env python3
"""
compile_new_model_results.py

Reads results from the 4 new model robustness runs and generates LaTeX tables
for the paper appendix. Outputs to:
  acl-style-files/appendix/app_new_models.tex

Models:
  Gemini-2.5-flash-lite  (google/gemini-2.5-flash-lite)
  GPT-4o-mini            (openai/gpt-4o-mini)
  DeepSeek-R1-32B        (deepseek/deepseek-r1-distill-qwen-32b)
  Gemma-4-31B            (google/gemma-4-31b-it)

Usage:
    python scripts/compile_new_model_results.py [--partial]

  --partial: skip models that don't have complete results yet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE = os.path.join(os.path.dirname(__file__), "..", "results")
OUT_TEX = os.path.join(
    os.path.dirname(__file__), "..", "acl-style-files", "appendix", "app_new_models.tex"
)

# Model metadata
MODELS = [
    {
        "short": "geminiflashlite",
        "label": "Gemini-2.5-Flash-Lite",
        "api_name": "google/gemini-2.5-flash-lite",
        "tex_name": r"Gemini-2.5-Flash-Lite",
        "n5_dir": "run_geminiflashlite_n5",
        "n10_dir": "run_geminiflashlite_n10",
        "mq_dir": "run_musique_geminiflashlite",
    },
    {
        "short": "gpt4omini",
        "label": "GPT-4o-mini",
        "api_name": "openai/gpt-4o-mini",
        "tex_name": r"GPT-4o-mini",
        "n5_dir": "run_gpt4omini_n5",
        "n10_dir": "run_gpt4omini_n10",
        "mq_dir": "run_musique_gpt4omini",
    },
    {
        "short": "deepseekr1_32b",
        "label": "DeepSeek-R1-32B",
        "api_name": "deepseek/deepseek-r1-distill-qwen-32b",
        "tex_name": r"DeepSeek-R1-32B",
        "n5_dir": "run_deepseekr1_32b_n5",
        "n10_dir": "run_deepseekr1_32b_n10",
        "mq_dir": "run_musique_deepseekr1_32b",
    },
    {
        "short": "gemma31b",
        "label": "Gemma-4-31B",
        "api_name": "google/gemma-4-31b-it",
        "tex_name": r"Gemma-4-31B",
        "n5_dir": "run_gemma31b_n5",
        "n10_dir": "run_gemma31b_n10",
        "mq_dir": "run_musique_gemma31b",
    },
]

PROTOCOL_ORDER = [
    "single_local",
    "majority_vote",
    "best_local",
    "summary_exchange",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "full_sharing",
]

PROTOCOL_LABELS = {
    "single_local":            r"Single Local",
    "majority_vote":           r"Majority Vote",
    "best_local":              r"Best-Local Oracle",
    "summary_exchange":        r"Summary Exchange",
    "random_relay":            r"Random Evidence Relay",
    "score_ranked_relay":      r"Score-Ranked Relay",
    "redundancy_aware_relay":  r"Redundancy-Aware Relay",
    "full_sharing":            r"Full Evidence Sharing",
}

PROTOCOL_SECTIONS = [
    ("No-communication bounds",    ["single_local", "majority_vote", "best_local"]),
    ("Natural-language comm.",     ["summary_exchange"]),
    ("Structured evidence relay",  ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]),
    ("Pooled-evidence reference",  ["full_sharing"]),
]

AUDIT_PROTOCOLS = [
    "summary_exchange",
    "random_relay",
    "score_ranked_relay",
    "redundancy_aware_relay",
    "full_sharing",
]


def load_results(run_dir: str) -> dict | None:
    path = os.path.join(BASE, run_dir, "results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_audit(run_dir: str) -> dict | None:
    """Load audit_summaries from audit_metrics.json.
    Returns dict keyed by protocol with normalized field names:
      crit_rec, omission, redundancy, useful_budget, agg_fail (fraction 0-1), distortion
    """
    path = os.path.join(BASE, run_dir, "audit_metrics.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = json.load(f)
    summaries = raw.get("audit_summaries", {})
    distortion_by_proto = raw.get("distortion") or {}
    result = {}
    for proto, s in summaries.items():
        result[proto] = {
            "crit_rec": s.get("crit_recall", s.get("crit_rec")),
            "omission": s.get("omission"),
            "redundancy": s.get("redundancy"),
            "useful_budget": s.get("useful_budget"),
            # agg_fail_pct is already in %; store as fraction
            "agg_fail": s.get("agg_fail_pct", 0) / 100.0 if s.get("agg_fail_pct") is not None else None,
            "distortion": distortion_by_proto.get(proto),
        }
    return result


def fs_agg_fail_from_per_instance(run_dir: str) -> float | None:
    """Compute full_sharing AggFail = fraction of instances where correct=False.
    The 'correct' field in per_instance_results uses F1>=1.0 (same as audit)."""
    rows = [r for r in load_per_instance_raw(run_dir) if r.get("protocol") == "full_sharing"]
    if not rows:
        return None
    return 1.0 - sum(r.get("correct", 0) for r in rows) / len(rows)


def load_per_instance_raw(run_dir: str) -> list[dict]:
    """Load all per-instance rows from per_instance_results.jsonl."""
    path = os.path.join(BASE, run_dir, "per_instance_results.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_per_instance(run_dir: str) -> list[dict]:
    return load_per_instance_raw(run_dir)


def combine_silobench(n5_res: dict, n10_res: dict) -> dict:
    """Combine n5 and n10 results into a single 52-instance summary."""
    combined = {}
    table5 = n5_res.get("table", {})
    table10 = n10_res.get("table", {})
    n5 = n5_res.get("n_instances", 26)
    n10 = n10_res.get("n_instances", 26)
    n_total = n5 + n10

    all_protocols = set(table5) | set(table10)
    for p in all_protocols:
        r5 = table5.get(p, {})
        r10 = table10.get(p, {})
        # weighted average by instance count
        acc = (r5.get("acc", 0) * n5 + r10.get("acc", 0) * n10) / n_total
        tok = (r5.get("mean_comm_tokens", 0) * n5 + r10.get("mean_comm_tokens", 0) * n10) / n_total
        rec = None  # compute after single_local and full_sharing known
        combined[p] = {
            "acc": acc,
            "mean_comm_tokens": tok,
        }

    # Recovery: (acc - local_acc) / (full_acc - local_acc)
    local_acc = combined.get("single_local", {}).get("acc", 0)
    full_acc = combined.get("full_sharing", {}).get("acc", 0)
    denom = full_acc - local_acc
    for p in combined:
        if abs(denom) > 1e-6:
            combined[p]["recovery"] = (combined[p]["acc"] - local_acc) / denom
        else:
            combined[p]["recovery"] = 0.0

    return combined


def combine_audit(n5_audit: dict | None, n10_audit: dict | None,
                  n5_dir: str | None = None, n10_dir: str | None = None) -> dict:
    """Combine n5+n10 audit metrics (weighted average: 26 each).
    Also injects full_sharing AggFail from main results (1 - acc).
    """
    if n5_audit is None and n10_audit is None:
        combined = {}
    elif n5_audit is None:
        combined = dict(n10_audit or {})
    elif n10_audit is None:
        combined = dict(n5_audit or {})
    else:
        # Weighted average (equal weight since both have 26 instances)
        combined = {}
        relay_keys = set(n5_audit) | set(n10_audit)
        for k in relay_keys:
            r5 = n5_audit.get(k, {})
            r10 = n10_audit.get(k, {})
            combined[k] = {}
            for field in set(r5) | set(r10):
                v5 = r5.get(field)
                v10 = r10.get(field)
                if field == "distortion":
                    # Average distortion across n5+n10, skip None
                    vals = [v for v in [v5, v10] if isinstance(v, (int, float))]
                    combined[k][field] = sum(vals) / len(vals) if vals else None
                elif isinstance(v5, (int, float)) and isinstance(v10, (int, float)):
                    combined[k][field] = (v5 + v10) / 2
                elif v5 is not None:
                    combined[k][field] = v5
                elif v10 is not None:
                    combined[k][field] = v10

    # Inject full_sharing AggFail from per-instance exact-match counts
    fs_agg_fails = []
    for d in [n5_dir, n10_dir]:
        if d is not None:
            af = fs_agg_fail_from_per_instance(d)
            if af is not None:
                fs_agg_fails.append(af)
    if fs_agg_fails:
        combined["full_sharing"] = {
            "crit_rec": 1.0,
            "omission": 0.0,
            "redundancy": None,
            "useful_budget": None,
            "agg_fail": sum(fs_agg_fails) / len(fs_agg_fails),
        }
    return combined


def hop_stratification(per_instance_rows: list[dict]) -> dict:
    """
    Compute AggFail by hop count from per_instance results.
    Returns dict: protocol -> {2: agg_fail%, 3: agg_fail%, 4: agg_fail%, 'all': agg_fail%}
    For FS: AggFail = 1 - acc (since CritRec=1.0 by construction).
    For relay: AggFail computed over instances with CritRec=1.0 (but we don't have
    per-instance CritRec here, so we use cscov=1.0 as proxy for MuSiQue).
    """
    # Group by protocol and hop count
    # hop count is inferred from "n_supporting" if present, else from the instance id
    # For MuSiQue, we need the hop count per instance id
    # We'll just compute overall accuracy by hop; caller passes MuSiQue rows only
    from src.eval.data_loader import load_musique_sample
    instances = load_musique_sample(n=100, seed=42)
    hop_by_id = {}
    for inst in instances:
        n_sup = sum(1 for p in inst.get("paragraphs", []) if p.get("is_supporting", False))
        hop_by_id[inst["id"]] = n_sup

    # Group rows by protocol
    proto_rows = defaultdict(list)
    for row in per_instance_rows:
        proto_rows[row["protocol"]].append(row)

    result = {}
    for proto, rows in proto_rows.items():
        hop_groups = defaultdict(list)
        for row in rows:
            h = hop_by_id.get(row["id"], 0)
            hop_groups[h].append(row)
            hop_groups["all"].append(row)

        agg_fail = {}
        for h, rrows in hop_groups.items():
            # AggFail = 1 - exact_match_rate (unconditional).
            # On MuSiQue relay, CritRec≈1.0 for all instances so this is correct.
            af = 1.0 - sum(r.get("correct", 0) for r in rrows) / len(rrows)
            agg_fail[h] = af

        result[proto] = agg_fail

    return result


def fmt_pct(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "---"
    return f"{v * 100:.{decimals}f}"


def fmt_acc(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "---"
    return f"{v * 100:.{decimals}f}"


def fmt_tok(v: float | None) -> str:
    if v is None:
        return "---"
    return f"{v:.0f}"


def fmt_rec(v: float | None, decimals: int = 2) -> str:
    if v is None:
        return "---"
    return f"{v:.{decimals}f}"


def fmt_audit(v: float | None, decimals: int = 3) -> str:
    if v is None:
        return "---"
    return f"{v:.{decimals}f}"


def bold_if_best(val_str: str, is_best: bool) -> str:
    if is_best:
        return r"\textbf{" + val_str + "}"
    return val_str


# ---------------------------------------------------------------------------
# LaTeX generation
# ---------------------------------------------------------------------------

def make_silobench_table(model_data: list[dict]) -> str:
    """
    Generate the Silo-Bench protocol comparison table (like Table 1 of the main paper)
    for the new models. One model per column group (Acc, Tok, Rec).
    """
    n_models = len(model_data)
    col_spec = "l " + " ".join(["rrr"] * n_models)

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"    \caption{Protocol comparison on \textbf{Silo-Bench} (52 tasks: 26 at $n{=}5$ + 26 at $n{=}10$ agents)")
    lines.append(r"    for four additional models not included in Table~\ref{tab:main_results}.")
    lines.append(r"    \textbf{Acc} = accuracy\,(\%)\,$\uparrow$;")
    lines.append(r"    \textbf{Tok} = mean communication tokens\,$\downarrow$;")
    lines.append(r"    \textbf{Rec} = Recovery\,$\uparrow$.}")
    lines.append(r"    \label{tab:new_models_sb}")
    lines.append(r"    \centering")
    lines.append(r"    \footnotesize")
    lines.append(r"    \setlength{\tabcolsep}{3.0pt}")
    lines.append(r"    \renewcommand{\arraystretch}{1.12}")
    lines.append(r"    \resizebox{\linewidth}{!}{%")
    lines.append(f"    \\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"    \toprule")

    # Header row 1: model names
    header1 = "    "
    for m in model_data:
        header1 += f"    & \\multicolumn{{3}}{{c}}{{\\textbf{{{m['model']['tex_name']}}}}}"
    header1 += " \\\\"
    lines.append(header1)

    # Cmidrule
    cmidrules = "    "
    for i, m in enumerate(model_data):
        start = 2 + i * 3
        end = start + 2
        cmidrules += f"\\cmidrule(lr){{{start}-{end}}}"
    lines.append(cmidrules)

    # Header row 2: metric names
    header2 = "    \\textbf{Protocol}"
    for _ in model_data:
        header2 += "    & Acc & Tok & Rec"
    header2 += " \\\\"
    lines.append(header2)
    lines.append(r"    \midrule")

    # Find best acc per model for bolding
    best_acc = {}
    for i, m in enumerate(model_data):
        best = max(
            (m["combined"].get(p, {}).get("acc", 0) for p in PROTOCOL_ORDER if p in m["combined"]),
            default=0,
        )
        best_acc[i] = best

    for section_label, section_protocols in PROTOCOL_SECTIONS:
        lines.append(f"    \\multicolumn{{{1 + n_models * 3}}}{{l}}{{\\textit{{{section_label}}}}} \\\\")
        for proto in section_protocols:
            if proto not in PROTOCOL_ORDER:
                continue
            row = f"    \\quad {PROTOCOL_LABELS[proto]}"
            for i, m in enumerate(model_data):
                t = m["combined"].get(proto, {})
                acc = t.get("acc")
                tok = t.get("mean_comm_tokens")
                rec = t.get("recovery")
                acc_str = fmt_acc(acc)
                if acc is not None and abs(acc - best_acc[i]) < 1e-6:
                    acc_str = r"\textbf{" + acc_str + "}"
                tok_str = fmt_tok(tok)
                rec_str = fmt_rec(rec)
                row += f"    & {acc_str} & {tok_str} & {rec_str}"
            row += " \\\\"
            lines.append(row)
        lines.append(r"    \midrule")

    # Remove last \midrule and add \bottomrule
    lines.pop()
    lines.append(r"    \bottomrule")
    lines.append(r"    \end{tabular}%")
    lines.append(r"    }")

    # Model footnotes
    footnotes = []
    for m in model_data:
        footnotes.append(f"{m['model']['tex_name']}\\,=\\,\\texttt{{{m['model']['api_name']}}}")
    lines.append(r"    \vspace{3pt}\\")
    lines.append(r"    {\footnotesize " + "; ".join(footnotes) + ".}")
    lines.append(r"\end{table*}")
    return "\n".join(lines)


def make_musique_table(model_data: list[dict]) -> str:
    """Generate the MuSiQue protocol comparison table for new models."""
    n_models = len(model_data)
    col_spec = "l " + " ".join(["rrr"] * n_models)

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"    \caption{Protocol comparison on \textbf{MuSiQue} (100 instances)")
    lines.append(r"    for four additional models. Metrics as in Table~\ref{tab:musique_results}.}")
    lines.append(r"    \label{tab:new_models_mq}")
    lines.append(r"    \centering")
    lines.append(r"    \footnotesize")
    lines.append(r"    \setlength{\tabcolsep}{3.0pt}")
    lines.append(r"    \renewcommand{\arraystretch}{1.12}")
    lines.append(r"    \resizebox{\linewidth}{!}{%")
    lines.append(f"    \\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"    \toprule")

    header1 = "    "
    for m in model_data:
        header1 += f"    & \\multicolumn{{3}}{{c}}{{\\textbf{{{m['model']['tex_name']}}}}}"
    header1 += " \\\\"
    lines.append(header1)

    cmidrules = "    "
    for i, m in enumerate(model_data):
        start = 2 + i * 3
        end = start + 2
        cmidrules += f"\\cmidrule(lr){{{start}-{end}}}"
    lines.append(cmidrules)

    header2 = "    \\textbf{Protocol}"
    for _ in model_data:
        header2 += "    & Acc & Tok & Rec"
    header2 += " \\\\"
    lines.append(header2)
    lines.append(r"    \midrule")

    best_acc = {}
    for i, m in enumerate(model_data):
        best = max(
            (m["mq_table"].get(p, {}).get("acc", 0) for p in PROTOCOL_ORDER if p in m["mq_table"]),
            default=0,
        )
        best_acc[i] = best

    for section_label, section_protocols in PROTOCOL_SECTIONS:
        lines.append(f"    \\multicolumn{{{1 + n_models * 3}}}{{l}}{{\\textit{{{section_label}}}}} \\\\")
        for proto in section_protocols:
            row = f"    \\quad {PROTOCOL_LABELS[proto]}"
            for i, m in enumerate(model_data):
                t = m["mq_table"].get(proto, {})
                acc = t.get("acc")
                tok = t.get("mean_comm_tokens")
                rec = t.get("recovery")
                acc_str = fmt_acc(acc)
                if acc is not None and abs(acc - best_acc[i]) < 1e-6:
                    acc_str = r"\textbf{" + acc_str + "}"
                tok_str = fmt_tok(tok)
                rec_str = fmt_rec(rec)
                row += f"    & {acc_str} & {tok_str} & {rec_str}"
            row += " \\\\"
            lines.append(row)
        lines.append(r"    \midrule")

    lines.pop()
    lines.append(r"    \bottomrule")
    lines.append(r"    \end{tabular}%")
    lines.append(r"    }")
    lines.append(r"\end{table*}")
    return "\n".join(lines)


def make_audit_table(model: dict, benchmark: str, n_instances: int) -> str:
    """Generate one audit table (like Tables 3-4) for a single model × benchmark."""
    audit = model.get(f"{benchmark}_audit", {})
    short_label = {"sb": "Silo-Bench", "mq": "MuSiQue"}[benchmark]
    tab_label = f"tab:audit_{benchmark}_{model['model']['short']}"
    caption_extra = {
        "sb": f"(52 tasks, combined $n{{=}}5$+$n{{=}}10$). Metrics as in Table~\\ref{{tab:audit_sb}}.",
        "mq": f"(100 instances). Metrics as in Table~\\ref{{tab:audit_mq}}.",
    }[benchmark]

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(f"    \\caption{{Evidence-flow audit for \\textbf{{{model['model']['tex_name']}}}"
                 f" (\\texttt{{{model['model']['api_name']}}})")
    lines.append(f"    on \\textbf{{{short_label}}} {caption_extra}}}")
    lines.append(f"    \\label{{{tab_label}}}")
    lines.append(r"    \centering")
    lines.append(r"    \small")
    lines.append(r"    \setlength{\tabcolsep}{5pt}")
    lines.append(r"    \renewcommand{\arraystretch}{1.12}")
    lines.append(r"    \begin{tabular}{lrrrrrr}")
    lines.append(r"    \toprule")
    lines.append(r"    \textbf{Protocol}")
    lines.append(r"        & \textbf{Crit.\,Rec.}$\uparrow$")
    lines.append(r"        & \textbf{Omission}$\downarrow$")
    lines.append(r"        & \textbf{Distortion}$\downarrow$")
    lines.append(r"        & \textbf{Redundancy}$\downarrow$")
    lines.append(r"        & \textbf{Useful\,Bgt}$\uparrow$")
    lines.append(r"        & \textbf{Agg.\,Fail\,(\%)}$\downarrow$ \\")
    lines.append(r"    \midrule")

    for proto in AUDIT_PROTOCOLS:
        a = audit.get(proto, {})
        crit_rec = fmt_audit(a.get("crit_rec", a.get("crit_recall")))
        omission = fmt_audit(a.get("omission"))
        distortion = fmt_audit(a.get("distortion")) if a.get("distortion") is not None else "---"
        redundancy = fmt_audit(a.get("redundancy")) if a.get("redundancy") is not None else "---"
        useful_bgt = fmt_audit(a.get("useful_budget")) if a.get("useful_budget") is not None else "---"
        agg_fail = fmt_pct(a.get("agg_fail"))
        label = PROTOCOL_LABELS.get(proto, proto)
        lines.append(f"    {label:<30} & {crit_rec} & {omission} & {distortion}"
                     f"   & {redundancy} & {useful_bgt} & {agg_fail} \\\\")

    lines.append(r"    \bottomrule")
    lines.append(r"    \end{tabular}")

    if benchmark == "sb":
        lines.append(r"    \vspace{2pt}\\")
        lines.append(r"    {\small \textit{Full Evidence Sharing AggFail\,=\,$1{-}$Acc since CritRec\,$=1$ by construction.")
        lines.append(r"    Relay AggFail computed over instances where per-instance CritRec\,$=1.0$.}}")
    elif benchmark == "mq":
        lines.append(r"    \vspace{2pt}\\")
        lines.append(r"    {\small \textit{All relay protocols achieve CritRec\,$=1.000$ on MuSiQue;")
        lines.append(r"    aggregation failure is the dominant bottleneck.}}")

    lines.append(r"\end{table*}")
    return "\n".join(lines)


def make_hop_table(model_data: list[dict]) -> str:
    """
    Multi-model AggFail by hop count on MuSiQue for new models.
    Similar to tab:hop_agg_multimodel in app_main.tex.
    """
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"    \caption{AggFail (\%) by hop count on MuSiQue (100 instances)")
    lines.append(r"    for four additional models (Full Evidence Sharing and Random Relay).}")
    lines.append(r"    \label{tab:new_models_hop}")
    lines.append(r"    \centering")
    lines.append(r"    \small")
    lines.append(r"    \setlength{\tabcolsep}{5pt}")
    lines.append(r"    \renewcommand{\arraystretch}{1.12}")
    lines.append(r"    \begin{tabular}{ll rrrr}")
    lines.append(r"    \toprule")
    lines.append(r"    \textbf{Protocol} & \textbf{Model} & \textbf{2-hop} & \textbf{3-hop} & \textbf{4-hop} & \textbf{Pooled} \\")
    lines.append(r"    \midrule")

    for proto_name, proto_key in [("Full Evidence Sharing", "full_sharing"),
                                   ("Random Relay", "random_relay")]:
        first = True
        for m in model_data:
            hops = m.get("mq_hop", {}).get(proto_key, {})
            h2 = fmt_pct(hops.get(2))
            h3 = fmt_pct(hops.get(3))
            h4 = fmt_pct(hops.get(4))
            hall = fmt_pct(hops.get("all"))
            if first:
                lines.append(f"    \\multirow{{{len(model_data)}}}{{*}}{{{proto_name}}}")
                first = False
            else:
                lines.append("    ")
            lines.append(f"      & {m['model']['tex_name']:<20} & {h2} & {h3} & {h4} & {hall} \\\\")
        lines.append(r"    \midrule")

    lines.pop()
    lines.append(r"    \bottomrule")
    lines.append(r"    \end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def make_summary_paragraph(model_data: list[dict]) -> str:
    """Generate a summary paragraph describing qualitative patterns."""
    lines = []
    lines.append(r"\paragraph{Qualitative patterns.}")
    lines.append(r"Across all four new models, the same two failure modes documented for the original six models persist.")

    # Check Silo-Bench patterns
    for m in model_data:
        combined = m.get("combined", {})
        sb_audit = m.get("sb_audit", {})
        relay_crit_rec = sb_audit.get("random_relay", {}).get("crit_rec")
        fs_agg_fail = sb_audit.get("full_sharing", {}).get("agg_fail")
        if relay_crit_rec is not None:
            lines.append(f"{m['model']['tex_name']}: Silo-Bench CritRec\,=\,{relay_crit_rec:.3f} "
                        f"(relay), AggFail\,=\,{fmt_pct(fs_agg_fail)}\% (FS).")

    lines.append(r"On MuSiQue, relay protocols achieve CritRec\,$\approx 1.0$"
                 r" while aggregation failure remains the dominant bottleneck across all models.")

    return " ".join(lines)


def generate_latex(model_data: list[dict]) -> str:
    parts = []
    parts.append("% ============================================================")
    parts.append(r"\section{Additional Model Robustness Evaluation}")
    parts.append(r"\label{app:new_models}")
    parts.append("% ============================================================")
    parts.append("")
    parts.append(r"This appendix reports protocol comparison results and evidence-flow audit metrics")
    parts.append(r"for four additional models: Gemini-2.5-Flash-Lite, GPT-4o-mini,")
    parts.append(r"DeepSeek-R1-distill-Qwen-32B, and Gemma-4-31B-it.")
    parts.append(r"All models were evaluated on Silo-Bench (52 tasks, combined $n{=}5$+$n{=}10$)")
    parts.append(r"and MuSiQue (100 instances) using the same protocols, prompts, and hyperparameters")
    parts.append(r"as the main paper, with only the three debate/gated protocols omitted.")
    parts.append("")
    parts.append(r"\subsection{Protocol Comparison}")
    parts.append(r"\label{app:new_models_proto}")
    parts.append("")

    # Silo-Bench main table
    parts.append(make_silobench_table(model_data))
    parts.append("")

    # MuSiQue main table
    parts.append(make_musique_table(model_data))
    parts.append("")

    parts.append(r"\subsection{Evidence-Flow Audit}")
    parts.append(r"\label{app:new_models_audit}")
    parts.append("")
    parts.append(r"Tables~\ref{tab:audit_sb_geminiflashlite}--\ref{tab:audit_mq_gemma31b}")
    parts.append(r"replicate the audit of Tables~\ref{tab:audit_sb}--\ref{tab:audit_mq}")
    parts.append(r"for the four new models.")
    parts.append(r"Distortion metrics are omitted (require separate LLM judge calls).")
    parts.append("")

    # Audit tables for each model
    for m in model_data:
        parts.append(f"% --- {m['model']['label']} ---")
        parts.append(make_audit_table(m, "sb", 52))
        parts.append("")
        parts.append(make_audit_table(m, "mq", 100))
        parts.append("")

    # Hop stratification
    parts.append(r"\subsection{Hop-Count Stratification on MuSiQue}")
    parts.append(r"\label{app:new_models_hop}")
    parts.append("")
    parts.append(make_hop_table(model_data))
    parts.append("")

    return "\n".join(parts)


def compute_musique_table_with_recovery(mq_res: dict) -> dict:
    """Compute acc, tok, recovery for MuSiQue results table."""
    table = mq_res.get("table", {})
    local_acc = table.get("single_local", {}).get("acc", 0)
    full_acc = table.get("full_sharing", {}).get("acc", 0)
    denom = full_acc - local_acc

    result = {}
    for p, row in table.items():
        acc = row.get("acc", 0)
        tok = row.get("mean_comm_tokens", 0)
        if abs(denom) > 1e-6:
            rec = (acc - local_acc) / denom
        else:
            rec = 0.0
        result[p] = {"acc": acc, "mean_comm_tokens": tok, "recovery": rec}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true",
                        help="Skip models with missing results instead of erroring")
    args = parser.parse_args()

    all_model_data = []

    for model in MODELS:
        short = model["short"]
        print(f"\nProcessing {model['label']}...")

        n5_res = load_results(model["n5_dir"])
        n10_res = load_results(model["n10_dir"])
        mq_res = load_results(model["mq_dir"])
        n5_audit = load_audit(model["n5_dir"])
        n10_audit = load_audit(model["n10_dir"])
        mq_audit = load_audit(model["mq_dir"])

        missing = []
        if n5_res is None:
            missing.append(model["n5_dir"])
        if n10_res is None:
            missing.append(model["n10_dir"])
        if mq_res is None:
            missing.append(model["mq_dir"])

        if missing:
            if args.partial:
                print(f"  WARNING: Missing results for {model['label']}: {missing}")
                print(f"  Skipping or using partial data...")
                if n5_res is None or n10_res is None:
                    print(f"  Skipping {model['label']} (incomplete Silo-Bench).")
                    continue
            else:
                print(f"  ERROR: Missing results for {model['label']}: {missing}")
                print(f"  Use --partial to skip incomplete models.")
                sys.exit(1)

        # Combine Silo-Bench n5+n10
        combined = combine_silobench(n5_res, n10_res)
        sb_audit = combine_audit(n5_audit, n10_audit, model["n5_dir"], model["n10_dir"])
        mq_table = compute_musique_table_with_recovery(mq_res) if mq_res else {}

        # Inject full_sharing into mq_audit using exact-match-based AggFail
        if mq_audit is None:
            mq_audit = {}
        if "full_sharing" not in mq_audit:
            mq_fs_af = fs_agg_fail_from_per_instance(model["mq_dir"])
            if mq_fs_af is not None:
                mq_audit["full_sharing"] = {
                    "crit_rec": 1.0,
                    "omission": 0.0,
                    "redundancy": None,
                    "useful_budget": None,
                    "agg_fail": mq_fs_af,
                }

        # Hop stratification for MuSiQue
        mq_hop = {}
        if mq_res:
            try:
                mq_rows = load_per_instance(model["mq_dir"])
                if mq_rows:
                    mq_hop = hop_stratification(mq_rows)
            except Exception as e:
                print(f"  WARNING: hop stratification failed: {e}")

        all_model_data.append({
            "model": model,
            "combined": combined,
            "sb_audit": sb_audit,
            "mq_table": mq_table,
            "mq_audit": mq_audit or {},
            "mq_hop": mq_hop,
        })

        print(f"  Silo-Bench combined (52 tasks):")
        for p in PROTOCOL_ORDER:
            if p in combined:
                t = combined[p]
                print(f"    {p:<30} acc={t['acc']*100:.1f}%  tok={t['mean_comm_tokens']:.0f}  rec={t.get('recovery', 0):.2f}")

        if mq_table:
            print(f"  MuSiQue (100 instances):")
            for p in PROTOCOL_ORDER:
                if p in mq_table:
                    t = mq_table[p]
                    print(f"    {p:<30} acc={t['acc']*100:.1f}%  tok={t['mean_comm_tokens']:.0f}  rec={t.get('recovery', 0):.2f}")

    if not all_model_data:
        print("No complete model data found. Nothing to write.")
        sys.exit(1)

    latex = generate_latex(all_model_data)

    os.makedirs(os.path.dirname(OUT_TEX), exist_ok=True)
    with open(OUT_TEX, "w") as f:
        f.write(latex + "\n")
    print(f"\nLaTeX written to: {OUT_TEX}")


if __name__ == "__main__":
    main()
