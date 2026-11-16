"""A3 score: does the audit name the matched lost/corrupted fact? Rule: rebuttal/pilots/prereg/Stage-naming-A3-fact-named-v1.md.

    .conda-env/bin/python scripts/f39_a3_score.py                 # original table -> a3_score.json
    .conda-env/bin/python scripts/f39_a3_score.py --strict        # build-bug correction (amendment 1) -> a3_score_strict.json
Output: rebuttal/pilots/20261116_stage_naming/a3_score.json (or a3_score_strict.json)
"""
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261116_stage_naming'
RULE = ROOT / 'rebuttal/pilots/prereg/Stage-naming-A3-fact-named-v1.md'
EXPECT_SHA = 'd8ac0cac79df66867ffdd35db7d188c843caa3cfa9e7c7d940a5c8589ba817b8'


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def named_rule(r):
    st = r['audit_status']
    if r['population'] == 'deleted':
        return not st['extraction'] and not st['board']
    return any(x in ('distorted', 'absent') for x in st['board'])


def main():
    sha = hashlib.sha256(RULE.read_bytes()).hexdigest()
    assert sha == EXPECT_SHA, 'rule changed after hashing'
    strict = '--strict' in sys.argv
    table = 'fact_tables_strict.json' if strict else 'fact_tables.json'
    rows = json.loads((OUT / table).read_text())
    # a case-level exclusion (no unique fact match) removes both of that case's runs
    matched = [r for r in rows if 'backbone' in r and 'excluded' not in r]
    excluded = [r for r in rows if 'excluded' in r and 'backbone' in r]
    case_level = [r for r in rows if 'excluded' in r and 'backbone' not in r]
    excluded = excluded + [dict(r, backbone=b) for r in case_level for b in ('qwen', 'gemini')]
    out = {'rule_sha256': sha, 'table': table, 'cases_known_cause': 41, 'runs_total': 82, 'runs_matched': len(matched),
           'runs_excluded': len(excluded), 'cases_excluded_no_unique_fact_match': len(case_level),
           'excluded_reasons': dict(Counter(r['excluded'] for r in excluded)),
           'cells': {}}
    for pop in ('injected', 'deleted'):
        for bb in ('qwen', 'gemini'):
            sub = [r for r in matched if r['population'] == pop and r['backbone'] == bb]
            k = sum(1 for r in sub if named_rule(r))
            loose = sum(1 for r in sub if any(x != 'faithful' for cp in r['audit_status'].values() for x in cp))
            out['cells'][f'{pop}|{bb}'] = {'named': k, 'matched': len(sub), 'rate': round(k / len(sub), 3) if sub else None,
                                          'wilson95': wilson(k, len(sub)), 'loose_any_nonfaithful': loose}
    tot = [r for r in matched if named_rule(r)]
    out['all_matched'] = {'named': len(tot), 'matched': len(matched), 'rate': round(len(tot) / len(matched), 3),
                          'wilson95': wilson(len(tot), len(matched))}
    (OUT / ('a3_score_strict.json' if strict else 'a3_score.json')).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
