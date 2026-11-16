"""Build the two send-ready author packets (SB anchor, E4 distortion swap check) and record the
blocked E2-A wave-2 spot packet. Blank sheets only: no labels, judge, matcher or lexical output.

Nothing is sent. The builder writes private hash->(instance, model) maps outside the packet dirs.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from src.audit.pilot_common import blind_view, digest, freeze
from scripts.build_final_author_packet import E1_ANSWERS, packages

ROOT = Path('rebuttal/annotation/packets_20261110')
PRIVATE = Path('rebuttal/pilots/20261110_packets')
N80 = Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json')
E4MAN = Path('rebuttal/results/batch1/E4_manifest/manifest.json')
SWAP_ANSWERS = ['swap_source_quote', 'swap_is_verbatim', 'swap_preserves_fact', 'rationale', 'minutes_spent']
BANNED = ['qwen', 'gemma', 'gpt4o', 'gpt-4o', 'gemini', 'matcher', 'lexical', 'judge', 'diagnosis']
NOW = lambda: datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def export(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sb_draw_rule():
    p = PRIVATE / 'SB_anchor_draw_rule.json'
    if p.exists():
        return json.loads(p.read_text())
    m = json.loads(N80.read_text())
    ids = sorted(i for h, v in m['strata'].items() if h.startswith('SB/') for i in v['ids'])
    assert len(ids) == 20, len(ids)
    rule = {
        'rule': 'all 20 held-out Silo-Bench instances in e1_n80_locked_manifest.json; no subsampling; '
                'sorted instance id; first 10 assigned pair A/B, remaining 10 pair C/D; all three paper models per instance',
        'source': str(N80), 'source_sha256': sha(N80),
        'instances': ids, 'instances_sha256': digest(ids),
        'models': ['qwen235b', 'gpt4omini', 'gemma31b'],
        'frozen_utc': NOW(),
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    freeze(p, rule)
    return rule


def sb_anchor():
    rule = sb_draw_rule()
    ids = rule['instances']
    pk = packages(set(ids))
    rows, private = [], {}
    for pos, inst in enumerate(ids):
        pair = ['A', 'B'] if pos < 10 else ['C', 'D']
        for model in rule['models']:
            t = pk[(model, inst)]
            v = blind_view(t)
            h = digest(v)
            private[h] = {'instance_id': inst, 'model': model}
            for who in pair:
                rows.append({'task': 'Silo-Bench anchor (claim-evidence check)', 'item_id': h,
                             'assigned_annotator': who, 'annotator_id': '', 'k': 3,
                             'trace': v, 'answers': {k: '' for k in E1_ANSWERS}})
    out = ROOT / 'SB_anchor'
    export(out / 'packet.jsonl', rows)
    freeze(PRIVATE / 'SB_anchor_private_map.json', private)
    return rows, ids


def e4_swap():
    man = json.loads(E4MAN.read_text())
    cases = [c for c in man['cases'] if c['group'] == 'distortion' and c['matcher_status'] == 'ok']
    assert len(cases) == 25, len(cases)
    pk = packages({c['instance'] for c in cases})
    order = sorted(cases, key=lambda c: digest(['E4-swap-v1', 42, c['instance'], c['model']]))
    rows, private = [], {}
    for pos, c in enumerate(order):
        t = pk[(c['model'], c['instance'])]
        v = blind_view(t)
        h = digest(['E4-swap-item-v1', c['instance'], c['model']])
        private[h] = {'instance_id': c['instance'], 'model': c['model']}
        new = [u['text'] for u in c['repair']['units']]
        rows.append({'task': 'E4 distortion swap check', 'item_id': h,
                     'assigned_annotator': 'ABCD'[pos % 4], 'annotator_id': '', 'k': 1,
                     'swap_check': {'target_agent': c['target_agent'], 'target_fact': c['target_span'],
                                    'donor_agent': c['donor_agent'], 'donor_span': c['donor_span'],
                                    'replacement_units': new},
                     'trace': v,
                     'answers': {k: '' for k in SWAP_ANSWERS}})
    out = ROOT / 'E4_distortion_swap'
    export(out / 'packet.jsonl', rows)
    freeze(PRIVATE / 'E4_swap_private_map.json', private)
    return rows


def blindness(rows):
    """Count model-name / output-type tokens inside trace fields only (the payload shown to authors)."""
    text = '\n'.join(json.dumps(r['trace'], ensure_ascii=False).lower() for r in rows)
    return {w: text.count(w) for w in BANNED if w in text}


def readme(name, sha_val, rows, traces, authors, hours, ret, extra):
    return f"""# {name} author packet

