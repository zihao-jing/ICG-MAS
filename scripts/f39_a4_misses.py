"""A4: read every audit miss (old rule, 82 runs) against its fact-table row and sort it into a cause.

Rule: rebuttal/pilots/prereg/Stage-naming-A4-miss-causes-v1.md (hashed before this script ran). Zero calls.
Options (amendment 1, build-bug correction): --strict reads fact_tables_strict.json and writes a4_misses_strict.json;
--only gemini:<instance-id>,... restricts the rerun to the listed Gemini items.
Output: rebuttal/pilots/20261116_stage_naming/a4_misses.json (default)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'
RULE = P / 'prereg/Stage-naming-A4-miss-causes-v1.md'
EXPECT = '1951d8c85ee9ae7a9d3abc38e2dade05d0bd5252caf844179393a286f1b8e50b'
DELETED_DROP = {'2hop__826864_17335', '2hop__434218_29898', '2hop__189094_612080',
                '2hop__301587_233146', '3hop2__88342_93066_90766', '3hop1__163654_503371_21711'}


def misses():
    out = []
    for it in json.loads((P / '20261115_b5_attribution_2x2/audit_a_gemini.json').read_text())['items']:
        if it['key'].startswith('inj/') and it.get('stage') != it['known_stage']:
            out.append((it['key'], 'gemini', it['known_stage'], it.get('stage')))
    for it in json.loads((P / '20261115_b5_qwen_design_a/results.json').read_text())['items']:
        if it['key'].startswith('inj/') and it.get('stage') != it['known_stage']:
            out.append((it['key'], 'qwen', it['known_stage'], it.get('stage')))
    res = json.loads((P / '20261115_injection_amendA3/results.json').read_text())
    for c in res['cases']:
        if c.get('kept') in (True, 'True') and c['instance'] not in DELETED_DROP:
            m = c['methods'] if isinstance(c['methods'], dict) else __import__('ast').literal_eval(c['methods'])
            key = f"case/{c['type']}/{c['model']}/{c['instance']}"
            for bb in ('qwen', 'gemini'):
                st = m.get(f'audit_{bb}_old')
                if st != c['type']:
                    out.append((key, bb, c['type'], st))
    return out


def classify(key, bb, known, stage, row):
    if row is None or 'excluded' in row:
        return 'unreadable', 'no fact-table row'
    st = row['audit_status']
    ext, brd = st['extraction'], st['board']
    absent_both = not ext and not brd
    if known in ('extraction', 'sharding') and absent_both:
        return 'lost fact routed past its checkpoint', f'table: absent at both; audit said {stage}'
    if known == 'transmission' and any(x in ('distorted', 'absent') for x in brd):
        return 'distorted fact routed away from transmission', f'table: extraction {ext}, board {brd}; audit said {stage}'
    if stage == 'aggregation' and brd and all(x in ('faithful', 'partial') for x in brd):
        return 'fact carried, answer still wrong', f'table: extraction {ext}, board {brd}'
    return 'other', f'table: extraction {ext}, board {brd}; audit said {stage}'


def main():
    sha = hashlib.sha256(RULE.read_bytes()).hexdigest()
    assert sha == EXPECT, 'rule changed after hashing'
    strict = '--strict' in sys.argv
    only = None
    for a in sys.argv:
        if a.startswith('--only='):
            only = {tuple(x.split(':', 1)) for x in a.split('=', 1)[1].split(',')}
    rows = json.loads((OUT / ('fact_tables_strict.json' if strict else 'fact_tables.json')).read_text())
    idx = {(r['key'], r['backbone']): r for r in rows if 'backbone' in r}
    out = []
    for key, bb, known, stage in misses():
        if only is not None and not any(bb == b and inst in key for b, inst in only):
            continue
        row = idx.get((key, bb))
        cat, why = classify(key, bb, known, stage, row)
        out.append({'key': key, 'backbone': bb, 'known': known, 'audit_stage': stage, 'category': cat,
                    'evidence': why, 'table_status': (row or {}).get('audit_status')})
    name = 'a4_misses_strict.json' if strict else 'a4_misses.json'
    if only is not None:
        name = name.replace('.json', '_only.json')
    (OUT / name).write_text(json.dumps({'rule_sha256': sha, 'n': len(out), 'items': out}, indent=1))
    from collections import Counter
    print(json.dumps({'n_misses': len(out), 'categories': Counter(o['category'] for o in out)}, indent=1))
    for o in out:
        print(o['backbone'], o['key'], o['known'], '->', o['audit_stage'], '|', o['category'], '|', o['evidence'])


if __name__ == '__main__':
    main()
