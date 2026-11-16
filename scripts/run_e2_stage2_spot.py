"""E2-A stage 2, narrow: injections and clean reruns for the pre-registered wave-2 spot items only.

Selection rule: E2-A.md line 64 — among injections made on wave-1 spot items that the gate passed
(judge and author both defect-free), first 2 per fault type by ascending SHA-256 of
["E2-spot-v2", 42, "wave2", fault_type, item_key]; fewer than 2 passed in a type -> take all,
report shortfall, no redistribution. The stage-1 gate passed 12/12; 8 items were both defect-free,
so aggregation has 1 passed item and the wave-2 set is 7, not 8.

No outcome is read: the runner computes no score, no judge verdict, no yield and no accuracy. It only
confirms that each injection exists, edits exactly the intended unit, and returns a non-empty answer.

    python -m scripts.run_e2_stage2_spot            # dry check, no calls
    python -m scripts.run_e2_stage2_spot --execute   # capped at 50 calls / $0.50

Output: rebuttal/results/batch1/E2A_stage2_spot
"""
import argparse, datetime, glob, hashlib, json, re
from pathlib import Path

from src.audit.critical_fact_validation import get_transmitted_units, load_run, \
    reconstruct_states_and_scores
from src.audit.fault_injection import inject_evidence
from src.audit.matcher_v2 import match_trace, structured_call, obj
from src.audit.pilot_common import CallLedger, digest, freeze
from scripts.build_final_author_packet import packages
from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt
from scripts.run_e1_anchor_matcher import adapt

PREREG = Path('rebuttal/pilots/prereg/E2-A.md')
CFG = Path('rebuttal/pilots/configs/E2A-stage2-spot-v4.json')
MANIFEST = Path('rebuttal/pilots/20261108_review8/e2_spotcheck_wave1_manifest.json')
GATE = Path('rebuttal/results/batch1/E2_stage1_judge/gate.json')
MATCHER = Path('rebuttal/results/batch1/E4_pool_matcher/matcher')
OUT = Path('rebuttal/results/batch1/E2A_stage2_spot')
TYPES = ['extraction_omission', 'selection_omission', 'distortion', 'aggregation']


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def selected_items(cfg):
    gate = json.loads(GATE.read_text())
    assert sha(GATE) == cfg['gate_sha256']
    assert sha(MANIFEST) == cfg['manifest_sha256']
    passed = {r['position'] for r in gate['rows']
              if r['judge_defect_free'] == 'yes' and r['author_defect_free'] == 'yes'}
    man = json.loads(MANIFEST.read_text())
    items = [i for i in man['wave1_items'] if i['position'] in passed]
    sel = []
    for ft in TYPES:
        cand = sorted([i for i in items if i['fault_type'] == ft],
                      key=lambda i: (digest(['E2-spot-v2', 42, 'wave2', ft, i['item_key']]), i['item_key']))
        sel += cand[:2]
    sel.sort(key=lambda i: (digest(['E2-spot-v2', 42, 'wave2', i['fault_type'], i['item_key']]),
                            i['fault_type'], i['item_key']))
    out = [{'position': i['position'], 'fault_type': i['fault_type'], 'item_key': i['item_key'],
            'trace_id': i['trace_id'], 'target_agent': i['target_agent']} for i in sel]
    for n, i in enumerate(out):
        i['author'] = 'ABCD'[n % 4]
    assert digest(out) == cfg['selection_sha256'], 'selection changed since the freeze'
    return out


def matcher_index(cfg):
    out = {}
    files = glob.glob(str(MATCHER / '*.json'))
    if (OUT / 'matcher').is_dir():
        files += glob.glob(str(OUT / 'matcher' / '*.json'))
    for extra in cfg.get('matcher_labels_extra', []):
        files += glob.glob(str(Path(extra) / '*.json'))
    for p in files:
        d = json.loads(Path(p).read_text())
        if d.get('status') == 'ok' and 'facts' in d and 'carriers' in d:
            out[(d['instance_id'], d['model'])] = d
    return out