**Status: NOT SENT.** Prepared but not sent to any annotator.

- Packet file SHA-256: `{sha_val}`
- Rows: {rows}; traces: {traces}; annotators: {authors}
- Estimated time per author: {hours} h
- Return format: {ret}
- No judge, matcher, or lexical output. Sheets are blank; the builder writes no label.
{extra}
"""


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    sb_rows, sb_ids = sb_anchor()
    swap_rows = e4_swap()
    manifest = {
        'status': 'NOT SENT',
        'built_utc': NOW(),
        'packets': {
            'SB_anchor': {
                'path': 'rebuttal/annotation/packets_20261110/SB_anchor/packet.jsonl',
                'sha256': sha(ROOT / 'SB_anchor/packet.jsonl'),
                'rows': len(sb_rows), 'instances': len(sb_ids), 'traces': len(sb_rows) // 2,
                'annotators': 4, 'hours_per_author': 2.13,
                'hours_basis': '60 traces; 33 SB-5 at 2.93 min and 27 SB-10 at 5.87 min; 8.52 h total / 4',
                'draw_rule': str(PRIVATE / 'SB_anchor_draw_rule.json'),
                'draw_rule_sha256': sha(PRIVATE / 'SB_anchor_draw_rule.json'),
                'return_format': 'one JSONL per annotator, same rows, fill annotator_id and every answers field',
                'label_content': 'blank; no label written by the builder',
            },
            'E4_distortion_swap': {
                'path': 'rebuttal/annotation/packets_20261110/E4_distortion_swap/packet.jsonl',
                'sha256': sha(ROOT / 'E4_distortion_swap/packet.jsonl'),
                'rows': len(swap_rows), 'cases': 25, 'annotators': 4,
                'hours_per_author': round(25 * 1.54 / 60 / 4, 2),
                'hours_basis': '25 cases at 1.54 min = 0.64 h total, split across 4',
                'return_format': 'one JSONL per annotator, same rows, fill swap_source_quote, both yes/no fields, rationale, minutes_spent',
                'label_content': 'blank; no label written by the builder',
            },
            'E2A_wave2_spot': {
                'status': 'cannot be built before injections',
                'reason': 'E2-A v5 fixes the 8 wave-2 items as injections made on wave-1 spot items that passed '
                          'the stage-2 gate; no injection has been made and stage 2 is not run, so no item exists. '
                          'The packet is generated after stage 2, never fabricated.',
                'rows': 0,
            },
        },
        'blindness_check': {'banned_token_counts_in_traces': blindness(sb_rows + swap_rows)},
        'contains_judge_matcher_lexical_output': False,
    }
    (ROOT / 'packet_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'SB_anchor' / 'PACKET.md').write_text(readme(
        'Silo-Bench anchor', manifest['packets']['SB_anchor']['sha256'], len(sb_rows), 60, 4, '2.13',
        'one JSONL per annotator over the same rows, fill annotator_id and every answers field',
        '- Draw rule (hashed before build): rebuttal/pilots/20261110_packets/SB_anchor_draw_rule.json'
        f", SHA-256 `{manifest['packets']['SB_anchor']['draw_rule_sha256']}`\n"
        '- 20 held-out SB instances, 3 paper models, 60 traces; 33 SB-5 and 27 SB-10\n'))
    (ROOT / 'E4_distortion_swap' / 'PACKET.md').write_text(readme(
        'E4 distortion swap check', manifest['packets']['E4_distortion_swap']['sha256'], len(swap_rows), 25, 4,
        '0.16', 'one JSONL per annotator, same rows, fill swap_source_quote, both yes/no fields, rationale, '
        'minutes_spent', '- 25 distortion cases under the frozen E4 manifest\n'))
    (ROOT / 'E2A_wave2_spot_BLOCKED.md').write_text(
        '# E2-A wave-2 spot items: NOT BUILT, NOT SENT\n\n'
        'E2-A v5 (rebuttal/pilots/prereg/E2-A.md, wave-2 spot rule) fixes the 8 items as injections made on\n'
        'wave-1 spot items that passed the stage-2 gate. No injection has been run and stage 2 has not\n'
        'returned, so no wave-2 item exists. The packet is generated after stage 2; building it now would\n'
        'mean inventing label content. Nothing is sent to any annotator.\n')
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if 'basis' not in kk}
                      for k, v in manifest['packets'].items()}, indent=1))
    print('blindness', manifest['blindness_check']['banned_token_counts_in_traces'])


if __name__ == '__main__':
    main()