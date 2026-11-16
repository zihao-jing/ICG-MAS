"""Paired exact (McNemar) test: judge alone vs judge + audit evidence on the 82 known-cause runs (step 46).

Reads only stored outputs (no calls). Judge alone: injected runs from judge_qwen.json / results_v2.json,
deleted-fact runs from 20261115_injection_amendA3/results.json (methods.judge_*). Judge + audit: a2_results.jsonl
(51 runs) and a2_results_all82.jsonl (31 runs). Correct = stage equals the known stage (injected: transmission).
Prints the 2x2 table and the two-sided exact binomial p-value.
"""
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots/'
S = P / '20261116_stage_naming/'


def load_alone():
    out = {}
    for it in json.loads((P / '20261115_b5_attribution_2x2/judge_qwen.json').read_text())['items']:
        if it['population'] == 'injected':
            out[('qwen', it['key'])] = it['stage'] == it['known_stage']
    for it in json.loads((P / '20261113_attribution_comparison/results_v2.json').read_text())['items']:
        if it['population'] == 'injected':
            out[('gemini', it['key'])] = it['judge']['stage'] == it['known_stage']
    cases = json.loads((P / '20261115_injection_amendA3/results.json').read_text())['cases']
    kept = {(c['model'], c['instance'], c['type']): c for c in cases if c.get('kept') in (True, 'True')}
    for r in json.loads((S / 'fact_tables_strict.json').read_text()):
        if r.get('population') == 'deleted' and 'backbone' in r:
            _, typ, m, inst = r['key'].split('/')
            c = kept[(m, inst, typ)]
            out[(r['backbone'], r['key'])] = c['methods']['judge_' + r['backbone']] == r['known_stage']
    return out


def load_with():
    out = {}
    for f in ('a2_results.jsonl', 'a2_results_all82.jsonl'):
        for l in (S / f).read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r['population'] == 'injected':
                ok = r['judge_with_audit'] == 'transmission'
            else:
                ok = r['judge_with_audit'] == r['known_stage']
            out[(r['backbone'], r['key'])] = ok
    return out


def mcnemar_exact(b, c):
    n = b + c
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, p)


if __name__ == '__main__':
    alone, withe = load_alone(), load_with()
    keys = sorted(set(alone) & set(withe))
    assert len(keys) == 82, len(keys)
    a1 = sum(alone[k] for k in keys)
    a2 = sum(withe[k] for k in keys)
    both = sum(alone[k] and withe[k] for k in keys)
    alone_only = sum(alone[k] and not withe[k] for k in keys)
    with_only = sum(withe[k] and not alone[k] for k in keys)
    neither = sum((not alone[k]) and (not withe[k]) for k in keys)
    print(json.dumps({'n': len(keys), 'judge_alone_correct': a1, 'judge_with_audit_correct': a2,
                      'both': both, 'alone_only': alone_only, 'with_audit_only': with_only, 'neither': neither,
                      'mcnemar_exact_two_sided_p': round(mcnemar_exact(alone_only, with_only), 4)}, indent=1))
