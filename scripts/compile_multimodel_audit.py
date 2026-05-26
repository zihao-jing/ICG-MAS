#!/usr/bin/env python3
"""
compile_multimodel_audit.py

Regenerates acl-style-files/appendix/app_audit_multimodel.tex
using audit_metrics.json files (including distortion if computed).

Models covered: Mistral-S, Qwen-80B-T, Qwen-3.6-Flash, Ring-1T, Qwen-235B
Benchmarks: Silo-Bench (n5+n10 combined) and MuSiQue (100 instances)
"""
from __future__ import annotations
import json, os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE = os.path.join(os.path.dirname(__file__), "..", "results")
OUT = os.path.join(
    os.path.dirname(__file__), "..", "acl-style-files", "appendix", "app_audit_multimodel.tex"
)

MODELS = [
    {
        "short":    "mistrals",
        "label":    "Mistral-S",
        "api_name": "mistralai/mistral-small-2603",
        "tex_name": r"Mistral-S",
        "sb_n5":    "run_mistrals",
        "sb_n10":   "run_mistrals_n10",
        "mq":       "run_musique_mistrals",
        "sb_note":  "All 52 instances included (complete extraction data).",
        "mq_note":  None,
    },
    {
        "short":    "qwen80bt",
        "label":    "Qwen-80B-T",
        "api_name": "qwen/qwen3-235b-a22b-thinking-2507",
        "tex_name": r"Qwen-80B-T",
        "sb_n5":    "run_qwen80bt",
        "sb_n10":   "run_qwen80bt_n10",
        "mq":       "run_musique_qwen80bt",
        "sb_note":  "All 52 instances included.",
        "mq_note":  None,
    },
    {
        "short":    "qwen36f",
        "label":    "Qwen-3.6-Flash",
        "api_name": "qwen/qwen3-6b-a3b",
        "tex_name": r"Qwen-3.6-Flash",
        "sb_n5":    "run_20260523_214416",
        "sb_n10":   "run_silobench_n10",
        "mq":       "run_musique_100",
        "sb_note":  "All 52 instances included.",
        "mq_note":  None,
    },
    {
        "short":    "ring1t",
        "label":    "Ring-1T",
        "api_name": "inclusionai/ring-2.6-1t",
        "tex_name": r"Ring-1T",
        "sb_n5":    None,
        "sb_n10":   "run_ring1t_n10",
        "mq":       "run_musique_ring1t",
        "sb_note":  r"Audit computed on $n{=}10$ only (extraction success rate near zero for $n{=}5$). Instance count may be lower than 26.",
        "mq_note":  None,
    },
    {
        "short":    "qwen235b",
        "label":    "Qwen-235B",
        "api_name": "qwen/qwen3-235b-a22b-2507",
        "tex_name": r"Qwen-235B",
        "sb_n5":    "run_qwen235b_n5",
        "sb_n10":   "run_qwen235b_n10",
        "mq":       "run_qwen235b_musique",
        "sb_note":  "All 52 instances included.",
        "mq_note":  None,
    },
]

RELAY_PROTOS = ["random_relay", "score_ranked_relay", "redundancy_aware_relay"]
PROTO_LABELS = {
    "summary_exchange":       "Summary Exchange",
    "random_relay":           "Random Evidence Relay",
    "score_ranked_relay":     "Score-Ranked Relay",
    "redundancy_aware_relay": "Redundancy-Aware Relay",
    "full_sharing":           "Full Evidence Sharing",
}
AUDIT_ORDER = ["summary_exchange", "random_relay", "score_ranked_relay",
               "redundancy_aware_relay", "full_sharing"]


def load_audit(run_dir: str) -> dict | None:
    if run_dir is None:
        return None
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
            "crit_rec":    s.get("crit_recall", s.get("crit_rec")),
            "omission":    s.get("omission"),
            "redundancy":  s.get("redundancy"),
            "useful_bgt":  s.get("useful_budget"),
            "agg_fail":    s.get("agg_fail_pct"),      # already in %
            "distortion":  distortion_by_proto.get(proto),
        }
    # Inject full_sharing from results.json (CritRec=1.0 by construction)
    res_path = os.path.join(BASE, run_dir, "results.json")
    if os.path.exists(res_path):
        with open(res_path) as f:
            res = json.load(f)
        fs_acc = res.get("table", {}).get("full_sharing", {}).get("acc")
        if fs_acc is not None:
            result["full_sharing"] = {
                "crit_rec":   1.0,
                "omission":   0.0,
                "redundancy": None,
                "useful_bgt": None,
                "agg_fail":   (1.0 - fs_acc) * 100.0,
                "distortion": 0.0,
            }
    return result


