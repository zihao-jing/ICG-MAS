"""Fixed prompt v4 at the Silo-Bench extraction pool, instance-cluster CIs."""
import argparse
import json
import random
from pathlib import Path

from scripts.coverage_validation import kappa_binary
from scripts.per_fact_extraction_v5 import call, file_sha, parse_reference, sha
from scripts.per_fact_labeller import MAX_TOKENS, parse, render

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction_sb_v2'
OLD = ROOT / 'rebuttal/pilots/20261114_per_fact_extraction_sb'
RULE = ROOT / 'rebuttal/pilots/prereg/Per-fact-extraction-sb-v2.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_prompt_v4.json'
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
    ex = {r['instance_id'] for r in json.loads((OLD / 'population.json').read_text())}
    for l in (ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl').read_text().splitlines():
        r = json.loads(l)
        if r['dataset'] == 'silobench':
            ex.add(r['instance_id'])
    for l in (ROOT / 'rebuttal/results/batch1/E1/anchor_agreement_rows.jsonl').read_text().splitlines():
        c = json.loads(l)['cluster']
        if '_n' in c:
            ex.add(c)
    return ex


def build():
    from src.audit.critical_fact_validation import build_trace_packages
    runs = {('qwen235b', 5): 'run_qwen235b_n5', ('qwen235b', 10): 'run_qwen235b_n10',
            ('gpt4omini', 5): 'run_gpt4omini_n5', ('gpt4omini', 10): 'run_gpt4omini_n10',
            ('gemma31b', 5): 'run_gemma31b_n5', ('gemma31b', 10): 'run_gemma31b_n10'}
    ex = excluded()
    pool, seen = [], set()
    for (model, n), run in runs.items():
        for t in build_trace_packages(dataset='silobench', run_dir=f'results/{run}',
                                     protocol='score_ranked_relay', source_id=run,
                                     n_agents=n):
            if t['instance_id'] in ex:
                continue
            seen.add(t['instance_id'])
            pool.append({'key': f"sbv2/{model}/{t['instance_id']}",
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
    pool.sort(key=lambda r: sha(f'43|extract-sb-v2|{r["model"]}|{r["instance_id"]}'))
    rows = pool[:N]
    assert len(rows) == N, len(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True, 'rule_sha256': file_sha(RULE),
        'labeller_prompt_sha256': file_sha(PROMPT),
        'labeller_system_sha256': sha(json.loads(PROMPT.read_text())['system']),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'reference_system_sha256': sha(json.loads(REF_PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP), 'reference_model': GEMINI,
        'labeller_model': HAIKU, 'n': len(rows), 'clusters': len({r['instance_id'] for r in rows}),
        'seed': SEED, 'cap_usd': 1.0}, indent=1))
    print(json.dumps({'n': len(rows), 'clusters': len({r['instance_id'] for r in rows}),
                      'facts': sum(len(r['facts']) for r in rows)}))


def reference(cap):
    man = json.loads(BUILD.read_text())
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done, total = set(), 0.0
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
    spec = json.loads(PROMPT.read_text())
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
    clusters, fact_n, fact_ok = {}, 0, 0
    for key, r in rows.items():
        lab = r.get('labeller')
        if not lab:
            continue
        pairs = []
        for f in r['facts']:
            rc = bool(ref[key].get(f['fact_id']))
            lc = lab.get(f['fact_id'], {}).get('status', 'absent') != 'absent'
            pairs.append((1 if rc else 0, 1 if lc else 0))
            fact_n += 1; fact_ok += rc == lc
        clusters.setdefault(r['instance_id'], []).extend(pairs)
    n = fact_n
    k = fact_ok
    kap = kappa_binary([p for v in clusters.values() for p in v])
    rng = random.Random(SEED)
    ids = sorted(clusters)
    ags, kaps = [], []
    for _ in range(10000):
        draw = [ids[rng.randrange(len(ids))] for _ in ids]
        pairs = [p for i in draw for p in clusters[i]]
        ags.append(sum(a == b for a, b in pairs) / len(pairs))
        kaps.append(kappa_binary(pairs))
    ags = sorted(v for v in ags if v == v); kaps = sorted(v for v in kaps if v == v)
    alo, ahi = ags[int(.025 * len(ags))], ags[int(.975 * len(ags)) - 1]
    klo, khi = kaps[int(.025 * len(kaps))], kaps[int(.975 * len(kaps)) - 1]
    spend = 0.0
    for p in (REF_CALLS, LAB_CALLS):
        if p.exists():
            spend += sum(json.loads(l).get('cost_usd', 0.0) for l in p.read_text().splitlines()
                         if l.strip() and json.loads(l).get('event') == 'result')
    verdict = 'PASS' if k / n >= .80 and kap >= .60 else 'FAIL'
    lines = ['# Prompt v4 at the Silo-Bench extraction pool', '',
             f"Rule `Per-fact-extraction-sb-v2.md` (sha256 `{file_sha(RULE)[:12]}`); "
             f"reference labels `{file_sha(REF_LABELS)[:12]}`, frozen before the Haiku calls. "
             f"Prompt v4 (system `47cd9e47…`). {len(rows)} fresh Silo-Bench traces, "
             f"{len(clusters)} instances, {n} facts. Spend ${spend:.6f}, cap $1.00.", '',
             f"**Per-fact presence agreement {k}/{n} = {k/n:.3f}** "
             f"(instance-cluster 95% CI {alo:.3f}-{ahi:.3f}); kappa **{kap:.3f}** "
             f"(cluster 95% CI {klo:.3f}-{khi:.3f}) - **{verdict}** against 0.80/0.60.",
             '', f"CIs resample the {len(clusters)} instances, not the {len(rows)} traces."]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n_facts': n, 'clusters': len(clusters), 'agreement': k / n,
                      'agreement_ci': [alo, ahi], 'kappa': kap, 'kappa_ci': [klo, khi],
                      'passes': verdict == 'PASS', 'spend': round(spend, 6)}))


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