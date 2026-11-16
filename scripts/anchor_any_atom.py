"""Any-atom roll-up vs all-atom roll-up on the 80 anchor facts (no calls).

The A2 anchor run stored per-atom statuses in `calls.jsonl`. This re-scores the same labels
under two roll-up rules and compares each with the author's per-fact presence.
"""
import json
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.distortion_rescore_run import boot

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_anchor_points'
POP = OUT / 'population_aligned.json'
CALLS = OUT / 'calls.jsonl'
REPORT = OUT / 'any_atom_rule.md'


def labels():
    got = {}
    for line in CALLS.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get('event') != 'result' or not e.get('success'):
            continue
        key = e['key']
        if '/attempt-' in key:
            key = key.rsplit('/attempt-', 1)[0]
        obj = last_object(e.get('content') or '')
        if not isinstance(obj, dict) or not isinstance(obj.get('atoms'), dict):
            continue
        row = {}
        for aid, a in obj['atoms'].items():
            if isinstance(a, dict) and a.get('status') in ('present', 'partial', 'absent'):
                row[aid] = a['status']
        if row:
            got[key] = row
    return got


def score(rows, rule, tag):
    pairs = []
    cells = {}
    for r in rows:
        st = r['atoms']
        if not st:
            continue
        if rule == 'all_present':
            p = all(v == 'present' for v in st.values())
        elif rule == 'any_present':
            p = any(v == 'present' for v in st.values())
        else:
            p = any(v != 'absent' for v in st.values())
        a = bool(r['author_present'])
        pairs.append((a, p, r['instance_id']))
        cells[f'author_{a}_pred_{p}'] = cells.get(f'author_{a}_pred_{p}', 0) + 1
    aa, aci, ak, akci = boot(pairs)
    return {'rule': rule, 'model': tag, 'n': len(pairs), 'cells': cells,
            'agreement': aa, 'agreement_ci': list(aci), 'kappa': ak, 'kappa_ci': list(akci)}


def main():
    rows = json.loads(POP.read_text())
    all_lab = labels()
    lab = {k[len('labh/'):]: v for k, v in all_lab.items() if k.startswith('labh/')}
    ref = {k[len('refg/'):]: v for k, v in all_lab.items() if k.startswith('refg/')}
    rows_a = []
    for r in rows:
        fid = r['facts'][0]['fact_id']
        k = f"{r['key']}/{fid}"
        rows_a.append({'key': r['key'], 'instance_id': r['instance_id'],
                       'author_present': r['author_present'],
                       'atoms': lab.get(k, {}), 'ref_atoms': ref.get(k, {})})
    res = {}
    for tag, field in (('labeller_haiku', 'atoms'), ('reference_gemini', 'ref_atoms')):
        for rule in ('all_present', 'any_present', 'any_carried'):
            rows_in = [{'atoms': r[field], 'author_present': r['author_present'],
                        'instance_id': r['instance_id']} for r in rows_a]
            res[f'{tag}|{rule}'] = score(rows_in, rule, tag)
    (OUT / 'any_atom_results.json').write_text(json.dumps(res, indent=1))
    lines = [
        '# Anchor roll-up rules side by side (no calls)',
        '',
        '2026-11-15. Same 80 anchor facts, same per-atom labels from the A2 run (Haiku labeller, Gemini '
        'reference), board checkpoint. Author present = a non-absent board carrier. Three roll-ups: '
        'all atoms present (the A2 rule), any atom present, any atom carried (present or partial).',
        '',
        '| model | rule | n | agreement [95% CI] | kappa [95% CI] |',
        '| --- | --- | ---: | --- | --- |',
    ]
    for key in ('labeller_haiku|all_present', 'labeller_haiku|any_present', 'labeller_haiku|any_carried',
                'reference_gemini|all_present', 'reference_gemini|any_present',
                'reference_gemini|any_carried'):
        x = res[key]
        lines.append(f"| {x['model']} | {x['rule']} | {x['n']} | "
                     f"{x['agreement']:.3f} [{x['agreement_ci'][0]:.3f}, {x['agreement_ci'][1]:.3f}] | "
                     f"{x['kappa']:.3f} [{x['kappa_ci'][0]:.3f}, {x['kappa_ci'][1]:.3f}] |")
    lines += ['', 'Cells (author / predicted):', '']
    for key in ('labeller_haiku|all_present', 'labeller_haiku|any_carried',
                'reference_gemini|all_present', 'reference_gemini|any_carried'):
        x = res[key]
        lines.append(f"- {x['model']} / {x['rule']}: {x['cells']}")
    lines += ['',
              'Instance-cluster bootstrap, 2,000 draws, seed 43. Bars are not applied here: this is a '
              'zero-cost re-scoring of stored labels, not a new validation.',
              '', '## Ledger', 'Spend $0.000000.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()