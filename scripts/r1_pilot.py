"""R1 (released prompt and parser, our renderer) on the 30 injected cases. Cap $0.80.

Rule `prereg/R1-reimplementation-pilot.md`, frozen before any call.

    ./run.sh python -m scripts.r1_pilot --build
    ./run.sh python -m scripts.r1_pilot --run
    ./run.sh python -m scripts.r1_pilot --score
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.audit_diagnosis_89 import accepted, corrupted
from scripts.b5_attribution_2x2 import CASES, adapt
from src.audit.official_adapters import parse_r1, r1_prompt
from src.audit.pilot_common import render_trace
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_r1_pilot'
RULE = ROOT / 'rebuttal/pilots/prereg/R1-reimplementation-pilot.md'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'google/gemini-3.6-flash'
PRICE = (0.75 / 1e6, 3.75 / 1e6)
CAP = 0.8
TOK = 4096

MODE_STAGE = {
    'P.1': 'extraction', 'P.2': 'extraction', 'R.1': 'aggregation', 'R.2': 'aggregation',
    'R.3': 'aggregation', 'R.4': 'aggregation', 'PL.1': 'aggregation', 'PL.2': 'aggregation',
    'A.1': 'extraction', 'A.2': 'extraction', 'A.3': 'aggregation', 'A.4': 'aggregation',
    'V.1': 'transmission', 'V.2': 'aggregation', 'C.1': 'aggregation', 'C.2': 'transmission',
    'C.3': 'aggregation'}


def cp_ci(k, n):
    if n == 0:
        return 0.0, 1.0
    try:
        from scipy.stats import beta
        lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
        hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
        return lo, hi
    except Exception:
        p = k / n
        z = 1.96
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return max(0.0, c - h), min(1.0, c + h)


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(ROOT / 'rebuttal/external/whowhen_eval/prompts.py'),
           'taxonomy_sha256': file_sha(ROOT / 'rebuttal/external/taxonomy.yaml'),
           'mode_stage_map_sha256': sha(json.dumps(MODE_STAGE, sort_keys=True)),
           'model': MODEL, 'cases': 30, 'cap_usd': CAP}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def run():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert sha(json.dumps(MODE_STAGE, sort_keys=True)) == man['mode_stage_map_sha256'], 'map changed'
    cases = [c for c in json.loads(CASES.read_text()) if c['population'] == 'injected']
    acc = accepted()
    done = ({json.loads(l)['trace_id'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    total = spent()
    for c in cases:
        if c['key'] in done:
            continue
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        t = corrupted(c, acc)
        t['answer_text'] = c.get('answer') or ''
        t['gold_answer'] = acc[(model, inst)]['gold']
        t.setdefault('question', c['question'])
        msgs, steps = r1_prompt(trace=t, gold=False)
        user = msgs[0]['content'] if isinstance(msgs[0], dict) else msgs[0]
        if isinstance(user, list):
            user = '\n'.join(b.get('text', '') for b in user if isinstance(b, dict))
        est = math.ceil(len(user) / 4)
        if total + est * PRICE[0] + TOK * PRICE[1] > CAP:
            print(json.dumps({'stop': 'cap', 'spent': round(total, 6)})); return
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'intent', 'key': c['key'], 'model': MODEL,
                                'user_sha256': sha(user)}) + '\n')
        resp = single_request(APIRequest(system_query='', user_query=user, model=MODEL,
                                         max_tokens=TOK, temperature=0,
                                         metadata={'pilot': 'r1_pilot'}))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', est) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
        parsed = parse_r1(resp.content or '', steps) if resp.success else {}
        mode = (parsed or {}).get('mode') or ''
        stage = MODE_STAGE.get(mode, 'unmapped')
        rec = {'trace_id': c['key'], 'known_stage': c['known_stage'], 'mode': mode, 'stage': stage,
               'parses': (parsed or {}).get('parses'), 'valid_mode_code': (parsed or {}).get('valid_mode_code'),
               'agent': (parsed or {}).get('agent'), 'step': (parsed or {}).get('step'),
               'raw': (resp.content or '')[:1200]}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'result', 'key': c['key'], 'model': MODEL, 'success': resp.success,
                                'usage': u, 'cost_usd': round(cost, 8)}) + '\n')
        total += cost
        print(json.dumps({'key': c['key'], 'mode': mode, 'stage': stage, 'spent': round(total, 6)}),
              flush=True)
    print(json.dumps({'spent': round(spent(), 6), 'done': len(RESULTS.read_text().splitlines())}))


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    n = len(rows)
    right = sum(1 for r in rows if r['stage'] == r['known_stage'])
    lo, hi = cp_ci(right, n)
    from collections import Counter
    modes = Counter(r['mode'] or '(unparsed)' for r in rows)
    out = {'n': n, 'right': right, 'accuracy': right / n if n else None, 'cp_ci': [lo, hi],
           'modes': dict(modes), 'unmapped': sum(1 for r in rows if r['stage'] == 'unmapped'),
           'spend_usd': round(spent(), 6)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# [R1] on our traces: 30-case pilot (re-implementation)', '',
             '2026-11-15. Released all-at-once prompt and parser, our trace renderer, frozen mode->stage map '
             '(`R1-reimplementation-pilot.md`, sha `%s...`). Gemini 3.6 Flash. Spend $%.4f, cap $0.80.'
             % (file_sha(RULE)[:8], out['spend_usd']), '',
             '| quantity | value |', '| --- | ---: |', '| cases | %d |' % n,
             '| stage correct | %d/%d = %.3f |' % (right, n, out['accuracy'] or 0),
             '| 95%% CI | [%.3f, %.3f] |' % (lo, hi),
             '| unmapped modes | %d |' % out['unmapped'], '',
             '| mode | n |', '| --- | ---: |']
    for m, v in modes.most_common():
        lines.append('| %s | %d |' % (m, v))
    lines += ['', 'Label: re-implementation. Deviations are listed in the rule: our renderer, and our frozen map '
              'from the 17 released modes to the four audit stages.', '', '## Ledger', 'Spend $%.6f.' % out['spend_usd']]
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