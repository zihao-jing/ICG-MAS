"""MuSiQue 6/30 fix: hop-anchored proxy facts (v4). Rule: prereg/MQ-hop-anchor-check.md.

    ./.conda-env/bin/python -m scripts.mq_hop_anchor_check --build
    ./.conda-env/bin/python -m scripts.mq_hop_anchor_check --pilot     # set A, first 3 traces
    ./.conda-env/bin/python -m scripts.mq_hop_anchor_check --run       # all 90 traces
    ./.conda-env/bin/python -m scripts.mq_hop_anchor_check --score
"""
import argparse
import hashlib
import json
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import scripts.q1_second_sample as Q2
from scripts.answer_equiv import last_object
from scripts.per_fact_points_run import parse
from scripts.proxy_support_run import render_docs, validate_facts
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
RULE = PILOTS / 'prereg/MQ-hop-anchor-check.md'
PROMPT = PILOTS / 'prereg/proxy_facts_prompt_v4_hop_anchored.json'
LABEL_PROMPT = PILOTS / 'prereg/per_fact_points_prompt_v1.json'
MQ = PILOTS / '20261115_proxy_support_mq'
OUT = PILOTS / '20261115_mq_hop_anchor'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
FACTS = OUT / 'facts.json'
POP = OUT / 'population.json'
PROXY_MODEL = 'qwen/qwen3-235b-a22b-2507'
LABEL_MODEL = 'anthropic/claude-haiku-5.5'
PRICE = {PROXY_MODEL: (0.14e-6, 0.80e-6), LABEL_MODEL: (0.10e-6, 0.50e-6)}
CAP = 1.00
WORKERS = 8
STAGES = ('extraction', 'transmission', 'aggregation')
LOCK = threading.Lock()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def atoms_of(text):
    return [a.strip() for a in text.replace('\n', ' ').split('. ') if len(a.strip()) > 3]


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def log(row):
    with LOCK:
        with CALLS.open('a') as f:
            f.write(json.dumps(row) + '\n')


def call(model, system, user, max_tokens, key):
    """One logged call. Returns (content or None, cost)."""
    pin, pout = PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    with LOCK:
        if spent() + est_in * pin + max_tokens * pout > CAP:
            pass_cap = True
        else:
            pass_cap = False
    if pass_cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0})
        return None, 0.0
    log({'event': 'intent', 'key': key, 'model': model, 'system_sha256': hashlib.sha256(system.encode()).hexdigest(),
         'user_sha256': hashlib.sha256(user.encode()).hexdigest()})
    resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                     max_tokens=max_tokens, temperature=0,
                                     metadata={'pilot': 'mq_hop_anchor'}))
    u = resp.usage or {}
    cost = u.get('prompt_tokens', est_in) * pin + u.get('completion_tokens', 0) * pout
    log({'event': 'result', 'key': key, 'model': model, 'success': resp.success, 'error': resp.error,
         'content': resp.content, 'usage': u, 'cost_usd': round(cost, 8)})
    return (resp.content if resp.success else None), cost


def sets():
    """Sets A, B, C as fixed by the rule."""
    pop = {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    used31 = set()
    for d in ('20261115_q1_gold_stage', '20261115_q1_gold_stage_2', '20261115_q1_gold_stage_3'):
        used31 |= set(json.loads((PILOTS / d / 'results.json').read_text()))
    A = sorted({json.loads(l)['instance'] for l in
                (PILOTS / '20261115_q1_second_sample/results.jsonl').read_text().splitlines() if l.strip()})
    facts_v1 = json.loads((MQ / 'facts.json').read_text())
    B, rest = [], []
    for inst in sorted(pop):
        if inst in used31 or inst in A:
            continue
        r = pop[inst]
        gold = (r.get('gold_supports') or [{'text': ''}])[0]['text']
        ext = ' '.join(u['text'] for u in r['checkpoints'].get('extraction') or [])
        board = ' '.join(u['text'] for u in r['checkpoints'].get('board') or [])
        if not gold or not ext or not board:
            continue
        rest.append(inst)
        if len(B) < 30 and (Q2.atom_missing(ext, gold) or Q2.atom_missing(board, gold)):
            B.append(inst)
    rest_all = [i for i in sorted(pop) if i not in A and i not in B]
    C = random.Random(20261115).sample(rest_all, 30)
    return A, B, sorted(C), pop, facts_v1


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    A, B, C, pop, _ = sets()
    rows = []
    for name, ids in (('A', A), ('B', B), ('C', C)):
        for inst in ids:
            r = pop[inst]
            rows.append({'set': name, 'instance': inst, 'key': r['key'], 'question': r['question'],
                         'documents': r['documents'], 'gold': (r.get('gold_supports') or [{'text': ''}])[0]['text'],
                         'extraction': r['checkpoints'].get('extraction') or [],
                         'board': r['checkpoints'].get('board') or []})
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'label_prompt_sha256': file_sha(LABEL_PROMPT),
           'proxy_model': PROXY_MODEL, 'label_model': LABEL_MODEL, 'cap_usd': CAP,
           'sets': {'A': A, 'B': B, 'C': C}, 'traces': len(rows)}
    BUILD.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({'A': len(A), 'B': len(B), 'C': len(C), 'rule_sha256': man['rule_sha256'],
                      'prompt_sha256': man['prompt_sha256']}, indent=1))


def load_rows():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(LABEL_PROMPT) == man['label_prompt_sha256'], 'labeller prompt changed'
    return json.loads(POP.read_text())


