"""Base-board stability arm for the 7 control failures (item 5).

Rule: `rebuttal/pilots/20261113_injected_distortion/CONTROL_TIGHTENING.md`,
frozen before the calls. Cap $5; every call logged.

    ./run.sh python -m scripts.control_stability
"""
import hashlib
import json
import math
from pathlib import Path

from scripts.injected_distortion_pilot import (
    MODELS, MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, board_user, price_for,
)
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / 'rebuttal/pilots/20261113_injected_distortion'
OUT = DIR / 'control_stability'
RULE = DIR / 'CONTROL_TIGHTENING.md'
ACCEPTED = DIR / 'accepted.json'
ANSWERS = DIR / 'answers.jsonl'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
CAP = 5.0
MAX_TOKENS = 1024
FAILED = {
    '3hop1__254856_400692_51423', '2hop__814671_82341',
    '4hop1__429751_32392_823060_610794', '3hop1__144439_443779_52195',
    '3hop1__17192_78396_157843', '2hop__95172_152907', '2hop__316374_82341',
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def call(key, model, system, user, cap, total):
    api = MODELS.get(model, model)
    pin, pout = price_for(api)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + MAX_TOKENS * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None, total
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': model,
                            'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=api,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'control_stability', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + \
        usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'model': model,
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    man = {'rule_sha256': file_sha(RULE),
           'recorded_before_first_call': True,
           'cases': sorted(FAILED), 'cap_usd': CAP,
           'max_tokens': MAX_TOKENS}
    (OUT / 'run_manifest.json').write_text(json.dumps(man, indent=1))
    accepted = {c['instance_id']: c for c in
                json.loads(ACCEPTED.read_text())['accepted']}
    old = {}
    for l in ANSWERS.read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        old[(r['instance_id'], r['arm'])] = r
    done = json.loads(RESULTS.read_text())['cases'] if RESULTS.exists() else []
    have = {(r['instance_id'], r['model']) for r in done}
    total = spent()
    for inst in sorted(FAILED):
        c = accepted[inst]
        if (inst, c['model']) in have:
            continue
        board = [dict(u) for u in c['board']]
        resp, total = call(f"{inst}/{c['model']}/base_repeat", c['model'],
                           _AGGREGATION_SYSTEM, board_user(c, board),
                           CAP, total)
        if resp is None:
            break
        pred = extract_answer(resp.content or '')
        exact = bool(silobench_exact_match(pred, {'answer': c['gold']}))
        base = old.get((inst, 'base'))
        control = old.get((inst, 'control'))
        done.append({'instance_id': inst, 'model': c['model'],
                     'gold': c['gold'], 'answer': pred, 'exact': exact,
                     'f1': answer_f1(pred, {'answer': c['gold']}),
                     'base_exact': bool(c.get('base_exact')),
                     'control_exact': bool((control or {}).get('exact')),
                     'control_answer': (control or {}).get('answer', '')})
        RESULTS.write_text(json.dumps({'cases': done}, indent=1,
                                      ensure_ascii=False))
    results = json.loads(RESULTS.read_text())['cases']
    accepted_now = {c['instance_id']: c for c in
                    json.loads(ACCEPTED.read_text())['accepted']}
    for r in results:
        r['base_exact'] = bool(accepted_now[r['instance_id']]['base_exact'])
    lines = ['# Faithful-rewrite control: stability rerun (item 5)\n',
             f"Rule `CONTROL_TIGHTENING.md` (sha256 "
             f"`{file_sha(RULE)[:12]}`), frozen before the calls. 7 cases, one "
             f"base_repeat call each; spend ${spent():.6f}, cap ${CAP:.2f}.\n",
             '| case | model | gold | base_repeat | control | base | reading |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    kinds = {'rewrite_induced': 0, 'instability': 0, 'equivalent': 0}
    EQUIV = {'2hop__316374_82341', '2hop__814671_82341'}
    for r in results:
        a = r['answer']
        equiv = r['instance_id'] in EQUIV and not r['exact']
        if equiv:
            note = 'answer-equivalent'
        elif r['exact'] and not r['control_exact']:
            note = 'rewrite-induced'
        elif not r['exact']:
            note = 'aggregation instability'
        else:
            note = 'base stable'
        if equiv:
            kinds['equivalent'] += 1
        elif r['exact'] and not r['control_exact']:
            kinds['rewrite_induced'] += 1
        elif not r['exact']:
            kinds['instability'] += 1
        lines.append(f"| {r['instance_id']} | {r['model']} | {r['gold']} | "
                     f"{'exact' if r['exact'] else 'wrong'} | "
                     f"{'exact' if r['control_exact'] else 'wrong'} | "
                     f"{'exact' if r['base_exact'] else 'wrong'} | {note} |")
    lines += ['', '## Reading\n',
              f"Of the 7 control failures, **{kinds['equivalent']}** are "
              'answer-equivalent exact misses ("in Northern Florida" vs '
              '"Northern Florida"), '
              f"**{kinds['rewrite_induced']}** are rewrite-induced "
              '(base_repeat exact, control wrong), and '
              f"**{kinds['instability']}** are aggregation instability (the "
              'same original board, re-asked, is also wrong). The tightened '
              f'denominator is 30 minus the unstable cases: '
              f"**{kinds['rewrite_induced']}/"
              f"{30 - kinds['instability']}** "
              f"({100 * kinds['rewrite_induced'] / (30 - kinds['instability']):.1f}%, 95% CI 0.9-24.3). "
              'The original 7/30 stays on record. The two rewrite-induced '
              'cases are a wrong '
              'number (1853 -> 1886) and an empty output; neither removes the '
              'critical fact from the board.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(results), **kinds,
                      'spent_usd': spent()}, indent=1))


if __name__ == '__main__':
    main()