"""Redundancy tests on existing MuSiQue main-table traces ($0, no model calls).

(a) redundancy-aware relay as the redundancy repair: duplicate share and critical-fact coverage with and
    without it, per model.
(b) critical-fact loss against redundancy: coverage by redundancy quartile under the same budget.

    ./run.sh python -m scripts.redundancy_tests
"""
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from src.audit.critical_fact_validation import (get_transmitted_units, load_run,
                                                reconstruct_states_and_scores)
from src.audit.e4_fix_gates import STOP, recall
from src.eval.evaluate import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_redundancy'
RUNS = {'qwen235b': 'run_qwen235b_musique', 'gpt4omini': 'run_musique_gpt4omini',
        'gemma31b': 'run_musique_gemma31b'}
PROTOCOLS = ['random_relay', 'redundancy_aware_relay', 'score_ranked_relay', 'summary_exchange']
K = 3


def gold_supports(results, inst):
    rec = None
    for lst in results.get('instance_results', {}).values():
        for r in lst:
            if r.get('id') == inst:
                rec = r
    return rec


def coverage(texts, gold):
    if not gold:
        return None
    ft = [t for t in normalize(gold) if t not in STOP]
    if not ft:
        return None
    best = 0.0
    for t in texts:
        best = max(best, recall(t, ' '.join(ft)))
    return best


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for model, run in RUNS.items():
        results, responses = load_run(ROOT / 'results' / run)
        states, scores = reconstruct_states_and_scores(responses)
        for inst in sorted(states):
            n = int(inst.split('_')[0].replace('hop', '').replace('hop1', '1').replace('hop2', '2')
                    .replace('hop3', '3').replace('hop4', '4').split('__')[0][-1]) if '__' in inst else 2
            n = 2 if inst.startswith('2hop') else 3 if inst.startswith('3hop1') else 4
            gold_rec = None
            for lst in results['instance_results'].values():
                for r in lst:
                    if r['id'] == inst:
                        gold_rec = r
            if not gold_rec:
                continue
            supports = gold_rec.get('supporting_facts') or gold_rec.get('gold_supports') or []
            for protocol in PROTOCOLS:
                if protocol == 'summary_exchange':
                    continue
                tr = get_transmitted_units(inst, protocol, states, scores, n, k=K)
                units = [u for lst in tr.values() for u in lst]
                total = len(units)
                uniq = len(set(units))
                red = (total - uniq) / total if total else 0.0
                cov = coverage(units, gold_rec.get('gold'))
                rows.append({'model': model, 'instance': inst, 'protocol': protocol,
                             'units': total, 'redundancy': round(red, 4),
                             'coverage': None if cov is None else round(cov, 4),
                             'correct': bool(gold_rec.get('correct'))})
    (OUT / 'rows.json').write_text(json.dumps(rows, indent=1))
    by = defaultdict(list)
    for r in rows:
        by[r['protocol']].append(r)
    out = {}
    for p, rs in by.items():
        red = [r['redundancy'] for r in rs]
        covs = [1.0 if (r['coverage'] is not None and r['coverage'] >= 0.8) else 0.0 for r in rs]
        out[p] = {'n': len(rs), 'redundancy_mean': round(statistics.mean(red), 4),
                  'critical_coverage': round(statistics.mean(covs), 4)}
    # (b) coverage by redundancy quartile (redundancy_aware vs score_ranked pooled)
    pool = [r for r in rows if r['protocol'] in ('redundancy_aware_relay', 'score_ranked_relay')]
    pool.sort(key=lambda r: r['redundancy'])
    q = len(pool) // 4
    bins = []
    for i in range(4):
        seg = pool[i * q:(i + 1) * q] if i < 3 else pool[3 * q:]
        covs = [1.0 if (r['coverage'] is not None and r['coverage'] >= 0.8) else 0.0 for r in seg]
        bins.append({'quartile': i + 1, 'n': len(seg),
                     'redundancy_mean': round(statistics.mean(r['redundancy'] for r in seg), 4),
                     'critical_coverage': round(statistics.mean(covs), 4)})
    out['by_quartile'] = bins
    (OUT / 'report.json').write_text(json.dumps(out, indent=1))
    lines = ['# Redundancy tests on existing MuSiQue traces', '',
             '2026-11-15. $0, no model calls. Units reconstructed from the stored extraction and scoring phases; '
             'k = 3 per agent; critical-fact coverage = gold answer string found in a transmitted unit at lexical '
             'recall >= 0.8.', '', '| protocol | n | mean redundancy | critical-fact coverage |', '| --- | ---: | ---: | ---: |']
    for p in out:
        if p == 'by_quartile':
            continue
        v = out[p]
        lines.append('| %s | %d | %.3f | %.3f |' % (p, v['n'], v['redundancy_mean'], v['critical_coverage']))
    lines += ['', '## Coverage by redundancy quartile (redundancy-aware and score-ranked pooled)', '',
              '| quartile | n | mean redundancy | critical-fact coverage |', '| --- | ---: | ---: | ---: |']
    for b in bins:
        lines.append('| %d | %d | %.3f | %.3f |' % (b['quartile'], b['n'], b['redundancy_mean'], b['critical_coverage']))
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()