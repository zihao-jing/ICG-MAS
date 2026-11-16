"""E3 on Silo-Bench from the validated labels, relay protocols only. $0, no model calls.

Extraction checkpoint: point-level labels (prompt per_fact_points_prompt_v1, validated atom kappa .847) in
  rebuttal/pilots/20261115_sb_extraction_points_pool/results.jsonl (summary_exchange rows excluded).
Board checkpoint: per-fact presence labels (prompt labeller_prompt.json, validated kappa .653 on 515 facts) in
  rebuttal/pilots/20261113_sb_presence_full/results.json (checkpoint board; summary_exchange excluded).
    ./.conda-env/bin/python -m scripts.e3_sb_validated
Output: rebuttal/pilots/20261115_e3_sb_validated/{e3.json}
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261115_e3_sb_validated'
EXT = [P / '20261115_sb_extraction_points_pool/results.jsonl',   # 1,180 rows: 790 relay + 390 summary
       P / '20261115_sb_extraction_points_rule/results.jsonl']     # 380 earlier relay supports, reused at $0
BOARD = P / '20261113_sb_presence_full/results.json'
RELAY = {'random_relay', 'score_ranked_relay', 'redundancy_aware_relay'}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def ci_block(k, n):
    return {'k': k, 'n': n, 'rate': round(k / n, 3) if n else None, 'wilson95': wilson(k, n)}


def extraction():
    traces = {}
    rows_all = 0
    seen = set()
    for path in EXT:
        for l in path.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            rows_all += 1
            protocol = r.get('protocol') or r['key'].split('|')[3]
            if protocol not in RELAY:
                continue
            sid = (r['key'], r.get('support_idx'))
            assert sid not in seen, sid
            seen.add(sid)
            traces.setdefault(r['key'], []).append(r)
    supports = atoms = atoms_present = supports_present = invalid = 0
    for key, rows in traces.items():
        for r in rows:
            if not r.get('valid', True):
                invalid += 1
                continue
            st = list(r['statuses'].values())
            supports += 1
            atoms += len(st)
            atoms_present += sum(1 for s in st if s == 'present')
            supports_present += int(all(s == 'present' for s in st))
    return {'source': ['rebuttal/pilots/20261115_sb_extraction_points_pool/results.jsonl (relay rows)',
                       'rebuttal/pilots/20261115_sb_extraction_points_rule/results.jsonl (relay rows)'],
            'rows_in_file': rows_all, 'relay_traces': len(traces), 'relay_supports': supports,
            'invalid_rows_excluded': invalid,
            'support_present': ci_block(supports_present, supports),
            'atom_present': ci_block(atoms_present, atoms)}


def board(model=None):
    items = json.loads(BOARD.read_text())['items']
    per = {}
    for it in items:
        if it['checkpoint'] != 'board' or it['protocol'] not in RELAY:
            continue
        if model is not None and it['model'] != model:
            continue
        per.setdefault(it['key'], it)
    facts = present = partial = absent = missing = 0
    by_n = {}
    for key, it in per.items():
        lab = it.get('labeller') or {}
        for f in it.get('facts', []):
            facts += 1
            d = lab.get(f['fact_id'])
            st = d.get('status') if d else None
            if st is None:
                missing += 1
                continue
            present += int(st == 'present')
            partial += int(st == 'partial')
            absent += int(st == 'absent')
            b = by_n.setdefault(it['n_agents'], [0, 0])
            b[0] += int(st == 'present')
            b[1] += 1
    labelled = present + partial + absent
    return {'source': 'rebuttal/pilots/20261113_sb_presence_full/results.json (checkpoint board)',
            'models': sorted({it['model'] for it in items if it['checkpoint'] == 'board'} if model is None else [model]),
            'relay_board_traces': len(per), 'facts_listed': facts, 'facts_unlabelled': missing,
            'present': present, 'partial': partial, 'absent': absent,
            'fact_present': ci_block(present, labelled),
            'fact_present_by_n_agents': {str(k): ci_block(v[0], v[1]) for k, v in sorted(by_n.items())}}


def main():
    out = {'population': 'Silo-Bench relay protocols only (random, score-ranked, redundancy-aware); '
                         'summary exchange excluded at both checkpoints',
           'extraction': extraction(),
           'board_all_models': board(),
           'board_qwen235b_only': board('qwen235b')}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'e3.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
