"""Contrast for the E4 direct-insertion run, after the run report.

Included pairs: both arms answered, both manipulation checks pass, and the plan's volume match is
true. Paired correctness difference R-ins minus V-ins; 95% percentile CI by instance-cluster
bootstrap (2,000 draws, seed 42). Descriptive when fewer than 5 pairs. No table or draft is edited.

    python -m scripts.analyze_e4_direct_insertion
"""
import json
from pathlib import Path

from src.audit.pilot_common import cluster_bootstrap, read_jsonl
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

OUT = Path('rebuttal/results/batch1/E4_direct_insertion')
ACTIONS = Path('rebuttal/pilots/20261110_e4_phase1/actions_phase1.json')
DRAWS, SEED = 2000, 42


def score(answer, gold):
    return 1.0 if answer and answer_f1(extract_answer(answer), gold) >= 1.0 else 0.0


def boot(rows):
    stat = lambda rs: sum(r['delta'] for r in rs) / len(rs) if rs else None
    return cluster_bootstrap(rows, stat, draws=DRAWS, seed=SEED)


def main():
    actions = {r['trace_id']: r for r in json.loads(ACTIONS.read_text())
               if r['group'] == 'extraction_omission'}
    checks = json.loads((OUT / 'checks.json').read_text())
    by_case = {r['instance']: r for r in checks['rows']}
    raw = {}
    for p in sorted((OUT / 'raw').glob('*.json')):
        recs = json.loads(p.read_text())
        raw[recs[0]['trace_id']] = {r['arm']: r for r in recs if r.get('arm')}
    cases, excluded = [], []
    for tid, recs in raw.items():
        a = actions[tid]
        gold = {'answer': a['gold_answer'], 'answer_aliases': a.get('answer_aliases', [])}
        r, v = recs.get('R-ins') or {}, recs.get('V-ins') or {}
        ok = ('answer' in r and 'answer' in v and r.get('manipulation_check') is True
              and v.get('manipulation_check') is True and (r.get('control_match') or {}).get('matched'))
        if not ok:
            excluded.append({'instance': a['instance_id'], 'trace_id': tid,
                             'reason': 'missing arm, manipulation check, or volume match'})
            continue
        rs, vs = score(r['answer'], gold), score(v['answer'], gold)
        cases.append({'instance_id': a['instance_id'], 'protocol': a['benchmark'],
                      'model': a['model'], 'r_ins': rs, 'v_ins': vs, 'delta': rs - vs,
                      'r_answer': extract_answer(r['answer']), 'v_answer': extract_answer(v['answer'])})
    out = {'pairs': len(cases), 'excluded': excluded,
           'r_ins_correct': int(sum(c['r_ins'] for c in cases)),
           'v_ins_correct': int(sum(c['v_ins'] for c in cases)),
           'wins': sum(c['delta'] > 0 for c in cases), 'losses': sum(c['delta'] < 0 for c in cases),
           'ties': sum(c['delta'] == 0 for c in cases), 'overall': boot(cases)}
    out['by_protocol'] = {}
    for b in ('MQ', 'SB-5', 'SB-10'):
        rs = [c for c in cases if c['protocol'] == b]
        out['by_protocol'][b] = {'pairs': len(rs), 'clusters': len({c['instance_id'] for c in rs}),
                                 'r_ins_correct': int(sum(c['r_ins'] for c in rs)),
                                 'v_ins_correct': int(sum(c['v_ins'] for c in rs)),
                                 'wins': sum(c['delta'] > 0 for c in rs),
                                 'losses': sum(c['delta'] < 0 for c in rs),
                                 'ties': sum(c['delta'] == 0 for c in rs),
                                 'contrast': boot(rs) if rs else None,
                                 'descriptive': len(rs) < 5}
    (OUT / 'contrast.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    md = ['# E4 direct insertion: contrast', '',
          'After the run report. Paired R-ins minus V-ins correctness on pairs that pass both',
          'manipulation checks and the ±10% volume match. Descriptive when fewer than 5 pairs.', '',
          f"- Included pairs: **{out['pairs']}**; excluded: {len(excluded)}.",
          f"- R-ins correct: **{out['r_ins_correct']} of {out['pairs']}**; V-ins correct: "
          f"**{out['v_ins_correct']} of {out['pairs']}**; wins/losses/ties: "
          f"{out['wins']}/{out['losses']}/{out['ties']}.", '',
          '| Setting | Pairs | Clusters | R-ins correct | V-ins correct | W/L/T | Mean Δ [95% CI] |',
          '|---|---:|---:|---:|---:|---|---|']
    cells = [('all', out['overall'], out['pairs'], len({c['instance_id'] for c in cases}),
              out['r_ins_correct'], out['v_ins_correct'], out['wins'], out['losses'], out['ties'])]
    for b, v in out['by_protocol'].items():
        if v['contrast'] is not None:
            cells.append((b, v['contrast'], v['pairs'], v['clusters'], v['r_ins_correct'],
                          v['v_ins_correct'], v['wins'], v['losses'], v['ties']))
    for name, cell, pairs, clusters, r_ok, v_ok, w, l, t in cells:
        desc = ' (descriptive)' if name != 'all' and out['by_protocol'][name]['descriptive'] else ''
        md.append(f"| {name} | {pairs} | {clusters} | {r_ok} | {v_ok} | {w}/{l}/{t} | "
                  f"{cell['estimate']:.3f} [{cell['lo']:.3f}, {cell['hi']:.3f}]{desc} |")
    md += ['', 'Per-case:', '',
           '| Case | Setting | R-ins | V-ins | Δ |', '|---|---|---:|---:|---:|']
    for c in cases:
        md.append(f"| {c['instance_id']} | {c['protocol']} | {int(c['r_ins'])} | {int(c['v_ins'])} | "
                  f"{int(c['delta']):+d} |")
    (OUT / 'contrast.md').write_text('\n'.join(md) + '\n')
    print(json.dumps({k: out[k] for k in ('pairs', 'r_ins_correct', 'v_ins_correct', 'wins',
                                           'losses', 'ties', 'overall')}, indent=1))
    print(json.dumps(out['by_protocol'], indent=1))


if __name__ == '__main__':
    main()