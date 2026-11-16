"""Answer-equivalence re-score of the aggregation repair (Paper Table 9, MuSiQue rows, 213 cases).

Same instrument as the distortion restore row: the frozen prompt
`rebuttal/pilots/20261112_answer_equiv/answer_equiv_v1.json` on google/gemini-3.6-flash, whose validation gate
passed in `rebuttal/pilots/20261116_restore_equiv_gemini/validation_summary.json`. Both the original answer and the
stronger-aggregator (Gemini terminal) answer are scored, so a case counts as a failure only if the original answer is
not equivalent, and as recovered only if the repaired answer is. Stored answers only; no new aggregation calls.

    ./.conda-env/bin/python -m scripts.agg_repair_equiv --run
    ./.conda-env/bin/python -m scripts.agg_repair_equiv --report
"""
import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import scripts.restore_equiv_gemini as R

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'iclr2027_paper/experiments/repair/results/aggregation_stage_swap_20260926/comparison_per_case.csv'
OUT = ROOT / 'rebuttal/pilots/20261116_agg_repair_equiv'
RESULTS = OUT / 'results.jsonl'
R.OUT = OUT
R.CALLS = OUT / 'calls.jsonl'
R.CAP = 0.80


def cases():
    gold = {}
    for name in ('musique_ans_v1.0_dev.jsonl', 'musique_full_v1.0_dev.jsonl'):
        for l in (ROOT / 'data/musique' / name).read_text().splitlines():
            if l.strip():
                d = json.loads(l)
                gold.setdefault(d['id'], (d['question'], d['answer']))
    out = []
    for r in csv.DictReader(SRC.open()):
        if r['dataset'] != 'musique':
            continue
        q, g = gold[r['instance_id']]
        out.append({'key': f"{r['setting']}|{r['instance_id']}", 'question': q, 'gold': g,
                    'original': r['original_prediction'], 'repair': r['terminal_gemini_prediction'],
                    'original_f1': float(r['original_score']), 'repair_f1': float(r['terminal_gemini_score'])})
    return out


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    assert json.loads((ROOT / 'rebuttal/pilots/20261116_restore_equiv_gemini/validation_summary.json')
                      .read_text())['gate_pass']
    spec = R.load_prompt()
    done = set()
    if RESULTS.exists():
        done = {(json.loads(l)['key'], json.loads(l)['arm']) for l in RESULTS.read_text().splitlines() if l.strip()}
    jobs = [(c, arm) for c in cases() for arm in ('original', 'repair') if (c['key'], arm) not in done]
    total = R.spent()
    print(json.dumps({'cases': len(cases()), 'jobs': len(jobs), 'spent_before': round(total, 6)}))
    for c, arm in jobs:
        ans = c[arm].strip() or '(empty)'
        rec, total = R.call(f"{arm}:{c['key']}", c['question'], c['gold'], ans, spec, total)
        if rec is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            return
        with RESULTS.open('a') as f:
            f.write(json.dumps({'key': c['key'], 'arm': arm, 'answer': c[arm], 'gold': c['gold'],
                                'verdict': rec['verdict']}, ensure_ascii=False) + '\n')
    print(json.dumps({'spent_total': round(R.spent(), 6)}))


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def report():
    v = {}
    recovered_parse = []
    for l in RESULTS.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            v[(r['key'], r['arm'])] = r['verdict']
    # Truncated outputs (max_tokens) keep an unambiguous verdict field: read it with a looser pattern.
    import re
    for l in R.CALLS.read_text().splitlines():
        if l.strip():
            c = json.loads(l)
            if c.get('event') == 'result' and c.get('verdict') is None and c.get('content'):
                m = re.search(r'"verdict"\s*:\s*"(EQUIVALENT|NOT_EQUIVALENT)"', c['content'])
                arm, key = c['key'].split(':', 1)
                if m and v.get((key, arm)) is None:
                    v[(key, arm)] = m.group(1)
                    recovered_parse.append(c['key'])
    cs = cases()
    unparsed = sum(1 for c in cs for a in ('original', 'repair') if v.get((c['key'], a)) is None)
    fails = [c for c in cs if v.get((c['key'], 'original')) != 'EQUIVALENT']
    rec = [c for c in fails if v.get((c['key'], 'repair')) == 'EQUIVALENT']
    lo, hi = wilson(len(rec), len(fails))
    by = {}
    for c in fails:
        s = c['key'].split('|')[0]
        by.setdefault(s, [0, 0])
        by[s][1] += 1
        by[s][0] += v.get((c['key'], 'repair')) == 'EQUIVALENT'
    exact = sum(c['repair_f1'] >= 0.999 for c in cs)
    summ = {'cases': len(cs), 'original_equivalent': len(cs) - len(fails), 'failures': len(fails),
            'recovered': len(rec), 'share': round(len(rec) / len(fails), 4), 'wilson95': [round(lo, 4), round(hi, 4)],
            'by_setting': by, 'unparsed_count_as_not_equivalent': unparsed, 'verdicts_read_from_truncated_output': len(recovered_parse),
            'exact_f1_1_recovered_all213': exact, 'spend_total_usd': round(R.spent(), 6)}
    (OUT / 'score.json').write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.run:
        run()
    if a.report:
        report()
