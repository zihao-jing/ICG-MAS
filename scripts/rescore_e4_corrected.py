"""Re-score the archived E4 arms with the corrected scorer (R1).

The originals in cases.json / case_sheets.md stay unchanged. This script
recomputes every arm with the current normalize() (punctuation -> space),
uses silobench_exact_match for Silo-Bench cases, and writes only the rows
that changed to rebuttal/diagnosis/corrected_scores.md (+ .json).

No model calls.

    ./run.sh python -m scripts.rescore_e4_corrected
"""
import json
import re
import string
from pathlib import Path

from src.eval.evaluate import answer_f1, normalize
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / 'rebuttal/diagnosis/cases.json'
OUT = ROOT / 'rebuttal/diagnosis/corrected_scores.md'
OUT_JSON = ROOT / 'rebuttal/diagnosis/corrected_scores.json'


def normalize_old(text):
    """The scorer that produced the archived numbers: punctuation deleted."""
    text = text.lower()
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text.split()


def f1_with(pred, gold, fn):
    # answer_f1 reads the module global, so patch the module under test
    import src.eval.evaluate as ev
    orig = ev.normalize
    ev.normalize = fn
    try:
        return ev.answer_f1(pred, {'answer': gold, 'answer_aliases': []})
    finally:
        ev.normalize = orig


def score(pred, gold, benchmark):
    old_f1 = round(f1_with(pred, gold, normalize_old), 3)
    new_f1 = round(answer_f1(pred, {'answer': gold, 'answer_aliases': []}), 3)
    em = round(silobench_exact_match(pred, {'answer': gold, 'answer_aliases': []}), 3)
    metric = 'em' if benchmark.startswith('SB') else 'f1'
    return {'old_f1': old_f1, 'new_f1': new_f1, 'em': em, 'metric': metric}


def main():
    cases = json.loads(CASES.read_text())
    changed, all_rows = [], []
    ins_arms = {'R-ins', 'V-ins'}
    groups = [
        ('Missing-fact repair', 'extraction', cases['extraction'], False),
        ('Direct insertion', 'insertion', cases['extraction'], True),
        ('Selection cohort', 'selection', cases['selection'], None),
        ('Distortion repair', 'distortion', cases['distortion'], None),
    ]
    for title, kind, rows, ins_only in groups:
        for r in rows:
            benchmark = r.get('benchmark', '')
            for arm, a in r['answers'].items():
                if ins_only is not None and (arm in ins_arms) != ins_only:
                    continue
                pred = a.get('pred') or extract_answer(a['answer'])
                s = score(pred, r['gold'], benchmark)
                old = a['em'] if s['metric'] == 'em' else a['f1']
                new = s['em'] if s['metric'] == 'em' else s['new_f1']
                row = {'experiment': title, 'kind': kind, 'instance_id': r['instance_id'],
                       'model': r.get('model', ''), 'trace_id': r['trace_id'], 'arm': arm,
                       'pred': pred, 'metric': s['metric'], 'old': old, 'new': new,
                       'old_f1': s['old_f1'], 'new_f1': s['new_f1'], 'em': s['em']}
                all_rows.append(row)
                if round(old, 3) != round(new, 3):
                    changed.append(row)
    OUT_JSON.write_text(json.dumps({'changed': changed, 'n_arms': len(all_rows)}, indent=1) + '\n')
    lines = ['# Corrected scores (R1)\n',
             'The scorer now maps punctuation to a space; Silo-Bench rows use exact '
             'match. Originals are unchanged in `cases.json` and `case_sheets.md`. '
             'This table lists every arm whose score changed.\n',
             f'Arms compared: {len(all_rows)}; changed: {len(changed)}.\n',
             '| experiment | case | model | arm | pred | metric | old | new |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in changed:
        pred = ' '.join((r['pred'] or '').split())
        pred = pred if len(pred) <= 90 else pred[:87] + '...'
        model = r['model'].split('/')[-1] if '/' in r['model'] else r['model']
        lines.append(f"| {r['experiment']} | {r['instance_id']} | {model} | {r['arm']} | "
                     f"{pred} | {r['metric']} | {r['old']:.3f} | {r['new']:.3f} |")
    OUT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'arms': len(all_rows), 'changed': len(changed),
                      'by_kind': {k: sum(r['kind'] == k for r in changed)
                                  for k in ('extraction', 'insertion', 'selection', 'distortion')}}))


if __name__ == '__main__':
    main()