def make_facts(r, spec):
    """v4 facts for one trace: up to 3 attempts, validated."""
    docs = {d['unit_id'] for d in r['documents']}
    user = spec['user'].format(question=r['question'], documents=render_docs(r))
    for n in (1, 2, 3):
        raw, _ = call(PROXY_MODEL, spec['system'], user, spec['max_tokens'], f"facts/{r['key']}/attempt-{n}")
        if raw is None:
            return {'status': 'failed', 'value': None, 'attempts': n}
        v = validate_facts(last_object(raw), docs)
        if v is not None:
            return {'status': 'ok', 'value': v, 'attempts': n}
    return {'status': 'failed', 'value': None, 'attempts': 3}


def label(spec, question, fact_text, units, key):
    atoms = atoms_of(fact_text)
    if not atoms:
        return None
    alist = [(f'a{i}', t) for i, t in enumerate(atoms, 1)]
    user = spec['user'].format(question=question, fact=fact_text,
                               atoms='\n'.join(f'{a}: {t}' for a, t in alist),
                               entries='\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                                                 for u in units))
    raw, _ = call(LABEL_MODEL, spec['system'], user, 4096, key)
    lab = parse(raw or '', {a for a, _ in alist}) if raw else None
    if lab is None:
        return {'valid': False, 'status': None, 'atoms': {}}
    st = [v['status'] for v in lab.values()]
    return {'valid': True, 'status': 'absent' if 'absent' in st else ('partial' if 'partial' in st else 'present'),
            'atoms': {k: v['status'] for k, v in lab.items()}}


def process_trace(r, facts_rec, lspec):
    out = {'set': r['set'], 'instance': r['instance'], 'facts_status': facts_rec['status'], 'gold': {}, 'proxy': []}
    out['gold'] = {cp: label(lspec, r['question'], r['gold'], r[cp], f"{r['key']}/gold/{cp}")
                   for cp in ('extraction', 'board')}
    if facts_rec['status'] == 'ok':
        for f in facts_rec['value']['facts']:
            out['proxy'].append({'fact_id': f['fact_id'], 'text': f['text'],
                                 **{cp: label(lspec, r['question'], f['text'], r[cp],
                                              f"{r['key']}/proxy/{f['fact_id']}/{cp}")
                                    for cp in ('extraction', 'board')}})
    return out


def run(only_pilot=False):
    rows = load_rows()
    spec_f = json.loads(PROMPT.read_text())
    spec_l = json.loads(LABEL_PROMPT.read_text())
    if only_pilot:
        rows = [r for r in rows if r['set'] == 'A'][:3]
    done = set()
    if RESULTS.exists():
        done = {json.loads(l)['instance'] for l in RESULTS.read_text().splitlines() if l.strip()}
    rows = [r for r in rows if r['instance'] not in done]
    facts = json.loads(FACTS.read_text()) if FACTS.exists() else {}

    def one(r):
        fr = facts.get(r['instance']) or make_facts(r, spec_f)
        return r, fr, process_trace(r, fr, spec_l)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(one, r) for r in rows]
        for fut in as_completed(futs):
            r, fr, res = fut.result()
            facts[r['instance']] = fr
            FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False))
            with LOCK:
                with RESULTS.open('a') as f:
                    f.write(json.dumps(res, ensure_ascii=False) + '\n')
            print(json.dumps({'set': r['set'], 'instance': r['instance'], 'facts': fr['status'],
                              'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent_usd': round(spent(), 6), 'cap_usd': CAP,
                      'traces_done': len(facts), 'pilot_only': only_pilot}, indent=1))


def side(rec, side_key):
    if side_key == 'gold':
        g = rec['gold']
        if not all(g.get(cp) and g[cp]['valid'] for cp in ('extraction', 'board')):
            return None
        if g['extraction']['status'] == 'absent':
            return 'extraction'
        if g['board']['status'] == 'absent':
            return 'transmission'
        return 'aggregation'
    if not rec['proxy']:
        return None
    for p in rec['proxy']:
        for cp in ('extraction', 'board'):
            if not p.get(cp) or not p[cp]['valid']:
                return None
    if any(p['extraction']['status'] == 'absent' for p in rec['proxy']):
        return 'extraction'
    if any(p['board']['status'] == 'absent' for p in rec['proxy']):
        return 'transmission'
    return 'aggregation'


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def score():
    man = json.loads(BUILD.read_text())
    recs = {json.loads(l)['instance']: json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()}
    out = {'rule_sha256': man['rule_sha256'], 'prompt_sha256': man['prompt_sha256'],
           'spend_usd': round(spent(), 6), 'sets': {}}
    for name in ('A', 'B', 'C'):
        ids = man['sets'][name]
        both, no_stage = [], 0
        conf = {p: {g: 0 for g in STAGES} for p in STAGES}
        for i in ids:
            rec = recs.get(i)
            p = side(rec, 'proxy') if rec else None
            g = side(rec, 'gold') if rec else None
            if p is None or g is None:
                no_stage += 1
                continue
            both.append((p, g))
            conf[p][g] += 1
        k = sum(1 for p, g in both if p == g)
        lo, hi = wilson(k, len(both))
        out['sets'][name] = {'traces': len(ids), 'both_stages': len(both), 'agree': k,
                             'rate': round(k / len(both), 4) if both else None,
                             'wilson95': [round(lo, 4), round(hi, 4)], 'no_stage': no_stage,
                             'confusion_proxy_by_gold': conf}
    b, c = out['sets']['B'], out['sets']['C']
    out['pass'] = bool(b['rate'] is not None and c['rate'] is not None and b['rate'] >= 0.80 and c['rate'] >= 0.765)
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        run(only_pilot=True)
    if a.run:
        run()
    if a.score:
        score()
