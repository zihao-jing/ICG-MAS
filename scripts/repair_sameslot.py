"""Audit-guided versus judge-guided repair on the 30 injected cases.

Rule `prereg/Repair-A-vs-J.md` (hashed before calls). Cap $2.00.

    ./run.sh python -m scripts.repair_ab --build
    ./run.sh python -m scripts.repair_ab --run
    ./run.sh python -m scripts.repair_ab --score
"""
import argparse
import re
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.audit_diagnosis_89 import accepted, corrupted
from scripts.b5_attribution_2x2 import CASES, adapt, qwen_facts_carriers
from scripts.b7d_gemini_aggregator import board_user
from src.protocols.relay import _AGGREGATION_SYSTEM, _EXTRACTION_SYSTEM
from src.protocols.base import extract_answer
from src.audit.e4_fix_gates import recall
from src.eval.evaluate import answer_f1
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_repair_sameslot'
RULE = ROOT / 'rebuttal/pilots/prereg/Repair-same-slot.md'
JUDGE = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/results_v2.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'google/gemini-3.6-flash'
PRICE = (0.75 / 1e6, 3.75 / 1e6)
MODEL_IDS = {'qwen235b': 'qwen/qwen3-235b-a22b-2507',
             'gpt4omini': 'openai/gpt-4o-mini',
             'gemma31b': 'google/gemma-4-31b-it'}
PRICE_TRACE = {'qwen235b': (0.14 / 1e6, 0.8 / 1e6), 'gpt4omini': (0.15 / 1e6, 0.6 / 1e6),
               'gemma31b': (0.14 / 1e6, 0.4 / 1e6)}
CAP = 2.0
TOK = 512

AUDIT_SYS = ("You are an evidence repair assistant. Quote the single sentence from the agent's private evidence "
             "that states the given fact. Output one line, the quoted sentence only, no preamble.")
JUDGE_SYS = ("You are an evidence repair assistant. Quote the single sentence from the agent's private evidence "
             "that is most relevant to the question. Output one line, the quoted sentence only, no preamble.")


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': sha(RULE.read_text()),
           'audit_sys_sha256': sha(AUDIT_SYS), 'judge_sys_sha256': sha(JUDGE_SYS),
           'agg_sys_sha256': sha(_AGGREGATION_SYSTEM), 'repair_model': MODEL,
           'cases': 30, 'cap_usd': CAP, 'max_tokens': TOK, 'temperature': 0}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def call(key, model, price, system, user, cap_total, total):
    pin, pout = price
    est = math.ceil((len(system) + len(user)) / 4)
    if total + est * pin + TOK * pout > cap_total:
        return None, total
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': model,
                            'system_sha256': sha(system), 'user_sha256': sha(user)}) + '\n')
    resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                     max_tokens=TOK, temperature=0, metadata={'pilot': 'repair_ab'}))
    u = resp.usage or {}
    cost = u.get('prompt_tokens', est) * pin + u.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'model': model, 'success': resp.success,
                            'usage': u, 'cost_usd': round(cost, 8),
                            'content': (resp.content or '')[:2000]}) + '\n')
    return resp, total + cost


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert sha(RULE.read_text()) == man['rule_sha256'], 'rule changed'
    cases = [c for c in json.loads(CASES.read_text()) if c['population'] == 'injected']
    acc = accepted()
    jl = {x['key']: (x.get('judge') or {}) for x in json.loads(JUDGE.read_text())['items']}
    qf = qwen_facts_carriers()
    done = ({json.loads(l)['trace_id'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    total = spent()
    for c in cases:
        if c['key'] in done:
            continue
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        t = corrupted(c, acc)
        a = acc[(model, inst)]
        agent = a['agent_id']
        shard = c['source'][str(agent)]
        question = c['question']
        # audit fact: the qwen fact backed by that agent
        facts = ((qf.get(c['key']) or {}).get('facts') or {}).get('facts') or []
        fact = next((f['text'] for f in facts if any(str(agent) in str(s) for s in f.get('source_ids', []))),
                    (facts[0]['text'] if facts else ''))
        ua = f"Question: {question}\nFact to state: {fact}\nAgent {agent} evidence:\n{shard}"
        uj = f"Question: {question}\nAgent {agent} evidence:\n{shard}"
        r = {}
        facts_pre = (qf.get(c['key']) or {}).get('facts') or {}
        ftexts = [f['text'] for f in (facts_pre.get('facts') or [])]
        def faithful(_board):
            return sum(1 for f in ftexts if any(recall(u['text'], f) >= 0.8 for u in _board))
        before = faithful(t['checkpoints']['board'])
        for arm, system, user in (('audit', AUDIT_SYS, ua), ('judge', JUDGE_SYS, uj)):
            resp, total = call(f"{c['key']}/{arm}/repair", MODEL, PRICE, system, user, CAP, total)
            if resp is None:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
            text = (resp.content or '').strip()
            board = [dict(u) for u in t['checkpoints']['board']]
            quote = text.splitlines()[0].lstrip('0123456789. -').strip('"') if text else ''
            quote = re.sub(r'^["\']|["\']$', '', quote)
            for u in board:
                if u['unit_id'] == a['unit_id']:
                    u['text'] = quote or a.get('original', '')
            user_agg = board_user({'question': question, 'n_agents': t.get('n_agents') or c.get('n_agents') or 5}, board)
            mid = MODEL_IDS[model]
            resp2, total = call(f"{c['key']}/{arm}/answer", mid, PRICE_TRACE[model],
                                _AGGREGATION_SYSTEM, user_agg, CAP, total)
            if resp2 is None:
                print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            f1 = answer_f1(ans, {'answer': a['gold'], 'answer_aliases': a.get('aliases') or []})
            after = faithful(board)
            r[arm] = {'answer': ans, 'exact': float(f1 == 1.0), 'board': board, 'faithful_before': before, 'faithful_after': after, 'lost': before - after}
        rec = {'trace_id': c['key'], 'model': model, 'instance_id': inst, 'agent': agent,
               'gold': a['gold'], 'audit': {k: v for k, v in r['audit'].items() if k != 'board'}, 'judge': {k: v for k, v in r['judge'].items() if k != 'board'}}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'key': c['key'], 'audit': r['audit']['exact'], 'judge': r['judge']['exact'],
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'rows': len(RESULTS.read_text().splitlines())}))


