"""Matched-granularity rescore of the failure-enriched proxy-vs-gold agreement (cap $1).

Rule `prereg/Proxy-gold-merge-v1.md`, hashed into build_manifest.json before any call. Stored labels from
`20261115_q1_second_sample` are reused at $0; the only calls are the equivalence check, one per trace.

    ./run.sh python -m scripts.proxy_gold_merge --build
    ./run.sh python -m scripts.proxy_gold_merge --run
    ./run.sh python -m scripts.proxy_gold_merge --score
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Proxy-gold-merge-v1.md'
PROMPT = PILOTS / 'prereg/proxy_support_equiv_prompt_v1.json'
SRC = PILOTS / '20261115_q1_second_sample'
OUT = PILOTS / '20261115_proxy_gold_merge'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'equiv.jsonl'
MODEL = 'google/gemini-3.6-flash'
PRICE = (0.15 / 1e6, 0.60 / 1e6)
CAP = 1.00


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def stored():
    """Per-trace gold text, proxy facts, and stored stages."""
    man = json.loads((SRC / 'build_manifest.json').read_text())
    rows = [json.loads(l) for l in (SRC / 'results.jsonl').read_text().splitlines() if l.strip()]
    pop = {r['instance_id']: r for r in json.loads(
        (PILOTS / '20261115_proxy_support_mq/population.json').read_text()) if r['protocol'] == 'random_relay'}
    facts = json.loads((PILOTS / '20261115_proxy_support_mq/facts.json').read_text())
    out = []
    for inst in man['traces']:
        recs = [r for r in rows if r['instance'] == inst and r['valid']]
        gold = [r for r in recs if r['kind'] == 'gold']
        proxy = [r for r in recs if r['kind'] == 'proxy']
        if not gold or not proxy:
            continue
        p = pop[inst]
        f = facts.get(p['key']) or {}
        if f.get('status') != 'ok':
            continue
        out.append({'instance': inst, 'key': p['key'], 'question': p['question'],
                    'gold_text': (p.get('gold_supports') or [{'text': ''}])[0]['text'],
                    'gold_support_ids': [g.get('unit_id') or (p.get('gold_supports') or [{}])[0].get('unit_id')
                                         for g in (p.get('gold_supports') or [])],
                    'proxy_facts': f['value']['facts'],
                    'labels': {r['fact_id']: r['stages'] for r in recs},
                    'atoms': {r['fact_id']: r['atoms'] for r in recs}})
    return out


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    rows = stored()
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'model': MODEL, 'cap_usd': CAP,
           'traces': [r['instance'] for r in rows], 'calls': len(rows),
           'note': 'stored labels from 20261115_q1_second_sample reused at $0'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'traces'}, indent=1))


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and file_sha(PROMPT) == man['prompt_sha256']
    spec = json.loads(PROMPT.read_text())
    done = set()
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                done.add(json.loads(l)['instance'])
    total = spent()
    for r in stored():
        if r['instance'] in done:
            continue
        facts_txt = '\n'.join(f"{f['fact_id']}: {f['text']}" for f in r['proxy_facts'])
        user = spec['user'].format(question=r['question'], facts=facts_txt, supports=r['gold_text'])
        est_in = math.ceil((len(spec['system']) + len(user)) / 4)
        est_out = 120 + 60 * len(r['proxy_facts'])
        if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
            print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'instance': r['instance']}) + '\n')
        resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                                         max_tokens=3000, temperature=0))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', est_in) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
        total += cost
        txt = resp.content or ''
        a, b = txt.find('{'), txt.rfind('}')
        parsed = None
        try:
            obj = json.loads(txt[a:b + 1])
            parsed = {x['fact_id']: {'verdict': x.get('verdict'),
                                     'support_ids': x.get('support_ids') or []} for x in obj['facts']}
        except Exception:
            parsed = None
        rec = {'instance': r['instance'], 'equiv': parsed, 'valid': parsed is not None and
               set(parsed) == {f['fact_id'] for f in r['proxy_facts']}}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'instance': r['instance'], 'usage': u,
                                'cost_usd': round(cost, 8), 'valid': rec['valid']}) + '\n')
        print(json.dumps({'inst': r['instance'], 'valid': rec['valid'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def merge_stage(r, equiv):
    gold_ids = set(r['gold_support_ids'])
    groups = {}
    for f in r['proxy_facts']:
        fid = f['fact_id']
        e = (equiv or {}).get(fid) or {}
        ids = set(e.get('support_ids') or [])
        if e.get('verdict') == 'equivalent' and len(ids) == 1 and ids <= gold_ids:
            gid = ('gold', sorted(ids)[0])
        else:
            gid = ('proxy', fid)
        groups.setdefault(gid, []).append(fid)
    stage_of = {}
    for gid, fids in groups.items():
        for cp in ('extraction', 'board'):
            sts = [r['labels'][fid][cp] for fid in fids]
            stage_of[(gid, cp)] = ('present' if 'present' in sts else
                                   'partial' if 'partial' in sts else 'absent')
    for cp, name in (('extraction', 'extraction'), ('board', 'transmission')):
        if any(stage_of[(g, cp)] == 'absent' for g in groups):
            return name, len(groups)
    return 'aggregation', len(groups)


def trace_stage(labels):
    if any(v['extraction'] == 'absent' for v in labels.values()):
        return 'extraction'
    if any(v['board'] == 'absent' for v in labels.values()):
        return 'transmission'
    return 'aggregation'


def wilson(k, n, z=1.959964):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - h, c + h


def score():
    eq = {}
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                eq[e['instance']] = (e.get('equiv'), e['valid'])
    rows = []
    for r in stored():
        equiv, valid = eq.get(r['instance'], (None, False))
        proxy_labels = {k: v for k, v in r['labels'].items() if k != 'g0'}
        gold_stage = trace_stage({'g0': r['labels']['g0']})
        unmerged = trace_stage(proxy_labels)
        merged, ngroups = merge_stage(r, equiv if valid else None)
        rows.append({'instance': r['instance'], 'gold': gold_stage, 'unmerged': unmerged,
                     'merged': merged, 'groups': ngroups, 'equiv_valid': valid,
                     'equivalent_facts': sum(1 for v in (equiv or {}).values() if v['verdict'] == 'equivalent')})
    n = len(rows)
    ku = sum(r['gold'] == r['unmerged'] for r in rows)
    km = sum(r['gold'] == r['merged'] for r in rows)
    pu, lu, hu = wilson(ku, n)
    pm, lm, hm = wilson(km, n)
    out = {'n': n, 'unmerged': {'k': ku, 'rate': pu, 'ci': [lu, hu]},
           'merged': {'k': km, 'rate': pm, 'ci': [lm, hm]},
           'spend_usd': round(spent(), 6), 'rule_sha256': file_sha(RULE),
           'rows': rows}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    for r in rows:
        print(r['instance'], r['gold'], r['unmerged'], '->', r['merged'], 'groups', r['groups'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build: build()
    if a.run: run()
    if a.score: score()