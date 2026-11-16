"""Build the E2-A wave-2 author spot-check packet from the stage-2 v4 items. Blank sheets only.

The packet shows, per item, the before and after trace and the declared edit; the authors fill
`E2A_post_wave2_schema.json` fields. No judge, matcher, lexical or outcome value is displayed or
computed here. Injection mechanics are reused from `run_e2_stage2_spot.py`; no call is made.

    python -m scripts.build_e2a_wave2_spot_packet
"""
import json
from pathlib import Path

from src.audit.pilot_common import blind_view, digest, freeze
import scripts.run_e2_stage2_spot as runner

ROOT = Path('rebuttal/annotation/packets_20261110/E2A_wave2_spot')
PRIVATE = Path('rebuttal/pilots/20261110_packets')
RAW = Path('rebuttal/results/batch1/E2A_stage2_spot_v4/raw')
ANSWERS = ['exactly_one_critical_defect', 'other_critical_facts_unchanged', 'wrong_in_two_reruns',
           'one_visible_step_changed_if_aggregation', 'source_citations', 'uncertain_reason',
           'minutes_spent']
BANNED = ['qwen', 'gemma', 'gpt4o', 'gpt-4o', 'gemini', 'matcher', 'lexical', 'judge', 'diagnosis']


def main():
    cfg = json.loads(runner.CFG.read_text())
    items = runner.selected_items(cfg)
    man = json.loads(runner.MANIFEST.read_text())
    cands = json.loads(Path('rebuttal/pilots/20261108_review5/E2A_combined_manifest.json').read_text())['candidates']
    cm = {c['trace_id']: c for c in cands}
    fam_model = {'qwen': 'qwen235b', 'gpt': 'gpt4omini', 'gemma': 'gemma31b'}
    inst_model = {it['trace_id']: (cm[it['trace_id']]['instance_id'], cm[it['trace_id']]['model_family'])
                  for it in items}
    pk = runner.packages_with_scores({i for i, _ in inst_model.values()})
    boards = {tid: runner.k1_board(pk[(fam_model[f], inst)]) for tid, (inst, f) in inst_model.items()}
    built = []
    for it in items:
        raw = json.loads((RAW / f"{digest(['item', it['item_key']])}.json").read_text())
        if raw['status'] != 'ok':
            continue
        tid = it['trace_id']
        inst, f = inst_model[tid]
        p = pk[(fam_model[f], inst)]
        row = dict(p, checkpoints=dict(p['checkpoints'], board=boards[tid], transmission=boards[tid]),
                   board_units=boards[tid])
        before = blind_view(row)
        if it['fault_type'] == 'aggregation':
            after = dict(before)
            after['answer_text'] = raw['rewrite']['value']['answer_text']
            reruns = []
            edit = {'type': 'aggregation', 'target_agent': None,
                    'changed_step': 'the single visible RATIONALE step, rewritten by the model',
                    'board_unchanged': True}
        else:
            after = blind_view(raw['edited_trace'])
            reruns = list(raw['injected_outputs'])
            edit = {'type': it['fault_type'], 'target_agent': it['target_agent'],
                    'injected_fact_id': raw.get('fact_id'), 'carrier_ids': raw['edited_trace']['injection']['carrier_ids'],
                    'edit': ('all carriers of the injected fact removed from the pool; the target board unit '
                             'replaced by the next noncarrier' if it['fault_type'] == 'extraction_omission' else
                             'the target board unit replaced by the next noncarrier; pool unchanged'
                             if it['fault_type'] == 'selection_omission' else
                             'one entity, number, date, relation or negation changed in the target board unit; pool unchanged')}
        item_id = digest(['E2-wave2-item-v1', it['item_key']])
        built.append({'position': it['position'], 'fault_type': it['fault_type'], 'item_key': it['item_key'],
                      'item_id': item_id, 'trace_id': tid, 'target_agent': it['target_agent'],
                      'edit': edit, 'before': before, 'after': after, 'reruns': reruns})
    order = sorted(built, key=lambda r: (digest(['E2-spot-v2', 42, 'wave2', r['fault_type'], r['item_key']]),
                                         r['fault_type'], r['item_key']))
    rows, private = [], {}
    for n, r in enumerate(order):
        private[r['item_id']] = {'item_key': r['item_key'], 'trace_id': r['trace_id'],
                                 'fault_type': r['fault_type'], 'target_agent': r['target_agent']}
        rows.append({'task': 'E2 wave-2 post-injection spot-check', 'item_id': r['item_id'],
                     'spotcheck_fault_type': r['fault_type'], 'target_agent_id': r['target_agent'],
                     'declared_edit': r['edit'], 'assigned_annotator': 'ABCD'[n % 4],
                     'annotator_id': '', 'k': 1, 'before_trace': r['before'], 'after_trace': r['after'],
                     'rerun_outputs': r['reruns'], 'answers': {k: '' for k in ANSWERS}})
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'packet.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    freeze(PRIVATE / 'E2A_wave2_spot_private_map.json', private)
    text = '\n'.join(json.dumps([r['before_trace'], r['after_trace'], r['rerun_outputs']],
                                ensure_ascii=False).lower() for r in rows)
    blind = {w: text.count(w) for w in BANNED if w in text}
    meta = {'status': 'NOT SENT', 'rows': len(rows),
            'stop_rule': ('stop at any disagreement among the 6 spot items (zero tolerance); the 8 wave-2 '
                          'positions have 6 built, shortfall 2 of 8: distortion position 8 (no exclusive-target '
                          'fact) and the second aggregation slot (only position 5 passed the gate)'),
            'item_ids_sha256': digest([r['item_id'] for r in rows]),
            'packet_sha256': __import__('hashlib').sha256((ROOT / 'packet.jsonl').read_bytes()).hexdigest(),
            'ineligible': [it['position'] for it in items
                           if json.loads((RAW / f"{digest(['item', it['item_key']])}.json").read_text())['status'] != 'ok'],
            'hours_per_author': round(6 * 0.175 / 4, 2), 'blindness_token_counts': blind,
            'return_format': 'one JSONL per annotator, same rows, fill annotator_id and every answers field',
            'label_content': 'blank; the builder writes no label'}
    (ROOT / 'PACKET.json').write_text(json.dumps(meta, indent=2) + '\n')
    (ROOT / 'PACKET.md').write_text(
        '# E2 wave-2 post-injection spot-check packet\n\n'
        f"**Status: NOT SENT.** {len(rows)} items; packet SHA-256 `{meta['packet_sha256']}`.\n"
        f"Item order SHA-256 `{meta['item_ids_sha256']}`. Ineligible wave-2 position(s): {meta['ineligible']}\n"
        f"(no fact met the exclusive-target rule; shortfall reported, no redistribution).\n"
        '- **Stop rule (zero tolerance): stop at any disagreement among the 6 spot items.** Wave-2 asks for 8\n'
        '  positions; 6 are built. Shortfall 2 of 8: position 8 (distortion) has no fact meeting the\n'
        '  exclusive-target rule; the second aggregation slot has no item, because only position 5 passed the\n'
        '  gate (positions 1 and 6 failed judge and author defect-free). No redistribution.\n\n'
        '- One row per item: before trace, after trace, declared edit, the two rerun outputs for evidence edits\n'
        '  (the rewritten answer for aggregation). Sheets are blank; no label is written here.\n'
        '- Return format: one JSONL per annotator over the same rows, fill `annotator_id` and every `answers` field.\n'
        f"- Estimated time per author: {meta['hours_per_author']} h (6 items x 10.5 min / 4).\n"
        f"- Blindness scan over traces and rerun outputs: {blind}.\n")
    print(json.dumps({k: v for k, v in meta.items() if k != 'blindness_token_counts'}, indent=1))
    print('blindness', blind)


if __name__ == '__main__':
    main()