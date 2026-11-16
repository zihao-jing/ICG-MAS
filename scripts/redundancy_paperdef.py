"""Paper-definition redundancy and useful budget on existing MuSiQue traces ($0).

RedundancyRate = mean pairwise Jaccard similarity of transmitted units (lowercase whitespace tokens).
UsefulBudget = distinct best-matched gold support texts / transmitted units.
Definitions copied from `src/audit/metrics.py` and appendix "Redundancy Rate (Re)" / "Useful Budget (UB)".

    ./run.sh python -m scripts.redundancy_paperdef
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.audit.critical_fact_validation import (get_transmitted_units, load_run,
                                                reconstruct_states_and_scores)
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_redundancy'
RUNS = {'qwen235b': 'run_qwen235b_musique', 'gpt4omini': 'run_musique_gpt4omini',
        'gemma31b': 'run_musique_gemma31b'}
PROTOCOLS = ['random_relay', 'redundancy_aware_relay', 'score_ranked_relay']
K = 3


def jaccard(a, b):
    ta, tb = set(normalize(a)), set(normalize(b))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0


def redundancy(units):
    if len(units) < 2:
        return 0.0
    vals = [jaccard(units[i], units[j]) for i in range(len(units)) for j in range(i + 1, len(units))]
    return sum(vals) / len(vals)


def load_supports():
    sup = {}
    for p in Path('data/musique').glob('musique_full_v1.0_*.jsonl'):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            paras = d.get('paragraphs') or []
            gold = [x['paragraph_text'] for x in paras if x.get('is_supporting')]
            if gold:
                sup[d['id']] = gold
    return sup


def useful_budget(units, supports):
    if not units:
        return 0.0
    matched = set()
    for u in units:
        nu = set(normalize(u))
        best, idx = 0.0, None
        for i, s in enumerate(supports):
            ns = set(normalize(s))
            r = len(nu & ns) / max(1, len(ns))
            if r > best:
                best, idx = r, i
        if best >= 0.5 and idx is not None:
            matched.add(idx)
    return len(matched) / len(units)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    supports = load_supports()
    rows = []
    for model, run in RUNS.items():
        results, responses = load_run(ROOT / 'results' / run)
        states, scores = reconstruct_states_and_scores(responses)
        for inst in sorted(states):
            n = 2 if inst.startswith('2hop') else 3 if inst.startswith('3hop1') else 4
            gold = supports.get(inst)
            if not gold:
                continue
            for protocol in PROTOCOLS:
                tr = get_transmitted_units(inst, protocol, states, scores, n, k=K)
                units = [u for lst in tr.values() for u in lst]
                rows.append({'model': model, 'instance': inst, 'protocol': protocol,
                             'redundancy': round(redundancy(units), 4),
                             'useful_budget': round(useful_budget(units, gold), 4)})
    (OUT / 'rows_paperdef.json').write_text(json.dumps(rows, indent=1))
    by = defaultdict(list)
    for r in rows:
        by[r['protocol']].append(r)
    out = {}
    for p, rs in by.items():
        out[p] = {'n': len(rs),
                  'redundancy_mean': round(statistics.mean(r['redundancy'] for r in rs), 4),
                  'useful_budget_mean': round(statistics.mean(r['useful_budget'] for r in rs), 4)}
    # by-model view
    bym = defaultdict(list)
    for r in rows:
        bym[(r['model'], r['protocol'])].append(r)
    out['by_model'] = {'%s|%s' % k: {'n': len(v),
                                    'redundancy_mean': round(statistics.mean(x['redundancy'] for x in v), 4),
                                    'useful_budget_mean': round(statistics.mean(x['useful_budget'] for x in v), 4)}
                       for k, v in bym.items()}
    (OUT / 'report_paperdef.json').write_text(json.dumps(out, indent=1))
    lines = ['# Redundancy and useful budget under the paper definitions', '',
             '2026-11-15. $0, no model calls. RedundancyRate = mean pairwise Jaccard similarity of transmitted '
             'units; UsefulBudget = distinct best-matched gold support texts / transmitted units. k = 3.', '',
             '| protocol | n | RedundancyRate | UsefulBudget |', '| --- | ---: | ---: | ---: |']
    for p, v in out.items():
        if p == 'by_model':
            continue
        lines.append('| %s | %d | %.3f | %.3f |' % (p, v['n'], v['redundancy_mean'], v['useful_budget_mean']))
    lines += ['', '## By model', '', '| model | protocol | n | RedundancyRate | UsefulBudget |', '| --- | --- | ---: | ---: | ---: |']
    for key, v in sorted(out['by_model'].items()):
        m, p = key.split('|')
        lines.append('| %s | %s | %d | %.3f | %.3f |' % (m, p, v['n'], v['redundancy_mean'], v['useful_budget_mean']))
    (OUT / 'report_paperdef.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()