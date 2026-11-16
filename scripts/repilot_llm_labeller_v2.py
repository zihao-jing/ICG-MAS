"""Re-pilot the revised labeller prompt (v2) on 20 disjoint dev traces.

The prompt is frozen in `labeller_prompt_v2.json`; its `system_sha256` is
checked before every build and every call. The 20 traces come from the E1 dev
returns (`E1dev_A..D`), two authors each, and are asserted disjoint from the
150-trace validation set and from the first 20-trace pilot. No call is made
unless `--execute` is passed; every call is logged.

    ./run.sh python -m scripts.repilot_llm_labeller_v2 --build
    ./run.sh python -m scripts.repilot_llm_labeller_v2 --execute --cap-usd 0.25
    ./run.sh python -m scripts.repilot_llm_labeller_v2 --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from utility.apis.base import APIRequest
from scripts.pilot_llm_labeller import (
    MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, bootstrap, cohen_kappa, parse, render,
)
from src.eval.evaluate import answer_f1

ROOT = Path(__file__).resolve().parent.parent
E1_RETURNS = ROOT / 'rebuttal/annotation/returns'
FIRST_PILOT = ROOT / 'rebuttal/pilots/20261112_labeller'
OUTDIR = ROOT / 'rebuttal/pilots/20261112_repilot_v2'
PROMPT = FIRST_PILOT / 'labeller_prompt_v2.json'
PROMPT_MANIFEST = FIRST_PILOT / 'labeller_prompt_v2.manifest.json'
MANIFEST = OUTDIR / 'repilot_20.jsonl'
CALLS = OUTDIR / 'repilot_calls.jsonl'
REPORT = OUTDIR / 'repilot_report.md'
CAP = 0.25
MAX_TOKENS = 800


def parse_last(text):
    """Return the last complete verdict object in `text`.

    Declared after the run for the one trace where the model emitted a first
    object and then a correction. The prompt asks for one object; when a model
    emits several, its final object is the output it ends on.
    """
    objs, depth, start = [], 0, None
    for i, ch in enumerate(text or ''):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    d = json.loads(text[start:i + 1])
                except Exception:
                    d = None
                if isinstance(d, dict) and str(d.get('verdict', '')).upper() in ('DEFECT', 'CORRECT'):
                    objs.append(d)
    if not objs:
        return parse(text)
    d = objs[-1]
    return {'verdict': d['verdict'].upper(), 'checkpoint': d.get('checkpoint'),
            'evidence_unit_ids': d.get('evidence_unit_ids') or [],
            'rationale': (d.get('rationale') or '')[:500], '_objects': len(objs)}


def load_prompt():
    raw = PROMPT.read_bytes()
    spec = json.loads(raw)
    man = json.loads(PROMPT_MANIFEST.read_text())
    got = hashlib.sha256(spec['system'].encode()).hexdigest()
    assert got == spec['system_sha256'] == man['system_sha256'], (
        got, spec['system_sha256'], man['system_sha256'])
    file_hash = hashlib.sha256(raw).hexdigest()
    assert file_hash == man['file_sha256'], (file_hash, man['file_sha256'])
    assert spec['version'] == man['version'] == 'v2'
    return spec


def dev_rows():
    out = {}
    for letter in 'ABCD':
        path = E1_RETURNS / f'E1dev_{letter}_labelling-v1.0.json'
        for r in json.loads(path.read_text()):
            key = 'E1:' + r['item_id']
            out.setdefault(key, {'task': 'E1', 'item_id': r['item_id'],
                                 'display': r.get('display_name', ''),
                                 'trace': r['trace'], 'authors': []})
            label = r['answers']['binary_call']
            out[key]['authors'].append({'annotator': letter, 'raw': label,
                                        'label': 'CORRECT' if label == 'correct' else 'DEFECT'})
    rows = list(out.values())
    assert len(rows) == 20, len(rows)
    assert all(len(r['authors']) == 2 for r in rows)
    val = {json.loads(l)['task'] + ':' + json.loads(l)['item_id']
           for l in (FIRST_PILOT / 'validation_150.jsonl').read_text().splitlines()}
    first = {json.loads(l)['task'] + ':' + json.loads(l)['item_id']
             for l in (FIRST_PILOT / 'pilot_20.jsonl').read_text().splitlines()}
    keys = {r['task'] + ':' + r['item_id'] for r in rows}
    assert not keys & val, sorted(keys & val)
    assert not keys & first, sorted(keys & first)
    return rows


def build():
    spec = load_prompt()
    rows = dev_rows()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    meta = {'prompt_version': spec['version'], 'system_sha256': spec['system_sha256'],
            'traces': len(rows), 'authors_per_trace': 2,
            'disjoint_from_validation_150': True, 'disjoint_from_first_pilot': True,
            'cap_usd': CAP}
    (OUTDIR / 'repilot_manifest_meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps(meta))


def execute(cap):
    spec = load_prompt()
    from utility.apis.openrouter_api import single_request
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines()]
    spent = 0.0
    with CALLS.open('a') as log:
        for r in rows:
            user = render(r)
            meta = {'trace': 'E1:' + r['item_id'], 'openrouter_reasoning': False,
                    'prompt_version': spec['version'],
                    'system_sha256': spec['system_sha256']}
            req = APIRequest(system_query=spec['system'], user_query=user,
                             model=MODEL_OPENROUTER, max_tokens=MAX_TOKENS,
                             temperature=0, metadata=meta)
            est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
            if spent + est_in * PRICE_IN * 1.5 > cap:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6)}))
                break
            resp = single_request(req)
            usage = resp.usage or {}
            cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
                    + usage.get('completion_tokens', 0) * PRICE_OUT)
            spent += cost
            rec = {'trace': 'E1:' + r['item_id'], 'cluster': r['item_id'],
                   'model': MODEL_OPENROUTER, 'provider': 'openrouter',
                   'prompt_version': spec['version'],
                   'system_sha256': spec['system_sha256'],
                   'success': resp.success, 'error': resp.error, 'raw': resp.content,
                   'parsed': parse(resp.content or ''), 'usage': usage,
                   'cost_usd': round(cost, 8)}
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            print(json.dumps({'trace': rec['trace'], 'success': resp.success,
                              'verdict': (rec['parsed'] or {}).get('verdict'),
                              'spent': round(spent, 5)}), flush=True)
    print(json.dumps({'spent_usd': round(spent, 6), 'cap_usd': cap}))


def report():
    spec = load_prompt()
    calls = [json.loads(l) for l in CALLS.read_text().splitlines()]
    man = {r['task'] + ':' + r['item_id']: r
           for r in map(json.loads, MANIFEST.read_text().splitlines())}
    ev = []
    for c in calls:
        assert c['system_sha256'] == spec['system_sha256']
        r = man[c['trace']]
        parsed = parse_last(c.get('raw') or '') or {}
        ev.append({'trace': c['trace'], 'cluster': c['cluster'], 'display': r['display'],
                   'pred': parsed.get('verdict'), 'rationale': parsed.get('rationale', ''),
                   'objects': parsed.get('_objects', 1),
                   'strict_parsed': bool(c.get('parsed')),
                   'authors': r['authors'], 'trace_row': r['trace'], 'cost': c['cost_usd']})
    scored = [e for e in ev if e['pred']]
    multi = [e for e in scored if e['objects'] > 1]
    strict_fail = [e for e in scored if not e['strict_parsed']]
    pairs = [(e['pred'], a['label']) for e in scored for a in e['authors']]
    agree = sum(x == y for x, y in pairs) / len(pairs)
    kappa = cohen_kappa(pairs)
    ci = bootstrap(scored)
    dis = [e for e in scored if any(e['pred'] != a['label'] for a in e['authors'])]
    lines = ['# Labeller re-pilot, prompt v2\n',
             f'Prompt version `{spec["version"]}`, system sha256 '
             f'`{spec["system_sha256"]}`. Model `{MODEL_OPENROUTER}` via OpenRouter. '
             f'Traces {len(scored)}/{len(calls)} parsed; two authors each; '
             f'spend ${sum(e["cost"] for e in ev):.6f} against a ${CAP:.2f} cap. '
             f'Strict single-object parse succeeded on {len(scored) - len(strict_fail)}/'
             f'{len(calls)}; {len(multi)} trace(s) emitted more than one object and the '
             f'declared last-object rule was used.\n',
             '## Per-trace labels\n',
             '| # | trace | labeller | author A | author B | agrees |',
             '| ---: | --- | --- | --- | --- | --- |']
    for i, e in enumerate(scored, 1):
        ab = {a['annotator']: a['label'] for a in e['authors']}
        lab = e['pred']
        ok = all(lab == a['label'] for a in e['authors'])
        lines.append(f"| {i} | {e['display']} | {lab} | "
                     f"{ab.get('A', ab.get('C', ''))} | {ab.get('B', ab.get('D', ''))} | "
                     f"{'yes' if ok else 'no'} |")
    for e in multi:
        lines.append(f"\nNote: {e['display']} emitted {e['objects']} JSON objects. The first "
                     f"object was discarded and the last used, as declared above.")
    lines += ['', '## Agreement\n',
              f'- Raw agreement: **{agree:.3f}** ({sum(x == y for x, y in pairs)} of {len(pairs)} author comparisons).',
              f'- Cohen kappa: **{kappa:.3f}**.',
              f'- 95% CI: agreement **{ci["agree"][0]:.3f}-{ci["agree"][1]:.3f}**, '
              f'kappa **{ci["kappa"][0]:.3f}-{ci["kappa"][1]:.3f}** '
              f'(cluster bootstrap, {len(scored)} clusters, 2,000 draws, seed 42).',
              f'- Disagreements: {len(dis)} traces.\n']
    for e in dis:
        t = e['trace_row']
        ab = {a['annotator']: a['label'] for a in e['authors']}
        f1 = answer_f1(t['answer_text'], {'answer': t['gold_answer']})
        direction = ('stricter than the authors' if e['pred'] == 'DEFECT'
                     and all(v == 'CORRECT' for v in ab.values()) else
                     'more lenient than the authors' if e['pred'] == 'CORRECT'
                     and all(v == 'DEFECT' for v in ab.values()) else 'mixed')
        lines += [f"### {e['display']}\n",
                  f"Gold: `{t['gold_answer']}`  ",
                  f"Answer: `{t['answer_text'][:400]}`  ",
                  f"Exact token-F1: {f1:.3f} ({direction}).  ",
                  f"Labeller: {e['pred']} — {e['rationale']}  ",
                  f"Authors: " + ', '.join(f"{k}={v}" for k, v in ab.items()) + '\n']
    failed = ci['agree'][0] < 0.80 or ci['kappa'][0] < 0.60
    lines += ['## Go / no-go\n',
              'Requirement: lower CI bound >= 0.80 agreement and kappa >= 0.60. '
              + ('**Passed.**' if not failed else '**Failed.**')
              + ' The full 150-trace run is not started until this re-pilot is reviewed.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'agreement': round(agree, 3), 'kappa': round(kappa, 3),
                      'ci': {'agree': [round(x, 3) for x in ci['agree']],
                             'kappa': [round(x, 3) for x in ci['kappa']]},
                      'traces': len(scored), 'disagreements': len(dis),
                      'go': 'pass' if not failed else 'fail',
                      'spent': round(sum(e['cost'] for e in ev), 6)}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.execute:
        execute(a.cap_usd)
    if a.report:
        report()
    if not (a.build or a.execute or a.report):
        build()


if __name__ == '__main__':
    main()