def packages_with_scores(instances):
    pk = packages(instances)
    cache = {}
    for (model, inst), p in pk.items():
        run_dir = Path(p['run_dir'])
        if run_dir not in cache:
            cache[run_dir] = reconstruct_states_and_scores(load_run(run_dir)[1])
        states, scores = cache[run_dir]
        p['scores'] = {int(a): v for a, v in scores.get(inst, {}).items()}
        p['_states'] = states
        p['_scores'] = scores
    return pk


def k1_board(trace_pkg):
    """The k=1 transmitted board the wave-1 packet and the judge saw: one selected pool unit per agent.

    The packet builder assigns fresh ids ('k1:aX:u0'); the injection code needs the board unit id to be
    the selected pool unit's id, so the same unit is named here by its extraction id.
    """
    inst = trace_pkg['instance_id']
    units = get_transmitted_units(inst, 'score_ranked_relay', trace_pkg['_states'],
                                  trace_pkg['_scores'], len(trace_pkg['source_contexts']), k=1)
    pool = trace_pkg['checkpoints']['extraction']
    board = []
    for agent, texts in sorted(units.items()):
        assert len(texts) == 1, 'k=1 board must hold one unit per agent'
        match = [u for u in pool if u['agent_id'] == agent and u['text'] == texts[0]]
        assert len(match) == 1, f'selected unit not unique in pool: agent {agent}'
        board.append({'unit_id': match[0]['unit_id'], 'agent_id': agent, 'text': match[0]['text']})
    return board


def target_fact(labels, agent, board):
    """Fact in every sufficient set, all pool carriers on the target agent, carried by its k=1 unit."""
    if not labels['facts']['support_sets']:
        return None
    common = set.intersection(*map(set, labels['facts']['support_sets']))
    byid = {u['unit_id']: u for u in labels['_pool']}
    carried = next(u['unit_id'] for u in board if u['agent_id'] == agent)
    choices = []
    for r in labels['carriers']['facts']:
        ids = {i for c in r['extraction'] for i in c['unit_ids']}
        agents = {byid[i]['agent_id'] for i in ids} if ids else set()
        if r['fact_id'] in common and agents == {agent} and carried in ids:
            remaining = [u for u in labels['_pool'] if u['agent_id'] == agent and u['unit_id'] not in ids]
            if remaining:
                choices.append((r['fact_id'], sorted(ids)))
    return sorted(choices)[0] if choices else None


