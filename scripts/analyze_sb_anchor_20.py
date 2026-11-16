"""Silo-Bench checks for the returned 20-instance anchor, and the E1 anchor split by benchmark.

Reads (read-only):
  rebuttal/annotation/packets_20261110/returns/SB_anchor/annotator_*.jsonl
  rebuttal/pilots/20261110_packets/SB_anchor_private_map.json
  rebuttal/results/batch1/E1_judge_sealed/outputs/*.json
  rebuttal/results/batch1/E4_pool_matcher/matcher/*.json
  rebuttal/results/batch1/E1/anchor_agreement_rows.jsonl

Writes: rebuttal/results/batch1/SB_anchor_20/analysis.json and .md
Descriptive only: no pass/fail threshold. 95% CIs are percentile instance-cluster bootstrap,
2,000 draws, seed 42. The lexical rule is `align_gold_to_transmitted`, unchanged.
"""
import json, random
from collections import Counter, defaultdict
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted

RET = Path('rebuttal/annotation/packets_20261110/returns/SB_anchor')
PMAP = Path('rebuttal/pilots/20261110_packets/SB_anchor_private_map.json')
JUDGE = Path('rebuttal/results/batch1/E1_judge_sealed/outputs')
MATCHER = Path('rebuttal/results/batch1/E4_pool_matcher/matcher')
ANCHOR_ROWS = Path('rebuttal/results/batch1/E1/anchor_agreement_rows.jsonl')
OUT = Path('rebuttal/results/batch1/SB_anchor_20')
DRAWS, SEED = 2000, 42
SB8 = ['I-02_n5', 'I-08_n5', 'I-09_n10', 'II-13_n10',
       'III-24_n5', 'III-27_n5', 'III-29_n5', 'III-30_n10']


def kappa(rows, ka, kb, cats):
    n = sum(r['weight'] for r in rows)
    if not n:
        return None
    ca, cb = Counter(), Counter()
    agree = 0.0
    for r in rows:
        w = r['weight']; ca[r[ka]] += w; cb[r[kb]] += w; agree += w * (r[ka] == r[kb])
    pe = sum(ca[c] * cb[c] for c in cats) / n ** 2
    return None if abs(1 - pe) < 1e-12 else (agree / n - pe) / (1 - pe)


def ac1(rows, ka, kb, cats):
    n = sum(r['weight'] for r in rows)
    if not n:
        return None
    counts = Counter(); agree = 0.0
    for r in rows:
        w = r['weight']; counts[r[ka]] += w / 2; counts[r[kb]] += w / 2; agree += w * (r[ka] == r[kb])
    q = len(cats)
    pe = sum((counts[c] / n) * (1 - counts[c] / n) for c in cats) / (q - 1)
    return None if abs(1 - pe) < 1e-12 else (agree / n - pe) / (1 - pe)


def rate(rows, fn):
    n = sum(r['weight'] for r in rows)
    return sum(r['weight'] * fn(r) for r in rows) / n if n else None


def boot(rows, fn):
    by = defaultdict(list)
    for r in rows:
        by[r['cluster']].append(r)
    keys = list(by)
    if not keys:
        return {'estimate': None, 'lo': None, 'hi': None, 'valid_draws': 0}
    rng = random.Random(SEED)
    vals = []
    for _ in range(DRAWS):
        draw = []
        for _ in keys:
            draw += by[keys[rng.randrange(len(keys))]]
        try:
            v = fn(draw)
        except (ZeroDivisionError, ValueError):
            v = None
        if v is not None:
            vals.append(v)
    if not vals:
        return {'estimate': fn(rows), 'lo': None, 'hi': None, 'valid_draws': 0}
    vals.sort()
    return {'estimate': fn(rows), 'lo': vals[int(0.025 * len(vals))],
            'hi': vals[int(0.975 * len(vals)) - 1], 'valid_draws': len(vals)}


def block(rows, ka, kb, cats, label):
    return {'label': label, 'rows': len(rows), 'clusters': len({r['cluster'] for r in rows}),
            'agreement': boot(rows, lambda d: rate(d, lambda r: r[ka] == r[kb])),
            'kappa': boot(rows, lambda d: kappa(d, ka, kb, cats)),
            'counts': dict(Counter(f'{r[ka]}|{r[kb]}' for r in rows))}


def bin3(x):
    return 'correct' if x == 'correct' else ('defect' if x in
            ('reached_but_unused', 'lost', 'exclude_partial', 'DEFECT') else None)


def load_new():
    pm = json.loads(PMAP.read_text())
    labels = defaultdict(list)
    traces = {}
    for p in sorted(RET.glob('annotator_*.jsonl')):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            m = pm[r['item_id']]
            key = (m['instance_id'], m['model'])
            labels[key].append(r)
            traces[key] = r['trace']
    return labels, traces


