"""Silo-Bench: are the gold supports whole agent shards or subsets of their records? $0, no calls.

For each of the 208 main-table traces: records in the agents' private shards, records named by the gold
supports, and a per-support classification (whole shard / subset of a shard / not found).
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POP = ROOT / 'rebuttal/pilots/20261115_proxy_support_sb_fixed/population.json'
OUT = ROOT / 'rebuttal/pilots/20261115_sb_nogold_check'


def parse(x):
    for f in (json.loads, ast.literal_eval):
        try:
            return f(x)
        except Exception:
            pass
    return None


def records(text):
    v = parse(text.strip())
    if isinstance(v, list) and len(v) > 1:
        return len(v), 'list'
    if isinstance(v, dict) and len(v) > 1:
        return len(v), 'dict'
    return 1, 'text'


def norm(x):
    return ' '.join(str(x).split())


def main():
    rows = json.loads(POP.read_text())
    per = []
    tot = {'traces': 0, 'shards': 0, 'shard_records': 0, 'gold_supports': 0, 'gold_records': 0,
           'whole': 0, 'subset': 0, 'not_found': 0}
    for r in rows:
        shards = {norm(d['text']): d['unit_id'] for d in r['documents']}
        shard_rec = sum(records(d['text'])[0] for d in r['documents'])
        g_rec = 0
        cls = {'whole': 0, 'subset': 0, 'not_found': 0}
        for g in (r.get('gold_supports') or []):
            n, kind = records(g['text'])
            g_rec += n
            t = norm(g['text'])
            if t in shards:
                cls['whole'] += 1
            elif any(t in s for s in shards):
                cls['subset'] += 1
            else:
                cls['not_found'] += 1
        per.append({'key': r['key'], 'shards': len(r['documents']), 'shard_records': shard_rec,
                    'gold_supports': len(r.get('gold_supports') or []), 'gold_records': g_rec,
                    **cls})
        tot['traces'] += 1; tot['shards'] += len(r['documents']); tot['shard_records'] += shard_rec
        tot['gold_supports'] += len(r.get('gold_supports') or []); tot['gold_records'] += g_rec
        for k in cls:
            tot[k] += cls[k]
    ex = next(p for p in per if p['shards'] >= 5)
    exrow = next(r for r in rows if r['key'] == ex['key'])
    out = {'totals': tot, 'per_trace': per, 'example': {
        'key': exrow['key'], 'question': exrow['question'],
        'shards': [{'unit_id': d['unit_id'], 'records': records(d['text'])[0], 'text': d['text']}
                   for d in exrow['documents']],
        'gold_supports': [{'unit_id': g['unit_id'], 'records': records(g['text'])[0], 'text': g['text']}
                          for g in exrow['gold_supports']]}}
    (OUT / 'shard_check.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(tot, indent=1))


if __name__ == '__main__':
    main()