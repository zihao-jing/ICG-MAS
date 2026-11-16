"""Analyse the paper-evaluator validation (Paper-evaluators-v1).

  python -m scripts.analyze_paper_evaluators                 lexical (a) on all eligible rows, no calls
  python -m scripts.analyze_paper_evaluators --rows FILE     lexical + judge on a rows.jsonl (pilot/full)

Weighted, within-stratum instance-cluster bootstrap, 2,000 draws, seed 42, percentile 95% CI. The
lexical rule is `align_gold_to_transmitted` as run by `run_paper_evaluators`; nothing is recomputed
with a different rule.
"""
import argparse, json, random
from collections import Counter, defaultdict
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted
from scripts.run_paper_evaluators import rows, COLLAPSE, RET, PMAP, N80

DRAWS, SEED = 2000, 42
OUT = Path('rebuttal/results/batch1/E1')


def kappa(rows, ka, kb, cats):
    total = sum(r['weight'] for r in rows)
    if not total:
        return None
    ca, cb = Counter(), Counter()
    agree = 0.0
    for r in rows:
        w = r['weight']; ca[r[ka]] += w; cb[r[kb]] += w; agree += w * (r[ka] == r[kb])
    pe = sum(ca[c] * cb[c] for c in cats) / total ** 2
    return None if abs(1 - pe) < 1e-12 else (agree / total - pe) / (1 - pe)


def ac1(rows, ka, kb, cats):
    total = sum(r['weight'] for r in rows)
    if not total:
        return None
    counts = Counter(); agree = 0.0
    for r in rows:
        w = r['weight']; counts[r[ka]] += w / 2; counts[r[kb]] += w / 2; agree += w * (r[ka] == r[kb])
    q = len(cats); pe = sum((counts[c] / total) * (1 - counts[c] / total) for c in cats) / (q - 1)
    return None if abs(1 - pe) < 1e-12 else (agree / total - pe) / (1 - pe)


def rate(rows, fn):
    total = sum(r['weight'] for r in rows)
    return sum(r['weight'] * fn(r) for r in rows) / total if total else None


def boot(rows, fn):
    by = defaultdict(list)
    for r in rows:
        by[(r['stratum'], r['instance'])].append(r)
    rng = random.Random(SEED); vals = []
    for _ in range(DRAWS):
        # within-stratum cluster bootstrap: resample clusters inside each stratum
        draw = []
        for h in sorted({k[0] for k in by}):
            keys = [k for k in by if k[0] == h]
            for _ in keys:
                draw += by[keys[rng.randrange(len(keys))]]
        vals.append(fn(draw))
    vals = [v for v in vals if v is not None]
    vals.sort()
    lo = vals[int(0.025 * len(vals))]; hi = vals[int(0.975 * len(vals)) - 1]
    return {'estimate': fn(rows), 'lo': lo, 'hi': hi, 'valid_draws': len(vals)}


def block(rs, src_presence, src_fidelity, label):
    pres = [r for r in rs if r.get(src_presence) in ('yes', 'no') and r.get('author_presence') in ('yes', 'no')]
    fid = [r for r in rs if r.get(src_fidelity) in ('absent', 'faithful', 'partial', 'distorted')]
    out = {'label': label, 'presence_rows': len(pres),
           'presence': {'accuracy': boot(pres, lambda d: rate(d, lambda r: r[src_presence] == r['author_presence'])),
                        'kappa': boot(pres, lambda d: kappa(d, src_presence, 'author_presence', ('yes', 'no'))),
                        'ac1': boot(pres, lambda d: ac1(d, src_presence, 'author_presence', ('yes', 'no'))),
                        'prevalence_yes': rate(pres, lambda r: r['author_presence'] == 'yes')},
           'fidelity_rows': len(fid),
           'fidelity': {'accuracy': boot(fid, lambda d: rate(d, lambda r: r[src_fidelity] == r['author_fidelity'])),
                        'kappa': boot(fid, lambda d: kappa(d, src_fidelity, 'author_fidelity',
                                                           ('absent', 'faithful', 'partial', 'distorted'))),
                        'ac1': boot(fid, lambda d: ac1(d, src_fidelity, 'author_fidelity',
                                                       ('absent', 'faithful', 'partial', 'distorted'))),
                        'prevalence_faithful': rate(fid, lambda r: r['author_fidelity'] == 'faithful')},
           'author_fidelity_dist': dict(Counter(r['author_fidelity'] for r in fid)),
           'pred_dist': dict(Counter(r[src_fidelity] for r in fid))}
    return out


