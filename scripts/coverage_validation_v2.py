"""Validate the revised coverage prompt on held-out author labels.

Rule: `rebuttal/pilots/20261113_coverage_validation_v2/COVERAGE_VALIDATION_RULE_V2.md`,
frozen before any call. Cap $5; every call logged.

    ./run.sh python -m scripts.coverage_validation_v2 --build
    ./run.sh python -m scripts.coverage_validation_v2 --pilot --cap-usd 5
    ./run.sh python -m scripts.coverage_validation_v2 --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_rescore import parse_coverage, render
from scripts.coverage_validation import author_complete, load_returns
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_coverage_validation_v2'
RULE = OUT / 'COVERAGE_VALIDATION_RULE_V2.md'
PROMPT = OUT / 'coverage_prompt_v2.json'
SETA = ROOT / 'rebuttal/pilots/20261112_labeller/validation_150.jsonl'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
MAX_TOKENS = 2000
PASS_AGREE = 0.80
PASS_KAPPA = 0.60


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validation_ids():
    return {r['item_id'] for r in
            (json.loads(l) for l in SETA.read_text().splitlines() if l.strip())
            if r['task'] == 'E1'}


def heldout():
    ret = load_returns()
    seen = validation_ids()
    out = []
    for item_id, anns in ret.items():
        if item_id in seen:
            continue
        first = next(iter(anns.values()))
        out.append({
            'item_id': item_id, 'display': first['display_name'],
            'trace': first['trace'],
            'authors': [{'annotator': a, 'author_complete': author_complete(x)}
                        for a, x in sorted(anns.items())],
        })
    out.sort(key=lambda r: r['display'])
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
                            'model': spec['model'],
                            'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'coverage_validation_v2', 'key': key,
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
    rs = heldout()
    spec = json.loads(PROMPT.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_file_sha256': file_sha(PROMPT),
        'prompt_system_sha256': sha(spec['system']),
        'excluded_set_sha256': file_sha(SETA),
        'traces': len(rs),
        'author_comparisons': sum(len(r['authors']) for r in rs),
        'author_complete': sum(a['author_complete'] for r in rs
                               for a in r['authors']),
        'pass_agreement': PASS_AGREE, 'pass_kappa': PASS_KAPPA,
        'model': spec['model'], 'temperature': 0, 'max_tokens': MAX_TOKENS,
    }, indent=1))
    print(json.dumps({'traces': len(rs),
                      'comparisons': sum(len(r['authors']) for r in rs),
                      'author_complete': sum(a['author_complete'] for r in rs
                                             for a in r['authors']),
                      'displays': [r['display'] for r in rs]}, indent=1))


def pilot(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(PROMPT) == man['prompt_file_sha256']
    assert file_sha(SETA) == man['excluded_set_sha256']
    spec = json.loads(PROMPT.read_text())
    rs = heldout()
    assert len(rs) == man['traces']
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    out = []
    for r in rs:
        key = 'heldout/' + r['item_id']
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


def kappa_ci(pairs):
    """Nonparametric bootstrap over comparisons, seed 43, 10000 draws."""
    import random
    rng = random.Random(43)
    vals = []
    n = len(pairs)
    for _ in range(10000):
        vals.append(kappa_binary([pairs[rng.randrange(n)] for _ in range(n)]))
    vals.sort()
    return vals[250], vals[9750]


def report():
    items = [r for r in json.loads(RESULTS.read_text())['items']
             if r.get('success') and r.get('labeller')]
    total = spent()
    comps = [(bool(r['labeller']['complete']), bool(a['author_complete']))
             for r in items for a in r['authors']]
    k = sum(x == y for x, y in comps)
    agree = k / len(comps)
    lo, hi = cp_ci(k, len(comps))
    kap = kappa_binary(comps)
    klo, khi = kappa_ci(comps)
    admitted = agree >= PASS_AGREE and kap >= PASS_KAPPA
    lines = ['# Coverage prompt v2 — held-out validation\n',
             f"Rule `COVERAGE_VALIDATION_RULE_V2.md` (sha256 "
             f"`{file_sha(RULE)[:12]}`), prompt `coverage_prompt_v2.json` "
             f"(sha256 `{file_sha(PROMPT)[:12]}`). {len(items)} traces, "
             f"{len(comps)} held-out author comparisons; spend ${total:.6f}.\n",
             f"Agreement: **{k}/{len(comps)}** ({100*agree:.1f}%, exact "
             f"Clopper-Pearson 95% CI {100*lo:.1f}-{100*hi:.1f}%); Cohen kappa "
             f"**{kap:.3f}** (bootstrap 95% CI {klo:.3f}-{khi:.3f}).\n",
             f"Pass rule fixed before the run: agreement >= "
             f"{PASS_AGREE:.2f} **and** kappa >= {PASS_KAPPA:.2f}. Verdict: "
             f"**{'PASS' if admitted else 'FAIL'}**.\n",
             ('The v2 labeller is validated on held-out author labels; the '
              'lexical figure stays beside it as the paper\'s existing '
              'measure.' if admitted else
              'The coverage labeller is **not validated**. The lexical rule '
              'remains the reported coverage figure, and no prompt edit '
              'follows this result.'),
             '', '| k | n | rate | 95% CI |', '| ---: | ---: | ---: | --- |',
             f'| {k} | {len(comps)} | {100*agree:.1f}% | '
             f'{100*lo:.1f}-{100*hi:.1f}% |', '',
             'Prompt complete: %d/%d; author complete: %d/%d.\n'
             % (sum(x for x, _ in comps), len(comps),
                sum(y for _, y in comps), len(comps)),
             '## Per item\n',
             '| item | prompt | authors | agreement |',
             '| --- | ---: | --- | ---: |']
    for r in items:
        p = bool(r['labeller']['complete'])
        au = [bool(a['author_complete']) for a in r['authors']]
        n_ok = sum(p == y for y in au)
        lines.append(f"| {r['display']} | {p} | {au} | {n_ok}/{len(au)} |")
    dis = [r for r in items if any(bool(r['labeller']['complete'])
                                   != bool(a['author_complete'])
                                   for a in r['authors'])]
    lines += ['', '## Disagreements\n',
              '| item | author | prompt | support statuses (id: status) |',
              '| --- | ---: | ---: | --- |']
    for r in dis:
        p = bool(r['labeller']['complete'])
        stat = '; '.join(f"{s['id']}: {s['status']}"
                         for s in r['labeller']['supports'])
        for a in r['authors']:
            if p != bool(a['author_complete']):
                lines.append(f"| {r['display']} | {a['annotator']} "
                             f"({a['author_complete']}) | {p} | {stat} |")
    if not dis:
        lines.append('| none | | | |')
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': len(comps), 'agreement': agree, 'kappa': kap,
                      'pass': admitted, 'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()