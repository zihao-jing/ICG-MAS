"""Silo-Bench two-step proxy pilot: select rows, then facts for those rows only.

Rule `rebuttal/pilots/prereg/Silo-Bench-two-step-pilot.md`, frozen before any call.
20 traces of 208, cap $1.50, truncation stop at 2%, granularity checked against gold.

    ./run.sh python -m scripts.sb_twostep_pilot --build
    ./run.sh python -m scripts.sb_twostep_pilot --run
    ./run.sh python -m scripts.sb_twostep_pilot --score
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.proxy_support_run import PRICE, QWEN, GEMINI, HAIKU, render_docs, validate_facts
from scripts.per_fact_labeller import parse as parse_audit
from scripts.per_fact_labeller import render as render_audit
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_sb_twostep_pilot'
RULE = ROOT / 'rebuttal/pilots/prereg/Silo-Bench-two-step-pilot.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v3_two_step.json'
EQUIV = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
SRC = ROOT / 'rebuttal/pilots/20261115_proxy_support_sb_fixed/population.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
SEED = 50
N = 20
CAP = 1.5
CHUNK = 0.9
FACTS_TOK = 8000
EQUIV_TOK = 8000
SEL_TOK = 800
LABEL = False
AUDIT_PROMPT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'
LABEL_TOK = 8192


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    rows = json.loads(SRC.read_text())
    keys = sorted(r['key'] for r in rows)
    rng = random.Random(SEED)
    pick = set(rng.sample(keys, N))
    pop = [r for r in rows if r['key'] in pick]
    pop.sort(key=lambda r: r['key'])
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    POP.write_text(json.dumps(pop, ensure_ascii=False))
    gold = [len(r['gold_supports']) for r in pop]
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'equiv_prompt_sha256': file_sha(EQUIV),
           'population_sha256': file_sha(POP), 'seed': SEED, 'traces': len(pop),
           'gold_mean': sum(gold) / len(gold), 'cap_usd': CAP, 'chunk_usd': CHUNK,
           'truncation_stop': 0.02, 'facts_per_trace_max': 30, 'granularity_factor': 1.2}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    assert file_sha(PROMPT) == m['prompt_sha256'], 'prompt changed'
    assert file_sha(EQUIV) == m['equiv_prompt_sha256'], 'equiv prompt changed'
    assert file_sha(POP) == m['population_sha256'], 'population changed'
    return m


def call(key, model, system, user, max_tokens, total):
    pin, pout = PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    if total + est_in * pin + max_tokens * pout > CAP:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': model,
                            'system_sha256': sha(system), 'user_sha256': sha(user),
                            'max_tokens': max_tokens, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                     max_tokens=max_tokens, temperature=0,
                                     metadata={'pilot': 'sb_twostep', 'key': key}))
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'model': model,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def selected_ids(content, doc_ids):
    obj = last_object(content or '')
    if not isinstance(obj, dict) or not isinstance(obj.get('needed'), list):
        return None
    out = []
    for x in obj['needed']:
        if not isinstance(x, str):
            return None
        # the model sometimes wraps ids as "[agent-0]" or "agent-0 (row 3)"; take the bare id
        x = x.strip().strip('[]').split(' (')[0].strip()
        if x not in doc_ids:
            return None
        if x not in out:
            out.append(x)
    return out or None


def one(row, total):
    prof = json.loads(PROMPT.read_text())
    eq = json.loads(EQUIV.read_text())
    docs = {d['unit_id']: d['text'] for d in row['documents']}
    rendered = render_docs(row)
    trace = {'key': row['key'], 'protocol': row['protocol'], 'gold_supports': len(row['gold_supports']),
             'truncated': False, 'selection': None, 'facts': None, 'equiv': None, 'attempts': {}}
    user = prof['selection']['user'].format(question=row['question'], documents=rendered)
    pick = None
    for n in (1, 2, 3):
        resp, total = call(f"select/{row['key']}/attempt-{n}", QWEN, prof['selection']['system'],
                           user, SEL_TOK, total)
        if resp is None:
            return None, total
        if (resp.usage or {}).get('completion_tokens', 0) >= SEL_TOK - 8:
            trace['truncated'] = True
        if resp.success:
            pick = selected_ids(resp.content, set(docs))
        trace['attempts']['selection'] = n
        if pick:
            break
    trace['selection'] = pick
    if not pick:
        return trace, total
    sub = [{'unit_id': u, 'text': docs[u]} for u in pick]
    user_f = prof['facts']['user'].format(question=row['question'],
                                          documents=render_docs({'documents': sub}))
    facts = None
    for n in (1, 2, 3):
        resp, total = call(f"facts/{row['key']}/attempt-{n}", QWEN, prof['facts']['system'],
                           user_f, FACTS_TOK, total)
        if resp is None:
            return None, total
        if (resp.usage or {}).get('completion_tokens', 0) >= FACTS_TOK - 8:
            trace['truncated'] = True
        if resp.success:
            facts = validate_facts(last_object(resp.content or ''), set(docs))
        trace['attempts']['facts'] = n
        if facts:
            break
    trace['facts'] = facts
    if not facts:
        return trace, total
    fids = [f['fact_id'] for f in facts['facts']]
    fl = '\n'.join(f"{f['fact_id']}: {f['text']}" for f in facts['facts'])
    sup = '\n\n'.join(f"[{s['unit_id']}]\n{s['text']}" for s in row['gold_supports'])
    user_e = eq['user'].format(question=row['question'], facts=fl, supports=sup)
    for n in (1, 2):
        resp, total = call(f"equiv/{row['key']}/attempt-{n}", GEMINI, eq['system'], user_e,
                           EQUIV_TOK, total)
        if resp is None:
            return None, total
        if (resp.usage or {}).get('completion_tokens', 0) >= EQUIV_TOK - 8:
            trace['truncated'] = True
        obj = last_object(resp.content or '') if resp.success else None
        ok = (isinstance(obj, dict) and isinstance(obj.get('facts'), list)
              and [x.get('fact_id') for x in obj['facts']] == fids
              and all(x.get('verdict') in {'equivalent', 'partial', 'unsupported', 'contradicted'}
                      for x in obj['facts']))
        if ok:
            trace['equiv'] = {x['fact_id']: x['verdict'] for x in obj['facts']}
            break
    if LABEL and trace['equiv'] is not None and row.get('has_extraction', True):
        sa = json.loads(AUDIT_PROMPT.read_text())
        ids = set(fids)
        trace['labels'] = {}
        for chk, name in (('extraction', 'extraction pool'), ('board', 'shared board')):
            arow = {'question': row['question'], 'facts': facts['facts'],
                    'entries': row['checkpoints'][chk], 'checkpoint_name': name}
            user_a = render_audit(arow)
            for n in (1, 2):
                resp, total = call(f"audit/{row['key']}/{chk}/attempt-{n}", HAIKU, sa['system'],
                                   user_a, LABEL_TOK, total)
                if resp is None:
                    return None, total
                if (resp.usage or {}).get('completion_tokens', 0) >= LABEL_TOK - 8:
                    trace['truncated'] = True
                lab = parse_audit(resp.content or '', ids) if resp.success else None
                if lab is not None:
                    trace['labels'][chk] = lab
                    break
    return trace, total


def run():
    man = check()
    rows = json.loads(POP.read_text())
    done = ({json.loads(l)['key'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    total = spent()
    chunk, start = 1, total
    print(json.dumps({'todo': len([r for r in rows if r['key'] not in done]),
                      'spent': round(total, 6)}), flush=True)
    completed = 0
    for row in rows:
        if row['key'] in done:
            completed += 1
            continue
        if total - start > CHUNK:
            over = total - start > 1.0
            print(json.dumps({'chunk': chunk, 'spend': round(total - start, 6),
                              'overrun': over}), flush=True)
            if over:
                print(json.dumps({'stop': 'chunk overrun'}))
                return
            chunk += 1
            start = total
        trace, total = one(row, total)
        if trace is None:
            print(json.dumps({'stop': 'cap', 'spent': round(total, 6)}))
            return
        with RESULTS.open('a') as f:
            f.write(json.dumps(trace, ensure_ascii=False) + '\n')
        completed += 1
        so_far = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
        trunc = sum(1 for x in so_far if x.get('truncated'))
        print(json.dumps({'key': row['key'], 'picked': len(trace['selection'] or []),
                          'facts': len((trace['facts'] or {}).get('facts') or []),
                          'trunc': trunc, 'done': completed, 'of': len(rows),
                          'spent': round(total, 6)}), flush=True)
        if trunc / completed > man['truncation_stop']:
            print(json.dumps({'stop': '2% truncation', 'truncated': trunc,
                              'completed': completed, 'spent': round(total, 6)}))
            return
    print(json.dumps({'spent': round(spent(), 6), 'completed': completed}))


def score():
    man = check()
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    n = len(rows)
    trunc = sum(1 for r in rows if r.get('truncated'))
    facts = [len((r['facts'] or {}).get('facts') or []) for r in rows]
    gold = [r['gold_supports'] for r in rows]
    eq = []
    for r in rows:
        if r.get('equiv'):
            eq += list(r['equiv'].values())
    good = sum(1 for v in eq if v == 'equivalent')
    out = {'n': n, 'truncated': trunc,
           'truncation_ci': list(cp_ci(trunc, n)) if n else None,
           'facts_mean': sum(facts) / n if n else None, 'facts_max': max(facts) if facts else None,
           'gold_mean': sum(gold) / n if n else None,
           'granularity_factor': (sum(facts) / sum(gold)) if sum(gold) else None,
           'equivalence': (good / len(eq)) if eq else None,
           'equivalence_n': len(eq), 'equivalence_ci': list(cp_ci(good, len(eq))) if eq else None,
           'spend_usd': round(spent(), 6)}
    out['truncation_pass'] = n > 0 and trunc / n <= man['truncation_stop']
    out['gen_failed'] = sum(1 for r in rows if not (r['facts'] or {}).get('facts'))
    out['granularity_pass'] = (n > 0 and out['gen_failed'] == 0
                               and out['facts_mean'] <= man['granularity_factor'] * out['gold_mean']
                               and out['facts_max'] <= man['facts_per_trace_max'])
    out['passes'] = bool(out['truncation_pass'] and out['granularity_pass'])
    SCORE.write_text(json.dumps(out, indent=1))
    write_report(out, man, rows)
    print(json.dumps(out, indent=1))


def write_report(res, man, rows):
    def pct(k, n):
        return '%.1f%%' % (100.0 * k / n) if n else '—'

    lines = ['# Silo-Bench two-step proxy pilot',
             '',
             '2026-11-15. Rule `Silo-Bench-two-step-pilot.md` (sha `%s...`), prompt '
             '`proxy_facts_prompt_v3_two_step.json` (sha `%s...`). 20 of 208 traces, seed %d; selection then '
             'facts for the selected rows only. Spend $%.6f, cap $1.50.'
             % (man['rule_sha256'][:8], man['prompt_sha256'][:8], man['seed'], res['spend_usd']),
             '',
             '| quantity | value [95% CI] | bar |',
             '| --- | --- | --- |',
             '| truncated traces | %d/%d (%s) [%s, %s] | <= 2%% |'
             % (res['truncated'], res['n'], pct(res['truncated'], res['n']),
                '%.1f%%' % (100 * res['truncation_ci'][0]) if res['truncation_ci'] else '—',
                '%.1f%%' % (100 * res['truncation_ci'][1]) if res['truncation_ci'] else '—'),
             '| facts per trace, mean / max | %.1f / %d | mean <= 1.2 x gold, max <= 30 |'
             % (res['facts_mean'], res['facts_max']),
             '| gold supports per trace, mean | %.1f | — |' % res['gold_mean'],
             '| facts / gold | %.2f | <= 1.20 |' % res['granularity_factor'],
             '| fact equivalence to gold | %s [%s, %s] (n=%d) | reported, not a bar |'
             % (pct(int((res['equivalence'] or 0) * res['equivalence_n']), res['equivalence_n']),
                '%.1f%%' % (100 * res['equivalence_ci'][0]) if res['equivalence_ci'] else '—',
                '%.1f%%' % (100 * res['equivalence_ci'][1]) if res['equivalence_ci'] else '—',
                res['equivalence_n']),
             '',
             '**Pilot %s.** Truncation bar %s; granularity bar %s.'
             % ('PASSES' if res['passes'] else 'FAILS',
                'pass' if res['truncation_pass'] else 'fail',
                'pass' if res['granularity_pass'] else 'fail'),
             '',
             '| trace | selected rows | facts | gold supports | truncated | agreement |',
             '| --- | ---: | ---: | ---: | --- | --- |']
    for r in rows:
        lines.append('| %s | %d | %d | %d | %s | %s |'
                     % (r['key'], len(r.get('selection') or []),
                        len((r.get('facts') or {}).get('facts') or []), r['gold_supports'],
                        'yes' if r.get('truncated') else 'no',
                        r.get('equiv') is not None))
    lines += ['', '## Ledger', 'Spend $%.6f.' % res['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


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