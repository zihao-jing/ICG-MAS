"""Reconcile set A of the hop-anchor check (5/29, .172) with the earlier 6/30 (.200) on the same 30 traces.

Set A = instances of rebuttal/pilots/20261115_q1_second_sample (the 6/30 run, proxy facts v1).
Hop run = rebuttal/pilots/20261115_mq_hop_anchor (proxy facts v4, hop-anchored).
$0, no model calls. Reads recorded labels only.
    ./.conda-env/bin/python -m scripts.mq_hop_reconcile
Output: rebuttal/pilots/20261115_mq_hop_reconcile/reconcile.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261115_mq_hop_reconcile'
Q1A_SCORE = P / '20261115_q1_second_sample/score.json'
HOP = P / '20261115_mq_hop_anchor/results.jsonl'
CROSS = P / '20261115_proxy_support_89/results.json'


def hop_gold(rec):
    g = rec['gold']
    if not all(g.get(cp) and g[cp]['valid'] for cp in ('extraction', 'board')):
        return None
    if g['extraction']['status'] == 'absent':
        return 'extraction'
    if g['board']['status'] == 'absent':
        return 'transmission'
    return 'aggregation'


def hop_proxy(rec):
    """Same rule as scripts.mq_hop_anchor_check.side: any invalid proxy label drops the trace (None)."""
    if not rec['proxy']:
        return None
    for p in rec['proxy']:
        for cp in ('extraction', 'board'):
            if not p.get(cp) or not p[cp]['valid']:
                return None
    if any(p['extraction']['status'] == 'absent' for p in rec['proxy']):
        return 'extraction'
    if any(p['board']['status'] == 'absent' for p in rec['proxy']):
        return 'transmission'
    return 'aggregation'


def main():
    q1 = json.loads(Q1A_SCORE.read_text())['stages']          # 30 traces, proxy v1 facts
    hop = {}
    for l in HOP.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            if r['set'] == 'A':
                hop[r['instance']] = r
    rows = []
    for i in sorted(q1):
        h = hop[i]
        rows.append({'instance': i, 'gold_q1': q1[i]['gold'], 'gold_hop': hop_gold(h),
                     'proxy_v1': q1[i]['proxy'], 'proxy_v4': hop_proxy(h)})
    gold_same = sum(1 for r in rows if r['gold_q1'] == r['gold_hop'])
    v1_agree = sum(1 for r in rows if r['proxy_v1'] == r['gold_q1'])
    v4_valid = [r for r in rows if r['proxy_v4'] is not None and r['gold_hop'] is not None]
    v4_agree = sum(1 for r in v4_valid if r['proxy_v4'] == r['gold_hop'])
    v4_agree_30 = sum(1 for r in rows if r['proxy_v4'] is not None and r['proxy_v4'] == r['gold_hop'])
    changed = [r for r in rows if r['proxy_v4'] is not None and r['proxy_v4'] != r['proxy_v1']]
    gained = [r['instance'] for r in changed if r['proxy_v4'] == r['gold_hop']]
    lost = [r['instance'] for r in changed if r['proxy_v1'] == r['gold_q1']]
    dropped = [r['instance'] for r in rows if r['proxy_v4'] is None]
    summary = {
        'population': 'set A: 30 instances of 20261115_q1_second_sample (same as the 6/30 run)',
        'gold_stage_identical_on_traces': f'{gold_same}/30',
        'v1_proxy_agree_6_of_30': f'{v1_agree}/30',
        'v4_proxy_agree_on_29_valid_traces': f'{v4_agree}/{len(v4_valid)}',
        'v4_proxy_agree_counting_dropped_as_disagree': f'{v4_agree_30}/30',
        'v4_proxy_stage_changed_traces': len(changed),
        'changed_gained_agreement': gained,
        'changed_lost_agreement': lost,
        'trace_dropped_for_invalid_proxy_label': dropped,
    }
    cross = crosstab()
    six = six_of_thirty()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'reconcile.json').write_text(json.dumps({'summary': summary, 'rows': rows, 'crosstab_62_81': cross, 'six_of_thirty': six}, indent=1))
    print(json.dumps(summary, indent=1))
    print(json.dumps(cross, indent=1))
    print(json.dumps(six, indent=1))


EARLY = ('extraction', 'sharding')


def crosstab():
    """Proxy stage (rows) by gold-audit stage (columns) on the 81 traces with facts, from the stored matrix."""
    m = json.loads(CROSS.read_text())['stage']['matrix']
    stages = ['extraction', 'transmission', 'sharding', 'aggregation']
    tab = {p: {g: m.get(f'{p}->{g}', 0) for g in stages} for p in stages}
    proxy_early = sum(tab[p][g] for p in EARLY for g in stages)
    proxy_early_confirmed = sum(tab[p][g] for p in EARLY for g in EARLY)
    gold_early = sum(tab[p][g] for p in stages for g in EARLY)
    return {'source': 'rebuttal/pilots/20261115_proxy_support_89/results.json (stage.matrix, 81 traces)',
            'matrix_proxy_rows_gold_cols': tab,
            'proxy_names_early_loss': proxy_early,
            'of_which_gold_also_early': proxy_early_confirmed,
            'of_which_gold_not_early': proxy_early - proxy_early_confirmed,
            'gold_early_losses': gold_early,
            'gold_early_missed_by_proxy': gold_early - proxy_early_confirmed,
            'missed_named_as': {p: sum(tab[p][g] for g in EARLY) for p in ('transmission', 'aggregation')}}


def six_of_thirty():
    """Same breakdown for the 6/30 set (set A, proxy facts v1), from its stored confusion."""
    c = json.loads(Q1A_SCORE.read_text())['confusion']
    early = ('extraction',)
    proxy_early = sum(c['extraction'].values())
    confirmed = c['extraction']['extraction']
    gold_early = sum(c[p]['extraction'] for p in c)
    return {'source': 'rebuttal/pilots/20261115_q1_second_sample/score.json (confusion)',
            'proxy_names_early_loss': proxy_early, 'of_which_gold_also_early': confirmed,
            'gold_early_losses': gold_early, 'gold_early_missed_by_proxy': gold_early - confirmed,
            'missed_named_as': {'aggregation': c['aggregation']['extraction'],
                                'transmission': c['transmission']['extraction']}}


if __name__ == '__main__':
    main()
