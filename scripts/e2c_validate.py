"""E2-C judge validation: 20 baseline outputs, Opus 5.5 then Gemini 3.6 Flash.

    ./run.sh python -m scripts.e2c_validate --baselines
    ./run.sh python -m scripts.e2c_validate --opus
    ./run.sh python -m scripts.e2c_validate --gemini
    ./run.sh python -m scripts.e2c_validate --report
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from src.audit.official_adapters import r1_prompt, parse_r1, verify_external, ww
from src.audit.pilot_common import CallLedger, render_trace
from utility.apis.base import APIRequest
from utility.apis.router import single_request

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl'
OUT = ROOT / 'rebuttal/pilots/20261114_e2c_validate'
PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-judge-validation.md'
QWEN = 'qwen/qwen3-235b-a22b-2507'
OPUS = 'anthropic/claude-opus-5.5'
GEMINI = 'google/gemini-3.6-flash'
PRICE = {OPUS: (4.0 / 1e6, 20.0 / 1e6), GEMINI: (0.75 / 1e6, 3.75 / 1e6)}
CAP_USD = 1.00

SYSTEM = ("You are an annotator for a research study on multi-agent evidence flow. "
          "You will see ONE recorded run and one attribution method's answer. The "
          "answer names an agent and a stage (extraction, transmission or aggregation). "
          "Decide whether that (agent, stage) is a site of a visible evidence-flow "
          "defect that could be decisive for the wrong final answer. Judge only from "
          "the trace and the method's answer; do not use outside knowledge. If the "
          "answer is unparseable, or no defect is visible at that agent and stage, "
          "answer \"no\". If the evidence is insufficient, answer \"uncertain\". Reply "
          "with a single JSON object and nothing else:\n"
          "{\"match\": \"yes|no|uncertain\", \"agent\": null, \"stage\": "
          "\"extraction|transmission|aggregation|null\", \"rationale\": \"\"}")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def items():
    rows = [json.loads(l) for l in SRC.read_text().splitlines()]
    val = rows[126:156][:10]
    assert len(val) == 10
    return val


def log(row):
    with (OUT / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')


def run_baselines():
    if verify_external():
        raise SystemExit('; '.join(verify_external()))
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': 42,
           'temperature': 0, 'max_tokens': 4096,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, 20)
    out = []
    try:
        for r in items():
            t = r['trace']
            steps = render_trace(t)
            history = [{'name': s['agent'], 'content': s['text']} for s in steps]
            key = f"val/{r['trace_id']}"
            wr = ww(ledger, key + '/ww', QWEN, history, t['question'])
            msgs, _ = r1_prompt(trace=t, gold=False)
            raw = ledger.call(key + '/r1', QWEN, msgs, max_tokens=4096)
            out.append({'trace_id': r['trace_id'], 'model': r['model'],
                        'instance_id': r['instance_id'],
                        'ww': {'raw': wr['raw'], 'stdout': wr['stdout']},
                        'r1': {'raw': raw, 'parsed': parse_r1(raw, steps)}})
    finally:
        ledger.close()
    (OUT / 'outputs.json').write_text(json.dumps(out, indent=1) + '\n')
    cost = sum(json.loads(l).get('cost_usd') or 0 for l in
               (OUT / 'calls.jsonl').read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')
    print(json.dumps({'items': len(out), 'calls': 20, 'cost_usd': round(cost, 6)}))


def flat_outputs():
    rows = json.loads((OUT / 'outputs.json').read_text())
    out = []
    for r in rows:
        out.append({'trace_id': r['trace_id'], 'instance_id': r['instance_id'],
                    'method': 'ww_all', 'raw': '\n'.join(r['ww']['raw']),
                    'parsed': None})
        out.append({'trace_id': r['trace_id'], 'instance_id': r['instance_id'],
                    'method': 'r1', 'raw': r['r1']['raw'], 'parsed': r['r1']['parsed']})
    return out


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    a, b = s.find('{'), s.rfind('}')
    if a < 0 or b < a:
        return None
    try:
        o = json.loads(s[a:b + 1])
    except Exception:
        return None
    return o if o.get('match') in ('yes', 'no', 'uncertain') else None


def judge(model, tag):
    rows = flat_outputs()
    traces = {r['trace_id']: r for r in items()}
    labelled, spent = [], 0.0
    for n, o in enumerate(rows, 1):
        body = (trace_text(traces[o['trace_id']]['trace'])
                + '\n\nATTRIBUTION TO CHECK:\n' + (o['raw'] or '')[:1600])
        key = f"e2c-val/{tag}/{o['trace_id']}/{o['method']}"
        log({'event': 'intent', 'key': key, 'model': model})
        resp = single_request(APIRequest(system_query=SYSTEM, user_query=body,
                                         model=model, max_tokens=1200,
                                         temperature=0,
                                         metadata={'openrouter_reasoning': True}))
        u = resp.usage or {}
        cost = (u.get('prompt_tokens', 0) * PRICE[model][0]
                + u.get('completion_tokens', 0) * PRICE[model][1])
        got = parse(resp.content) if resp.success else None
        labelled.append({'trace_id': o['trace_id'], 'method': o['method'],
                         'success': resp.success, 'valid': got is not None,
                         'parsed': got, 'raw': resp.content,
                         'usage': u, 'cost_usd': round(cost, 8)})
        spent += cost
        log({'event': 'result', 'key': key, 'model': model, 'success': resp.success,
             'usage': u, 'cost_usd': round(cost, 8), 'valid': got is not None})
        print(json.dumps({'n': n, 'of': len(rows), 'spent': round(spent, 6),
                          'valid': got is not None}), flush=True)
        if spent > CAP_USD:
            raise RuntimeError(f'cap passed: {spent}')
    path = OUT / f'{tag}_labels.json'
    path.write_text(json.dumps(labelled, indent=1) + '\n')
    (OUT / f'{tag}_labels.sha256').write_text(sha(path.read_bytes()) + '\n')
    print(json.dumps({'tag': tag, 'n': len(labelled),
                      'valid': sum(x['valid'] for x in labelled),
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
    opus = json.loads((OUT / 'opus_labels.json').read_text())
    gem = json.loads((OUT / 'gemini_labels.json').read_text())
    assert sha((OUT / 'opus_labels.json').read_bytes()) == (OUT / 'opus_labels.sha256').read_text().strip()
    pairs = [(o, g) for o, g in zip(opus, gem) if o['valid'] and g['valid']]
    a = [o['parsed']['match'] for o, g in pairs]
    b = [g['parsed']['match'] for o, g in pairs]
    agree = sum(x == y for x, y in zip(a, b)) / len(a)
    k = kappa(a, b); ci_a, ci_k = boot(a, b)
    out = {'n_valid': len(a), 'n_excluded': len(opus) - len(a),
           'agreement': agree, 'agreement_ci': ci_a, 'kappa': k, 'kappa_ci': ci_k,
           'bar': {'agreement': 0.80, 'kappa': 0.60},
           'passes': agree >= .80 and k >= .60,
           'opus_sha256': (OUT / 'opus_labels.sha256').read_text().strip(),
           'counts': {'opus': {c: a.count(c) for c in ('yes', 'no', 'uncertain')},
                      'gemini': {c: b.count(c) for c in ('yes', 'no', 'uncertain')}}}
    (OUT / 'validation.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('baselines', 'opus', 'gemini', 'report'):
        ap.add_argument('--' + f, action='store_true')
    a = ap.parse_args()
    if a.baselines:
        run_baselines()
    if a.opus:
        judge(OPUS, 'opus')
    if a.gemini:
        assert (OUT / 'opus_labels.sha256').exists()
        judge(GEMINI, 'gemini')
    if a.report:
        report()


if __name__ == '__main__':
    main()