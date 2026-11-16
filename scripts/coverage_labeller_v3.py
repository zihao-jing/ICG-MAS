"""Coverage labeller v3: development on the Anchor labels, final held-out check.

The development population is the 90 E1 Anchor traces already used by the v1
validation; it is never reported as a validation result. The final population
is the 25 E1 Dev/Calibration items (`coverage_validation_v2.heldout`); the
rule and pass thresholds are frozen in
`rebuttal/pilots/20261113_coverage_labeller_v3/COVERAGE_VALIDATION_RULE_V3.md`
before that run. Cap $5 for the final run.

    ./run.sh python -m scripts.coverage_labeller_v3 --dev --cap-usd 5
    ./run.sh python -m scripts.coverage_labeller_v3 --pilot --cap-usd 5
    ./run.sh python -m scripts.coverage_labeller_v3 --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.coverage_rescore import parse_coverage, render
from scripts.coverage_validation import rows as dev_rows
from scripts.coverage_validation_v2 import heldout, kappa_ci
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import PRICE_IN, PRICE_OUT
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_coverage_labeller_v3'
PROMPT = OUT / 'coverage_prompt_v5.json'
RULE = OUT / 'COVERAGE_VALIDATION_RULE_V3.md'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
DEV = OUT / 'dev_results.json'
FINAL = OUT / 'results.json'
REPORT = OUT / 'report.md'
MAX_TOKENS = 2000
PASS_AGREE = 0.80
PASS_KAPPA = 0.60


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prompt_sha():
    return file_sha(PROMPT)


def call(key, spec, user, cap, total, phase):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'phase': phase, 'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'phase': phase,
                            'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'coverage_labeller_v3', 'key': key,
                               'phase': phase, 'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'phase': phase,
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def spent(phase=None):
    if not CALLS.exists():
        return 0.0
    total = 0.0
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get('event') not in ('result', 'skipped'):
            continue
        if phase and r.get('phase') != phase:
            continue
        total += r.get('cost_usd', 0.0)
    return total


def run(population, out_path, phase, cap):
    spec = json.loads(PROMPT.read_text())
    psha = prompt_sha()
    total = spent()
    done = {}
    if out_path.exists():
        done = {r['key']: r for r in json.loads(out_path.read_text())['items']}
    out = list(done.values())
    for r in population:
        key = f'{phase}/{r["item_id"]}/{psha[:8]}'
        if key in done:
            continue
        user, _ = render({'trace': r['trace'], 'question': r['trace']['question']})
        resp, total = call(key, spec, user, cap, total, phase)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse_coverage(resp.content)
        out.append({'key': key, 'item_id': r['item_id'], 'display': r['display'],
                    'prompt_sha': psha, 'success': resp.success,
                    'labeller': lab, 'authors': r['authors']})
        out_path.write_text(json.dumps({'items': out}, indent=1,
                                       ensure_ascii=False))
        print(json.dumps({'display': r['display'],
                          'prompt_complete': None if not lab else lab['complete'],
                          'author': [a['author_complete'] for a in r['authors']],
                          'spent_usd': round(total, 6)}), flush=True)
    out_path.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'traces': len(out), 'spent_usd': round(spent(phase), 8)},
                     indent=1))


def metrics(items):
    comps = [(bool(r['labeller']['complete']), bool(a['author_complete']))
             for r in items for a in r['authors']]
    k = sum(x == y for x, y in comps)
    agree = k / len(comps)
    lo, hi = cp_ci(k, len(comps))
    from scripts.coverage_validation_v2 import kappa_binary
    kap = kappa_binary(comps)
    klo, khi = kappa_ci(comps)
    return {'k': k, 'n': len(comps), 'agree': agree, 'lo': lo, 'hi': hi,
            'kappa': kap, 'klo': klo, 'khi': khi,
            'prompt_complete': sum(x for x, _ in comps),
            'author_complete': sum(y for _, y in comps), 'comps': comps}


def dev_report():
    """Recompute the development metrics for every prompt version in the log.

    Development results are not validation results; the Anchor labels were
    used to design v3-v5, so these numbers only document the iterations.
    """
    from scripts.coverage_validation_v2 import kappa_binary
    rows = {r['item_id']: r for r in dev_rows()}
    by = {}
    for l in CALLS.read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get('event') != 'result' or r.get('phase') != 'dev':
            continue
        pref = r['key'].rsplit('/', 1)[1]
        by.setdefault(pref, {})[r['key'].split('/')[1]] = r
    names = {}
    for v in (3, 4, 5):
        p = OUT / f'coverage_prompt_v{v}.json'
        names[file_sha(p)[:8]] = f'v{v}'
    out = {}
    for pref, items in by.items():
        comps, unparsed = [], 0
        for iid, r in items.items():
            lab = parse_coverage(r.get('content'))
            if lab is None:
                unparsed += 1
                continue
            for a in rows[iid]['authors']:
                comps.append((bool(lab['complete']),
                              bool(a['author_complete'])))
        k = sum(x == y for x, y in comps)
        n = len(comps)
        out[names.get(pref, pref)] = {
            'items': len(items), 'unparsed': unparsed, 'agree': k / n,
            'compare': f'{k}/{n}', 'kappa': kappa_binary(comps),
            'prompt_complete': sum(x for x, _ in comps),
            'author_complete': sum(y for _, y in comps)}
    print(json.dumps(out, indent=1))
    return out


def report():
    spec = json.loads(PROMPT.read_text())
    psha = prompt_sha()
    items = [r for r in json.loads(FINAL.read_text())['items']
             if r.get('prompt_sha') == psha and r.get('success')
             and r.get('labeller')]
    m = metrics(items)
    admitted = m['agree'] >= PASS_AGREE and m['kappa'] >= PASS_KAPPA
    lines = ['# Coverage labeller v3 — held-out validation\n',
             f"Rule `COVERAGE_VALIDATION_RULE_V3.md` (sha256 "
             f"`{file_sha(RULE)[:12]}`), prompt `coverage_prompt_v3.json` "
             f"(sha256 `{psha[:12]}`, system `{sha(spec['system'])[:12]}`). "
             f"{len(items)} traces, {m['n']} held-out author comparisons; "
             f"spend ${spent('heldout'):.6f}.\n",
             f"Agreement: **{m['k']}/{m['n']}** ({100*m['agree']:.1f}%, exact "
             f"Clopper-Pearson 95% CI {100*m['lo']:.1f}-{100*m['hi']:.1f}%); "
             f"Cohen kappa **{m['kappa']:.3f}** (bootstrap 95% CI "
             f"{m['klo']:.3f}-{m['khi']:.3f}).\n",
             f"Pass rule fixed before the run: agreement >= {PASS_AGREE:.2f} "
             f"**and** kappa >= {PASS_KAPPA:.2f}. Verdict: "
             f"**{'PASS' if admitted else 'FAIL'}**.\n",
             ('The v3 labeller is validated on held-out author labels. The '
              'lexical rule remains the paper\'s existing measure and is '
              'reported beside it.' if admitted else
              'The coverage labeller is **not validated**. The lexical rule '
              'remains the reported coverage figure, and no prompt edit '
              'follows this result.'),
             '', '| k | n | rate | 95% CI |', '| ---: | ---: | ---: | --- |',
             f"| {m['k']} | {m['n']} | {100*m['agree']:.1f}% | "
             f"{100*m['lo']:.1f}-{100*m['hi']:.1f}% |", '',
             f"Prompt complete: {m['prompt_complete']}/{m['n']}; author "
             f"complete: {m['author_complete']}/{m['n']}.\n",
             '## Per item\n', '| item | prompt | authors | agreement |',
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
              '| item | author | prompt | main claim: status (id) |',
              '| --- | ---: | ---: | --- |']
    for r in dis:
        p = bool(r['labeller']['complete'])
        stat = '; '.join(f"{s['id']}: {s['status']} — {s['reason']}"
                         for s in r['labeller']['supports'])
        for a in r['authors']:
            if p != bool(a['author_complete']):
                lines.append(f"| {r['display']} | {a['annotator']} "
                             f"({a['author_complete']}) | {p} | {stat} |")
    if not dis:
        lines.append('| none | | | |')
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': m['n'], 'agreement': m['agree'],
                      'kappa': m['kappa'], 'pass': admitted,
                      'spent_usd': spent('heldout')}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--dev-report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.dev:
        run(dev_rows(), DEV, 'dev', a.cap_usd)
    if a.pilot:
        man = json.loads(MANIFEST.read_text())
        assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
        assert file_sha(PROMPT) == man['prompt_file_sha256'], 'prompt changed'
        run(heldout(), FINAL, 'heldout', a.cap_usd)
    if a.report:
        report()
    if a.dev_report:
        dev_report()


if __name__ == '__main__':
    main()