def main():
    labels, traces = load_new()
    assert len(traces) == 60, len(traces)
    judge = {}
    for p in JUDGE.glob('*.json'):
        d = json.loads(p.read_text())
        judge[(d['instance_id'], d['model'])] = d
    matcher = {}
    for p in MATCHER.glob('*.json'):
        d = json.loads(p.read_text())
        matcher[(d['instance_id'], d['model'])] = d

    # trace rows: one per (instance, model), author pair must agree; both labels retained as pairs
    pair_rows, author_rows, lexical = [], [], []
    for key, rs in sorted(labels.items()):
        inst, model = key
        a, b = rs[0]['answers']['binary_call'], rs[1]['answers']['binary_call']
        au, bu = ('correct' if a == 'CORRECT' else 'defect'), ('correct' if b == 'CORRECT' else 'defect')
        assert au == bu, key
        t = traces[key]
        board = t['checkpoints']['board']
        unit_text = [u['text'] for u in board]
        facts = json.loads(rs[0]['answers']['critical_facts_json'])
        covered = []
        for f in facts:
            covered.append(align_gold_to_transmitted([(0, f)], unit_text)[0]['covered'])
        lex = 'correct' if all(covered) else 'defect'
        au_rows = []
        for which in (0, 1):
            lab = rs[which]['answers']['binary_call']
            au = 'correct' if lab == 'CORRECT' else 'defect'
            j = judge.get(key)
            m = matcher.get(key)
            row = {'cluster': inst, 'protocol': traces[key]['instance_id'].split('_n')[1],
                   'author': au}
            if j and j.get('valid') and (j.get('parsed') or {}).get('binary_call'):
                row['judge'] = bin3((j['parsed'] or {}).get('binary_call'))
            if m.get('status') == 'ok' and m.get('trace_call'):
                row['matcher'] = bin3(m['trace_call'])
            row['lexical'] = lex
            au_rows.append(row)
        pair_rows += au_rows
        author_rows.append({'cluster': inst, 'weight': 1.0, 'a': au, 'b': bu})
        lexical.append({'cluster': inst, 'facts': len(facts), 'covered': sum(covered),
                        'all_covered': all(covered), 'author': au,
                        'protocol': traces[key]['instance_id'].split('_n')[1]})

    def withw(rs):
        return [dict(r, weight=1.0) for r in rs]

    out = {'traces': len(traces), 'instances': len({k[0] for k in traces}),
           'draws': DRAWS, 'seed': SEED, 'note': 'descriptive; no threshold'}
    out['author_author'] = block(withw(author_rows), 'a', 'b', ('correct', 'defect'),
                                 'author–author trace binary (60 traces, 20 instances)')
    jp = withw([r for r in pair_rows if r.get('judge')])
    mp = withw([r for r in pair_rows if r.get('matcher')])
    lp = withw([r for r in pair_rows if r.get('lexical')])
    out['judge_author'] = block(jp, 'judge', 'author', ('correct', 'defect'),
                                'reference judge – author trace binary')
    out['matcher_author'] = block(mp, 'matcher', 'author', ('correct', 'defect'),
                                  'frozen matcher – author trace binary')
    out['lexical_author'] = block(lp, 'lexical', 'author', ('correct', 'defect'),
                                  'lexical rule (all facts covered → correct) – author trace binary')
    cov = sum(r['covered'] for r in lexical) / sum(r['facts'] for r in lexical)
    out['lexical'] = {'facts': sum(r['facts'] for r in lexical),
                      'covered': sum(r['covered'] for r in lexical), 'covered_rate': cov,
                      'traces_all_covered': sum(r['all_covered'] for r in lexical),
                      'traces': len(lexical)}
    out['judge_coverage'] = {'pairs': len(pair_rows), 'valid': len(jp),
                             'missing': len(pair_rows) - len(jp)}
    out['matcher_coverage'] = {'pairs': len(pair_rows), 'valid': len(mp),
                               'missing': len(pair_rows) - len(mp)}
    out['author_label_dist'] = dict(Counter(r['a'] for r in author_rows))
    out['judge_label_dist'] = dict(Counter(r['judge'] for r in jp))
    out['matcher_label_dist'] = dict(Counter(r['matcher'] for r in mp))
    out['by_benchmark'] = {}
    for n in ('5', '10'):
        rs = [r for r in author_rows if r['cluster'].endswith('_n' + n)]
        out['by_benchmark']['SB-' + n] = block(withw(rs), 'a', 'b', ('correct', 'defect'),
                                               f'SB-{n} author–author')

    # 8-instance overlap with the E1 anchor
    pm2 = json.loads(Path('rebuttal/pilots/20261108_review8/packet_private_map.json').read_text())
    old = defaultdict(list)
    for p in Path('rebuttal/annotation/returns').glob('E1anchor_*_labelling-v1.0.json'):
        for r in json.load(open(p)):
            if r['item_id'] in pm2:
                m = pm2[r['item_id']]
                old[(m['instance_id'], m['model'])].append(r['answers']['binary_call'])
    ov = []
    for key in labels:
        if key[0] in SB8 and key in old:
            newlab = 'correct' if labels[key][0]['answers']['binary_call'] == 'CORRECT' else 'defect'
            ob = old[key]
            ob_bin = ['correct' if v == 'correct' else 'defect' for v in ob]
            assert ob_bin[0] == ob_bin[1], key
            oldlab = ob_bin[0]
            ov.append({'cluster': key[0], 'a': newlab, 'b': oldlab, 'weight': 1.0})
    out['anchor_overlap_8'] = block(ov, 'a', 'b', ('correct', 'defect'),
                                    'new 20-instance anchor – E1 anchor (8 instances, 24 traces)')

    # E1 anchor rows split by benchmark
    rows = [json.loads(l) for l in ANCHOR_ROWS.read_text().splitlines() if l.strip()]
    def narrow(r):
        return {'cluster': r['cluster'], 'weight': r['weight'], 'a': r['a'], 'b': r['b'],
                'benchmark': 'SB' if r['stratum'].startswith('SB') else 'MQ'}
    split = {}
    for kind in sorted({(r['row'], r['col']) for r in rows}):
        rs = [narrow(r) for r in rows if (r['row'], r['col']) == kind]
        for bm in ('MQ', 'SB', 'all'):
            x = [r for r in rs if bm == 'all' or r['benchmark'] == bm]
            cats = ('yes', 'no') if kind[1] == 'presence' else (
                ('absent', 'faithful', 'partial', 'distorted') if kind[1] == 'fidelity' else
                ('correct', 'reached_but_unused', 'lost'))
            entry = {'rows': len(x), 'clusters': len({r['cluster'] for r in x}),
                 'agreement': boot(x, lambda d: rate(d, lambda r: r['a'] == r['b'])),
                 'kappa': boot(x, lambda d: kappa(d, r'a', r'b', cats))}
            if kind[1] == 'fidelity':
                entry['ac1'] = boot(x, lambda d: ac1(d, r'a', r'b', cats))
            split[f'{kind[0]} | {kind[1]} | {bm}'] = entry
    out['anchor_by_benchmark'] = split

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    def fmt(x):
        return 'NA' if x is None else f'{x:.3f}'
    def ci(d):
        return f"{fmt(d['estimate'])} [{fmt(d['lo'])}, {fmt(d['hi'])}] ({d['valid_draws']})"
    L = ['# Silo-Bench 20-instance anchor: lexical, judge and matcher checks', '',
         'Descriptive only; no pass/fail threshold. Percentile instance-cluster bootstrap, '
         '2,000 draws, seed 42. Lexical rule `align_gold_to_transmitted`, unchanged.', '']
    L += [f"- Traces: {out['traces']} ({out['instances']} instances); author labels: {out['author_label_dist']}"]
    L += [f"- Author–author agreement {ci(out['author_author']['agreement'])}; κ {ci(out['author_author']['kappa'])}"]
    L += [f"- Judge–author: {out['judge_coverage']['valid']}/{out['judge_coverage']['pairs']} pairs; "
          f"agreement {ci(out['judge_author']['agreement'])}; κ {ci(out['judge_author']['kappa'])}"]
    L += [f"- Matcher–author: {out['matcher_coverage']['valid']}/{out['matcher_coverage']['pairs']} pairs; "
          f"agreement {ci(out['matcher_author']['agreement'])}; κ {ci(out['matcher_author']['kappa'])}"]
    L += [f"- Lexical–author: agreement {ci(out['lexical_author']['agreement'])}; "
          f"κ {ci(out['lexical_author']['kappa'])}; fact coverage "
          f"{out['lexical']['covered']}/{out['lexical']['facts']} = {out['lexical']['covered_rate']:.3f}"]
    L += [f"- 8-instance overlap with the E1 anchor: agreement {ci(out['anchor_overlap_8']['agreement'])}; "
          f"κ {ci(out['anchor_overlap_8']['kappa'])}"]
    L += ['', '## Split by benchmark (SB-5 / SB-10)', '']
    for k, v in out['by_benchmark'].items():
        L += [f"- {k}: agreement {ci(v['agreement'])}; κ {ci(v['kappa'])}"]
    L += ['', '## E1 anchor split by benchmark (recomputed from the saved rows)', '']
    for k, v in split.items():
        tail = f"; AC1 {ci(v['ac1'])}" if 'ac1' in v else ''
        L += [f"- {k}: n={v['rows']}, clusters={v['clusters']}; agreement {ci(v['agreement'])}; "
              f"κ {ci(v['kappa'])}{tail}"]
    (OUT / 'analysis.md').write_text('\n'.join(L) + '\n')
    print(json.dumps({k: out[k] for k in ('traces', 'instances', 'author_label_dist',
                                          'anchor_overlap_8', 'lexical')}, indent=1, ensure_ascii=False))
    print('\n'.join(L))


if __name__ == '__main__':
    main()