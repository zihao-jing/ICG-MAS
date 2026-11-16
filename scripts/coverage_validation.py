"""Validate the coverage prompt against author carrier labels.

Rule: `rebuttal/pilots/20261113_coverage_validation/COVERAGE_VALIDATION_RULE.md`,
frozen before any call. Cap $1; every call logged.

    ./run.sh python -m scripts.coverage_validation --build
    ./run.sh python -m scripts.coverage_validation --pilot --cap-usd 1
    ./run.sh python -m scripts.coverage_validation --report
"""
import argparse
import glob
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_rescore import MAX_TOKENS, PROMPT, parse_coverage, render
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_coverage_validation'
RULE = OUT / 'COVERAGE_VALIDATION_RULE.md'
SETA = ROOT / 'rebuttal/pilots/20261112_labeller/validation_150.jsonl'
RETURNS = ROOT / 'rebuttal/annotation/labelling_20261108/returns/E1*.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_returns():
    out = {}
    for p in glob.glob(str(RETURNS)):
        for x in json.load(open(p)):
            out.setdefault(x['item_id'], {})[x['annotator_id']] = x
    return out


def author_complete(x):
    facts = json.loads(x['answers']['critical_facts_json'])
    cars = json.loads(x['answers']['carriers_json'])
    board = {c.get('fact_id'): c for c in cars if c.get('checkpoint') == 'board'}
    return all(board.get(f['fact_id'], {}).get('fidelity') == 'faithful'
               for f in facts)


def rows():
    ret = load_returns()
    out = []
    seen = set()
    for r in (json.loads(l) for l in SETA.read_text().splitlines() if l.strip()):
        if r['task'] != 'E1':
            continue
        got = ret.get(r['item_id'], {})
        auth = []
        for a in r['authors']:
            x = got.get(a['annotator'])
            if x is None:
                continue
            auth.append({'annotator': a['annotator'], 'author_label': a['label'],
                         'author_complete': author_complete(x)})
        if len(auth) != 2:
            continue
        out.append({'item_id': r['item_id'], 'display': r['display'],
                    'trace': r['trace'], 'authors': auth})
    return out


def call(key, spec, user, cap, total):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'coverage_validation', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def build():
    rs = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads(PROMPT.read_text())
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_file_sha256': file_sha(PROMPT),
        'prompt_system_sha256': sha(spec['system']),
        'set_sha256': file_sha(SETA),
        'traces': len(rs), 'author_comparisons': 2 * len(rs),
        'model': spec['model'], 'temperature': 0, 'max_tokens': MAX_TOKENS,
    }, indent=1))
    print(json.dumps({'traces': len(rs),
                      'author_complete': sum(a['author_complete'] for r in rs
                                             for a in r['authors']),
                      'comparisons': 2 * len(rs)}, indent=1))


def pilot(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(PROMPT) == man['prompt_file_sha256']
    assert file_sha(SETA) == man['set_sha256']
    spec = json.loads(PROMPT.read_text())
    rs = rows()
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    out = []
    for r in rs:
        key = 'val/' + r['item_id']
        if key in done:
            out.append(done[key])
            continue
        user, _ = render({'trace': r['trace'], 'question': r['trace']['question']})
        resp, total = call(key, spec, user, cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse_coverage(resp.content)
        out.append({'key': key, 'item_id': r['item_id'], 'display': r['display'],
                    'success': resp.success, 'labeller': lab,
                    'authors': r['authors']})
        RESULTS.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
        print(json.dumps({'display': r['display'],
                          'prompt_complete': None if not lab else lab['complete'],
                          'author': [a['author_complete'] for a in r['authors']],
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'traces': len(out), 'spent_usd': round(total, 8)}, indent=1))


def kappa_binary(pairs):
    n = len(pairs)
    if not n:
        return float('nan')
    a = sum(x == y for x, y in pairs) / n
    p1 = sum(x for x, _ in pairs) / n
    p2 = sum(y for _, y in pairs) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return (a - pe) / (1 - pe) if pe < 1 else float('nan')


def report():
    rows_ = [r for r in json.loads(RESULTS.read_text())['items']
             if r.get('success') and r.get('labeller')]
    total = spent()
    comps = [(bool(r['labeller']['complete']), bool(a['author_complete']))
             for r in rows_ for a in r['authors']]
    k = sum(x == y for x, y in comps)
    lo, hi = cp_ci(k, len(comps))
    agree = k / len(comps)
    kap = kappa_binary(comps)
    lines = ['# Coverage prompt validation against author labels\n',
             f"Rule `COVERAGE_VALIDATION_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), "
             f"prompt `coverage_prompt_v1.json` (sha256 `{file_sha(PROMPT)[:12]}`). "
             f"{len(rows_)} traces, {len(comps)} author comparisons; spend "
             f"${total:.6f}.\n",
             f"Agreement: **{k}/{len(comps)}** ({100*agree:.1f}%, exact "
             f"Clopper-Pearson 95% CI {100*lo:.1f}-{100*hi:.1f}%); Cohen kappa "
             f"**{kap:.3f}**. Prompt complete {sum(x for x,_ in comps)}/"
             f"{len(comps)}; author complete {sum(y for _,y in comps)}/"
             f"{len(comps)}.\n",
             '| # | trace | prompt | author A | author B |',
             '| --- | --- | ---: | ---: | ---: |']
    for i, r in enumerate(rows_, 1):
        a = {x['annotator']: x['author_complete'] for x in r['authors']}
        lines.append(f"| {i} | {r['display']} | {r['labeller']['complete']} | "
                     f"{a.get('A')} | {a.get('B')} |")
    lines += ['', '## Disagreements\n']
    for r in rows_:
        pc = bool(r['labeller']['complete'])
        for a in r['authors']:
            if pc != bool(a['author_complete']):
                reasons = '; '.join(f"{s['id']}:{s['status']} {s['reason'][:90]}"
                                    for s in r['labeller']['supports'])
                lines.append(f"- {r['display']} / author {a['annotator']}: prompt "
                             f"{pc}, author {a['author_complete']} ({a['author_label']}). "
                             f"{reasons}")
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'traces': len(rows_), 'agreement': agree, 'kappa': kap,
                      'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=1.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()