"""Build the labelling package for the 92 restored cases plus 40 Opus-checked calibration rows.

No model calls. Reads frozen files only:
- rebuttal/pilots/20261113_restore_source/cases.json (question, gold, model, instance)
- rebuttal/pilots/20261116_restore_equiv_gemini/restore_results.jsonl (restore-arm answer, Gemini verdict)
- rebuttal/pilots/20261116_opus_checker_check/items.json and results.jsonl (40 calibration rows, Opus labels)

Writes iclr2027_rebuttal/labelling/ (visible sheet + instructions) and
iclr2027_rebuttal/labelling/key_do_not_share/ (hidden key: model, arm, checker labels).
"""
import csv
import hashlib
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PILOTS = ROOT / 'rebuttal/pilots'
OUT = ROOT / 'iclr2027_rebuttal/labelling'
KEY = OUT / 'key_do_not_share'
SEED = 2026

CASES = PILOTS / '20261113_restore_source/cases.json'
RESTORE = PILOTS / '20261116_restore_equiv_gemini/restore_results.jsonl'
OPUS_ITEMS = PILOTS / '20261116_opus_checker_check/items.json'
OPUS_RESULTS = PILOTS / '20261116_opus_checker_check/results.jsonl'


def norm(s):
    s = s.lower()
    s = re.sub(r'\b(the|a|an)\b', ' ', s)
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return ' '.join(s.split())


def rule_for(gold):
    return (f'Correct if the answer gives "{gold}" (same entity, number or date; capitalisation, '
            'articles and punctuation do not matter). Incorrect if it gives another answer, '
            'says it cannot tell, or is empty.')


def main():
    cases = {c['key']: c for c in json.loads(CASES.read_text())}
    restore = [json.loads(l) for l in RESTORE.read_text().splitlines() if l.strip()]
    arms = {}
    for r in restore:
        arms.setdefault(r['key'], {})[r['arm']] = r
    rows, hidden = [], {}
    for key in sorted(arms):
        c = cases[key]
        rr = arms[key]['restore']
        assert norm(rr['gold']) == norm(c['gold']), key
        rows.append({'question': c['question'], 'gold_answer': c['gold'], 'answer': rr['answer'],
                     'equivalence_rule': rule_for(c['gold'])})
        hidden[key] = {'kind': 'restored', 'model': c['model'], 'arm': 'restore',
                       'checker_label': rr['verdict'], 'opus_label': None,
                       'source_key': key}
    items = {it['item_id']: it for it in json.loads(OPUS_ITEMS.read_text())}
    opus = {json.loads(l)['item_id']: json.loads(l) for l in OPUS_RESULTS.read_text().splitlines() if l.strip()}
    assert len(items) == 40 and set(items) == set(opus)
    for iid in sorted(items):
        it, o = items[iid], opus[iid]
        t = it['trace']
        rows.append({'question': t['question'], 'gold_answer': t['gold_answer'], 'answer': t['answer_text'],
                     'equivalence_rule': rule_for(t['gold_answer'])})
        hidden[iid] = {'kind': 'calibration', 'model': None, 'arm': None,
                       'checker_label': o['gemini'], 'opus_label': o['opus'], 'source_key': iid}
    keys = list(hidden)
    order = list(range(len(rows)))
    random.Random(SEED).shuffle(order)
    OUT.mkdir(parents=True, exist_ok=True)
    KEY.mkdir(parents=True, exist_ok=True)
    # row ids are assigned in shuffled order; the hidden key maps them back.
    sheet, key_rows = [], []
    all_meta = []
    for i, r in enumerate(rows):
        all_meta.append(r)
    kind_keys = [k for k in hidden]
    # rows list order matches kind_keys order (restored first, then calibration)
    for pos, idx in enumerate(order):
        rid = f'R{pos + 1:03d}'
        r = all_meta[idx]
        sheet.append({'row_id': rid, 'question': r['question'], 'gold_answer': r['gold_answer'],
                      'answer': r['answer'], 'correct_or_incorrect': '',
                      'equivalence_rule': r['equivalence_rule']})
        k = kind_keys[idx]
        key_rows.append({'row_id': rid, **hidden[k]})
    with (OUT / 'labeller_sheet.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0].keys()))
        w.writeheader()
        w.writerows(sheet)
    (KEY / 'hidden_key.json').write_text(json.dumps({'seed': SEED, 'shuffle': 'random.Random(seed).shuffle over row order',
                                                     'n_rows': len(sheet), 'rows': key_rows}, indent=1))
    digest = hashlib.sha256((KEY / 'hidden_key.json').read_bytes()).hexdigest()
    print('rows', len(sheet), 'restored', sum(1 for k in key_rows if k['kind'] == 'restored'),
          'calibration', sum(1 for k in key_rows if k['kind'] == 'calibration'), 'key sha256', digest)


if __name__ == '__main__':
    main()