def mcnemar(b, c):
    # exact two-sided binomial on discordant pairs
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * p)


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ae = sum(r['audit']['exact'] for r in rows); je = sum(r['judge']['exact'] for r in rows)
    b = sum(1 for r in rows if r['audit']['exact'] and not r['judge']['exact'])
    c = sum(1 for r in rows if r['judge']['exact'] and not r['audit']['exact'])
    vals = [r['audit']['exact'] - r['judge']['exact'] for r in rows]
    rng = random.Random(43)
    bs = sorted(sum(vals[rng.randrange(len(vals))] for _ in vals) / len(vals) for _ in range(2000))
    out = {'n': len(rows), 'audit_exact': int(ae), 'judge_exact': int(je),
           'discordant_audit_only': b, 'discordant_judge_only': c,
           'mcnemar_p': mcnemar(b, c), 'diff': sum(vals) / len(vals),
           'diff_ci': [bs[50], bs[1949]], 'spend_usd': round(spent(), 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# Audit-guided versus judge-guided repair (30 injected cases)', '',
             '2026-11-15. Rule `Repair-A-vs-J.md` (sha `%s...`), one repair call and one answer call per arm. '
             'Spend $%.4f, cap $2.00.' % (sha(RULE.read_text())[:8], out['spend_usd']), '',
             '| arm | exact | n |', '| --- | ---: | ---: |',
             '| audit (fact + stage) | %d | %d |' % (ae, len(rows)),
             '| judge (stage + agent) | %d | %d |' % (je, len(rows)), '',
             'Discordant pairs: audit-only %d, judge-only %d. McNemar exact p = %.4f. Paired difference %+.3f [%+.3f, %+.3f].'
             % (b, c, out['mcnemar_p'], out['diff'], out['diff_ci'][0], out['diff_ci'][1]), '',
             '## Ledger', 'Spend $%.6f.' % out['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build: build()
    if a.run: run()
    if a.score: score()