"""Relay strict/broad rates under the v2 prompt (cap $0.5).

    ./run.sh python -m scripts.relay_v2_rescore --build
    ./run.sh python -m scripts.relay_v2_rescore --run
    ./run.sh python -m scripts.relay_v2_rescore --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from scripts.answer_equiv import last_object
from scripts.distortion_rescore_run import cp
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261115_relay_rescore/population_pairs.json'
OUT = ROOT / 'rebuttal/pilots/20261115_relay_v2_rescore'
RULE = ROOT / 'rebuttal/pilots/prereg/Relay-v2-rescore.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v2.json'
POP = OUT / 'population_pairs.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RATES = OUT / 'rates.json'
REPORT = OUT / 'report.md'
HAIKU = 'anthropic/claude-haiku-5.5'
PIN, POUT = 0.1 / 1e6, 0.5 / 1e6
EST_OUT = 300
CAP = 0.5
MAX_TOKENS = 2500
LOCK = Lock()
TOTAL = {'v': 0.0}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def render(spec, pair):
    return spec['user'].format(question='(not shown)', gold=pair['gold'][:2000],
                               entries=f"[unit 1] {pair['unit'][:2000]}")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(SRC.read_text())
    man = {'recorded_before_any_call': True,
           'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
           'population_sha256': file_sha(POP), 'pairs': 945,
           'by_protocol': dict(Counter(p['protocol'] for p in json.loads(POP.read_text()))),
           'labeller_model': HAIKU, 'cap_usd': CAP,
           'validated_label': 'strict_fidelity_relay_qwen v3-enriched, kappa .791 [.466, 1.000]'}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check_frozen():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == man['prompt_sha256'], 'prompt changed'
    assert file_sha(POP) == man['population_sha256'], 'population changed'
    return man


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, spec, user, cap):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    with LOCK:
        if TOTAL['v'] + est_in * PIN + EST_OUT * POUT > cap:
            with CALLS.open('a') as f:
                f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                    'cost_usd': 0.0}) + '\n')
            return None
    cid = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with LOCK, CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': HAIKU,
                            'system_sha256': sha(spec['system']), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=HAIKU,
                                     max_tokens=MAX_TOKENS, temperature=0,
                                     metadata={'pilot': 'relay_v2_rescore', 'key': key}))
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * PIN + usage.get('completion_tokens', 0) * POUT
    with LOCK:
        TOTAL['v'] += cost
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'model': HAIKU,
                                'success': resp.success, 'error': resp.error, 'content': resp.content,
                                'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


def parse(content):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('facts'), list) or not obj['facts']:
        return None
    f = obj['facts'][0]
    if f.get('fidelity') not in ('faithful', 'partial', 'distorted', 'absent'):
        return None
    return f['fidelity']


def labels():
    out = {}
    if not CALLS.exists():
        return out
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        f = parse(e.get('content'))
        if f is not None:
            k = e['key']
            out.setdefault(k.rsplit('/attempt-', 1)[0] if '/attempt-' in k else k, f)
    return out


def run(cap):
    check_frozen()
    spec = json.loads(PROMPT.read_text())
    pairs = json.loads(POP.read_text())
    done = set(labels())
    todo = [p for p in pairs if f'labh/{p["pair_id"]}' not in done]
    TOTAL['v'] = spent()
    print(json.dumps({'todo': len(todo), 'spent': round(TOTAL['v'], 6)}), flush=True)

    def one(p):
        user = render(spec, p)
        for attempt in (1, 2):
            resp = call(f'labh/{p["pair_id"]}/attempt-{attempt}', spec, user, cap)
            if resp is None:
                return None
            if resp.success and parse(resp.content) is not None:
                return True
        return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(one, p): p for p in todo}
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 100 == 0 or i == len(todo):
                print(json.dumps({'done': i, 'of': len(todo), 'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def shared_units(pairs):
    """How many (instance, agent, unit) pairs the three protocols have in common."""
    per = {}
    for p in pairs:
        per.setdefault(p['protocol'], set()).add((p['inst_id'], p['agent_id'], p['unit']))
    if len(per) < 3:
        return {}
    common = set.intersection(*per.values())
    union = set.union(*per.values())
    return {'common_all_three': len(common), 'union': len(union),
            'per_protocol': {k: len(v) for k, v in per.items()}}


def score():
    check_frozen()
    pairs = json.loads(POP.read_text())
    got = labels()
    out = {}
    for p in pairs:
        f = got.get(f'labh/{p["pair_id"]}')
        if f is None:
            continue
        m = out.setdefault(p['protocol'], {'pairs': 0, 'faithful': 0, 'partial': 0, 'distorted': 0,
                                           'absent': 0, 'covered': 0})
        m['pairs'] += 1
        m[f] += 1
        if f != 'absent':
            m['covered'] += 1
    pooled = {'pairs': 0, 'faithful': 0, 'partial': 0, 'distorted': 0, 'absent': 0, 'covered': 0}
    for m in out.values():
        for k in pooled:
            pooled[k] += m[k]
    for name, m in list(out.items()) + [('pooled', pooled)]:
        m['strict'] = m['distorted'] / m['covered'] if m['covered'] else None
        m['strict_ci'] = list(cp(m['distorted'], m['covered'])) if m['covered'] else None
        m['broad'] = (m['distorted'] + m['partial']) / m['covered'] if m['covered'] else None
        m['broad_ci'] = list(cp(m['distorted'] + m['partial'], m['covered'])) if m['covered'] else None
    res = {'by_protocol': {k: v for k, v in out.items()}, 'pooled': pooled,
           'spend_usd': round(spent(), 6), 'labelled': sum(v['pairs'] for v in out.values()),
           'shared_units': shared_units(pairs)}
    RATES.write_text(json.dumps(res, indent=1))
    write_report(res)
    print(json.dumps(res, indent=1))


def write_report(res):
    lines = ['# Relay strict and broad rates under the v2 prompt',
             '',
             '2026-11-15. Rule `Relay-v2-rescore.md` (sha `%s...`), prompt `strict_fidelity_pair_prompt_v2.json` '
             '(sha `%s...`), the prompt validated on this population at kappa .791 [.466, 1.000]. %d of 945 '
             'pairs labelled. Spend $%.6f, cap $0.5.'
             % (file_sha(RULE)[:8], file_sha(PROMPT)[:8], res['labelled'], res['spend_usd']),
             '',
             '| cell | pairs | covered | faithful | partial | distorted | absent | strict [95% CI] | broad [95% CI] |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |']

    def pct(x):
        return '—' if x is None else '%.1f%%' % (100 * x)

    def ci(x):
        return '' if not x else '[%.1f, %.1f]' % (100 * x[0], 100 * x[1])

    for name in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay', 'pooled'):
        m = res['by_protocol'].get(name) if name != 'pooled' else res['pooled']
        if not m:
            continue
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %s %s | %s %s |'
                     % (name, m['pairs'], m['covered'], m['faithful'], m['partial'], m['distorted'],
                        m['absent'], pct(m['strict']), ci(m['strict_ci']), pct(m['broad']), ci(m['broad_ci'])))
    lines += ['', 'Strict = distorted / covered; broad = (distorted + partial) / covered; absent pairs are '
              'listed, not in the denominator. Clopper-Pearson 95% intervals.',
              '', 'The three protocol samples share %d of their %d distinct (instance, agent, unit) pairs, so the pooled '
              'interval treats repeated units as independent and is too narrow; the protocol rows are the '
              'reliable unit of comparison.' % (res['shared_units'].get('common_all_three', 0),
                                                 res['shared_units'].get('union', 0)),
              '', 'The earlier step-9 rates (random 3.2%, score-ranked 4.3%, redundancy 2.9%, pooled 3.5%) '
              'were produced under the unvalidated prompt and are not quotable; this table replaces them.',
              '', '## Ledger', 'Spend $%.6f.' % res['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.score:
        score()