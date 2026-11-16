"""Prompt v3 at the extraction pool: Gemini reference, then Haiku labeller.

    ./run.sh python -m scripts.per_fact_extraction_v5 --build
    ./run.sh python -m scripts.per_fact_extraction_v5 --reference --cap-usd 1
    ./run.sh python -m scripts.per_fact_extraction_v5 --freeze-reference
    ./run.sh python -m scripts.per_fact_extraction_v5 --labeller --cap-usd 1
    ./run.sh python -m scripts.per_fact_extraction_v5 --report
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.per_fact_labeller import MAX_TOKENS, parse, render
from scripts.per_fact_v5 import call, file_sha, parse_reference, sha
from scripts.run_expansion_stage2 import MODELS, packages

ROOT = Path(__file__).resolve().parent.parent
V5 = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
OUT = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction'
RULE = ROOT / 'rebuttal/pilots/prereg/Per-fact-extraction-v5.md'
REF_PROMPT = ROOT / 'rebuttal/pilots/prereg/extraction_reference_prompt.json'
POP = OUT / 'population.json'
BUILD = OUT / 'build_manifest.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
REF_LABELS = OUT / 'reference_labels.json'
REF_MANIFEST = OUT / 'reference_manifest.json'
LAB_CALLS = OUT / 'labeller_calls.jsonl'
LAB_RESULTS = OUT / 'labeller_results.json'
REPORT = OUT / 'report.md'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
SEED = 43
MAX_REF = 8192


def build():
    rows = json.loads((V5 / 'population_v5.json').read_text())
    pk = {m: packages(m) for m in MODELS}
    out = []
    for r in rows:
        t = pk[r['model']][r['instance_id']]
        out.append({'key': r['key'], 'instance_id': r['instance_id'],
                    'model': r['model'], 'question': t['question'],
                    'facts': r['facts'], 'checkpoint': 'extraction',
                    'checkpoint_name': 'extraction pool',
                    'entries': [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                                 'text': u['text']}
                                for u in t['checkpoints']['extraction']]})
    assert len(out) == 60, len(out)
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True,
        'rule_sha256': file_sha(RULE),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'reference_system_sha256': sha(json.loads(REF_PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP),
        'reference_model': GEMINI, 'labeller_model': HAIKU,
        'n': len(out), 'seed': SEED, 'cap_usd': 1.0}, indent=1))
    print(json.dumps({'n': len(out)}))


def reference(cap):
    man = json.loads(BUILD.read_text())
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
    assert sha(spec['system']) == man['reference_system_sha256']
    rows = json.loads(POP.read_text())
    done = set()
    total = 0.0
    if REF_CALLS.exists():
        total = sum(json.loads(l).get('cost_usd', 0.0) for l in REF_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
        done = {json.loads(l)['key'] for l in REF_CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result'}
    for r in rows:
        if f"ref/{r['key']}" in done:
            continue
        resp, total = call(f"ref/{r['key']}", GEMINI, spec['system'], render(r),
                           MAX_REF, cap, total, REF_CALLS)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)})); break
        print(json.dumps({'key': r['key'], 'success': resp.success,
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(total, 6)}))


def freeze_reference():
    rows = json.loads(POP.read_text())
    calls = {json.loads(l)['key']: json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result'}
    labels = {}
    for r in rows:
        c = calls.get(f"ref/{r['key']}")
        if not c:
            raise SystemExit(f"missing {r['key']}")
        lab = parse_reference(c.get('content'), {f['fact_id'] for f in r['facts']})
        if lab is None:
            raise SystemExit(f"unparsed {r['key']}")
        labels[r['key']] = lab
    REF_LABELS.write_text(json.dumps({'model': GEMINI, 'labels': labels}, indent=1))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS), 'n': len(labels)}, indent=1))
    print(json.dumps({'labels': len(labels), 'sha256': file_sha(REF_LABELS)[:12]}))


def labeller(cap):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads((V5 / 'per_fact_prompt_v3.json').read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in json.loads(LAB_RESULTS.read_text())['items'] if r.get('labeller')}
    out = list(done.values())
    total = 0.0
    if LAB_CALLS.exists():
        total = sum(json.loads(l).get('cost_usd', 0.0) for l in LAB_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
    for r in rows:
        if r['key'] in done:
            continue
        resp, total = call(f"lab/{r['key']}", HAIKU, spec['system'], render(r),
                           MAX_TOKENS, cap, total, LAB_CALLS)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)})); break
        lab = parse(resp.content, {f['fact_id'] for f in r['facts']}) if resp.success else None
        out.append({'key': r['key'], 'instance_id': r['instance_id'], 'model': r['model'],
                    'facts': r['facts'], 'labeller': lab, 'success': resp.success,
                    'error': resp.error})
        LAB_RESULTS.write_text(json.dumps({'items': out}, indent=1, ensure_ascii=False))
        print(json.dumps({'key': r['key'], 'valid': lab is not None,
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'rows': len(rows), 'spent': round(total, 6)}))


def report():
    rows = {r['key']: r for r in json.loads(LAB_RESULTS.read_text())['items']}
    ref = json.loads(REF_LABELS.read_text())['labels']
    pairs, fact_n, fact_ok = [], 0, 0
    complete_ref = complete_lab = 0
    kinds = {}
    for key, r in rows.items():
        lab = r.get('labeller')
        if not lab:
            continue
        ok_ref = all(bool(v) for v in ref[key].values())
        ok_lab = True
        for f in r['facts']:
            fid = f['fact_id']
            rc = bool(ref[key].get(fid))
            lc = lab.get(fid, {}).get('status', 'absent') != 'absent'
            pairs.append((1 if rc else 0, 1 if lc else 0))
            fact_n += 1
            fact_ok += rc == lc
            if rc != lc:
                kinds[f'ref {rc} / lab {lc}'] = kinds.get(f'ref {rc} / lab {lc}', 0) + 1
            ok_lab = ok_lab and rc and lc
        complete_ref += ok_ref
        complete_lab += ok_lab
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    kap = kappa_binary(pairs)
    rng = random.Random(SEED)
    vals = []
    for _ in range(10000):
        draw = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(kappa_binary(draw))
    vals = sorted(v for v in vals if v == v)
    klo, khi = (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1])
    spend = 0.0
    for p in (REF_CALLS, LAB_CALLS):
        if p.exists():
            spend += sum(json.loads(l).get('cost_usd', 0.0) for l in p.read_text().splitlines()
                         if l.strip() and json.loads(l).get('event') == 'result')
    verdict = 'PASS' if k / n >= .80 and kap >= .60 else 'FAIL'
    lines = ['# Prompt v3 at extraction: independent-reference validation', '',
             f"Rule `Per-fact-extraction-v5.md` (sha256 `{file_sha(RULE)[:12]}`); "
             f"reference labels sha256 `{file_sha(REF_LABELS)[:12]}`, frozen before "
             f"the Haiku calls. Gemini 3.6 Flash reference; Claude Haiku 5.5, prompt v3; "
             f"60 frozen MuSiQue traces, extraction pool. Spend ${spend:.6f}, cap $1.00.",
             '',
             f"**Per-fact presence agreement {fact_ok}/{n} = {fact_ok/n:.3f}** "
             f"(95% CI {lo:.3f}-{hi:.3f}); kappa **{kap:.3f}** "
             f"({klo:.3f}-{khi:.3f}) - **{verdict}** against 0.80/0.60.",
             '',
             f"Trace-level complete agreement "
             f"{complete_ref}/{len(rows)} reference, {complete_lab}/{len(rows)} labeller; "
             f"not the pass criterion (degenerate at n=60). Disagreement counts: "
             + (', '.join(f'`{k}` x {v}' for k, v in sorted(kinds.items())) or 'none') + '.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n_facts': n, 'agreement': k / n, 'agreement_ci': [lo, hi],
                      'kappa': kap, 'kappa_ci': [klo, khi], 'passes': verdict == 'PASS',
                      'spend': round(spend, 6), 'complete_ref': complete_ref,
                      'complete_lab': complete_lab}))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze-reference', 'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true')
    ap.add_argument('--cap-usd', type=float, default=1.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.reference:
        reference(a.cap_usd)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()