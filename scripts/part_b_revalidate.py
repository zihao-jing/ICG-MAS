"""Revalidate judge v2 on 30 fresh traces: Opus 5.5, then Gemini 3.6 Flash."""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from utility.apis.base import APIRequest
from utility.apis.router import single_request

ROOT = Path(__file__).resolve().parent.parent
K1 = ROOT / 'rebuttal/pilots/20261114_part_b_k1'
OUT = K1 / 'reval'
PREREG = ROOT / 'rebuttal/pilots/prereg/Part-B-judge-v2.md'
PROMPT = ROOT / 'rebuttal/judge/E2-judge-v2.json'
OPUS = 'anthropic/claude-opus-5.5'
GEMINI = 'google/gemini-3.6-flash'
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6)}
CAP = 2.00


def sha(b):
    return hashlib.sha256(b).hexdigest()


def items():
    items = json.loads((K1 / 'extra' / 'fresh_items.json').read_text())['items']
    assert len(items) == 30
    return items


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


def call(model, tag):
    p = json.loads(PROMPT.read_text())
    sysmsg, user_t = p['system'], p['user_template']
    dig = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert dig(sysmsg) == p['system_sha256']
    OUT.mkdir(parents=True, exist_ok=True)
    rows, spent = [], 0.0
    for n, it in enumerate(items(), 1):
        key = f"reval/{tag}/{it['trace_id']}"
        body = user_t.format(trace=trace_text(it['trace']))
        log({'event': 'intent', 'key': key, 'model': model})
        resp = single_request(APIRequest(system_query=sysmsg, user_query=body,
                                         model=model, max_tokens=2500, temperature=0,
                                         metadata={'openrouter_reasoning': True}))
        u = resp.usage or {}
        cost = u.get('prompt_tokens', 0) * PRICE[model][0] + u.get('completion_tokens', 0) * PRICE[model][1]
        got = parse(resp.content) if resp.success else None
        rows.append({'trace_id': it['trace_id'], 'model': it['model'],
                     'instance_id': it['instance_id'], 'success': resp.success,
                     'valid': got is not None, 'parsed': got, 'raw': resp.content,
                     'usage': u, 'cost_usd': round(cost, 8)})
        spent += cost
        log({'event': 'result', 'key': key, 'model': model, 'success': resp.success,
             'usage': u, 'cost_usd': round(cost, 8), 'valid': got is not None})
        print(json.dumps({'n': n, 'of': 30, 'spent': round(spent, 6),
                          'valid': got is not None}), flush=True)
        if spent > CAP:
            raise RuntimeError('cap')
    path = OUT / f'{tag}.json'
    path.write_text(json.dumps(rows, indent=1) + '\n')
    (OUT / f'{tag}.sha256').write_text(sha(path.read_bytes()) + '\n')
    print(json.dumps({'tag': tag, 'valid': sum(r['valid'] for r in rows),
                      'spent': round(spent, 6), 'sha256': sha(path.read_bytes())}))


def kappa(a, b):
    cats = sorted(set(a) | set(b)); n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def boot(a, b, draws=2000, seed=42):
    rng = random.Random(seed); n = len(a); ks, ag = [], []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        aa = [a[i] for i in idx]; bb = [b[i] for i in idx]
        ks.append(kappa(aa, bb)); ag.append(sum(x == y for x, y in zip(aa, bb)) / n)
    ks.sort(); ag.sort()
    return (ag[int(.025 * draws)], ag[int(.975 * draws)]), (ks[int(.025 * draws)], ks[int(.975 * draws)])


def report():
    o = json.loads((OUT / 'opus.json').read_text())
    g = json.loads((OUT / 'gemini.json').read_text())
    assert sha((OUT / 'opus.json').read_bytes()) == (OUT / 'opus.sha256').read_text().strip()
    pairs = [(a, b) for a, b in zip(o, g) if a['valid'] and b['valid']]
    a = [x['parsed']['class'] for x, y in pairs]; b = [y['parsed']['class'] for x, y in pairs]
    agree = sum(x == y for x, y in zip(a, b)) / len(a); k = kappa(a, b)
    ci_a, ci_k = boot(a, b)
    out = {'n_valid': len(a), 'n_excluded': len(o) - len(a),
           'agreement': agree, 'agreement_ci': ci_a, 'kappa': k, 'kappa_ci': ci_k,
           'bar': {'agreement': .80, 'kappa': .60},
           'passes': agree >= .80 and k >= .60,
           'opus_sha256': (OUT / 'opus.sha256').read_text().strip(),
           'counts': {'opus': {c: a.count(c) for c in ('single', 'multiple', 'indeterminate')},
                      'gemini': {c: b.count(c) for c in ('single', 'multiple', 'indeterminate')}}}
    (OUT / 'validation.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('opus', 'gemini', 'report'):
        ap.add_argument('--' + f, action='store_true')
    x = ap.parse_args()
    if x.opus:
        call(OPUS, 'opus')
    if x.gemini:
        assert (OUT / 'opus.sha256').exists()
        call(GEMINI, 'gemini')
    if x.report:
        report()


if __name__ == '__main__':
    main()