def combine_sb(n5: dict | None, n10: dict | None) -> dict:
    """Weighted average n5+n10 audit (equal weights, 26 each)."""
    if n5 is None and n10 is None:
        return {}
    if n5 is None:
        return dict(n10)
    if n10 is None:
        return dict(n5)
    combined = {}
    for proto in set(n5) | set(n10):
        r5, r10 = n5.get(proto, {}), n10.get(proto, {})
        combined[proto] = {}
        for field in set(r5) | set(r10):
            v5, v10 = r5.get(field), r10.get(field)
            if field == "distortion":
                vals = [v for v in [v5, v10] if isinstance(v, (int, float))]
                combined[proto][field] = sum(vals) / len(vals) if vals else None
            elif isinstance(v5, (int, float)) and isinstance(v10, (int, float)):
                combined[proto][field] = (v5 + v10) / 2
            else:
                combined[proto][field] = v5 if v5 is not None else v10
    return combined


def f3(v) -> str:
    return f"{v:.3f}" if isinstance(v, (int, float)) else "---"

def fpct(v) -> str:
    return f"{v:.1f}" if isinstance(v, (int, float)) else "---"


def make_table(model: dict, benchmark: str, audit: dict, note: str | None) -> str:
    short_label = {"sb": "Silo-Bench (52 tasks, combined $n{=}5$+$n{=}10$)",
                   "mq": "MuSiQue (100 instances)"}[benchmark]
    tab_ref   = {"sb": "tab:audit_sb", "mq": "tab:audit_mq"}[benchmark]
    tab_label = f"tab:audit_{benchmark}_{model['short']}"

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(f"    \\caption{{Evidence-flow audit for \\textbf{{{model['tex_name']}}}"
                 f" (\\texttt{{{model['api_name']}}})")
    lines.append(f"    on \\textbf{{{short_label}}}.")
    lines.append(f"    Metrics as in Table~\\ref{{{tab_ref}}}.}}")
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

    for proto in AUDIT_ORDER:
        a = audit.get(proto, {})
        label = PROTO_LABELS.get(proto, proto)
        cr  = f3(a.get("crit_rec"))
        om  = f3(a.get("omission"))
        dt  = f3(a.get("distortion"))   # "---" if None
        rd  = f3(a.get("redundancy"))
        ub  = f3(a.get("useful_bgt"))
        af  = fpct(a.get("agg_fail"))
        # Full sharing has no redundancy/useful_bgt
        if proto == "full_sharing":
            rd, ub = "---", "---"
        # SE has no distortion (it's a relay-protocol measure)
        if proto == "summary_exchange":
            dt = "---"
        lines.append(f"    {label:<30} & {cr} & {om} & {dt}   & {rd} & {ub} & {af} \\\\")

    lines.append(r"    \bottomrule")
    lines.append(r"    \end{tabular}")
    if note:
        lines.append(r"    \vspace{2pt}\\")
        lines.append(f"    {{\\small \\textit{{{note}}}}}")
    lines.append(r"\end{table*}")
    return "\n".join(lines)


def main():
    sections = []

    intro = r"""% ============================================================
\section{Multi-Model Evidence-Flow Audit}
\label{app:multimodel_audit}
% ============================================================

Tables~\ref{tab:audit_sb_mistrals}--\ref{tab:audit_mq_qwen235b} replicate the evidence-flow audit of the main paper
(Tables~\ref{tab:audit_sb}--\ref{tab:audit_mq}) for additional models.
For each model we report the same metrics on Silo-Bench (combined $n{=}5$+$n{=}10$, 52 tasks)
and MuSiQue (100 instances).

Across all models with complete extraction data (Mistral-S, Qwen-80B-T, Qwen-3.6-Flash, Qwen-235B),
the qualitative patterns hold:
(i) Silo-Bench relay protocols achieve Crit.\,Rec.\,$<1$ (ranging 0.71--0.93),
confirming that omission failure is a consistent bottleneck across model families;
(ii) MuSiQue relay protocols achieve Crit.\,Rec.\,$=1$,
yet aggregation failure remains the dominant mode (47--82\%\ across models),
confirming that evidence survival alone does not guarantee correct answers.

Ring-1T (\texttt{inclusionai/ring-2.6-1t}) had low extraction success rates (\textasciitilde{}38\%\ for $n{=}5$;
near zero for $n{=}10$), so its audit is computed from the $n{=}10$ run only.
"""
    sections.append(intro)

    for model in MODELS:
        # Silo-Bench
        n5_audit  = load_audit(model["sb_n5"])
        n10_audit = load_audit(model["sb_n10"])
        sb_audit  = combine_sb(n5_audit, n10_audit)
        if sb_audit:
            sections.append(f"\n% ------ {model['label']} Silo-Bench ------")
            sections.append(make_table(model, "sb", sb_audit, model.get("sb_note")))

        # MuSiQue
        mq_audit = load_audit(model["mq"])
        if mq_audit:
            sections.append(f"\n% ------ {model['label']} MuSiQue ------")
            sections.append(make_table(model, "mq", mq_audit, model.get("mq_note")))

    out_text = "\n\n".join(sections)
    with open(OUT, "w") as f:
        f.write(out_text + "\n")
    print(f"Written: {OUT}")


if __name__ == "__main__":
    main()
