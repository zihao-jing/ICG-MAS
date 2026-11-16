"""Q1 rerun with the validated renderer on the 31 unique traces (cap $0.50).

Rule `prereg/Q1-validated-rerun.md`, hashed before any call.

    ./run.sh python -m scripts.q1_validated_rerun --build
    ./run.sh python -m scripts.q1_validated_rerun --run
    ./run.sh python -m scripts.q1_validated_rerun --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.per_fact_points_run import parse
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/Q1-validated-rerun.md'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
MQ = PILOTS / '20261115_proxy_support_mq'
OUT = PILOTS / '20261115_q1_validated_rerun'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 0.50
MAX_TOK = 4096
STAGES = ('extraction', 'transmission', 'aggregation')


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def atoms_of(text):
    return [a.strip() for a in text.replace('\n', ' ').split('. ') if len(a.strip()) > 3]


def population():
    pop = {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    facts = json.loads((MQ / 'facts.json').read_text())
    ids = []
    for d in ('20261115_q1_gold_stage', '20261115_q1_gold_stage_2', '20261115_q1_gold_stage_3'):
        ids += list(json.loads((PILOTS / d / 'results.json').read_text()))
    out = []
    for inst in sorted(set(ids)):
        r = pop[inst]
        gold = (r.get('gold_supports') or [{'text': ''}])[0]['text']
        out.append({'instance': inst, 'key': r['key'], 'question': r['question'],
                    'gold': gold, 'atoms': atoms_of(gold),
                    'facts': facts[r['key']]['value']['facts'],
                    'extraction': r['checkpoints'].get('extraction') or [],
                    'board': r['checkpoints'].get('board') or []})
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    rows = population()
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'model': MODEL, 'cap_usd': CAP,
           'traces': [r['instance'] for r in rows],
           'gold_calls': 2 * len(rows),
           'proxy_calls': 2 * sum(len(r['facts']) for r in rows),
           'gold_atoms': sum(len(r['atoms']) for r in rows),
           'proxy_facts': sum(len(r['facts']) for r in rows)}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'traces'}, indent=1))


def call(spec, question, fact_text, atoms, entries, total, key):
    user = spec['user'].format(question=question, fact=fact_text,
                               atoms='\n'.join(f'{a}: {t}' for a, t in atoms),
                               entries='\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                                                 for u in entries))
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est_out = min(MAX_TOK, 120 + 28 * len(atoms))
    if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total, False
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': MODEL}) + '\n')
    resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                                     max_tokens=MAX_TOK, temperature=0))
    u = resp.usage or {}
    cost = u.get('prompt_tokens', est_in) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
    lab = parse(resp.content or '', {a for a, _ in atoms})
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'model': MODEL, 'usage': u,
                            'cost_usd': round(cost, 8), 'valid': lab is not None}) + '\n')
    return lab, total + cost, lab is not None


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and file_sha(PROMPT) == man['prompt_sha256']
    spec = json.loads(PROMPT.read_text())
    done = set()
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                done.add((e['key'], e['kind'], e['fact_id']))
    total = spent()
    for r in population():
        jobs = [('gold', 'g0', r['gold'], r['atoms'])]
        jobs += [('proxy', f['fact_id'], f['text'], atoms_of(f['text'])) for f in r['facts']]
        for kind, fid, text, atoms in jobs:
            if (r['key'], kind, fid) in done:
                continue
            atoms = [(f'a{i}', t) for i, t in enumerate(atoms, 1)]
            rec = {'instance': r['instance'], 'key': r['key'], 'kind': kind, 'fact_id': fid,
                   'atoms': {}, 'valid': True, 'stages': {}}
            for cp in ('extraction', 'board'):
                lab, total, ok = call(spec, r['question'], text, atoms, r[cp], total,
                                      f"{r['key']}/{kind}/{fid}/{cp}")
                if not ok:
                    lab, total, ok = call(spec, r['question'], text, atoms, r[cp], total,
                                          f"{r['key']}/{kind}/{fid}/{cp}/retry")
                if not ok:
                    rec['valid'] = False
                    rec['stages'][cp] = 'invalid'
                else:
                    st = [v['status'] for v in lab.values()]
                    rec['stages'][cp] = ('absent' if 'absent' in st else
                                         'partial' if 'partial' in st else 'present')
                    rec['atoms'][cp] = {k: v['status'] for k, v in lab.items()}
            with RESULTS.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            print(json.dumps({'inst': r['instance'], 'kind': kind, 'fact': fid,
                              'stages': rec['stages'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def side_stage(rows):
    if any(not r['valid'] for r in rows):
        return None
    if any(r['stages']['extraction'] == 'absent' for r in rows):
        return 'extraction'
    if any(r['stages']['board'] == 'absent' for r in rows):
        return 'transmission'
    return 'aggregation'


def score():
    recs = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    by = {}
    for r in recs:
        by.setdefault(r['instance'], {'gold': [], 'proxy': []})[r['kind']].append(r)
    stage = {i: {'gold': side_stage(d['gold']), 'proxy': side_stage(d['proxy'])}
             for i, d in by.items()}
    out = {'rule_sha256': file_sha(RULE), 'spend_usd': round(spent(), 6), 'traces': len(stage),
           'samples': {}}
    for name, dirname in (('sample1_uniform', '20261115_q1_gold_stage'),
                          ('sample2_coarse', '20261115_q1_gold_stage_2'),
                          ('sample3_atom', '20261115_q1_gold_stage_3')):
        ids = list(json.loads((PILOTS / dirname / 'results.json').read_text()))
        both = [(i, stage[i]['proxy'], stage[i]['gold']) for i in ids
                if i in stage and stage[i]['gold'] and stage[i]['proxy']]
        conf = {p: {g: 0 for g in STAGES} for p in STAGES}
        for _, p, g in both:
            conf[p][g] += 1
        k = sum(1 for _, p, g in both if p == g)
        lo, hi = wilson(k, len(both))
        out['samples'][name] = {'n_both': len(both), 'agree': k,
                                'rate': k / len(both) if both else None, 'wilson': [lo, hi],
                                'confusion': conf,
                                'no_stage': sum(1 for i in ids if i in stage and
                                                not (stage[i]['gold'] and stage[i]['proxy']))}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
    if a.score:
        score()