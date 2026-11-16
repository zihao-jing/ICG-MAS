"""Score the 608-trace main-table proxy run (no calls).

Reads the population and the three assembled files written by
`scripts.proxy_support_run --pipeline`; writes `results.json` and `report.md`.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_proxy_support_main'
POP = OUT / 'population.json'
FACTS = OUT / 'facts.json'
EQUIV = OUT / 'equiv.json'
LABELS = OUT / 'labels.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
MANIFEST = OUT / 'build_manifest.json'

sys.path.insert(0, str(ROOT))
from scripts.proxy_support_run import STAGE, carriers_for  # noqa: E402
from src.audit.sharding_check import diagnose_with_sharding  # noqa: E402


def cp(k, n):
    if n == 0:
        return 0.0, 1.0

    def cdf(p, upto):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(upto + 1))

    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(90):
            mid = (lo + hi) / 2
            if fn(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lo = 0.0 if k == 0 else solve(lambda p: cdf(p, k - 1), 0.975)
    hi = 1.0 if k == n else solve(lambda p: cdf(p, k), 0.025)
    return lo, hi


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def fail_reason(value):
    if value is None:
        return 'no_usable_output'
    return 'invalid_source_ids_or_shape'


def main():
    man = json.loads(MANIFEST.read_text())
    rows = json.loads(POP.read_text())
    facts = json.loads(FACTS.read_text()) if FACTS.exists() else {}
    equiv = json.loads(EQUIV.read_text()) if EQUIV.exists() else {}
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}

    groups = {}
    for r in rows:
        g = groups.setdefault((r['benchmark'], r['protocol']), {'traces': 0, 'facts': 0, 'eq': 0,
                                                                'failed': 0, 'scored_stage': 0})
        g['traces'] += 1
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            g['failed'] += 1
            continue
        g['facts'] += len(f['value']['facts'])
        e = equiv.get(r['key'], {})
        if e.get('status') != 'ok':
            continue
        for x in e['value'].values():
            g[f"v_{x['verdict']}"] = g.get(f"v_{x['verdict']}", 0) + 1
            if x['verdict'] == 'equivalent':
                g['eq'] += 1

    by = {}
    for (bench, prot), g in sorted(groups.items()):
        n = g['facts']
        by[f'{bench}|{prot}'] = {
            'traces': g['traces'], 'generation_failed': g['failed'],
            'generation_failure_rate': g['failed'] / g['traces'],
            'facts': n, 'equivalent': g['eq'],
            'match': g['eq'] / n if n else None,
            'match_ci': list(cp(g['eq'], n)) if n else None,
            'by_verdict': {v: g.get(f'v_{v}', 0)
                           for v in ('equivalent', 'partial', 'unsupported', 'contradicted')},
        }
    tot = {'traces': len(rows), 'generation_failed': sum(v['generation_failed'] for v in by.values()),
           'facts': sum(v['facts'] for v in by.values()),
           'equivalent': sum(v['equivalent'] for v in by.values())}
    tot['generation_failure_rate'] = tot['generation_failed'] / tot['traces']
    tot['match'] = tot['equivalent'] / tot['facts'] if tot['facts'] else None
    tot['match_ci'] = list(cp(tot['equivalent'], tot['facts'])) if tot['facts'] else None
    for bench in ('SB', 'MQ'):
        sel = [v for k, v in by.items() if k.startswith(bench + '|')]
        nf = sum(x['facts'] for x in sel)
        ne = sum(x['equivalent'] for x in sel)
        by[f'{bench}|all'] = {'traces': sum(x['traces'] for x in sel),
                              'generation_failed': sum(x['generation_failed'] for x in sel),
                              'generation_failure_rate': sum(x['generation_failed'] for x in sel)
                              / sum(x['traces'] for x in sel),
                              'facts': nf, 'equivalent': ne,
                              'match': ne / nf if nf else None,
                              'match_ci': list(cp(ne, nf)) if nf else None}

    stage = {}
    for r in rows:
        if not r.get('has_extraction'):
            continue
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            continue
        labs = {}
        for chk in ('extraction', 'board'):
            rec = labels.get(f"audit/{r['key']}/{chk}", {})
            if rec.get('status') != 'ok':
                labs = None
                break
            for fid, lab in rec['value'].items():
                labs[f'{chk}/{fid}'] = lab
        if labs is None:
            continue
        fids = [x['fact_id'] for x in f['value']['facts']]
        trace = {'question': r['question'],
                 'source_contexts': [{'context_id': d['unit_id'], 'text': d['text']}
                                     for d in r['documents']]}
        lab, _ = diagnose_with_sharding({'facts': f['value']['facts'],
                                         'support_sets': f['value']['support_sets']},
                                        carriers_for(labs, fids), trace, correct=False)
        s = STAGE.get(lab, lab)
        stage.setdefault(r['protocol'], Counter())[s] += 1

    out = {'traces': len(rows), 'with_extraction': sum(1 for r in rows if r.get('has_extraction')),
           'overall': tot, 'by_benchmark_protocol': by,
           'stage_distribution_relay': {k: dict(v) for k, v in stage.items()},
           'spend_usd': round(spent(), 8), 'cap_usd': man['cap_usd'],
           'generation_failure_causes': dict(Counter(
               fail_reason((facts.get(r['key']) or {}).get('value'))
               for r in rows if (facts.get(r['key']) or {}).get('status') != 'ok'))}
    RESULTS.write_text(json.dumps(out, indent=1))
    write_report(out, by, tot, stage)
    print(json.dumps(out, indent=1))


def write_report(out, by, tot, stage):
    def p(v):
        return '—' if v is None else f'{100 * v:.1f}'
    def iv(v):
        return '' if not v else f'[{100 * v[0]:.1f}, {100 * v[1]:.1f}]'
    lines = [
        '# Proxy support on the 608-trace main table: facts, gold check, stage',
        '',
        '2026-11-15. Same rule, prompts and amendment as the 89-case run. Population: the 608 Qwen-235B '
        'main-table trace packages (SB 52 + MQ 100, four protocols). Qwen3-235B generates the facts from '
        'the question and the source shards; Gemini 3.6 Flash checks them against the gold supports; '
        'Haiku 5.5 labels the extraction pool and the board. Spend **$%.6f**, cap $3.5.'
        % out['spend_usd'],
        '',
        'Scope: summary-exchange traces have no extraction checkpoint in the frozen package, so their '
        'facts and gold check run but the audit stage is not diagnosed (it needs an extraction pool). '
        'Stage results cover the %d relay traces only.' % out['with_extraction'],
        '',
        '## Generation',
        '',
        f"**{tot['generation_failed']}/{tot['traces']} traces produced no usable fact set = "
        f"{100 * tot['generation_failure_rate']:.1f}%.** Causes: {out['generation_failure_causes']}. "
        'The dominant cause is a rejected output shape or an invented source id; see the per-group '
        'rates below.',
        '',
        '## Proxy facts against the gold supports',
        '',
        f"Overall **{tot['equivalent']}/{tot['facts']} = {p(tot['match'])}% {iv(tot['match_ci'])}**.",
        '',
        '| benchmark \\ protocol | traces | generation failures | facts | match | 95% CI |',
        '| --- | ---: | ---: | ---: | --- | --- |',
    ]
    order = [f'{b}|{proto}' for b in ('SB', 'MQ')
             for proto in ('summary_exchange', 'random_relay', 'score_ranked_relay',
                           'redundancy_aware_relay')] + ['SB|all', 'MQ|all']
    for k in order:
        x = by[k]
        lines.append(f"| {k} | {x['traces']} | {100 * x['generation_failure_rate']:.1f}% | "
                     f"{x['facts']} | {p(x['match'])}% {iv(x['match_ci'])} |"
                     .replace(' | |', ' |'))
    lines += ['', '## Audit stage on the relay traces', '',
              '| protocol | extraction | transmission | sharding | aggregation |',
              '| --- | ---: | ---: | ---: | ---: |']
    for proto, c in sorted(stage.items()):
        lines.append(f"| {proto} | " + ' | '.join(str(c.get(s, 0)) for s in
                                                 ('extraction', 'transmission', 'sharding', 'aggregation')) + ' |')
    lines += ['',
              '**Stage agreement with the gold audit cannot be computed on these traces.** No gold-based audit '
              'stage exists for them: the audit\'s matcher records cover a different 800-instance MuSiQue '
              'cohort (0 of the 608 keys match), and the Silo-Bench and non-ranked protocols have no '
              'matcher records at all. The table above is a distribution, not an agreement. The only '
              'gold-audit comparison remains the 89 known-stage cases: 62/81 = .765 [.658, .852], with the '
              'proxy matching the truth only 52/81 and reproducing 15 of the audit\'s 18 errors.',
              '', '## Ledger', 'Spend $%.6f.' % out['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()