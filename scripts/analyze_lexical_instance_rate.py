"""Instance-level rate of the lexical rule on the E1 anchor: share of traces (and instances) with complete
lexical coverage but at least one author-absent fact. Read-only; no model call."""

import json, random
from collections import defaultdict
from pathlib import Path

from scripts.analyze_lexical_bias import source_rows
from scripts.run_paper_evaluators import rows as labelled_rows

OUT = Path('rebuttal/results/batch1/E1/lexical_instance_rate.json')
DRAWS, SEED = 2000, 42


def main():
    rs = source_rows()
    base = {(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint']): r
            for r in labelled_rows()}
    for r in rs:
        r['weight'] = base[(r['instance'], r['trace'], r['annotator'], r['fact_id'], r['checkpoint'])]['weight']
    by_trace = defaultdict(list)
    for r in rs:
        by_trace[(r['instance'], r['stratum'], r['trace'], r['weight'])].append(r)
    traces = []
    for (inst, h, tr, w), sub in by_trace.items():
        traces.append({'instance': inst, 'stratum': h, 'trace': tr, 'weight': w,
                       'complete_lexical': all(r['covered'] for r in sub),
                       'absent': any(r['author_fidelity'] == 'absent' for r in sub),
                       'facts': len(sub)})

    def boot(units, fn):
        by = defaultdict(list)
        for t in units:
            by[(t['stratum'], t['instance'])].append(t)
        strata = {h: sorted(k for k in by if k[0] == h) for h in sorted({k[0] for k in by})}
        rng = random.Random(SEED); vals = []
        for _ in range(DRAWS):
            draw = []
            for h, keys in strata.items():
                for _ in keys:
                    draw += by[keys[rng.randrange(len(keys))]]
            vals.append(fn(draw))
        vals.sort()
        return {'estimate': fn(units), 'lo': vals[int(.025 * len(vals))],
                'hi': vals[int(.975 * len(vals)) - 1], 'draws': len(vals)}

    def wrate(units):
        num = sum(t['weight'] for t in units if t['complete_lexical'] and t['absent'])
        den = sum(t['weight'] for t in units if t['complete_lexical'])
        return num / den if den else None

    insts = sorted({t['instance'] for t in traces})
    affected_traces = [t for t in traces if t['complete_lexical'] and t['absent']]
    affected_insts = sorted({t['instance'] for t in affected_traces})
    inst_units = []
    for inst in insts:
        sub = [t for t in traces if t['instance'] == inst]
        inst_units.append({'instance': inst, 'stratum': sub[0]['stratum'], 'weight': sub[0]['weight'],
                           'complete_lexical': all(t['complete_lexical'] for t in sub),
                           'absent': any(t['absent'] for t in sub)})
    out = {'instances_affected_rate': boot(inst_units, lambda us: sum(u['complete_lexical'] and u['absent'] for u in us) / len(us)),
           'traces': len(traces), 'instances': len(insts),
           'complete_lexical_traces': sum(t['complete_lexical'] for t in traces),
           'affected_traces': len(affected_traces), 'affected_instances': len(affected_insts),
           'affected_instance_ids': affected_insts,
           'weighted_trace_rate': boot(traces, wrate),
           'unweighted_trace_rate': round(len(affected_traces) / len(traces), 6),
           'affected_trace_list': [{'instance': t['instance'], 'trace': t['trace'], 'stratum': t['stratum']}
                                   for t in affected_traces]}
    OUT.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()