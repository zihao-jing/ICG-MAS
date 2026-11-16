"""Part B judge validation: Opus 5.5 reference, then Gemini 3.6 Flash.

    ./run.sh python -m scripts.part_b_validate --opus
    ./run.sh python -m scripts.part_b_validate --gemini
    ./run.sh python -m scripts.part_b_validate --report
"""
import argparse
import hashlib
import json
import math
import random
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from utility.apis.base import APIRequest
from utility.apis.router import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261114_part_b_k1'
PREREG = ROOT / 'rebuttal/pilots/prereg/Part-B-k1.md'
PROMPTS = ROOT / 'rebuttal/judge/judge_prompts_v3.json'
OPUS = 'anthropic/claude-opus-5.5'
GEMINI = 'google/gemini-3.6-flash'
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6)}
CAP_USD = 2.00
N_VAL = 30


def sha(b):
    return hashlib.sha256(b).hexdigest()


def prompt_pair():
    p = json.loads(PROMPTS.read_text())['prompts']['E2_partB_natural_failure']
    return p['system'], p['user_template'], p['system_sha256']


def items():
    rows = [json.loads(l) for l in (OUT / 'answers.jsonl').read_text().splitlines()]
    assert len(rows) == 156
    return rows[-N_VAL:]


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    a, b = s.find('{'), s.rfind('}')
    if a < 0 or b < a:
        return None
    try:
        o = json.loads(s[a:b + 1])
    except Exception:
        return None
    return o if o.get('class') in ('single', 'multiple', 'indeterminate') else None


def log(row):
    with (OUT / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')


def call_all(model, tag):
    sysmsg, user_t, sys_sha = prompt_pair()
    assert sys_sha == sha(json.dumps(sysmsg, sort_keys=True,
                                     separators=(',', ':')).encode())
    rows, spent = [], 0.0
    for n, it in enumerate(items(), 1):
        key = f'partB-val/{tag}/{it["trace_id"]}'
        body = user_t.format(trace=trace_text(it['trace']))
        log({'event': 'intent', 'key': key, 'model': model})
        resp = single_request(APIRequest(system_query=sysmsg, user_query=body,
                                         model=model, max_tokens=2500,
                                         temperature=0,
                                         metadata={'openrouter_reasoning': True}))
        u = resp.usage or {}
        cost = (u.get('prompt_tokens', 0) * PRICE[model][0]
                + u.get('completion_tokens', 0) * PRICE[model][1])
        got = parse(resp.content) if resp.success else None
        rows.append({'trace_id': it['trace_id'], 'model': it['model'],
                     'instance_id': it['instance_id'], 'success': resp.success,
                     'valid': got is not None, 'parsed': got,
                     'raw': resp.content, 'usage': u, 'cost_usd': round(cost, 8)})
        spent += cost
        log({'event': 'result', 'key': key, 'model': model,
             'success': resp.success, 'usage': u, 'cost_usd': round(cost, 8),
             'valid': got is not None})
        print(json.dumps({'n': n, 'of': N_VAL, 'spent': round(spent, 6),
                          'valid': got is not None}), flush=True)
        if spent > CAP_USD:
            raise RuntimeError(f'validation cap passed: {spent}')
    path = OUT / f'{tag}_labels.json'
    path.write_text(json.dumps(rows, indent=1) + '\n')
    (OUT / f'{tag}_labels.sha256').write_text(sha(path.read_bytes()) + '\n')
    print(json.dumps({'tag': tag, 'n': len(rows), 'valid': sum(r['valid'] for r in rows),
                      'spent': round(spent, 6),
                      'sha256': sha(path.read_bytes())}))


def kappa(a, b):
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def boot(a, b, draws=2000, seed=42):
    rng = random.Random(seed)
    n = len(a)
    ks, ag = [], []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        aa = [a[i] for i in idx]
        bb = [b[i] for i in idx]
        ks.append(kappa(aa, bb))
        ag.append(sum(x == y for x, y in zip(aa, bb)) / n)
    ks.sort()
    ag.sort()
    return (ag[int(.025 * draws)], ag[int(.975 * draws)]), (ks[int(.025 * draws)], ks[int(.975 * draws)])


def report():
    opus = json.loads((OUT / 'opus_labels.json').read_text())
    gem = json.loads((OUT / 'gemini_labels.json').read_text())
    assert sha((OUT / 'opus_labels.json').read_bytes()) == (OUT / 'opus_labels.sha256').read_text().strip()
    pairs = [(o, g) for o, g in zip(opus, gem) if o['valid'] and g['valid']]
    a = [o['parsed']['class'] for o, g in pairs]
    b = [g['parsed']['class'] for o, g in pairs]
    agree = sum(x == y for x, y in zip(a, b)) / len(a)
    k = kappa(a, b)
    ci_a, ci_k = boot(a, b)
    out = {'n_valid': len(a), 'n_excluded': len(opus) - len(a),
           'agreement': agree, 'agreement_ci': ci_a,
           'kappa': k, 'kappa_ci': ci_k,
           'bar': {'agreement': 0.80, 'kappa': 0.60},
           'passes': agree >= .80 and k >= .60,
           'opus_sha256': (OUT / 'opus_labels.sha256').read_text().strip(),
           'per_class': {c: sum(x == c for x in a) for c in ('single', 'multiple', 'indeterminate')}}
    (OUT / 'validation.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--opus', action='store_true')
    ap.add_argument('--gemini', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.opus:
        call_all(OPUS, 'opus')
    if a.gemini:
        assert (OUT / 'opus_labels.sha256').exists()
        call_all(GEMINI, 'gemini')
    if a.report:
        report()


if __name__ == '__main__':
    main()