def run_item(item, trace_pkg, board, labels, cfg, ledger, model):
    kind = item['fault_type']
    out = {'item_key': item['item_key'], 'position': item['position'], 'fault_type': kind,
           'target_agent': item['target_agent'], 'status': 'ok', 'outcome_read': False,
           'card_qualified_keep': False}
    row = dict(trace_pkg)
    mid = cfg['models'][model]
    row['model'] = mid
    row['n_agents'] = len(trace_pkg['source_contexts'])
    row['facts'] = labels['facts']
    row['carriers'] = labels['carriers']
    row['board_units'] = board
    row['checkpoints'] = dict(trace_pkg['checkpoints'], board=board, transmission=board)
    system, user = original_prompt(row, row['board_units'])
    key = digest(['E2-stage2', kind, item['item_key']])
    clean = [ledger.call(key + f'/clean/{j}', row['model'], messages(system, user), max_tokens=4096)
             for j in range(2)]
    out['clean_outputs'] = clean
    out['clean_nonempty'] = all(bool(x) for x in clean)
    if kind == 'aggregation':
        schema = obj({'answer_text': {'type': 'string'}})
        rewrite = structured_call(ledger, key + '/rewrite', cfg['judge_model'],
                                  'Rewrite exactly the single visible RATIONALE step to misuse one stated board fact, '
                                  'and make ANSWER follow that wrong step. Preserve USED_EVIDENCE and all other text. '
                                  'Return JSON with answer_text only. Do not invent hidden reasoning.',
                                  {'question': row['question'], 'board': row['board_units'],
                                   'answer_text': row['answer_text']}, schema, lambda x: None)
        out['rewrite'] = rewrite
        out['status'] = 'ok' if rewrite['status'] == 'ok' else 'failed'
        out['well_formed'] = bool((rewrite.get('value') or {}).get('answer_text'))
        return out
    picked = target_fact(labels, item['target_agent'], board)
    if picked is None:
        out.update(status='ineligible', well_formed=False, reason='no fact meets the exclusive-target rule')
        return out
    fact_id, carrier_ids = picked
    replacement = None
    if kind == 'distortion':
        original = next(u['text'] for u in board if u['agent_id'] == item['target_agent'])
        schema = obj({'text': {'type': 'string'}})
        rewrite = structured_call(ledger, key + '/distort', cfg['judge_model'],
                                  'Change exactly one key entity, number, date, relation or negation in the supplied '
                                  'evidence unit. Keep all other details. Return JSON text only. This is a synthetic '
                                  'error-injection experiment.',
                                  {'unit': original, 'question': row['question']}, schema, lambda x: None)
        out['rewrite'] = rewrite
        replacement = (rewrite.get('value') or {}).get('text') if rewrite['status'] == 'ok' else None
        if not replacement:
            out.update(status='failed', well_formed=False, reason='distortion rewrite failed')
            return out
    edited = inject_evidence(row, kind, item['target_agent'], carrier_ids, replacement_text=replacement)
    before = {u['unit_id'] for u in row['board_units']}
    after = {u['unit_id'] for u in edited['checkpoints']['board']}
    out.update(fact_id=fact_id, board_sha256=digest(edited['checkpoints']['board']),
               board_units_before=len(before), board_units_after=len(after),
               edited_trace=edited)
    system, user = original_prompt(row, edited['checkpoints']['board'])
    edited_out = [ledger.call(key + f'/edited/{j}', row['model'], messages(system, user), max_tokens=4096)
                  for j in range(2)]
    out['injected_outputs'] = edited_out
    out['well_formed'] = bool(all(edited_out)) and len(after) == len(before) and edited.get('injection')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int, default=50)
    a = ap.parse_args()
    global OUT
    cfg = json.loads(CFG.read_text())
    OUT = Path(cfg['output'])
    assert cfg['prereg_sha256'] == sha(PREREG)
    assert sha(Path(__file__)) == cfg['runner_sha256']
    items = selected_items(cfg)
    inst_model = {}
    man = json.loads(MANIFEST.read_text())
    for it in items:
        cand = next(c for c in json.loads(Path('rebuttal/pilots/20261108_review5/E2A_combined_manifest.json').read_text())['candidates']
                    if c['trace_id'] == it['trace_id'])
        inst_model[it['trace_id']] = (cand['instance_id'], cand['model_family'])
    pk = packages_with_scores({i for i, _ in inst_model.values()})
    fam_model = {'qwen': 'qwen235b', 'gpt': 'gpt4omini', 'gemma': 'gemma31b'}
    label_cache = matcher_index(cfg)
    boards = {}
    for tid, (inst, fam) in inst_model.items():
        boards[tid] = k1_board(pk[(fam_model[fam], inst)])
    missing = [tid for tid in inst_model
               if (inst_model[tid][0], fam_model[inst_model[tid][1]]) not in label_cache]
    per_item = {i['item_key']: (5 if i['fault_type'] == 'distortion' else 4 if i['fault_type'] != 'aggregation' else 3)
                for i in items}
    bound = 2 * len(set(inst_model)) + len(missing) * 2 + sum(per_item.values())
    injectable, ineligible = 0, []
    for item in items:
        if item['fault_type'] == 'aggregation':
            continue
        inst, fam = inst_model[item['trace_id']]
        lab = label_cache.get((inst, fam_model[fam]))
        if lab is None:
            continue
        hit = target_fact(dict(lab, _pool=pk[(fam_model[fam], inst)]['checkpoints']['extraction']),
                          item['target_agent'], boards[item['trace_id']])
        if hit:
            injectable += 1
        else:
            ineligible.append(item['position'])
    print(json.dumps({'items': len(items), 'per_type': {t: sum(i['fault_type'] == t for i in items) for t in TYPES},
                      'injectable_evidence': injectable, 'ineligible_items': ineligible,
                      'aggregation_shortfall': 2 - sum(i['fault_type'] == 'aggregation' for i in items),
                      'unique_traces': len(inst_model), 'matcher_fallback_traces': len(missing),
                      'call_bound': bound, 'max_calls': a.max_calls,
                      'cost_cap_usd': cfg['cost_cap_usd'], 'selection_sha256': cfg['selection_sha256'],
                      'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = CallLedger(OUT, cfg, PREREG, a.max_calls)
    spent = lambda: sum((r.get('cost_usd') or 0) for r in ledger.done.values())
    results = []
    try:
        clean = {}
        for tid, (inst, fam) in inst_model.items():
            model = fam_model[fam]
            if (inst, model) not in label_cache:
                p = adapt(pk[(model, inst)])
                rec = match_trace(ledger, digest(['E2-stage2-matcher', 42, inst, model]), p, cfg['judge_model'])
                assert rec['status'] == 'ok', 'matcher failed; stop, no retry, unscored'
                label_cache[(inst, model)] = {'facts': rec['facts'], 'carriers': rec['carriers'],
                                              'status': 'ok', 'label_status': 'pilot_provisional'}
                freeze(OUT / 'matcher' / f'{digest([inst, model])}.json',
                       {'instance_id': inst, 'model': model, 'matcher_frozen': True, **rec})
            labels = dict(label_cache[(inst, model)])
            if spent() > cfg['cost_cap_usd']:
                raise RuntimeError('cost cap reached')
        for item in items:
            tid = item['trace_id']
            inst, fam = inst_model[tid]
            model = fam_model[fam]
            labels = dict(label_cache[(inst, model)])
            trace = pk[(model, inst)]
            labels['_pool'] = trace['checkpoints']['extraction']
            labels['_board'] = trace['checkpoints']['board']
            try:
                rec = run_item(item, trace, boards[tid], labels, cfg, ledger, model)
            except Exception as exc:
                rec = {'item_key': item['item_key'], 'position': item['position'],
                       'fault_type': item['fault_type'], 'status': 'failed',
                       'error': type(exc).__name__ + ': ' + str(exc), 'outcome_read': False}
            results.append(rec)
            (OUT / 'raw').mkdir(exist_ok=True)
            (OUT / 'raw' / f"{digest(['item', item['item_key']])}.json").write_text(
                json.dumps(rec, indent=1, sort_keys=True) + '\n')
            print(json.dumps({'item': item['position'], 'type': item['fault_type'],
                              'status': rec['status'], 'cost_usd': round(spent(), 6)}), flush=True)
            if spent() > cfg['cost_cap_usd']:
                raise RuntimeError('cost cap reached')
    finally:
        ledger.close()
    (OUT / 'summary.json').write_text(json.dumps({
        'planned_items': len(items), 'completed_items': len(results),
        'well_formed': sum(bool(r.get('well_formed')) for r in results),
        'by_type': {t: sum(r['fault_type'] == t and r['status'] == 'ok' for r in results) for t in TYPES},
        'calls': len(ledger.done), 'cost_usd': round(spent(), 6),
        'cost_cap_usd': cfg['cost_cap_usd'], 'max_calls': a.max_calls,
        'selection_sha256': cfg['selection_sha256'], 'outcome_read': False, 'end_utc': utc()},
        indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'done': True, 'calls': len(ledger.done), 'cost_usd': round(spent(), 6)}), flush=True)


if __name__ == '__main__':
    main()