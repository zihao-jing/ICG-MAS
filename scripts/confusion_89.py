"""Confusion tables (true known stage x named stage) on the 89 known-stage cases, judge and audit (statement check),
Gemini and Qwen. $0, reads stored labels only.

Audit statement check (new rule) = old audit stage (b5 2x2 file) with the per-case overrides in
rebuttal/pilots/20261115_sharding_semantic/canonical.json (`changed`). Checked against canonical `confusion_new` and
the canonical accuracy (66 Gemini, 64 Qwen).
    ./.conda-env/bin/python -m scripts.confusion_89
Output: rebuttal/pilots/20261115_confusion_89/{tables.md,tables.json}
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261115_confusion_89'
SRC = {
    'judge_gemini': P / '20261113_attribution_comparison/results_v2.json',   # field judge.stage
    'judge_qwen': P / '20261115_b5_attribution_2x2/judge_qwen.json',         # field stage
    'audit_gemini_old': P / '20261115_b5_attribution_2x2/audit_a_gemini.json',
    'audit_qwen_old': P / '20261115_b5_qwen_design_a/results.json',
    'canonical': P / '20261115_sharding_semantic/canonical.json',
}
KNOWN = ['extraction', 'sharding', 'transmission']
NAMED = ['extraction', 'sharding', 'transmission', 'aggregation', 'uncertain']


def load_items(path, stage_field):
    items = json.loads(path.read_text())['items']
    out = {}
    for x in items:
        if stage_field == 'judge.stage':
            st = (x.get('judge') or {}).get('stage')
        else:
            st = x.get(stage_field)
        out[x['key']] = {'known': x['known_stage'], 'stage': st or 'uncertain', 'population': x.get('population')}
    return out


def table(rows):
    cnt = Counter((r['known'], r['named']) for r in rows)
    n = len(rows)
    lines = ['| true \\ named | ' + ' | '.join(NAMED) + ' | total |', '|---|' + '---:|' * (len(NAMED) + 1)]
    for k in KNOWN:
        cells = [cnt.get((k, c), 0) for c in NAMED]
        lines.append(f'| {k} | ' + ' | '.join(str(x) for x in cells) + f' | {sum(cells)} |')
    tot = [sum(cnt.get((k, c), 0) for k in KNOWN) for c in NAMED]
    lines.append('| total | ' + ' | '.join(str(x) for x in tot) + f' | {n} |')
    correct = sum(cnt.get((k, k), 0) for k in KNOWN)
    return lines, correct, n


def main():
    base = load_items(SRC['judge_gemini'], 'judge.stage')
    keys = set(base)
    data = {
        'judge_gemini': {k: {'known': v['known'], 'named': v['stage']} for k, v in base.items()},
        'judge_qwen': {}, 'audit_gemini': {}, 'audit_qwen': {}}
    jq = load_items(SRC['judge_qwen'], 'stage')
    ag = load_items(SRC['audit_gemini_old'], 'stage')
    aq = load_items(SRC['audit_qwen_old'], 'stage')
    canon = json.loads(SRC['canonical'].read_text())
    for name, src in (('judge_qwen', jq), ('audit_gemini', ag), ('audit_qwen', aq)):
        assert set(src) == keys, name
    for k in keys:
        data['judge_qwen'][k] = {'known': jq[k]['known'], 'named': jq[k]['stage']}
    for name, src, cname in (('audit_gemini', ag, 'gemini'), ('audit_qwen', aq, 'qwen')):
        over = {c['key']: c['new'] for c in canon[cname]['changed']}
        for k in keys:
            new = over.get(k, src[k]['stage']) or 'uncertain'   # None = uncertain in the stored labels
            data[name][k] = {'known': src[k]['known'], 'named': new}
    summary, lines = {}, ['# Confusion tables, 89 known-stage cases (stored labels, $0)', '',
                          'Rows: known stage (injected = transmission; cohort = extraction or sharding). '
                          'Columns: stage named by the method. n = 89 in each table.', '']
    titles = {'judge_gemini': 'Judge, Gemini', 'judge_qwen': 'Judge, Qwen',
              'audit_gemini': 'Audit, statement check, Gemini', 'audit_qwen': 'Audit, statement check, Qwen'}
    srcs = {'judge_gemini': 'rebuttal/pilots/20261113_attribution_comparison/results_v2.json (judge.stage)',
            'judge_qwen': 'rebuttal/pilots/20261115_b5_attribution_2x2/judge_qwen.json (stage)',
            'audit_gemini': 'rebuttal/pilots/20261115_b5_attribution_2x2/audit_a_gemini.json (stage) + overrides in 20261115_sharding_semantic/canonical.json (changed)',
            'audit_qwen': 'rebuttal/pilots/20261115_b5_qwen_design_a/results.json (stage) + overrides in 20261115_sharding_semantic/canonical.json (changed)'}
    for name in ['judge_gemini', 'judge_qwen', 'audit_gemini', 'audit_qwen']:
        rows = [{'key': k, **v} for k, v in data[name].items()]
        tl, correct, n = table(rows)
        summary[name] = {'n': n, 'correct': correct, 'accuracy': round(correct / n, 4)}
        lines += [f'## {titles[name]}', '', f'Source: `{srcs[name]}`', ''] + tl + ['', f'Correct (diagonal): {correct}/{n}', '']
    # check against canonical confusion_new (audit rules)
    chk = {}
    for cname, name in (('gemini', 'audit_gemini'), ('qwen', 'audit_qwen')):
        rows = [v for v in data[name].values()]
        c = Counter(f"{v['known']}->{v['named']}" for v in rows if v['known'] != v['named'])
        chk[cname] = {'match_confusion_new': dict(c) == canon[cname]['confusion_new'],
                      'diag': sum(1 for v in rows if v['known'] == v['named'])}
    summary['check_vs_canonical'] = chk
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tables.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'tables.json').write_text(json.dumps({'summary': summary}, indent=1))
    print(json.dumps(summary, indent=1))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
