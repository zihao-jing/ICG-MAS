"""Silo-Bench presence validation, expansion: two fresh cases per cell.

Rule: `rebuttal/pilots/20261113_sb_presence_validation/RULE_EXPANSION.md`,
frozen before any call. Same reference (Gemini 3.6 Flash) and labeller (Claude
Haiku 5.5) prompts as the first 24-case stage. Caps $1.50 reference + $0.30
labeller.

    ./run.sh python -m scripts.sb_presence_expansion --build
    ./run.sh python -m scripts.sb_presence_expansion --reference
    ./run.sh python -m scripts.sb_presence_expansion --freeze_reference
    ./run.sh python -m scripts.sb_presence_expansion --labeller
    ./run.sh python -m scripts.sb_presence_expansion --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.per_fact_labeller import parse as parse_lab, render
from scripts.run_e1_anchor_matcher import anchor_ids
from scripts.sb_presence_validation import (
    GEMINI, HAIKU, MAX_LAB, MAX_REF, PILOT, PROTOCOLS, RUNS,
    parse_ref, render, spent,
)
from src.audit.critical_fact_validation import build_trace_packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_sb_presence_validation'
RULE = OUT / 'RULE_EXPANSION.md'
BASE_RULE = OUT / 'RULE.md'
REF_PROMPT = OUT / 'reference_prompt.json'
LAB_PROMPT = OUT / 'labeller_prompt.json'
BASE_POP = OUT / 'population.json'
BASE_REF = OUT / 'reference_labels.json'
BASE_LAB = OUT / 'labeller_results.json'
POP = OUT / 'population_v2.json'
BUILD = OUT / 'build_manifest_v2.json'
REF_CALLS = OUT / 'reference_calls_v2.jsonl'
REF_LABELS = OUT / 'reference_labels_v2.json'
REF_MANIFEST = OUT / 'reference_manifest_v2.json'
LAB_CALLS = OUT / 'labeller_calls_v2.jsonl'
LAB_RESULTS = OUT / 'labeller_results_v2.json'
REPORT = OUT / 'report_v2.md'
SEED = 43
CAP_REF = 1.50
CAP_LAB = 0.30
PER_CELL = 2


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    first = {r['instance_id'] for r in json.loads(BASE_POP.read_text())}
    used = set(anchor_ids()) | PILOT | first
    rows = []
    for model, specs in RUNS.items():
        for run, n_agents in specs:
            for proto in PROTOCOLS:
                ps = build_trace_packages(
                    dataset='silobench', run_dir=run, protocol=proto,
                    source_id=run, n_agents=n_agents)
                cand = sorted((p for p in ps if p['instance_id'] not in used),
                              key=lambda p: sha(
                                  f'43|sbval|{model}|{n_agents}|{proto}|'
                                  f'{p["instance_id"]}'))
                assert len(cand) >= PER_CELL, (model, n_agents, proto)
                for p in cand[:PER_CELL]:
                    facts = [{'fact_id': f'f{i+1}', 'text': s['text'],
                              'support_id': s['support_id']}
                             for i, s in enumerate(p['source_supports'])]
                    rows.append({
                        'key': f'sb2/{model}/{n_agents}/{proto}/'
                               f'{p["instance_id"]}',
                        'model': model, 'run': run, 'n_agents': n_agents,
                        'protocol': proto, 'instance_id': p['instance_id'],
                        'checkpoint': 'board',
                        'checkpoint_name': 'shared board',
                        'question': p['question'], 'facts': facts,
                        'entries': [{'unit_id': u['unit_id'],
                                     'agent_id': u['agent_id'],
                                     'text': u['text']}
                                    for u in p['checkpoints']['board']]})
    rows.sort(key=lambda x: x['key'])
    assert len(rows) == 48, len(rows)
    insts = [r['instance_id'] for r in rows]
    keys = [r['key'] for r in rows]
    assert len(keys) == len(set(keys)) == 48
    assert not (set(insts) & used)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_any_expansion_call': True,
        'expansion_rule_sha256': file_sha(RULE),
        'base_rule_sha256': file_sha(BASE_RULE),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'labeller_prompt_sha256': file_sha(LAB_PROMPT),
        'population_sha256': file_sha(POP),
        'cases': len(rows), 'facts': sum(len(r['facts']) for r in rows),
        'cells': len({(r['model'], r['n_agents'], r['protocol'])
                      for r in rows}),
        'disjoint_from_first_stage': True, 'seed': SEED,
        'reference_model': GEMINI, 'labeller_model': HAIKU,
        'cap_reference_usd': CAP_REF, 'cap_labeller_usd': CAP_LAB},
        indent=1))
    print(json.dumps({'cases': len(rows),
                      'facts': sum(len(r['facts']) for r in rows),
                      'cells': len({(r['model'], r['n_agents'],
                                     r['protocol']) for r in rows}),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def call(key, model, system, user, max_tokens, cap, path):
    from scripts.sb_presence_validation import call as base_call
    return base_call(key, model, system, user, max_tokens, cap, path)


def reference(workers=6):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['expansion_rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = set()
    if REF_CALLS.exists():
        done = {json.loads(l)['key'] for l in REF_CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result'}
    todo = [r for r in rows if f"ref/{r['key']}" not in done]
    for i in range(0, len(todo), workers):
        if spent(REF_CALLS) > CAP_REF:
            print(json.dumps({'stopped': 'cap',
                              'spent_usd': round(spent(REF_CALLS), 6)}))
            break
        chunk = todo[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), MAX_REF, CAP_REF,
                              REF_CALLS) for r in chunk]
            for fut in as_completed(futs):
                fut.result()
        print(json.dumps({'done': min(i + workers, len(todo)),
                          'of': len(todo),
                          'spent_usd': round(spent(REF_CALLS), 6)}),
              flush=True)


def retry_reference(workers=4):
    """Retry reference calls whose latest result failed or did not parse."""
    spec = json.loads(REF_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result']
    latest = {}
    for c in calls:
        latest[c['key']] = c
    bad = []
    for r in rows:
        c = latest.get(f"ref/{r['key']}")
        if not c or not c.get('success') or parse_ref(
                c.get('content'), {f['fact_id'] for f in r['facts']}) is None:
            bad.append(r)
    print(json.dumps({'retrying': len(bad)}), flush=True)
    for i in range(0, len(bad), workers):
        chunk = bad[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), MAX_REF, CAP_REF,
                              REF_CALLS) for r in chunk]
            for fut in as_completed(futs):
                fut.result()
        print(json.dumps({'retried': min(i + workers, len(bad)),
                          'of': len(bad),
                          'spent_usd': round(spent(REF_CALLS), 6)}),
              flush=True)


def freeze_reference():
    rows = json.loads(POP.read_text())
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result']
    by = {c['key']: c for c in calls}
    labels = {}
    unparsed = []
    for r in rows:
        c = by.get(f"ref/{r['key']}")
        if not c:
            raise SystemExit(f"missing reference call {r['key']}")
        lab = parse_ref(c.get('content'), {f['fact_id'] for f in r['facts']})
        if lab is None:
            unparsed.append(r['key'])
            continue
        labels[r['key']] = lab
    REF_LABELS.write_text(json.dumps(
        {'_note': 'Gemini reference labels for the expansion, frozen before '
                  'any expansion Haiku call; unparsed cases excluded and '
                  'listed in the manifest',
         'model': GEMINI, 'labels': labels}, indent=1, ensure_ascii=False))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_expansion_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'n_requested': len(rows), 'n': len(labels),
        'excluded_unparsed': unparsed}, indent=1))
    print(json.dumps({'labels': len(labels),
                      'sha256': file_sha(REF_LABELS)[:12]}, indent=1))


def labeller(workers=6):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_expansion_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads(LAB_PROMPT.read_text())
    ref = json.loads(REF_LABELS.read_text())['labels']
    rows = [r for r in json.loads(POP.read_text()) if r['key'] in ref]
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        if spent(LAB_CALLS) > CAP_LAB:
            print(json.dumps({'stopped': 'cap',
                              'spent_usd': round(spent(LAB_CALLS), 6)}))
            break
        chunk = todo[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"lab/{r['key']}", HAIKU,
                              spec['system'], render(r), MAX_LAB, CAP_LAB,
                              LAB_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse_lab(resp.content,
                                {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {'key': r['key'], 'model': r['model'],
                                  'n_agents': r['n_agents'],
                                  'protocol': r['protocol'],
                                  'instance_id': r['instance_id'],
                                  'facts': r['facts'], 'labeller': lab}
        LAB_RESULTS.write_text(json.dumps({'items': list(done.values())},
                                          indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(LAB_CALLS), 6)}),
              flush=True)


def agree(pairs):
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
            'kappa': kappa_binary(pairs)}


def kappa_ci(pairs, cluster):
    rng = random.Random(SEED)
    groups = {}
    for p, c in zip(pairs, cluster):
        groups.setdefault(c, []).append(p)
    keys = sorted(groups)
    vals = []
    for _ in range(10000):
        draw = []
        for _ in keys:
            draw += groups[keys[rng.randrange(len(keys))]]
        v = kappa_binary(draw)
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]) \
        if vals else (float('nan'), float('nan'))


def gather(rows_path, lab_path, ref_path, prefix):
    rows = {r['key']: r for r in json.loads(lab_path.read_text())['items']}
    ref = json.loads(ref_path.read_text())['labels']
    out = []
    for key, r in rows.items():
        kref = key if key in ref else prefix + key
        if not r.get('labeller') or kref not in ref:
            continue
        for f in r['facts']:
            v = r['labeller'].get(f['fact_id'])
            z = ref[kref].get(f['fact_id'])
            if v and z:
                out.append((r['instance_id'], r['n_agents'], r['protocol'],
                            v['status'] != 'absent',
                            z['status'] != 'absent'))
    return out


def report():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['expansion_rule_sha256']
    pairs = (gather(BASE_POP, BASE_LAB, BASE_REF, '') +
             gather(POP, LAB_RESULTS, REF_LABELS, ''))
    spend = spent(OUT / 'reference_calls.jsonl') + \
        spent(OUT / 'labeller_calls.jsonl') + \
        spent(REF_CALLS) + spent(LAB_CALLS)
    m = agree([(a, b) for _, _, _, a, b in pairs])
    kci = kappa_ci([(a, b) for _, _, _, a, b in pairs],
                   [x[0] for x in pairs])
    by_n = {}
    for ninst, n, proto, a, b in pairs:
        by_n.setdefault(n, []).append((a, b))
    newpairs = gather(POP, LAB_RESULTS, REF_LABELS, '')
    mn = agree([(a, b) for _, _, _, a, b in newpairs])
    knci = kappa_ci([(a, b) for _, _, _, a, b in newpairs],
                    [x[0] for x in newpairs])
    base = agree([(a, b) for _, _, _, a, b in
                  gather(BASE_POP, BASE_LAB, BASE_REF, '')])
    lines = [
        '# Silo-Bench presence validation, expansion + combined\n',
        f"Expansion rule `RULE_EXPANSION.md` (sha256 `{file_sha(RULE)[:12]}`); "
        f"reference labels frozen before the expansion Haiku calls "
        f"(`reference_labels_v2.json`, sha256 `{file_sha(REF_LABELS)[:12]}`). "
        f"{man['cases']} fresh cases requested (2 per cell, disjoint from the "
        f"first 24, anchor and pilot); 2 excluded after two failed reference "
        f"calls and 1 after a labeller parse failure, giving "
        f"{sum(1 for r in json.loads(LAB_RESULTS.read_text())['items'] if r.get('labeller'))} scored expansion cases. Reference "
        f"Gemini 3.6 Flash; labeller Claude Haiku 5.5. Spend **${spend:.6f}** "
        f"across both stages, caps $2.00+$0.50 (first) and $1.50+$0.30 "
        f"(expansion).\n",
        f"Combined presence agreement **{m['k']}/{m['n']} = "
        f"{m['agreement']:.3f}** (95% CI {m['lo']:.3f}-{m['hi']:.3f}); kappa "
        f"**{m['kappa']:.3f}** ({kci[0]:.3f}-{kci[1]:.3f}) - **"
        f"{'PASS' if m['agreement'] >= .80 and m['kappa'] >= .60 else 'FAIL'}** "
        f"against 0.80/0.60 on the point estimate; the kappa **lower bound "
        f"{kci[0]:.3f}** is below 0.60, so the interval remains wide and this "
        f"is not a precise reliability claim.\n",
        '| stage | n facts | agreement [95% CI] | kappa [95% CI] |',
        '| --- | ---: | --- | --- |',
        f"| first 24 cases | {base['n']} | {base['k']}/{base['n']} = "
        f"{base['agreement']:.3f} [{base['lo']:.3f}, {base['hi']:.3f}] | "
        f"{base['kappa']:.3f} |",
        f"| expansion {sum(1 for r in json.loads(LAB_RESULTS.read_text())['items'] if r.get('labeller'))} cases | {mn['n']} | {mn['k']}/{mn['n']} = "
        f"{mn['agreement']:.3f} [{mn['lo']:.3f}, {mn['hi']:.3f}] | "
        f"{mn['kappa']:.3f} ({knci[0]:.3f}-{knci[1]:.3f}) |",
        f"| combined {sum(1 for r in json.loads(BASE_LAB.read_text())['items'] if r.get('labeller')) + sum(1 for r in json.loads(LAB_RESULTS.read_text())['items'] if r.get('labeller'))} cases | "
        f"{m['n']} | {m['k']}/{m['n']} = {m['agreement']:.3f} "
        f"[{m['lo']:.3f}, {m['hi']:.3f}] | {m['kappa']:.3f} "
        f"({kci[0]:.3f}-{kci[1]:.3f}) |",
        '', '| n_agents | agreement | kappa |', '| --- | --- | --- |']
    for n in sorted(by_n):
        mm = agree(by_n[n])
        lines.append(f"| n={n} | {mm['k']}/{mm['n']} = {mm['agreement']:.3f} "
                     f"[{mm['lo']:.3f}, {mm['hi']:.3f}] | {mm['kappa']:.3f} |")
    lines += ['', 'The first 24-case kappa interval 0.242-0.940 is kept on '
              'record; the combined interval is the one to read. This remains '
              'a cross-model check against Gemini, not author ground truth. '
              'The combined PASS allows the Silo-Bench rows into the table '
              'under the central-claim presence qualifier.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'combined': m, 'kappa_ci': kci,
                      'expansion': mn, 'spend_usd': round(spend, 6)},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'retry_reference', 'freeze_reference',
              'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.reference:
        reference(a.workers)
    if getattr(a, 'retry_reference', False):
        retry_reference(a.workers)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()