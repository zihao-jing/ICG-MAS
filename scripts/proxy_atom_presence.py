"""Atom-level proxy presence with the validated point labeller on the Q1 traces (cap $0.30).

Rule `prereg/Proxy-atom-presence.md`, hashed before any call.

    ./run.sh python -m scripts.proxy_atom_presence --build
    ./run.sh python -m scripts.proxy_atom_presence --run
    ./run.sh python -m scripts.proxy_atom_presence --score
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
RULE = PILOTS / 'prereg/Proxy-atom-presence.md'
PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
MQ = PILOTS / '20261115_proxy_support_mq'
OUT = PILOTS / '20261115_proxy_atom_presence'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE = (0.10 / 1e6, 0.50 / 1e6)
CAP = 0.30
MAX_TOK = 4096


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


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
    pop = json.loads((MQ / 'population.json').read_text())
    facts = json.loads((MQ / 'facts.json').read_text())
    ids = []
    for d in ('20261115_q1_gold_stage', '20261115_q1_gold_stage_2', '20261115_q1_gold_stage_3'):
        ids += list(json.loads((PILOTS / d / 'results.json').read_text()))
    rows = {r['instance_id']: r for r in pop if r['protocol'] == 'random_relay'}
    out = []
    for inst in sorted(set(ids)):
        r = rows[inst]
        if facts.get(r['key'], {}).get('status') != 'ok':
            continue
        out.append({'instance': inst, 'key': r['key'], 'question': r['question'],
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
           'facts': sum(len(r['facts']) for r in rows)}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'traces'}, indent=1))


def call(spec, row_question, fact_text, atoms, entries, total, key):
    user = spec['user'].format(question=row_question, fact=fact_text,
                               atoms='\n'.join(f'{a}: {t}' for a, t in atoms),
                               entries='\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                                                 for u in entries))
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est_out = min(MAX_TOK, 120 + 28 * len(atoms))
    if total + est_in * PRICE[0] + est_out * PRICE[1] > CAP:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0}) + '\n')
        return None, total
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
    return lab, total + cost


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'] and file_sha(PROMPT) == man['prompt_sha256']
    spec = json.loads(PROMPT.read_text())
    done = set()
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                done.add((e['key'], e['fact_id']))
    total = spent()
    recs = {}
    if RESULTS.exists():
        for l in RESULTS.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                recs[(e['key'], e['fact_id'])] = e
    for r in population():
        for fact in r['facts']:
            if (r['key'], fact['fact_id']) in done:
                continue
            atoms = [(f'a{i}', t) for i, t in enumerate(atoms_of(fact['text']), 1)]
            if not atoms:
                recs[(r['key'], fact['fact_id'])] = {'key': r['key'], 'fact_id': fact['fact_id'],
                                                     'atoms': {}, 'valid': False, 'stages': {}}
                continue
            rec = {'key': r['key'], 'fact_id': fact['fact_id'], 'instance': r['instance'],
                   'atoms': {}, 'valid': True, 'stages': {}}
            for cp in ('extraction', 'board'):
                lab, total = call(spec, r['question'], fact['text'], atoms, r[cp], total,
                                  f"{r['key']}/{fact['fact_id']}/{cp}")
                if lab is None:
                    lab, total = call(spec, r['question'], fact['text'], atoms, r[cp], total,
                                      f"{r['key']}/{fact['fact_id']}/{cp}/retry")
                if lab is None:
                    rec['valid'] = False
                    rec['stages'][cp] = 'invalid'
                else:
                    st = [v['status'] for v in lab.values()]
                    rec['stages'][cp] = ('absent' if 'absent' in st else
                                         'partial' if 'partial' in st else 'present')
                    rec['atoms'][cp] = {k: v['status'] for k, v in lab.items()}
            recs[(r['key'], fact['fact_id'])] = rec
            with RESULTS.open('a') as f:
                f.write(json.dumps(rec) + '\n')
            print(json.dumps({'key': r['instance'], 'fact': fact['fact_id'],
                              'stages': rec['stages'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'records': len(recs)}))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def gold_stages(dirname):
    items = json.loads((PILOTS / dirname / 'results.json').read_text())
    STATUS = {'present', 'partial', 'absent'}

    def valid(labels, atoms):
        A = set(atoms)
        return (isinstance(labels, dict) and set(labels) == A
                and all(isinstance(v, dict) and v.get('status') in STATUS
                        and isinstance(v.get('unit_ids'), list) for v in labels.values()))

    out = {}
    for inst, rec in items.items():
        e, b = rec['labels'].get('extraction'), rec['labels'].get('board')
        if not (valid(e, rec['atoms']) and valid(b, rec['atoms'])):
            out[inst] = None
        elif any(v['status'] == 'absent' for v in e.values()):
            out[inst] = 'extraction'
        elif any(v['status'] == 'absent' for v in b.values()):
            out[inst] = 'transmission'
        else:
            out[inst] = 'aggregation'
    return out


def score():
    recs = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    by = {}
    for r in recs:
        by.setdefault(r['key'], []).append(r)
    atom = {}
    for key, rows in by.items():
        inst = rows[0]['instance']
        if any(not r['valid'] for r in rows):
            atom[inst] = None
            continue
        if any(r['stages']['extraction'] == 'absent' for r in rows):
            atom[inst] = 'extraction'
        elif any(r['stages']['board'] == 'absent' for r in rows):
            atom[inst] = 'transmission'
        else:
            atom[inst] = 'aggregation'
    out = {'rule_sha256': file_sha(RULE), 'spend_usd': round(spent(), 6), 'samples': {}}
    for name, dirname in (('sample1_uniform', '20261115_q1_gold_stage'),
                          ('sample2_coarse', '20261115_q1_gold_stage_2'),
                          ('sample3_atom', '20261115_q1_gold_stage_3')):
        gold = gold_stages(dirname)
        both = [(i, atom.get(i), g) for i, g in gold.items()]
        both = [(i, p, g) for i, p, g in both if p in ('extraction', 'transmission', 'aggregation')
                and g in ('extraction', 'transmission', 'aggregation')]
        conf = {p: {g: 0 for g in ('extraction', 'transmission', 'aggregation')}
                for p in ('extraction', 'transmission', 'aggregation')}
        for _, p, g in both:
            conf[p][g] += 1
        k = sum(1 for _, p, g in both if p == g)
        n = len(both)
        lo, hi = wilson(k, n)
        out['samples'][name] = {'n_both': n, 'agree': k, 'rate': k / n if n else None,
                                'wilson': [lo, hi],
                                'no_atom_stage': sum(1 for i in gold if atom.get(i) not in
                                                     ('extraction', 'transmission', 'aggregation')),
                                'confusion': conf}
    SCORE.write_text(json.dumps(out, indent=1))
    n_facts = len(recs)
    n_calls = sum(1 for l in CALLS.read_text().splitlines() if l.strip()
                  and json.loads(l).get('event') == 'result')
    n_skip = sum(1 for l in CALLS.read_text().splitlines() if l.strip()
                 and json.loads(l).get('event') == 'skipped')
    lines = ['# Proxy presence at atom level vs gold stage', '',
             '2026-11-15. Rule `Proxy-atom-presence.md` (sha `%s...`). Labeller: Claude Haiku 5.5 with the validated '
             'atom-level point prompt v1 (sha `86d84ff6...`), the same model as the gold labeller and the stored '
             'proxy checkpoint labels (which used the fact-level prompt v3). %d unique random_relay traces; '
             '$%.6f, cap $0.30.' % (out['rule_sha256'][:8], len(by), out['spend_usd']), '',
             'Calls: %d facts x 2 checkpoints = %d result calls, %d skipped at the cap, no retries. The trace '
             'counts below are per sample and the samples overlap (13 + 11 + 15 = 39 scores over 31 unique traces), '
             'so they are not multiplied by two checkpoints.' % (n_facts, n_calls, n_skip), '',
             '| sample | both stages | agree | rate [95% Wilson] | no atom stage |',
             '| --- | ---: | ---: | --- | ---: |']
    for name, s in out['samples'].items():
        r = '%.3f [%.3f, %.3f]' % (s['rate'], s['wilson'][0], s['wilson'][1]) if s['rate'] is not None else '—'
        lines.append('| %s | %d | %d | %s | %d |' % (name, s['n_both'], s['agree'], r, s['no_atom_stage']))
    lines += ['', '## Confusion, atom-level proxy stage (rows) by gold stage (columns)', '']
    for name, s in out['samples'].items():
        lines += ['### %s' % name, '', '| proxy \\ gold | extraction | transmission | aggregation |',
                  '| --- | ---: | ---: | ---: |']
        for p in ('extraction', 'transmission', 'aggregation'):
            lines.append('| %s | %s |' % (p, ' | '.join(str(s['confusion'][p][g])
                                                        for g in ('extraction', 'transmission', 'aggregation'))))
        lines.append('')
    REPORT.write_text('\n'.join(lines) + '\n')
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