"""Wilson 95% intervals for the response-file proportions, from source counts. $0.

    ./.conda-env/bin/python -m scripts.wilson_table
Output: rebuttal/pilots/20261115_response_wilson/wilson.json and printed table.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_response_wilson'


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(p, 3), round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


ROWS = {
    # attribution, 89 known-stage cases; corrupted = 30 injected, missing = 59 cohort
    'attr_qwen_token_corrupted': (27, 30), 'attr_qwen_token_missing': (30, 59), 'attr_qwen_token_total': (57, 89),
    'attr_qwen_stmt_corrupted': (27, 30), 'attr_qwen_stmt_missing': (37, 59), 'attr_qwen_stmt_total': (64, 89),
    'attr_qwen_judge_corrupted': (27, 30), 'attr_qwen_judge_missing': (29, 59), 'attr_qwen_judge_total': (56, 89),
    'attr_qwen_r1_corrupted': (25, 30), 'attr_qwen_r1_missing': (37, 59), 'attr_qwen_r1_total': (62, 89),
    'attr_gem_token_corrupted': (21, 30), 'attr_gem_token_missing': (40, 59), 'attr_gem_token_total': (61, 89),
    'attr_gem_stmt_corrupted': (21, 30), 'attr_gem_stmt_missing': (45, 59), 'attr_gem_stmt_total': (66, 89),
    'attr_gem_judge_corrupted': (24, 30), 'attr_gem_judge_missing': (43, 59), 'attr_gem_judge_total': (67, 89),
    'attr_gem_r1_corrupted': (27, 30), 'attr_gem_r1_missing': (26, 59), 'attr_gem_r1_total': (53, 89),
    'attr_lex_corrupted': (0, 30), 'attr_lex_missing': (39, 59), 'attr_lex_total': (39, 89),
    # UEGh W2 and CR8J validation: proportions with counts in the source reports
    'relay_strict_pooled': (38, 845), 'relay_broad_pooled': (245, 845),
    'summary_strict_numeric_old': (13, 148), 'omission_summary_numeric': (242, 390),
    'omission_relay_numeric': (25, 945),
    'musique_presence_val': (183, 189), 'silo_presence_val': (471, 515), 'musique_subclaim_val': (139, 144),
    'strict_natural_board_val': (158, 163), 'strict_constructed_val': (35, 37),
    'repair_reextract': (12, 39), 'repair_reextract_ctrl': (0, 39), 'repair_restore': (13, 92),
    'repair_restore_ctrl': (0, 92), 'repair_insert': (32, 59), 'repair_insert_ctrl': (0, 59),
    'repair_place': (8, 30), 'repair_place_ctrl': (0, 30),
    'e3_pool': (737, 2395), 'e3_aggregation': (789, 2395),
    'q1_6of30_agree': (6, 30), 'q1_62of81_agree': (62, 81),
    'relay_absent_validated': (100, 945),
}


def main():
    out = {}
    for name, (k, n) in ROWS.items():
        p, lo, hi = wilson(k, n)
        out[name] = {'k': k, 'n': n, 'p': p, 'wilson95': [lo, hi]}
        print(f'{name:32s} {k}/{n} = {p:.3f} [{lo:.3f}, {hi:.3f}]')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'wilson.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
