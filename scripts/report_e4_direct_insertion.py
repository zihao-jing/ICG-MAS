"""Report for the E4 direct-insertion run: counts, failures, manipulation checks, volume match,
cost. Reads no answers; writes no contrast.

    python -m scripts.report_e4_direct_insertion
"""
import json
from pathlib import Path

from src.audit.pilot_common import read_jsonl

CFG = Path('rebuttal/pilots/configs/E4-direct-insertion.json')
OUT = Path('rebuttal/results/batch1/E4_direct_insertion')
PLAN = Path('rebuttal/pilots/20261110_e4_insert/insertion_plan.json')


def main():
    cfg = json.loads(CFG.read_text())
    plan = json.loads(PLAN.read_text())
    calls = read_jsonl(OUT / 'calls.jsonl')
    results = [r for r in calls if r['event'] == 'result']
    failed = [r for r in results if not r.get('success')]
    summary = json.loads((OUT / 'summary.json').read_text())
    raw = {}
    for p in sorted((OUT / 'raw').glob('*.json')):
        recs = json.loads(p.read_text())
        raw[recs[0]['trace_id']] = recs
    rows, checks = [], []
    for case in plan['cases']:
        recs = {r['arm']: r for r in raw.get(case['trace_id'], []) if r.get('arm')}
        r = recs.get('R-ins') or {}
        v = recs.get('V-ins') or {}
        cm = r.get('control_match') or v.get('control_match') or {}
        rows.append({'instance': case['instance_id'], 'model': case['model'],
                     'protocol': case['benchmark'], 'target_tokens': case['repair_tokens'],
                     'control_tokens': case['control_tokens'], 'ratio': case['ratio'],
                     'volume_matched': bool(case['volume_matched']),
                     'manip_r': r.get('manipulation_check'), 'manip_v': v.get('manipulation_check'),
                     'answer_r': 'answer' in r, 'answer_v': 'answer' in v,
                     'failed_r': bool(r.get('failed')), 'failed_v': bool(v.get('failed')),
                     'donor_fallback': case['donor_fallback']})
        checks.append(rows[-1])
    n = len(rows)
    md = ['# E4 direct insertion: run report', '',
          'Read before any contrast. Counts, failures, manipulation checks, volume match and cost only;',
          'no answer or score is read here.', '',
          'R-ins appends the targeted-fact text as one board unit; it is a **positive control**, and',
          'its manipulation check passes by construction. V-ins appends a donor passage matched to its',
          'token count.', '',
          '| Case | Model | Setting | R-ins tokens | V-ins tokens | Ratio | Volume match | R-ins manipulation | V-ins manipulation | Donor fallback |',
          '|---|---|---|---:|---:|---:|---|---|---|---|']
    for x in rows:
        md.append(f"| {x['instance']} | {x['model']} | {x['protocol']} | {x['target_tokens']} | "
                  f"{x['control_tokens']} | {x['ratio']:.2f} | {'yes' if x['volume_matched'] else 'NO'} | "
                  f"{'pass' if x['manip_r'] else 'FAIL' if x['manip_r'] is False else 'not run'} | "
                  f"{'pass' if x['manip_v'] else 'FAIL' if x['manip_v'] is False else 'not run'} | "
                  f"{'yes' if x['donor_fallback'] else 'no'} |")
    md += ['', '## Counts', '',
           f'- Cases: **{n}**; planned calls 34; dispatched **{len(results)}**; failed **{len(failed)}**.',
           f'- R-ins manipulation check: **{sum(x["manip_r"] is True for x in rows)} of {n} pass**; '
           f'V-ins: **{sum(x["manip_v"] is True for x in rows)} of {n} pass**.',
           f'- Volume matched (equal added-unit count and ±10% added tokens): '
           f'**{sum(x["volume_matched"] for x in rows)} of {n}**.',
           f'- Unmatched controls: **{sum(not x["volume_matched"] for x in rows)}**.',
           f'- Donor fallback cases (donor is a support agent): **{sum(x["donor_fallback"] for x in rows)} of {n}**.',
           f'- Cost: **${summary["cost_usd"]:.6f}** against the ${cfg["cost_cap_usd"]:.2f} cap; '
           f'calls {summary["calls"]} of the {cfg["max_calls"]} cap.',
           f'- First/last call (from the ledger): {results[0]["time"] if results else "n/a"} / '
           f'{results[-1]["time"] if results else "n/a"} (epoch seconds).',
           '', 'Failed calls:', '']
    if failed:
        for f in failed:
            md.append(f"- `{f['key']}` on `{f['model_id']}`: {f.get('error')}")
    else:
        md.append('- none.')
    md += ['', 'No contrast, answer or score is in this file.', '']
    (OUT / 'insertion_report.md').write_text('\n'.join(md))
    (OUT / 'checks.json').write_text(json.dumps({'cases': n, 'calls': len(results),
                                                'failed': len(failed),
                                                'manip_r_pass': sum(x['manip_r'] is True for x in rows),
                                                'manip_v_pass': sum(x['manip_v'] is True for x in rows),
                                                'volume_matched': sum(x['volume_matched'] for x in rows),
                                                'donor_fallback': sum(x['donor_fallback'] for x in rows),
                                                'cost_usd': summary['cost_usd'],
                                                'cost_cap_usd': cfg['cost_cap_usd'],
                                                'rows': rows}, indent=1, sort_keys=True) + '\n')
    print(json.dumps({'cases': n, 'calls': len(results), 'failed': len(failed),
                      'manip_r_pass': sum(x['manip_r'] is True for x in rows),
                      'manip_v_pass': sum(x['manip_v'] is True for x in rows),
                      'volume_matched': sum(x['volume_matched'] for x in rows),
                      'cost_usd': summary['cost_usd']}, indent=1))


if __name__ == '__main__':
    main()