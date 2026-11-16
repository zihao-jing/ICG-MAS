"""Prompt v3 at the Silo-Bench extraction pool: Gemini reference, Haiku labeller."""
import argparse
import json
import random
from pathlib import Path

from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_extraction_v5 import call, file_sha, parse_reference, sha
from scripts.per_fact_labeller import MAX_TOKENS, parse, render

ROOT = Path(__file__).resolve().parent.parent
V5 = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
OUT = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction_sb'
RULE = ROOT / 'rebuttal/pilots/prereg/Per-fact-extraction-sb.md'
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
N = 30
MAX_REF = 8192


def excluded():
    ex = set()
    for r in json.loads((ROOT / 'rebuttal/pilots/20261113_sb_presence_validation/population_v2.json').read_text()):
        ex.add(r['instance_id'])
    for l in (ROOT / 'rebuttal/results/batch1/E1/anchor_agreement_rows.jsonl').read_text().splitlines():
        c = json.loads(l)['cluster']
        if '_n' in c:
            ex.add(c)
    for l in (ROOT / 'rebuttal/annotation/E1/evaluation_sheet.jsonl').read_text().splitlines():
        r = json.loads(l)
        if '_n' in r['trace']['instance_id'] and r['split'] != 'held_out':
            ex.add(r['trace']['instance_id'])
    for l in (ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl').read_text().splitlines():
        r = json.loads(l)
        if r['dataset'] == 'silobench':
            ex.add(r['instance_id'])
    return ex


def build():
    from src.audit.critical_fact_validation import build_trace_packages
    runs = {('qwen235b', 5): 'run_qwen235b_n5', ('qwen235b', 10): 'run_qwen235b_n10',
            ('gpt4omini', 5): 'run_gpt4omini_n5', ('gpt4omini', 10): 'run_gpt4omini_n10',
            ('gemma31b', 5): 'run_gemma31b_n5', ('gemma31b', 10): 'run_gemma31b_n10'}
    ex = excluded()
    pool = []
    for (model, n), run in runs.items():
        for t in build_trace_packages(dataset='silobench', run_dir=f'results/{run}',
                                     protocol='score_ranked_relay', source_id=run,
                                     n_agents=n):
            if t['instance_id'] in ex:
                continue
            pool.append({'key': f'sb/{model}/{t["instance_id"]}',
                         'instance_id': t['instance_id'], 'model': model,
                         'run': run, 'n_agents': n, 'question': t['question'],
                         'facts': [{'fact_id': f'f{i+1}', 'text': s['text'],
                                    'support_id': s['support_id']}
                                   for i, s in enumerate(t['source_supports'])],
                         'checkpoint': 'extraction',
                         'checkpoint_name': 'extraction pool',
                         'entries': [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                                      'text': u['text']}
                                     for u in t['checkpoints']['extraction']]})
    pool.sort(key=lambda r: sha(f'43|extract-sb|{r["model"]}|{r["instance_id"]}'))
    rows = pool[:N]
    assert len(rows) == N, len(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True, 'rule_sha256': file_sha(RULE),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'reference_system_sha256': sha(json.loads(REF_PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP), 'reference_model': GEMINI,
        'labeller_model': HAIKU, 'n': len(rows), 'seed': SEED, 'cap_usd': 1.0}, indent=1))
    print(json.dumps({'n': len(rows), 'facts': sum(len(r['facts']) for r in rows)}))


def reference(cap):
    man = json.loads(BUILD.read_text())
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
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
    kinds = {}
    for key, r in rows.items():
        lab = r.get('labeller')
        if not lab:
            continue
        for f in r['facts']:
            rc = bool(ref[key].get(f['fact_id']))
            lc = lab.get(f['fact_id'], {}).get('status', 'absent') != 'absent'
            pairs.append((1 if rc else 0, 1 if lc else 0))
            fact_n += 1
            fact_ok += rc == lc
            if rc != lc:
                kinds[f'ref {rc} / lab {lc}'] = kinds.get(f'ref {rc} / lab {lc}', 0) + 1
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
    klo, khi = vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]
    spend = 0.0
    for p in (REF_CALLS, LAB_CALLS):
        if p.exists():
            spend += sum(json.loads(l).get('cost_usd', 0.0) for l in p.read_text().splitlines()
                         if l.strip() and json.loads(l).get('event') == 'result')
    verdict = 'PASS' if k / n >= .80 and kap >= .60 else 'FAIL'
    lines = ['# Prompt v3 at the Silo-Bench extraction pool', '',
             f"Rule `Per-fact-extraction-sb.md` (sha256 `{file_sha(RULE)[:12]}`); reference "
             f"labels `{file_sha(REF_LABELS)[:12]}`, frozen before the Haiku calls. "
             f"Gemini 3.6 Flash reference; Claude Haiku 5.5 prompt v3; {len(rows)} fresh "
             f"Silo-Bench traces, {n} facts. Spend ${spend:.6f}, cap $1.00.", '',
             f"**Per-fact presence agreement {fact_ok}/{n} = {fact_ok/n:.3f}** "
             f"(95% CI {lo:.3f}-{hi:.3f}); kappa **{kap:.3f}** ({klo:.3f}-{khi:.3f}) - "
             f"**{verdict}** against 0.80/0.60.", '',
             'Disagreements: ' + (', '.join(f'`{k}` x {v}' for k, v in sorted(kinds.items())) or 'none') + '.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n_facts': n, 'agreement': k / n, 'agreement_ci': [lo, hi],
                      'kappa': kap, 'kappa_ci': [klo, khi], 'passes': verdict == 'PASS',
                      'spend': round(spend, 6), 'disagreements': kinds}))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze-reference', 'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true')
    ap.add_argument('--cap-usd', type=float, default=1.0)
    a = ap.parse_args()
    if a.build: build()
    if a.reference: reference(a.cap_usd)
    if a.freeze_reference: freeze_reference()
    if a.labeller: labeller(a.cap_usd)
    if a.report: report()


if __name__ == '__main__':
    main()