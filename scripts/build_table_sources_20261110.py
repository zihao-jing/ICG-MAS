"""Build raw table-source rows from existing outputs (no model call, no label change).

Writes JSONL sources for the paper-evaluator table, the lexical-rule correction table, the E2-A
yield table and the E4 manifest-count table. Every number is copied or computed from the named
output file; nothing is typed from memory. CIs are the ones already computed in those files, except
the exact Clopper-Pearson CIs for the trace/instance complete-coverage counts, computed here.
"""
import json
from pathlib import Path

from scripts.make_batch1_tables import cp_ci

ROOT = Path('rebuttal/results/batch1')
OUT = ROOT / 'table_sources'
AF = ROOT / 'E1/af_corrected.json'
LEX = ROOT / 'E1/lexical_bias.json'
PAPER = ROOT / 'E1/paper_evaluators_v11.json'
W1 = ROOT / 'E2A_wave1_screening/summary.json'
W2 = ROOT / 'E2A_wave2_screening/summary.json'
MAN = ROOT / 'E4_manifest/manifest.json'
REXT = ROOT / 'E4_manifest/rext_unit_reconstruction.json'

TYPES = ['extraction_omission', 'selection_omission', 'distortion', 'aggregation']
GROUP_LABEL = {'extraction_omission': 'extraction', 'selection_omission': 'selection',
               'distortion': 'distortion', 'aggregation': 'aggregation',
               'candidate_aggregation': 'aggregation', 'correct_control': 'controls'}


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))


def reported(row, col, est, lo, hi, n_rows, n_clusters, method, marks=(), value=None):
    r = {'row': row, 'col': col, 'estimate': est, 'ci_lo': lo, 'ci_hi': hi, 'n_rows': n_rows,
         'n_clusters': n_clusters, 'method': method, 'marks': list(marks)}
    if value is not None:
        r['value'] = value
    return r


def paper_evaluators():
    d = json.loads((ROOT / 'E1/paper_evaluators_v11_full.json').read_text())
    rows = []
    for scope, key, n in (('lexical, all 1,356 rows', 'lexical_all_rows', 1356),
                          ('lexical, eligible 852 rows', 'lexical_eligible_rows', 852)):
        block = d['v11'][key]
        for task in ('presence', 'fidelity'):
            b = block[task]
            for metric in ('accuracy', 'kappa', 'ac1'):
                v = b[metric]
                rows.append(reported(scope, task, v['estimate'], v['lo'], v['hi'], n, 30, 'bootstrap'))
                rows[-1]['metric'] = metric
    judge = d['judge']
    for task, sub in (('presence, pre-registered', judge['presence']),
                      ('presence, strict', d['judge_strict_presence']),
                      ('fidelity, pre-registered', judge['fidelity'])):
        for metric in ('accuracy', 'kappa', 'ac1'):
            v = sub[metric]
            rows.append(reported('Qwen-235B judge, eligible 852 rows', task, v['estimate'], v['lo'], v['hi'],
                                 852, 30, 'bootstrap'))
            rows[-1]['metric'] = metric
    write('T14_paper_evaluators.jsonl', rows)


