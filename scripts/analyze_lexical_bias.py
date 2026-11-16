"""Lexical-rule bias on the E1 anchor: the 40 author-absent rows, tie membership, and CritRec/OmissionRate
direction. Read-only over existing labels and traces; no model call."""

import json, random, re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted, _numbers_in_text
from scripts.run_paper_evaluators import rows, RET, PMAP, N80

OUT = Path('rebuttal/results/batch1/E1/lexical_bias.json')
DRAWS, SEED = 2000, 42
STOP = set('the a an and or of to in on at for with by from as is are was were be been it its this that these those which who whom whose what when where how not no yes'.split())


def source_rows():
    labels = {a: {r['display_name']: r for r in json.loads(
        (RET / f'E1anchor_{a}_labelling-v1.0.json').read_text())} for a in 'ABCD'}
    pmap = json.loads(PMAP.read_text())
    n80 = json.loads(N80.read_text())
    strata = {i: h for h, v in n80['strata'].items() for i in v['ids']}
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
                        best = unit_text[scores.index(top)] if unit_text else ''
                        gt = set(gold.lower().split()); bt = set(best.lower().split())
                        gn = _numbers_in_text(gold); bn = _numbers_in_text(best)
                        inter_n = gn & bn
                        num_score = len(inter_n) / len(gn) if gn else 0.0
                        jac = len(gt & bt) / len(gt | bt) if (gt or bt) else 0.0
                        shared = sorted(gt & bt)
                        ents = sorted({t for t in shared if re.search(r'\b' + re.escape(t) + r'\b', gold.lower()) and any(
                            w[0].isupper() for w in re.findall(r"[A-Za-z][\w\-']*", gold) if w.lower() == t)})
                        ents = [t for t in ents if t not in STOP]
                        common = [t for t in shared if t not in ents and t not in STOP]
                        driver = 'numeric' if (num_score > 0 and num_score >= jac) else (
                            'shared entity' if ents else (
                                'shared content word' if common else ('shared function word only' if shared else 'none')))
                        out.append({'instance': inst, 'stratum': h, 'trace': name, 'annotator': who,
                                    'fact_id': fa['fact_id'], 'checkpoint': cp, 'author_fidelity': fid,
                                    'covered': top > 0.0, 'score': top, 'gold': gold, 'candidate': best,
                                    'shared': shared, 'shared_numbers': sorted(inter_n),
                                    'entities': ents, 'common': common,
                                    'num_score': num_score, 'jaccard': jac, 'driver': driver})
    return out


def rate(rs, fn):
    return sum(fn(r) for r in rs) / len(rs) if rs else None


def boot_rate(rs, fn):
    by = defaultdict(list)
    for r in rs:
        by[(r['stratum'], r['instance'])].append(r)
    rng = random.Random(SEED); vals = []
    stratum_keys = {h: sorted(k for k in by if k[0] == h) for h in sorted({k[0] for k in by})}
    for _ in range(DRAWS):
        draw = []
        for h, keys in stratum_keys.items():
            for _ in keys:
                draw += by[keys[rng.randrange(len(keys))]]
        vals.append(rate(draw, fn))
    vals.sort()
    return {'estimate': rate(rs, fn), 'lo': vals[int(.025 * len(vals))], 'hi': vals[int(.975 * len(vals)) - 1], 'draws': len(vals)}


def main():
    rs = source_rows()
    base = {(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint']): r for r in rows()}
    assert len(rs) == len(base) == 1356
    for r in rs:
        b = base[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]
        assert b['author_fidelity'] == r['author_fidelity']
        r['weight'] = b['weight']
    absent = [r for r in rs if r['author_fidelity'] == 'absent']
    ties = [r for r in rs if not base[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]['unique_argmax']]
    report = {'rows': len(rs), 'absent_rows': len(absent),
              'absent_by_checkpoint': dict(Counter(r['checkpoint'] for r in absent)),
              'absent_in_tied_rows': sum(not base[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]['unique_argmax'] for r in absent),
              'tied_rows': len(ties), 'tied_by_fidelity': dict(Counter(r['author_fidelity'] for r in ties)),
              'absent_driver': dict(Counter(r['driver'] for r in absent)),
              'absent_list': absent,
              'rates': {}}
    for cp in ('pool', 'board'):
        sub = [r for r in rs if r['checkpoint'] == cp]
        report['rates'][cp] = {
            'n': len(sub),
            'lexical_covered': boot_rate(sub, lambda r: r['covered']),
            'author_present': boot_rate(sub, lambda r: r['author_fidelity'] != 'absent'),
            'absent': sum(r['author_fidelity'] == 'absent' for r in sub),
            'absent_covered': sum(r['author_fidelity'] == 'absent' and r['covered'] for r in sub),
        }
    report['by_benchmark'] = {}
    for bench in ('MQ', 'SB'):
        sub = [r for r in rs if r['stratum'].split('/')[0] == bench]
        report['by_benchmark'][bench] = {
            'rows': len(sub), 'instances': len({r['instance'] for r in sub}),
            'traces': len({(r['instance'], r['trace']) for r in sub}),
            'absent_rows': sum(r['author_fidelity'] == 'absent' for r in sub),
            'author_present': boot_rate(sub, lambda r: r['author_fidelity'] != 'absent')}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('rows', 'absent_rows', 'absent_by_checkpoint', 'absent_in_tied_rows',
                                             'tied_rows', 'tied_by_fidelity', 'absent_driver', 'rates')}, indent=1))


if __name__ == '__main__':
    main()