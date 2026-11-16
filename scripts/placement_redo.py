"""Placement pilot: stronger model redoes the diagnosed vs a random relay step.

Rule: `rebuttal/pilots/20261113_placement_redo/PLACEMENT_REDO_RULE.md`, frozen
before any call. Pilot 10 injected cases; cap $5; every call logged.

    ./run.sh python -m scripts.placement_redo --build
    ./run.sh python -m scripts.placement_redo --pilot --cap-usd 5
    ./run.sh python -m scripts.placement_redo --report
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.injected_distortion_pilot import MODELS, board_user, price_for
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.run_expansion_stage2 import packages
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_placement_redo'
RULE = OUT / 'PLACEMENT_REDO_RULE.md'
EXPANSION_RULE = OUT / 'PLACEMENT_EXPANSION.md'
MATCHED_RULE = OUT / 'PLACEMENT_MATCHED.md'
ACCEPTED = ROOT / 'rebuttal/pilots/20261113_injected_distortion/accepted.json'
CASES = OUT / 'cases.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
REPORT_EXPANSION = OUT / 'report_expansion.md'
MANIFEST = OUT / 'run_manifest.json'
EXPANSION_MANIFEST = OUT / 'run_manifest_expansion.json'
MATCHED_MANIFEST = OUT / 'run_manifest_matched.json'
MATCHED_RESULTS = OUT / 'results_matched.json'
MATCHED_REPORT = OUT / 'report_matched.md'
SEED = 43
PILOT_N = 10
EXPAND_N = 30
CAP = 5.0
STRONG = 'google/gemini-3.6-flash'
MAX_TRANS = 400
MAX_AGG = 1024

TRANS_SYSTEM = (
    'You are one agent in a multi-agent question-answering pipeline. You see '
    'only your own data shard and the question. Write the evidence from your '
    'shard that is needed to answer the question, as one concise statement. '
    'Do not use outside knowledge. If your shard contains nothing relevant, '
    'write exactly: NO EVIDENCE.')


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


def build():
    cs = json.loads(ACCEPTED.read_text())['accepted']
    for c in cs:
        c['key'] = sha(f"{SEED}|redo|{c['instance_id']}|{c['model']}|"
                       f"{c['unit_id']}")[:12]
    cs = sorted(cs, key=lambda c: c['key'])[:PILOT_N]
    OUT.mkdir(parents=True, exist_ok=True)
    CASES.write_text(json.dumps(
        [{'key': c['key'], 'instance_id': c['instance_id'],
          'model': c['model'], 'unit_id': c['unit_id'],
          'agent_id': c['agent_id'], 'question': c['question'],
          'gold': c['gold'], 'corrupt': c['corrupt'],
          'board': c['board']} for c in cs],
        indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps(
        {'recorded_before_first_call': True, 'rule_sha256': file_sha(RULE),
         'cases_sha256': file_sha(CASES), 'pilot_n': PILOT_N, 'seed': SEED,
         'strong_model': STRONG, 'cap_usd': CAP}, indent=1))
    print(json.dumps({'pilot': [c['instance_id'] for c in cs]}, indent=1))


def expand_build():
    """Build the 30-case expansion (10 pilot + next 20) and freeze it."""
    cs = json.loads(ACCEPTED.read_text())['accepted']
    for c in cs:
        c['key'] = sha(f"{SEED}|redo|{c['instance_id']}|{c['model']}|"
                       f"{c['unit_id']}")[:12]
    cs = sorted(cs, key=lambda c: c['key'])[:EXPAND_N]
    assert len(cs) == EXPAND_N, len(cs)
    old = {c['key'] for c in json.loads(CASES.read_text())}
    assert old <= {c['key'] for c in cs}, 'pilot cases changed'
    OUT.mkdir(parents=True, exist_ok=True)
    CASES.write_text(json.dumps(
        [{'key': c['key'], 'instance_id': c['instance_id'],
          'model': c['model'], 'unit_id': c['unit_id'],
          'agent_id': c['agent_id'], 'question': c['question'],
          'gold': c['gold'], 'corrupt': c['corrupt'],
          'board': c['board']} for c in cs],
        indent=1, ensure_ascii=False))
    EXPANSION_MANIFEST.write_text(json.dumps(
        {'recorded_before_first_call': True,
         'addendum_sha256': file_sha(EXPANSION_RULE),
         'pilot_rule_sha256': file_sha(RULE),
         'pilot_cases_sha256': json.loads(MANIFEST.read_text())['cases_sha256'],
         'cases_sha256': file_sha(CASES), 'n': EXPAND_N,
         'pilot_n': len(old), 'seed': SEED, 'strong_model': STRONG,
         'cap_usd': CAP}, indent=1))
    print(json.dumps({'n': len(cs), 'new': len(cs) - len(old)}, indent=1))


def call(key, model, system, user, max_tokens, cap, total):
    pin, pout = price_for(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'placement_redo', 'key': key,
                               'openrouter_reasoning': model == STRONG})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + \
        usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def pilot(cap, expansion=False):
    man = json.loads((EXPANSION_MANIFEST if expansion else
                      MANIFEST).read_text())
    if expansion:
        assert file_sha(EXPANSION_RULE) == man['addendum_sha256']
    else:
        assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(CASES) == man['cases_sha256']
    cs = json.loads(CASES.read_text())
    pk = {m: packages(m) for m in MODELS}
    total = spent()
    done = json.loads(RESULTS.read_text())['cases'] if RESULTS.exists() else []
    have = {(r['key'], r['arm']) for r in done}
    for c in cs:
        if (c['key'], 'diagnosed') in have:
            continue
        t = pk[c['model']][c['instance_id']]
        ctx = {x['agent_id']: x['text'] for x in t['source_contexts']}
        agents = sorted({u['agent_id'] for u in c['board']})
        others = [a for a in agents if a != c['agent_id']]
        rand = random.Random(SEED).choice(others) if others else c['agent_id']
        key = f"redo/{c['key']}/{c['agent_id']}/{rand}"
        for arm, agent in (('diagnosed', c['agent_id']), ('random', rand)):
            rec = {'key': c['key'], 'instance_id': c['instance_id'],
                   'model': c['model'], 'arm': arm, 'agent': agent,
                   'gold': c['gold']}
            user = f"QUESTION\n{c['question']}\n\nYOUR DATA SHARD\n{ctx[agent][:4000]}"
            resp, total = call(f"trans/{key}/{arm}", STRONG, TRANS_SYSTEM,
                               user, MAX_TRANS, cap, total)
            if resp is None:
                break
            text = (resp.content or '').strip()
            rec['transmission'] = text
            board = [dict(u) for u in c['board']]
            for u in board:
                if u['unit_id'] == c['unit_id']:
                    u['text'] = c['corrupt']
            if arm == 'diagnosed':
                target = next(u for u in board if u['unit_id'] == c['unit_id'])
            else:
                target = next(u for u in board if u['agent_id'] == agent)
            target['text'] = text or 'NO EVIDENCE.'
            case = {'question': c['question']}
            r2, total = call(f"agg/{key}/{arm}", MODELS[c['model']],
                             _AGGREGATION_SYSTEM, board_user(case, board),
                             MAX_AGG, cap, total)
            if r2 is None:
                break
            pred = extract_answer(r2.content or '')
            rec.update({'answer': pred,
                        'exact': bool(silobench_exact_match(pred,
                                                            {'answer': c['gold']}))})
            done.append(rec)
            RESULTS.write_text(json.dumps({'cases': done}, indent=1,
                                          ensure_ascii=False))
        print(json.dumps({'case': c['instance_id'],
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'cases': len(done), 'spent_usd': round(spent(), 8)},
                     indent=1))


def report(expansion=False):
    rows = json.loads(RESULTS.read_text())['cases']
    by = {}
    for r in rows:
        by.setdefault(r['key'], {})[r['arm']] = r
    pairs = [v for v in by.values() if 'diagnosed' in v and 'random' in v]
    d = sum(v['diagnosed']['exact'] for v in pairs)
    n = len(pairs)
    rn = sum(v['random']['exact'] for v in pairs)
    lo, hi = cp_ci(d, n)
    rule_name = ('PLACEMENT_EXPANSION.md' if expansion else
                 'PLACEMENT_REDO_RULE.md')
    rule_sha = file_sha(EXPANSION_RULE if expansion else RULE)
    scope = (f'expansion {n}/30 injected cases (10 pilot + {n - 10} new)'
             if expansion else f'pilot {n}/30 injected cases')
    spend = sum(json.loads(l).get('cost_usd', 0.0)
                for l in CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('key', '').startswith(
                    ('trans/redo/', 'agg/redo/')))
    lines = ['# Placement by redoing the blamed relay step (item 7)\n',
             f"Rule `{rule_name}` (sha256 `{rule_sha[:12]}`), "
             f"frozen before the calls. Stronger model `{STRONG}`; {scope}; "
             f"spend ${spend:.6f}, cap ${CAP:.2f}. "
             'Stage: relay checkpoint; aggregation held at the original '
             'model and prompt.\n',
             '| case | model | diagnosed agent | random agent | diagnosed | random |',
             '| --- | --- | ---: | ---: | --- | --- |']
    for v in sorted(by.values(), key=lambda x: x['diagnosed']['instance_id']):
        if 'diagnosed' not in v or 'random' not in v:
            continue
        a = v['diagnosed']
        b = v['random']
        lines.append(f"| {a['instance_id']} | {a['model']} | {a['agent']} | "
                     f"{b['agent']} | {'exact' if a['exact'] else 'wrong'} | "
                     f"{'exact' if b['exact'] else 'wrong'} |")
    lines += ['', f'Diagnosed arm exact **{d}/{n}** ({100 * d / n:.1f}%, 95% CI '
              f'{100 * lo:.1f}-{100 * hi:.1f}); random arm **{rn}/{n}** '
              f'({100 * rn / n:.1f}%). Paired difference {d - rn:+d} at n={n}; '
              'descriptive only.\n',
              '## Reading\n',
              'Both arms replace one board unit with a stronger-model '
              'transmission from that agent\'s own shard; only the agent '
              'changes. The diagnosed arm is the stage the audit blames. The arms '
              'are not symmetric: the diagnosed arm replaces the injected '
              'corrupted unit, while the random arm replaces an existing unit '
              'that was not corrupted and so may displace correct text. The '
              '11/30 versus 0/30 gap is therefore **confounded** and is not '
              'reported as a placement effect; the matched design and its '
              'result are in `report_matched.md`.'
              + (f' Of the {n} cases, 10 are the earlier pilot and '
                 f'{n - 10} are new.' if expansion else
                 ' n=10 is a pilot.') + ' Two earlier configurations '
              'are kept on record and are not scored: '
              '`results_pre_corruptfix.json` (the corruption was not applied '
              'to the board) and `results_reasoning_disabled.json` (Gemini '
              'rejected with 400 because reasoning was disabled).']
    path = REPORT_EXPANSION if expansion else REPORT
    path.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'pairs': n, 'diagnosed_exact': d, 'random_exact': rn,
                      'spent_usd': round(spend, 8)}, indent=1))


def matched_build():
    cs = json.loads(CASES.read_text())
    assert len(cs) == EXPAND_N, len(cs)
    MATCHED_MANIFEST.write_text(json.dumps(
        {'recorded_before_first_call': True,
         'addendum_sha256': file_sha(MATCHED_RULE),
         'expansion_rule_sha256': file_sha(EXPANSION_RULE),
         'cases_sha256': file_sha(CASES), 'n': len(cs), 'seed': SEED,
         'strong_model': STRONG, 'cap_usd': CAP}, indent=1))
    print(json.dumps({'matched_n': len(cs),
                      'addendum_sha256': file_sha(MATCHED_RULE)[:12]},
                     indent=1))


def matched(cap):
    man = json.loads(MATCHED_MANIFEST.read_text())
    assert file_sha(MATCHED_RULE) == man['addendum_sha256']
    assert file_sha(CASES) == man['cases_sha256']
    cs = json.loads(CASES.read_text())
    pk = {m: packages(m) for m in MODELS}
    total = 0.0
    done = json.loads(MATCHED_RESULTS.read_text())['cases'] \
        if MATCHED_RESULTS.exists() else []
    have = {(r['key'], r['arm']) for r in done}
    for c in cs:
        if (c['key'], 'diagnosed') in have:
            continue
        t = pk[c['model']][c['instance_id']]
        ctx = {x['agent_id']: x['text'] for x in t['source_contexts']}
        agents = sorted({u['agent_id'] for u in c['board']})
        others = [a for a in agents if a != c['agent_id']]
        rand = random.Random(SEED).choice(others) if others else c['agent_id']
        for arm, agent in (('diagnosed', c['agent_id']), ('random', rand)):
            key = f"matched/{c['key']}/{c['agent_id']}/{rand}/{arm}"
            rec = {'key': c['key'], 'instance_id': c['instance_id'],
                   'model': c['model'], 'arm': arm, 'agent': agent,
                   'gold': c['gold']}
            user = f"QUESTION\n{c['question']}\n\nYOUR DATA SHARD\n{ctx[agent][:4000]}"
            resp, total = call(f"trans/{key}", STRONG, TRANS_SYSTEM, user,
                               MAX_TRANS, cap, total)
            if resp is None:
                break
            text = (resp.content or '').strip()
            rec['transmission'] = text
            # both arms replace the corrupted unit at the same position
            board = [dict(u) for u in c['board']]
            target = next(u for u in board if u['unit_id'] == c['unit_id'])
            target['text'] = text or 'NO EVIDENCE.'
            r2, total = call(f"agg/{key}", MODELS[c['model']],
                             _AGGREGATION_SYSTEM, board_user({'question':
                                                              c['question']},
                                                             board),
                             MAX_AGG, cap, total)
            if r2 is None:
                break
            pred = extract_answer(r2.content or '')
            rec.update({'answer': pred,
                        'exact': bool(silobench_exact_match(
                            pred, {'answer': c['gold']}))})
            done.append(rec)
            MATCHED_RESULTS.write_text(json.dumps({'cases': done}, indent=1,
                                                ensure_ascii=False))
        print(json.dumps({'case': c['instance_id'],
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'records': len(done), 'spent_usd': round(total, 8)},
                     indent=1))


def matched_report():
    rows = json.loads(MATCHED_RESULTS.read_text())['cases']
    by = {}
    for r in rows:
        by.setdefault(r['key'], {})[r['arm']] = r
    pairs = [v for v in by.values() if 'diagnosed' in v and 'random' in v]
    d = sum(v['diagnosed']['exact'] for v in pairs)
    rn = sum(v['random']['exact'] for v in pairs)
    n = len(pairs)
    lo, hi = cp_ci(d, n)
    spend = sum(json.loads(l).get('cost_usd', 0.0)
                for l in CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('key', '').startswith(
                    ('trans/matched/', 'agg/matched/')))
    lines = ['# Matched placement test (item 7)\n',
             f"Rule `PLACEMENT_MATCHED.md` (sha256 "
             f"`{file_sha(MATCHED_RULE)[:12]}`), frozen before the calls. "
             f"Stronger model `{STRONG}`; {n}/30 injected cases; spend "
             f"${spend:.6f}, cap ${CAP:.2f}. Stage: relay checkpoint; "
             'aggregation held at the original model and prompt.\n',
             '| case | model | diagnosed agent | random agent | diagnosed | random |',
             '| --- | --- | ---: | ---: | --- | --- |']
    for v in sorted(pairs, key=lambda x: x['diagnosed']['instance_id']):
        a, b = v['diagnosed'], v['random']
        lines.append(f"| {a['instance_id']} | {a['model']} | {a['agent']} | "
                     f"{b['agent']} | {'exact' if a['exact'] else 'wrong'} | "
                     f"{'exact' if b['exact'] else 'wrong'} |")
    lines += ['', f'Diagnosed exact **{d}/{n}** ({100 * d / n:.1f}%, 95% CI '
              f'{100 * lo:.1f}-{100 * hi:.1f}); random exact **{rn}/{n}** '
              f'({100 * rn / n:.1f}%). Paired difference {d - rn:+d} at n={n}; '
              'descriptive only.\n',
              '## Reading\n',
              'Both arms replace the same corrupted unit at the same position, '
              'so both remove the injected corruption; only the agent whose '
              'shard the stronger model reads changes. This is the matched '
              'contrast the earlier 11/30 versus 0/30 result lacked. A '
              'difference here is a placement signal for this one replaced '
              'unit, not a full repair and not a claim about other pipeline '
              'stages.']
    MATCHED_REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'pairs': n, 'diagnosed_exact': d, 'random_exact': rn,
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--expand-build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--expand', action='store_true')
    ap.add_argument('--matched-build', action='store_true')
    ap.add_argument('--matched', action='store_true')
    ap.add_argument('--matched-report', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.expand_build:
        expand_build()
    if a.pilot:
        pilot(a.cap_usd)
    if a.expand:
        pilot(a.cap_usd, expansion=True)
    if a.matched_build:
        matched_build()
    if a.matched:
        matched(a.cap_usd)
    if a.matched_report:
        matched_report()
    if a.report:
        report(expansion=a.expand)


if __name__ == '__main__':
    main()