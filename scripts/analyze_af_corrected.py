"""Corrected AF count on the E1 anchor: complete coverage + non-perfect answer, under the lexical rule and
under the authors' presence labels, on the same 90 anchor traces. Read-only; no model call."""

import json, random
from collections import Counter, defaultdict
from pathlib import Path

from scripts.analyze_lexical_bias import source_rows, RET
from scripts.run_paper_evaluators import rows as labelled_rows
from src.eval.evaluate import token_f1

OUT = Path('rebuttal/results/batch1/E1/af_corrected.json')
DRAWS, SEED = 2000, 42


def trace_answers():
    out = {}
    for a in 'ABCD':
        for r in json.loads((RET / f'E1anchor_{a}_labelling-v1.0.json').read_text()):
            t, name = r['trace'], r['display_name']
            rec = (t['gold_answer'], t['answer_text'])
            assert out.setdefault(name, rec) == rec, f'{name} differs across files'
    return out


def boot(units, fn):
    by = defaultdict(list)
    for t in units:
        by[(t['stratum'], t['instance'])].append(t)
    strata = {h: sorted(k for k in by if k[0] == h) for h in sorted({k[0] for k in by})}
    rng = random.Random(SEED)
    vals = []
    for _ in range(DRAWS):
        draw = []
        for h, keys in strata.items():
            for _ in keys:
                draw += by[keys[rng.randrange(len(keys))]]
        vals.append(fn(draw))
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]


def main():
    rs = source_rows()
    base = {(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint']): r
            for r in labelled_rows()}
    for r in rs:
        r['weight'] = base[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]['weight']
    ans = trace_answers()
    by_trace = defaultdict(list)
    for r in rs:
        by_trace[(r['instance'], r['stratum'], r['trace'], r['weight'])].append(r)
    traces = []
    for (inst, h, tr, w), sub in by_trace.items():
        gold, pred = ans[tr]
        f1 = token_f1(pred, gold)
        traces.append({'instance': inst, 'stratum': h, 'trace': tr, 'weight': w, 'f1': f1,
                       'wrong': f1 < 1.0,
                       'complete_lexical': all(r['covered'] for r in sub),
                       'absent': any(r['author_fidelity'] == 'absent' for r in sub)})

    W = lambda us: sum(u['weight'] for u in us)
    af_lex = lambda us: sum(u['weight'] for u in us if u['complete_lexical'] and u['wrong']) / W(us)
    af_auth = lambda us: sum(u['weight'] for u in us
                             if u['complete_lexical'] and not u['absent'] and u['wrong']) / W(us)
    diff = lambda us: af_lex(us) - af_auth(us)
    lex, auth = af_lex(traces), af_auth(traces)
    lo_l, hi_l = boot(traces, af_lex)
    lo_a, hi_a = boot(traces, af_auth)
    lo_d, hi_d = boot(traces, diff)

    wrong = [t for t in traces if t['wrong']]
    drivers = [t for t in traces if t['wrong'] and t['absent']]
    strata = defaultdict(lambda: {'instances': set(), 'traces': 0, 'wrong': 0, 'absent': 0, 'weight': 0.0})
    for t in traces:
        s = strata[t['stratum']]
        s['instances'].add(t['instance'])
        s['traces'] += 1
        s['wrong'] += t['wrong']
        s['absent'] += t['absent']
        s['weight'] += t['weight']
    inst_af_lex = sorted({t['instance'] for t in traces if t['complete_lexical'] and t['wrong']})
    inst_af_auth = sorted({t['instance'] for t in traces
                           if t['complete_lexical'] and not t['absent'] and t['wrong']})
    out = {
        'traces': len(traces), 'instances': len({t['instance'] for t in traces}),
        'all_traces_complete_lexical': all(t['complete_lexical'] for t in traces),
        'wrong_traces': len(wrong),
        'af_lexical': round(lex, 6), 'af_lexical_ci': [round(lo_l, 6), round(hi_l, 6)],
        'af_author': round(auth, 6), 'af_author_ci': [round(lo_a, 6), round(hi_a, 6)],
        'change_points': round((auth - lex) * 100, 4),
        'change_ci_points': [round(-hi_d * 100, 4), round(-lo_d * 100, 4)],
        'driver_traces': len(drivers),
        'driver_instances': sorted({t['instance'] for t in drivers}),
        'driver_instance_count': len({t['instance'] for t in drivers}),
        'driver_list': [{'instance': t['instance'], 'trace': t['trace'], 'stratum': t['stratum']} for t in drivers],
        'unweighted': {'af_lexical': round(len(wrong) / len(traces), 6),
                       'af_author': round((len(wrong) - len(drivers)) / len(traces), 6)},
        'instance_level_af_lexical': {'count': len(inst_af_lex), 'instances': len({t['instance'] for t in traces})},
        'instance_level_af_author': {'count': len(inst_af_auth), 'instances': len({t['instance'] for t in traces})},
        'by_benchmark': {},
        'strata': {h: {'instances': len(s['instances']), 'traces': s['traces'], 'wrong': s['wrong'],
                       'absent': s['absent'], 'weight': round(s['weight'], 6)}
                   for h, s in sorted(strata.items())},
        'bootstrap': {'draws': DRAWS, 'seed': SEED, 'cluster': 'instance', 'sorted_strata': True},
    }
    for bench in ('MQ', 'SB'):
        us = [t for t in traces if t['stratum'].split('/')[0] == bench]
        out['by_benchmark'][bench] = {
            'traces': len(us), 'instances': len({t['instance'] for t in us}),
            'wrong': sum(t['wrong'] for t in us), 'absent': sum(t['absent'] for t in us),
            'af_lexical': round(af_lex(us), 6), 'af_author': round(af_auth(us), 6),
            'change_points': round((af_auth(us) - af_lex(us)) * 100, 4)}
    OUT.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()