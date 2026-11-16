"""E2-A stage-2 gate: judge vs author on the 6 wave-2 post-injection spot items.

Reads the frozen gate-judge outputs and the authors' returned wave-2 spot labels. The judge's
`defect_free` is compared with the author label mapped from `exactly_one_critical_defect`
(author says one critical defect -> not defect-free; says none -> defect-free).

Governing rule: the approved stop rule for the 6-item packet is zero tolerance, stop at any
disagreement (DEVIATIONS 2026-11-09T23:04:00Z, which supersedes the E2-A-v5.md:69 "more than 1 of the
8" text before any author result existed). The gate fails on any author-judge disagreement.

Run: python -m scripts.analyze_e2_stage2_gate
"""
import json
from pathlib import Path

OUT = Path('rebuttal/results/batch1/E2A_stage2_gate_judge')
RET = Path('rebuttal/annotation/packets_20261110/returns/E2A_wave2_spot')
PRIVATE = Path('rebuttal/pilots/20261110_packets/E2A_wave2_spot_private_map.json')
V4_RAW = Path('rebuttal/results/batch1/E2A_stage2_spot_v4/raw')
CFG = Path('rebuttal/pilots/configs/E2A-stage2-gate-judge.json')


def norm(v):
    return str(v).strip().lower()


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa = sum(a) / n; pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return None
    return round((po - pe) / (1 - pe), 4)


def author_defect_free(answers):
    v = norm(answers.get('exactly_one_critical_defect'))
    if v == 'no':
        return 'yes'
    if v == 'yes':
        return 'no'
    return None


def main():
    cfg = json.loads(CFG.read_text())
    priv = json.loads(PRIVATE.read_text())
    raws = {json.loads(p.read_text())['item_key']: json.loads(p.read_text()) for p in V4_RAW.glob('*.json')}

    authors = {}
    for f in sorted(RET.glob('annotator_*.jsonl')):
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                authors[r['item_id']] = r

    judge = {}
    for f in sorted((OUT / 'outputs').glob('*.json')):
        d = json.loads(f.read_text())
        judge[d['packet_item_id']] = d
    assert len(judge) == 6 and len(authors) == 6

    rows = []
    for item_id, d in judge.items():
        p = priv[item_id]
        raw = raws[p['item_key']]
        a = authors[item_id]
        j = d.get('parsed') or {}
        j_df = j.get('defect_free')
        a_df = author_defect_free(a['answers'])
        rows.append({'position': raw['position'], 'fault_type': p['fault_type'],
                     'item_id': item_id, 'item_key': p['item_key'],
                     'author': a.get('annotator_id'), 'target_agent': p['target_agent'],
                     'judge_status': d['status'], 'judge_defect_free': j_df,
                     'author_one_critical_defect': a['answers'].get('exactly_one_critical_defect'),
                     'author_defect_free': a_df,
                     'agree_defect_free': (norm(j_df) == norm(a_df)) if (j_df is not None and a_df) else None})
    rows.sort(key=lambda r: r['position'])

    n = len([r for r in rows if r['agree_defect_free'] is not None])
    k = sum(1 for r in rows if r['agree_defect_free'])
    dis = [r for r in rows if r['agree_defect_free'] is False]
    jb = [1 if norm(r['judge_defect_free']) == 'yes' else 0 for r in rows]
    ab = [1 if norm(r['author_defect_free']) == 'yes' else 0 for r in rows]

    calls = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [c for c in calls if c['event'] == 'result']
    drift = {'results': len(res), 'failed_calls': sum(not r['success'] for r in res),
             'resolved_models': sorted({r.get('resolved_model') for r in res if r.get('resolved_model')}),
             'config_hashes': sorted({r['config_sha256'] for r in res}),
             'unexpected_model': any(r.get('resolved_model') != cfg['model'] for r in res)}
    drift['clean'] = (drift['results'] == 6 and drift['failed_calls'] == 0
                      and drift['resolved_models'] == [cfg['model']]
                      and len(drift['config_hashes']) == 1 and not drift['unexpected_model'])

    gate = {'n': n, 'agree': k, 'disagree': n - k, 'disagreements': dis,
            'agreement_proportion': round(k / n, 4),
            'judge_not_defect_free': n - sum(jb), 'author_not_defect_free': n - sum(ab),
            'kappa': kappa(jb, ab),
            'rule': 'approved stop rule for the 6-item packet: zero tolerance (DEVIATIONS '
                    '2026-11-09T23:04:00Z, superseding the E2-A-v5.md:69 text)',
            'passed': (n - k) == 0}
    payload = {'gate': gate, 'rows': rows, 'drift': drift,
               'judge_config_sha256': json.loads((OUT / 'run_identity.json').read_text()),
               'prereg': cfg['prereg'], 'prereg_sha256': cfg['prereg_sha256']}
    (OUT / 'gate.json').write_text(json.dumps(payload, indent=1) + '\n')

    lines = ['# E2-A stage-2 gate: the 6 wave-2 post-injection spot items', '',
             f"Judge: `{cfg['model']}`, frozen prompt `{cfg['task']}`, one call per item, frozen "
             f"{cfg['frozen_utc']}, hard cap 10. Author: one label per item (single-coded).",
             '', '| Pos | Fault type | Author | Judge defect_free | Author exactly_one_critical_defect | Author defect_free | Agree |',
             '|---:|---|---|---|---|---|---|']
    lines += [f"| {r['position']} | {r['fault_type']} | {r['author']} | {r['judge_defect_free']} | "
              f"{r['author_one_critical_defect']} | {r['author_defect_free']} | "
              f"{'yes' if r['agree_defect_free'] else 'no'} |" for r in rows]
    lines += ['', f"**defect_free agreement:** {k}/{n} = {gate['agreement_proportion']:.3f}; "
                  f"disagreements {n - k} (positions {', '.join(str(r['position']) for r in dis) or 'none'}); "
                  f"Cohen kappa {gate['kappa']} (judge not defect-free {gate['judge_not_defect_free']}, "
                  f"author not defect-free {gate['author_not_defect_free']}).",
              f"**Gate result (approved 6-item rule, zero tolerance):** "
              f"**{'PASS' if gate['passed'] else 'FAIL (stop)'}** with {n - k} disagreement(s).",
              '', f"**Drift:** {drift['results']} results, {drift['failed_calls']} failed, resolved models "
                  f"{drift['resolved_models']}, one config hash: {'clean' if drift['clean'] else 'CHECK'}."]
    (OUT / 'gate.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(json.dumps({'gate': {k2: gate[k2] for k2 in ('n', 'agree', 'disagree', 'agreement_proportion', 'kappa', 'passed')},
                      'drift': drift}, indent=1))


if __name__ == '__main__':
    main()