def lexical_correction():
    af = json.loads(AF.read_text())
    lex = json.loads(LEX.read_text())
    board = lex['rates']['board']
    n = board['n']
    a = board['author_present']
    rows = [
        reported('coverage / CritRec (fact level, board)', 'lexical rule', board['lexical_covered']['estimate'],
                 board['lexical_covered']['lo'], board['lexical_covered']['hi'], n, 30, 'cluster bootstrap',
                 ['paper: tab_audit_combined.tex:8; tab_claim_evidence.tex:20; 4-experiments.tex:31']),
        reported('coverage / CritRec (fact level, board)', "authors' presence labels", a['estimate'],
                 a['lo'], a['hi'], n, 30, 'cluster bootstrap',
                 ['paper: tab_audit_combined.tex:8; tab_claim_evidence.tex:20; 4-experiments.tex:31']),
        reported('OmissionRate = 1 - CritRec', 'lexical rule', 1 - board['lexical_covered']['estimate'],
                 1 - board['lexical_covered']['hi'], 1 - board['lexical_covered']['lo'], n, 30,
                 'cluster bootstrap',
                 ['paper: 3-methodology.tex:93; 3-methodology.tex:97']),
        reported('OmissionRate = 1 - CritRec', "authors' presence labels", 1 - a['estimate'],
                 1 - a['hi'], 1 - a['lo'], n, 30, 'cluster bootstrap',
                 ['paper: 3-methodology.tex:93; 3-methodology.tex:97']),
    ]
    # Complete-coverage counts under both rules. 90 traces and 30 instances; the author rule marks
    # a trace/instance incomplete when any labelled fact row is author-absent.
    import scripts.analyze_af_corrected as afs
    rs = afs.source_rows()
    by_trace, by_inst = {}, {}
    inst_of = {}
    for r in rs:
        by_trace[(r['instance'], r['trace'])] = by_trace.get((r['instance'], r['trace']), True) and not (
            r['author_fidelity'] == 'absent')
        by_inst[r['instance']] = by_inst.get(r['instance'], True) and not (r['author_fidelity'] == 'absent')
        inst_of[r['instance']] = r['stratum']
    tr = len(by_trace)
    tr_ok = sum(by_trace.values())
    inum = len(by_inst)
    in_ok = sum(by_inst.values())
    for unit, k_lex, k_author, n_unit, clusters in (
            ('complete coverage (trace level)', tr, tr_ok, tr, len(by_inst)),
            ('complete coverage (instance level)', inum, in_ok, inum, inum)):
        lo, hi = cp_ci(k_author, n_unit)
        rows.append(reported(unit, 'lexical rule', 1.0, 1.0, 1.0, n_unit, clusters, 'exact Clopper-Pearson',
                             ['paper: 0-abstract.tex:4; 1-introduction.tex:37; 4-experiments.tex:76']))
        rows.append(reported(unit, "authors' presence labels", k_author / n_unit, lo, hi, n_unit, clusters,
                             'exact Clopper-Pearson',
                             ['paper: 0-abstract.tex:4; 1-introduction.tex:37; 4-experiments.tex:76']))
    for row, est, lo, hi, n_rows, clusters in (
            ('AF = complete coverage + non-perfect answer (trace level, weighted)', af['af_lexical'],
             af['af_lexical_ci'][0], af['af_lexical_ci'][1], af['traces'], af['instances']),
            ('AF = complete coverage + non-perfect answer (trace level, weighted)', af['af_author'],
             af['af_author_ci'][0], af['af_author_ci'][1], af['traces'], af['instances'])):
        rows.append(reported(row, 'lexical rule' if est == af['af_lexical'] else "authors' presence labels",
                             est, lo, hi, n_rows, clusters, 'cluster bootstrap',
                             ['paper: tab_audit_combined.tex:8; 4-experiments.tex:76; 0-abstract.tex:5']))
    rows.append(reported('AF instance level (count)', 'lexical rule',
                         af['instance_level_af_lexical']['count'], None, None, af['instances'], af['instances'],
                         'descriptive', ['paper: tab_audit_combined.tex:8']))
    rows.append(reported('AF instance level (count)', "authors' presence labels",
                         af['instance_level_af_author']['count'], None, None, af['instances'], af['instances'],
                         'descriptive', ['paper: tab_audit_combined.tex:8']))
    write('T15_lexical_correction.jsonl', rows)


def e2a_yields():
    w1 = json.loads(W1.read_text())
    w2 = json.loads(W2.read_text())
    rows = []
    for t in TYPES:
        lab = GROUP_LABEL[t]
        for col, v in (('wave-1 pairs (68 bases)', w1['eligible_pairs_per_type'][t]),
                       ('option C pairs (219 bases)', w2['eligible_pairs_per_type'][t]),
                       ('combined pairs', w1['eligible_pairs_per_type'][t] + w2['eligible_pairs_per_type'][t]),
                       ('wave-1 traces', w1['eligible_traces_per_type'][t]),
                       ('option C traces', w2['eligible_traces_per_type'][t]),
                       ('50/type reached (1=yes)', int(w2['reached_50_per_type'][t]))):
            rows.append({'row': lab, 'col': col, 'value': v})
    write('T16_e2a_yields.jsonl', rows)


