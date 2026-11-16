"""E3 on Silo-Bench routes from the validated labels, relay protocols, qwen235b. $0, no model calls.

Extraction (per fact): point-level labels rolled up by the frozen roll-up (present iff all atoms present, partial iff some,
absent iff none), rows in rebuttal/pilots/20261115_sb_extraction_points_{pool,rule}/results.jsonl, fact = gold_supports[support_idx]
of the population in 20261115_proxy_support_sb_fixed/population.json (text checked against the board facts).
Board (per fact): presence labels in rebuttal/pilots/20261113_sb_presence_full/results.json (checkpoint board).
No fidelity label exists for Silo-Bench in the validated set, so the fidelity removal is not computed here.
    ./.conda-env/bin/python -m scripts.e3_sb_routing_validated
Output: rebuttal/pilots/20261115_e3_sb_routing_validated/{results.json,report.md}
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.stage_ablation import route, route_changes

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261115_e3_sb_routing_validated'
POP = P / '20261115_proxy_support_sb_fixed/population.json'
EXT = [P / '20261115_sb_extraction_points_pool/results.jsonl', P / '20261115_sb_extraction_points_rule/results.jsonl']
BOARD = P / '20261113_sb_presence_full/results.json'
RELAY = ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay')
MODEL = 'qwen235b'


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def rollup(statuses):
    st = list(statuses.values())
    if not st:
        return None
    if all(s == 'present' for s in st):
        return 'present'
    if any(s == 'present' for s in st):
        return 'partial'
    return 'absent'


def main():
    pop = {r['key']: r for r in json.loads(POP.read_text()) if r['model'] == MODEL and r['protocol'] in RELAY}
    rows = defaultdict(dict)   # key -> support_idx -> row
    for path in EXT:
        for l in path.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            proto = r.get('protocol') or r['key'].split('|')[3]
            if r['key'].split('|')[0] != MODEL or proto not in RELAY:
                continue
            r['protocol'] = proto
            assert r['support_idx'] not in rows[r['key']], ('duplicate support', r['key'], r['support_idx'])
            rows[r['key']][r['support_idx']] = r
    board = {}
    for x in json.loads(BOARD.read_text())['items']:
        if x['checkpoint'] != 'board' or x['model'] != MODEL or x['protocol'] not in RELAY:
            continue
        board[(x['instance_id'], x['protocol'])] = x
    traces, excluded, text_mismatch = [], Counter(), 0
    for key, sr in rows.items():
        p = pop.get(key)
        if p is None:
            excluded['no_population_row'] += 1
            continue
        b = board.get((p['instance_id'], p['protocol']))
        if b is None:
            excluded['no_board_item'] += 1
            continue
        gold = p['gold_supports']
        bfacts = {f['fact_id']: f['text'] for f in b['facts']}
        if len(gold) != len(bfacts):
            excluded['fact_count_mismatch'] += 1
            continue
        ext, bl, bad = {}, {}, False
        for si, g in enumerate(gold):
            r = sr.get(si)
            if r is None or not r.get('valid', True) or not r['statuses']:
                bad = True
                break
            fid = f'f{si + 1}'
            if bfacts.get(fid) != g['text']:
                text_mismatch += 1
                bad = True
                break
            ext[fid] = {'status': rollup(r['statuses'])}
            lab = b['labeller'].get(fid) if b.get('labeller') else None
            if not lab or lab.get('status') is None:
                bad = True
                break
            bl[fid] = {'status': lab['status']}
        if bad:
            excluded['unlabelled_or_mismatch'] += 1
            continue
        traces.append({'key': key, 'instance': p['instance_id'], 'protocol': p['protocol'],
                       'extraction': ext, 'board': bl, 'answer_correct': bool(b['answer_correct'])})
    full = [route(t['extraction'], t['board'], t['answer_correct']) for t in traces]
    out = {'population': f'Silo-Bench {MODEL}, relay protocols', 'n_traces': len(traces),
           'excluded': dict(excluded), 'text_mismatch': text_mismatch,
           'full_routes': dict(Counter(full)), 'removals': {}}
    for name, rem in {'pool': ['pool'], 'aggregation': ['aggregation']}.items():
        r = route_changes(traces, rem)
        out['removals'][name] = {'changed': r['changed'], 'n': r['n'], 'ci': wilson(r['changed'], r['n']),
                                 'pairs': {f'{a}->{b}': v for (a, b), v in sorted(r['pairs'].items())}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'results.json').write_text(json.dumps(out, indent=1) + '\n')
    lines = ['# E3 Silo-Bench routes from the validated labels (relay, qwen235b)', '',
             f"$0, no model calls. {len(traces)} traces. Script `scripts/e3_sb_routing_validated.py`; numbers in `results.json`.",
             f"Excluded: {dict(excluded)}. Fidelity removal not computed (no validated fidelity label on Silo-Bench).", '',
             '| removed | changed | share [95% CI] | route changes |', '|---|---:|---|---|']
    for name, r in out['removals'].items():
        ch = '; '.join(f'{k} ({v})' for k, v in r['pairs'].items())
        lines.append(f"| {name} | {r['changed']}/{r['n']} | {r['changed']/r['n']:.3f} [{r['ci'][0]:.3f}, {r['ci'][1]:.3f}] | {ch} |")
    lines += ['', '| full route | n |', '|---|---:|'] + [f'| {k} | {v} |' for k, v in sorted(out['full_routes'].items())]
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
