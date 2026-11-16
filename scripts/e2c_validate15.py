"""E2-C judge validation completion: 15 carded traces, adding 5 to the 10.

    ./run.sh python -m scripts.e2c_validate15 --baselines
    ./run.sh python -m scripts.e2c_validate15 --opus
    ./run.sh python -m scripts.e2c_validate15 --gemini
    ./run.sh python -m scripts.e2c_validate15 --report

The first 10 traces are already labelled in 20261114_e2c_validate. This
completion adds rows 136:141 of answers.jsonl (5 traces, 10 outputs) and
reports the combined 15-trace / 30-output validation. The rule hash is
checked before every stage.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from src.audit.official_adapters import r1_prompt, parse_r1, verify_external, ww
from src.audit.pilot_common import CallLedger, render_trace
from utility.apis.base import APIRequest
from utility.apis.router import single_request

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl'
OLD = ROOT / 'rebuttal/pilots/20261114_e2c_validate'
OUT = ROOT / 'rebuttal/pilots/20261114_e2c_validate15'
PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-judge-validation-15.md'
RULE_SHA256 = '21bc3d109e38cf0ccb7c096f0b3f64e55e1b637f9b60098821e01bb098f24c6b'
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


def check_rule():
    got = sha(PREREG.read_bytes())
    if got != RULE_SHA256:
        raise SystemExit(f'rule changed: {got} != {RULE_SHA256}')
    return got


def all_items():
    rows = [json.loads(l) for l in SRC.read_text().splitlines()]
    val = rows[126:141]
    assert len(val) == 15
    return val


def new_items():
    return all_items()[10:15]


def log(row):
    with (OUT / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')


def run_baselines():
    check_rule()
    if verify_external():
        raise SystemExit('; '.join(verify_external()))
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': 42,
           'temperature': 0, 'max_tokens': 4096,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, 10)
    out = []
    try:
        for r in new_items():
            t = r['trace']
            steps = render_trace(t)
            history = [{'name': s['agent'], 'content': s['text']} for s in steps]
            key = f"val15/{r['trace_id']}"
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
    cost = sum(float(json.loads(l).get('cost_usd') or 0) for l in
               (OUT / 'calls.jsonl').read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')
    print(json.dumps({'items': len(out), 'calls': 10, 'cost_usd': round(cost, 6)}))


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
    check_rule()
    rows = flat_outputs()
    traces = {r['trace_id']: r for r in new_items()}
    labelled, spent = [], 0.0
    for n, o in enumerate(rows, 1):
        body = (trace_text(traces[o['trace_id']]['trace'])
                + '\n\nATTRIBUTION TO CHECK:\n' + (o['raw'] or '')[:1600])
        key = f"e2c-val15/{tag}/{o['trace_id']}/{o['method']}"
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
    import random
    rng = random.Random(seed); n = len(a); ks, ag = [], []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        aa = [a[i] for i in idx]; bb = [b[i] for i in idx]
        ks.append(kappa(aa, bb)); ag.append(sum(x == y for x, y in zip(aa, bb)) / n)
    ks.sort(); ag.sort()
    return ((ag[int(.025 * draws)], ag[int(.975 * draws)]),
            (ks[int(.025 * draws)], ks[int(.975 * draws)]))


def _load(path, sha_path):
    data = json.loads(path.read_text())
    assert sha(path.read_bytes()) == sha_path.read_text().strip(), f'{path} changed'
    return data


def report():
    check_rule()
    old_opus = _load(OLD / 'opus_labels.json', OLD / 'opus_labels.sha256')
    old_gem = _load(OLD / 'gemini_labels.json', OLD / 'gemini_labels.sha256')
    new_opus = _load(OUT / 'opus_labels.json', OUT / 'opus_labels.sha256')
    new_gem = _load(OUT / 'gemini_labels.json', OUT / 'gemini_labels.sha256')
    old = {(x['trace_id'], x['method']): x for x in old_opus}
    oldg = {(x['trace_id'], x['method']): x for x in old_gem}
    new = {(x['trace_id'], x['method']): x for x in new_opus}
    newg = {(x['trace_id'], x['method']): x for x in new_gem}
    traces = all_items()
    assert len({r['trace_id'] for r in traces}) == 15
    pairs, ids = [], set()
    for r in traces:
        for method in ('ww_all', 'r1'):
            k = (r['trace_id'], method)
            assert k not in ids, f'duplicate {k}'
            ids.add(k)
            if k in old:
                pairs.append((old[k], oldg[k]))
            else:
                assert k in new, f'missing new label {k}'
                pairs.append((new[k], newg[k]))
    assert len(pairs) == 30
    valid = [(o, g) for o, g in pairs if o['valid'] and g['valid']]
    a = [o['parsed']['match'] for o, g in valid]
    b = [g['parsed']['match'] for o, g in valid]
    agree = sum(x == y for x, y in zip(a, b)) / len(a)
    k = kappa(a, b); ci_a, ci_k = boot(a, b)
    out = {'n_traces': 15, 'n_outputs': 30, 'n_valid': len(a),
           'n_excluded': len(pairs) - len(a),
           'agreement': agree, 'agreement_ci': ci_a, 'kappa': k, 'kappa_ci': ci_k,
           'bar': {'agreement': 0.80, 'kappa': 0.60},
           'passes': agree >= .80 and k >= .60,
           'opus_sha256': sha((OLD / 'opus_labels.json').read_bytes()
                              + (OUT / 'opus_labels.json').read_bytes()),
           'sources': {'first_stage': str(OLD.relative_to(ROOT)),
                       'completion': str(OUT.relative_to(ROOT))},
           'counts': {'opus': {c: a.count(c) for c in ('yes', 'no', 'uncertain')},
                      'gemini': {c: b.count(c) for c in ('yes', 'no', 'uncertain')}},
           'note': 'combined 10-trace first stage + 5-trace completion; '
                   'three invalid-JSON Gemini outputs from the first stage are '
                   'excluded from the valid pairs'}
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