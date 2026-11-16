"""A1 balance export, before any outcome: matched/possible counts and the pair-level balance table.

Reads only frozen inputs: the frozen action/donor manifest (`20926a06…`), the local R-ext unit
reconstruction, the frozen case list and the trace packages. No repair, control or scoring outcome is
read and no model call is made. Pairs: extraction (reconstructed), selection and distortion (frozen
added tokens). Controls, partial and aggregation have no repair/volume-control pair.

    python -m scripts.export_e4_a1_balance
"""
import json
from pathlib import Path

from src.audit.base_tokenizers import count_added_tokens
from src.audit.e4_balance import balance
from src.audit.pilot_common import digest, freeze

from scripts.build_e4_manifest import BASE, COHORT
from scripts.build_final_author_packet import packages

MANIFEST = Path('rebuttal/results/batch1/E4_manifest/manifest.json')
RECON = Path('rebuttal/results/batch1/E4_manifest/rext_unit_reconstruction.json')
OUT = Path('rebuttal/results/batch1/E4_A1_balance')
GROUPS = ['extraction_omission', 'selection_omission', 'distortion']
BENCH = ['MQ', 'SB-5', 'SB-10']


def bench(x):
    return 'MuSiQue' if x == 'MQ' else 'Silo-Bench'


def main():
    man = json.loads(MANIFEST.read_text())
    rec = json.loads(RECON.read_text())
    assert rec['source_manifest_sha256'] == digest(MANIFEST.read_bytes())
    ids = {r['instance'] for r in man['cases'] if r.get('group') in GROUPS}
    pk = packages(ids)
    tok = {}
    for c in man['cases']:
        if c.get('group') not in GROUPS or c.get('matcher_status') != 'ok':
            continue
        p = pk[(c['model'], c['instance'])]
        raw = '\n'.join([p['question']] + [u['text'] for u in p['checkpoints']['extraction']]
                        + [u['text'] for u in p['checkpoints']['board']])
        tok[(c['instance'], c['model'])] = count_added_tokens(BASE[c['model']], raw)
    rows = []
    for r in rec['rows']:
        for cand in r['donor_possible']:
            rows.append({'instance_id': r['instance'], 'trace_id': digest([r['instance'], r['model'], 1]),
                         'failure_type': 'extraction_omission', 'benchmark': bench(r['benchmark']),
                         'protocol': r['benchmark'], 'base_model': BASE[r['model']],
                         'trace_tokens': tok[(r['instance'], r['model'])],
                         'repair_tokens': r['repair_tokens'], 'control_tokens': cand['control_tokens'],
                         'matched': bool(cand['matched'])})
    for c in man['cases']:
        if c.get('group') not in ('selection_omission', 'distortion') or c.get('matcher_status') != 'ok':
            continue
        rows.append({'instance_id': c['instance'], 'trace_id': digest([c['instance'], c['model'], 1]),
                     'failure_type': c['group'], 'benchmark': bench(c['benchmark']),
                     'protocol': c['benchmark'], 'base_model': BASE[c['model']],
                     'trace_tokens': tok[(c['instance'], c['model'])],
                     'repair_tokens': c['added_tokens']['repair'],
                     'control_tokens': c['added_tokens']['control'],
                     'matched': bool(c['matched'])})
    cells = []
    for g in GROUPS:
        for b in BENCH:
            pos = [r for r in rows if r['failure_type'] == g and r['protocol'] == b]
            mat = [r for r in pos if r['matched']]
            note = ''
            if len(mat) < 5:
                note = ('no same-volume control available' if not mat
                        else f'fewer than 5 matched pairs ({len(mat)}); descriptive only')
            cells.append({'failure_type': g, 'protocol': b, 'benchmark': bench(b),
                          'possible': len(pos), 'matched': len(mat),
                          'clusters': len({r['instance_id'] for r in mat}), 'note': note})
    out = {'experiment': 'E4 A1 balance', 'prereg': 'E4-v7.md',
           'prereg_sha256': digest(Path('rebuttal/pilots/prereg/E4-v7.md').read_bytes()),
           'manifest_sha256': digest(MANIFEST.read_bytes()),
           'reconstruction_sha256': digest(RECON.read_bytes()),
           'case_list_sha256': digest(COHORT.read_bytes()),
           'frozen_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
           .strftime('%Y-%m-%dT%H:%M:%SZ'),
           'outcomes_read': False,
           'pair_rows': rows, 'counts': cells, 'balance': balance(rows),
           'notes': ['Matched contrast uses matched pairs only; all pairs enter the all-case '
                     'volume-adjusted sensitivity once an outcome exists.',
                     'Distortion pairs await the author swap check; no distortion outcome is read.',
                     'SB cells with fewer than 5 matched pairs read "no same-volume control available".',
                     'Fewer than 10 matched clusters stays descriptive.']}
    freeze(OUT / 'A1_balance.json', out)
    md = ['# E4 A1 balance (before any outcome)', '',
          f"Frozen {out['frozen_utc']}. Manifest `{out['manifest_sha256'][:8]}…`, reconstruction "
          f"`{out['reconstruction_sha256'][:8]}…`. No outcome read; no model call.", '',
          '| Failure type | Protocol | Possible pairs | Matched pairs | Matched clusters | Note |',
          '|---|---|---:|---:|---:|---|']
    md += [f"| {c['failure_type']} | {c['protocol']} | {c['possible']} | {c['matched']} | {c['clusters']} | {c['note']} |"
           for c in cells]
    md += ['', '| Variable | Level | Matched n | Unmatched n | Matched median | Unmatched median | SMD |',
           '|---|---|---:|---:|---:|---:|---:|']
    md += [f"| {b['variable']} | {b['level']} | {b['matched_n']} | {b['unmatched_n']} | "
           f"{b['matched_median']} | {b['unmatched_median']} | "
           f"{(round(b['smd'], 3) if b['smd'] is not None else 'n/a')} |" for b in out['balance']]
    (OUT / 'A1_balance.md').write_text('\n'.join(md) + '\n')
    print(json.dumps({'frozen_utc': out['frozen_utc'], 'pair_rows': len(rows),
                      'cells': len(cells), 'matched': sum(r['matched'] for r in rows),
                      'sha256': digest((OUT / 'A1_balance.json').read_bytes())}, indent=1))


if __name__ == '__main__':
    main()