def spotcheck_and_quality():
    gate = json.loads((ROOT / 'E2_stage1_judge/gate.json').read_text())
    rows = []
    for r in gate['rows']:
        a, b = r['judge_defect_free'], r['author_defect_free']
        if a in (None, '') or b in (None, ''):
            continue
        rows.append({'row': 'wave-1 spot items (all 12)', 'col': 'judge vs author defect-free', 'a': a, 'b': b})
    write('T10_spotcheck_rows.jsonl', rows)
    q = gate['judge_quality']
    qrows = []
    for col, k in (('self-contradictions', q['self_contradictions']),
                   ('eligible field disagrees with derived rule', q['eligible_field_disagrees_with_rule'])):
        for _ in range(int(k)):
            qrows.append({'row': 'wave-1 spot items', 'col': col, 'y': 1})
        for _ in range(int(q['n'] - k)):
            qrows.append({'row': 'wave-1 spot items', 'col': col, 'y': 0})
    write('T11_judge_quality_rows.jsonl', qrows)


def run_integrity():
    w1 = json.loads(W1.read_text())
    w2 = json.loads(W2.read_text())
    e4 = json.loads((ROOT / 'E4_manifest/summary.json').read_text())
    pe = json.loads((ROOT / 'Paper_evaluators_full_v11/summary.json').read_text())
    rows = []
    for run, planned, calls, valid, failed, cost in (
            ('E2-A wave 1 screening', w1['planned'], w1['calls'], w1['valid'], w1['failed'], w1['cost_usd']),
            ('E2-A option C screening', w2['planned'], w2['calls'], w2['valid'], w2['failed'], w2['cost_usd']),
            ('E4 manifest donor pass', e4['planned_calls'], e4['calls'], e4['calls'] - e4['failed'],
             e4['failed'], e4['cost_usd'])):
        for col, v in (('planned', planned), ('called', calls), ('valid', valid), ('failed', failed)):
            rows.append({'row': run, 'col': col, 'value': v})
        rows.append({'row': run, 'col': 'cost (USD micros)', 'value': round(cost * 1e6)})
    rows.append({'row': 'E2-A option C total (seeds + screening)', 'col': 'cost (USD micros)',
                 'value': round(w2['option_c_cost_usd'] * 1e6)})
    rows += [{'row': 'Paper evaluators v1.1 judge', 'col': col, 'value': pe[k]}
             for k, col in (('planned', 'planned'), ('calls', 'called'), ('valid', 'valid'), ('failed', 'failed'))]
    rows.append({'row': 'Paper evaluators v1.1 judge', 'col': 'cost (USD micros)', 'value': round(pe['cost_usd'] * 1e6)})
    write('run_integrity_rows.jsonl', rows)


def e4_counts():
    m = json.loads(MAN.read_text())
    r = json.loads(REXT.read_text())
    rows = []
    groups = {}
    for c in m['cases']:
        g = c.get('group') or ('unscored' if c.get('matcher_status') == 'failed' else 'unknown')
        groups.setdefault(g, {}).setdefault(c['benchmark'], 0)
        groups[g][c['benchmark']] += 1
    for g in ('extraction_omission', 'distortion', 'selection_omission', 'candidate_aggregation',
              'correct_control', 'partial', 'unscored'):
        for b in ('MQ', 'SB-5', 'SB-10'):
            rows.append({'row': GROUP_LABEL.get(g, g), 'col': f'{b} scored' if g != 'unscored' else f'{b} unscored',
                         'value': groups.get(g, {}).get(b, 0)})
    rows += [
        {'row': 'all cases', 'col': 'cohort cases', 'value': len(m['cases'])},
        {'row': 'all cases', 'col': 'scored', 'value': m['counts']['scored']},
        {'row': 'all cases', 'col': 'unscored (matcher failed)', 'value': m['counts']['unscored']},
        {'row': 'extraction (R-ext reconstruction)', 'col': 'cases', 'value': r['cases']},
        {'row': 'extraction (R-ext reconstruction)', 'col': 'possible donor volumes', 'value': r['possible_pairs']},
        {'row': 'extraction (R-ext reconstruction)', 'col': 'same-volume matched pairs', 'value': r['matched_pairs']},
    ]
    for b, v in r['matched_by_benchmark'].items():
        rows.append({'row': f'extraction matched ({b})', 'col': 'same-volume matched pairs', 'value': v})
    write('T17_e4_manifest_counts.jsonl', rows)


if __name__ == '__main__':
    paper_evaluators()
    lexical_correction()
    e2a_yields()
    e4_counts()
    spotcheck_and_quality()
    run_integrity()
    print('wrote', sorted(p.name for p in OUT.glob('T1*.jsonl')))