def detail_rows():
    """Same loop as `run_paper_evaluators.rows`, keeping the top lexical score for tie reporting."""
    labels = {a: {r['display_name']: r for r in json.loads(
        (RET / f'E1anchor_{a}_labelling-v1.0.json').read_text())} for a in 'ABCD'}
    pmap = json.loads(PMAP.read_text())
    n80 = json.loads(N80.read_text())
    strata = {i: h for h, v in n80['strata'].items() for i in v['ids']}
    war = {h: v['weight'] for h, v in json.loads(
        Path('rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json').read_text())['strata'].items()}
    out = []
    for a, b in (('A', 'B'), ('C', 'D')):
        for name in sorted(set(labels[a]) & set(labels[b])):
            ra, rb = labels[a][name], labels[b][name]
            inst = pmap[ra['item_id']]['instance_id']
            h = strata[inst]
            t = ra['trace']
            gold_units = {s['support_id']: s['text'] for s in t['source_supports']}
            for who, r in (('A', ra), ('B', rb)):
                facts = json.loads(r['answers']['critical_facts_json'])
                cars = {(c['fact_id'], c['checkpoint']): c for c in json.loads(r['answers']['carriers_json'])}
                for fa in facts:
                    src = fa.get('source_ids') or []
                    if len(src) != 1 or src[0] not in gold_units:
                        continue
                    gold = gold_units[src[0]]
                    for cp, cpk in (('pool', 'extraction'), ('board', 'board')):
                        car = cars.get((fa['fact_id'], cp))
                        fid = (car or {}).get('fidelity') or 'absent'
                        if fid == 'uncertain':
                            continue
                        unit_text = [u['text'] for u in t['checkpoints'][cpk]]
                        scores = [align_gold_to_transmitted([(0, fa['text'])], [ut])[0]['score'] for ut in unit_text]
                        top = max(scores) if scores else 0.0
                        out.append({'instance': inst, 'trace': name, 'annotator': who, 'fact_id': fa['fact_id'],
                                    'checkpoint': cp, 'author_fidelity': fid, 'unique_argmax': len(
                                        [i for i, s in enumerate(scores) if s == top]) == 1, 'top_score': top})
    return out


def tie_breakdown(allr, det):
    assert len(allr) == len(det)
    det = {(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint']): r for r in det}
    fixed, ties = [], []
    for r in allr:
        d = det[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]
        assert d['unique_argmax'] == r['unique_argmax'] and d['author_fidelity'] == r['author_fidelity']
        row = dict(r, top_score=d['top_score'])
        (fixed if r['unique_argmax'] else ties).append(row)
    def counts(rs):
        out = {'rows': len(rs),
               'all_zero': sum(r['top_score'] == 0.0 for r in rs),
               'positive': sum(r['top_score'] > 0.0 for r in rs)}
        out['by_checkpoint'] = {cp: {'rows': sum(r['checkpoint'] == cp for r in rs),
                                     'all_zero': sum(r['checkpoint'] == cp and r['top_score'] == 0.0 for r in rs),
                                     'positive': sum(r['checkpoint'] == cp and r['top_score'] > 0.0 for r in rs)}
                                for cp in ('pool', 'board')}
        out['by_fidelity'] = {f: {'rows': sum(r['author_fidelity'] == f for r in rs),
                                  'all_zero': sum(r['author_fidelity'] == f and r['top_score'] == 0.0 for r in rs),
                                  'positive': sum(r['author_fidelity'] == f and r['top_score'] > 0.0 for r in rs)}
                              for f in sorted({r['author_fidelity'] for r in rs})}
        out['lexical_covered'] = sum(r['lexical_covered'] for r in rs)
        return out
    return {'tied': counts(ties), 'unique_argmax': counts(fixed),
            'all_rows': counts(fixed + ties)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows')
    ap.add_argument('--out')
    ap.add_argument('--v11', action='store_true', help='also score the lexical rule on all 1,356 rows and report ties')
    a = ap.parse_args()
    allr = rows()
    elig = [r for r in allr if r['unique_argmax']]
    for r in allr:
        r['lexical_presence'] = 'yes' if r['lexical_covered'] else 'no'
        r['lexical_fidelity'] = 'faithful' if r['lexical_covered'] else 'absent'
    report = {'rows_all': len(allr), 'eligible': len(elig),
              'lexical': block(elig, 'lexical_presence', 'lexical_fidelity', 'lexical (align_gold_to_transmitted)')}
    if a.v11:
        report['v11'] = {'lexical_all_rows': block(allr, 'lexical_presence', 'lexical_fidelity',
                                                   'lexical on all 1,356 rows (v1.1)'),
                         'lexical_eligible_rows': report['lexical'],
                         'tie_breakdown': tie_breakdown(allr, detail_rows())}
    if a.rows:
        jr = [json.loads(l) for l in Path(a.rows).read_text().splitlines() if l.strip()]
        valid = [r for r in jr if r.get('judge_valid')]
        for r in valid:
            r['judge_presence_strict'] = 'yes' if r['judge_label'] in ('EXACT', 'PARAPHRASE') else 'no'
        report['judge_rows_file'] = a.rows
        report['judge_coverage'] = {'rows': len(jr), 'valid': len(valid)}
        report['judge'] = block(valid, 'judge_presence', 'judge_fidelity', 'alignment judge')
        report['judge_strict_presence'] = block(valid, 'judge_presence_strict', 'judge_fidelity',
                                                'alignment judge (EXACT/PARAPHRASE only)')['presence']
        report['judge_label_dist'] = dict(Counter(r['judge_label'] for r in valid))
    out = Path(a.out) if a.out else OUT / 'paper_evaluators_lexical.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2)[:3000])


if __name__ == '__main__':
    main()