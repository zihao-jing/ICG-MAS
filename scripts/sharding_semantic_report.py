"""Canonical sharding-rescore numbers: 89 denominators, old/new confusion, changed cases, repair effect. $0."""
import json
from collections import Counter
from pathlib import Path

import scripts.b5_attribution_2x2 as B

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
OUT = PILOTS / '20261115_sharding_semantic'


def rollup(st):
    v = list(st.values())
    if not v:
        return 'invalid'
    if all(x == 'present' for x in v):
        return 'present'
    if all(x == 'absent' for x in v):
        return 'absent'
    return 'partial'


def stages():
    cases = {c['key']: c for c in json.loads(B.CASES.read_text())}
    known = {k: c['known_stage'] for k, c in cases.items()}
    old = {'gemini': {r['key']: (r.get('stage') or 'uncertain')
                      for r in json.loads(B.AUDIT_A_RESULTS.read_text())['items']},
           'qwen': {r['key']: (r.get('stage') or 'uncertain') for r in
                    json.loads((PILOTS / '20261115_b5_qwen_design_a/results.json').read_text())['items']}}
    miss = json.loads((OUT / 'missing_by_cell.json').read_text())
    lab = {}
    for l in (OUT / 'results.jsonl').read_text().splitlines():
        if l.strip():
            e = json.loads(l)
            lab[(e['key'], e['fact_id'])] = rollup(e['statuses'])
    new = {}
    for cell in ('gemini', 'qwen'):
        r = {}
        for k, st in old[cell].items():
            fids = miss.get(f'{k}|{cell}')
            ls = [lab.get((k, f), 'invalid') for f in (fids or [])]
            r[k] = st if (not fids or 'invalid' in ls) else ('sharding' if 'absent' in ls else 'extraction')
        new[cell] = r
    return known, old, new, lab, miss


def main():
    known, old, new, lab, miss = stages()
    out = {}
    for cell in ('gemini', 'qwen'):
        keys = list(known)
        co = Counter((known[k], old[cell][k]) for k in keys)
        cn = Counter((known[k], new[cell][k]) for k in keys)
        ok_o = sum(known[k] == old[cell][k] for k in keys)
        ok_n = sum(known[k] == new[cell][k] for k in keys)
        changed = [k for k in keys if old[cell][k] != new[cell][k]]
        broke = [k for k in changed if known[k] == old[cell][k]]
        fixed = [k for k in changed if known[k] == new[cell][k]]
        sel = [k for k in keys if known[k] == 'sharding' and old[cell][k] == 'extraction']
        out[cell] = {
            'old': ok_o, 'new': ok_n,
            'confusion_old': {f'{a}->{b}': n for (a, b), n in co.items() if a != b},
            'confusion_new': {f'{a}->{b}': n for (a, b), n in cn.items() if a != b},
            'uncertain_old': [k for k in keys if old[cell][k] == 'uncertain'],
            'changed': [{'key': k, 'known': known[k], 'old': old[cell][k], 'new': new[cell][k],
                         'facts': [(f, lab.get((k, f))) for f in miss.get(f'{k}|{cell}', [])]}
                        for k in changed],
            'broke': [k for k in broke],
            'fixed': [k for k in fixed],
            'sharding15': {'n': len(sel), 'moved': sum(1 for k in sel if new[cell][k] == 'sharding'),
                           'stay_extraction': sum(1 for k in sel if new[cell][k] == 'extraction')},
        }
    (OUT / 'canonical.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({c: {k: v for k, v in out[c].items() if k != 'changed'} for c in out}, indent=1))


if __name__ == '__main__':
    main()