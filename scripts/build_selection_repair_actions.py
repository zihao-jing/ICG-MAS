"""Build the frozen selection-repair action manifest (no model calls, no outcome).

Population: the 56 MuSiQue traces routed to `selection` by the E3 rule on the
main-table redo. 52 have a pool carrier; 4 are unrepairable and reported.
Rule: `rebuttal/pilots/prereg/Selection-repair-control.md`.

    ./run.sh python -m scripts.build_selection_repair_actions
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from src.audit.pilot_common import digest, freeze
from src.audit.stage_ablation import route
from src.eval.data_loader import load_musique
from scripts.run_expansion_stage2 import MODELS, packages

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'rebuttal/pilots/20261113_main_table_redo/results.json'
POPULATION = ROOT / 'rebuttal/pilots/20261113_main_table_redo/population.json'
RULE = ROOT / 'rebuttal/pilots/prereg/Selection-repair-control.md'
RULE_SHA256 = 'd2b7418aeb9ae368585daa8d8d5a63ba95c4d28c3c6f4ff8f06799af992930a2'
OUT = ROOT / 'rebuttal/pilots/20261114_selection_repair'
SEED = 44


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def agent_of(unit_id):
    m = re.search(r':a(\d+):', unit_id)
    if not m:
        raise ValueError(f'cannot parse agent from {unit_id}')
    return int(m.group(1))


def main():
    got = sha(RULE)
    if got != RULE_SHA256:
        raise SystemExit(f'rule changed: {got} != {RULE_SHA256}')
    items = json.loads(RESULTS.read_text())['items']
    pop = json.loads(POPULATION.read_text())
    popby = {(x['model'], x['instance_id'], x['checkpoint']): x for x in pop}
    by = defaultdict(dict)
    for x in items:
        model, inst, cp = x['key'].split('|')
        by[(model, inst)][cp] = x
    aliases = {i['id']: i.get('answer_aliases', []) for i in load_musique()}
    pk = {m: packages(m) for m in MODELS}

    rows, unrepairable = [], []
    for (model, inst), cps in sorted(by.items()):
        e = cps['extraction'].get('labeller')
        b = cps['board'].get('labeller')
        if e is None or b is None:
            continue
        correct = bool(cps['board']['answer_correct'])
        if route(e, b, correct) != 'selection':
            continue
        target = None
        for fid in sorted(e, key=lambda x: int(x[1:])):
            if e[fid].get('status') in ('present', 'partial') and b.get(fid, {}).get('status') == 'absent':
                units = e[fid].get('unit_ids') or []
                if units:
                    target = (fid, units)
                    break
        if target is None:
            unrepairable.append({'model': model, 'instance_id': inst,
                                 'reason': 'no pool carrier for the board-absent fact'})
            continue
        fid, units = target
        agents = sorted({agent_of(u) for u in units})
        target_agent = sorted(agents, key=lambda a: (digest([SEED, inst, a]), a))[0]
        request = sorted(units)[:2]
        t = pk[model][inst]
        board = t['checkpoints']['board']
        pool = t['checkpoints']['extraction']
        board_agents = {u['agent_id'] for u in board}
        board_ids = {u['unit_id'] for u in board}
        carrier_agents = {agent_of(u) for v in e.values() for u in (v.get('unit_ids') or [])}
        donors = [a for a in sorted(board_agents) if a != target_agent and a not in carrier_agents]
        if not donors:
            donors = [a for a in sorted(board_agents) if a != target_agent]
        donor_agent = (sorted(donors, key=lambda a: (digest([SEED, inst, a]), a))[0]
                       if donors else None)
        donor_pool = ([u for u in pool if u['agent_id'] == donor_agent and u['unit_id'] not in board_ids]
                      if donor_agent is not None else [])
        donor_units = sorted(u['unit_id'] for u in donor_pool)[:len(request)]
        row = {
            'trace_id': digest([inst, model, 'selection-repair']),
            'instance_id': inst, 'benchmark': 'musique', 'group': 'selection_omission',
            'model': MODELS[model], 'n_agents': len(t['source_contexts']),
            'board_units': board, 'pool_units': pool,
            'source_contexts': t['source_contexts'], 'question': t['question'],
            'facts': popby[(model, inst, 'board')]['facts'],
            'carriers': {'extraction': e, 'board': b},
            'answer_text': t['baseline_prediction'], 'gold_answer': t['gold_answer'],
            'answer_aliases': aliases.get(inst, []),
            'target_agent': target_agent, 'donor_agent': donor_agent,
            'target_unit_ids': request, 'donor_unit_ids': donor_units,
            'target_next_unit_ids': request, 'donor_next_unit_ids': donor_units,
            'board_sha256': digest(board), 'label_status': 'frozen_manifest',
            'phase1_arms': ['Rerun', 'R-sel', 'V-sel'],
            'selection_fact': fid, 'volume_control_ok': len(donor_units) >= len(request),
        }
        rows.append(row)

    assert len(unrepairable) == 4, unrepairable
    assert len(rows) == 52, len(rows)
    assert len({r['trace_id'] for r in rows}) == 52
    OUT.mkdir(parents=True, exist_ok=True)
    freeze(OUT / 'actions.json', rows)
    pilot = sorted(rows, key=lambda r: digest([SEED, r['instance_id'], r['model']]))[:3]
    freeze(OUT / 'actions_pilot.json', pilot)
    meta = {'rule_sha256': got, 'seed': SEED, 'population': 56, 'tested': len(rows),
            'unrepairable': unrepairable,
            'volume_control_ok': sum(1 for r in rows if r['volume_control_ok']),
            'volume_control_missing': sum(1 for r in rows if not r['volume_control_ok']),
            'unique_instances': len({r['instance_id'] for r in rows}),
            'calls_full': len(rows) * 3, 'calls_pilot': len(pilot) * 3,
            'actions_sha256': sha(OUT / 'actions.json'),
            'pilot_sha256': sha(OUT / 'actions_pilot.json')}
    (OUT / 'selection.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()