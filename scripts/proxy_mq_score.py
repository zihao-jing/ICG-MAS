"""Score the MuSiQue population run (400 traces, amended caps). No calls.

    ./run.sh python -m scripts.proxy_mq_score [--dir DIR]
"""
import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import hashlib


def parse_key(k):
    """'facts/<row>/attempt-1' or 'audit/<row>/<checkpoint>/attempt-1' -> (stage, row)."""
    stage, rest = k.split('/', 1)
    rest = rest.rsplit('/attempt-', 1)[0]
    if stage == 'audit':
        rest = rest.rsplit('/', 1)[0]
    return stage, rest


def cp(k, n):
    if n == 0:
        return 0.0, 1.0

    def cdf(p, upto):
        lp, lq = math.log(p), math.log(1 - p)
        return math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1)
                                  - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                         for i in range(upto + 1))

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


def cluster_boot(pairs, draws=2000, seed=43):
    by = {}
    for k, ok in pairs:
        by.setdefault(k, []).append(ok)
    keys = sorted(by)
    if not keys:
        return 0.0, 1.0
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        vals = [v for _ in range(len(keys)) for v in by[rng.choice(keys)]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='rebuttal/pilots/20261115_proxy_support_mq')
    a = ap.parse_args()
    out = ROOT / a.dir
    man = json.loads((out / 'build_manifest.json').read_text())
    rows = json.loads((out / 'population.json').read_text())
    facts = json.loads((out / 'facts.json').read_text())
    equiv = json.loads((out / 'equiv.json').read_text())
    labels = json.loads((out / 'labels.json').read_text())
    caps = json.loads((ROOT / 'rebuttal/pilots/prereg/Proxy-support-caps-v1.json').read_text())
    ftok, etok, atok = caps['facts_max_tokens'], caps['equiv_max_tokens'], caps['labeller_max_tokens']

    # per-call completion tokens, to separate truncation from other failures
    last_ct, at_cap = {}, set()
    calls = out / 'calls.jsonl'
    for line in calls.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get('event') != 'result':
            continue
        stage, key = parse_key(e['key'])
        ct = (e.get('usage') or {}).get('completion_tokens', 0)
        last_ct[(stage, key)] = ct
        lim = {'facts': ftok, 'equiv': etok, 'audit': atok}[stage]
        if ct >= lim - 8:
            at_cap.add((stage, key))

    def trunc(rec):
        for stage in ('facts', 'equiv'):
            s = rec.get(stage) or {}
            if s.get('status') == 'ok':
                continue
            if (stage, rec['key']) in at_cap:
                return True
        return False

    recs = {}
    pl = out / 'pipeline.jsonl'
    for line in pl.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            recs[e['key']] = e
    n = len(recs)
    n_trunc = sum(trunc(recs[k]) for k in recs)
    gen_fail = [k for k, r in recs.items() if (r['facts'] or {}).get('status') != 'ok']
    eq_fail = [k for k, r in recs.items() if (r['equiv'] or {}).get('status') != 'ok']

    def match(keys):
        pairs, kk, nn = [], 0, 0
        for k in keys:
            r = recs.get(k) or {}
            e = r.get('equiv') or {}
            if e.get('status') != 'ok':
                continue
            for fid, x in e['value'].items():
                ok = x['verdict'] == 'equivalent'
                pairs.append((r.get('key'), ok))
                kk += ok
                nn += 1
        return {'equivalent': kk, 'facts': nn, 'rate': kk / nn if nn else None,
                'cp_ci': list(cp(kk, nn)) if nn else None,
                'cluster_ci': list(cluster_boot(pairs)) if pairs else None}

    by_prot = {}
    for prot in sorted({r['protocol'] for r in rows}):
        keys = [r['key'] for r in rows if r['protocol'] == prot]
        m = match(keys)
        m['traces'] = len(keys)
        m['generation_failed'] = sum(1 for k in keys if k in gen_fail)
        m['truncated'] = sum(trunc(recs[k]) for k in keys if k in recs)
        m['spend_usd'] = None
        by_prot[prot] = m
    overall = match([r['key'] for r in rows])
    overall['traces'] = len(rows)
    overall['generation_failed'] = len(gen_fail)
    overall['truncated'] = n_trunc
    overall['truncation_rate'] = n_trunc / n if n else None
    overall['truncation_ci'] = list(cp(n_trunc, n)) if n else None
    overall['generation_failure_rate'] = len(gen_fail) / n if n else None
    overall['equiv_failed'] = len(eq_fail)
    overall['scored_traces'] = n

    # spend per protocol
    per = Counter()
    for line in calls.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get('event') != 'result':
            continue
        per[parse_key(e['key'])[1]] += e.get('cost_usd') or 0.0
    spend = round(sum(per.values()), 6)
    by_prot_spend = Counter()
    rowsp = {r['key']: r['protocol'] for r in rows}
    for k, v in per.items():
        by_prot_spend[rowsp[k]] += v
    for p, v in by_prot.items():
        v['spend_usd'] = round(by_prot_spend[p], 6)

    # stage distribution (relay traces only; no gold stage exists for this population)
    from scripts.proxy_support_run import STAGE, carriers_for
    from src.audit.sharding_check import diagnose_with_sharding
    stage = {}
    for r in rows:
        if not r.get('has_extraction'):
            continue
        f = facts.get(r['key'], {})
        if f.get('status') != 'ok':
            continue
        labs = {}
        ok = True
        for chk in ('extraction', 'board'):
            rec = labels.get(f"audit/{r['key']}/{chk}", {})
            if rec.get('status') != 'ok':
                ok = False
                break
            for fid, lab in rec['value'].items():
                labs[f'{chk}/{fid}'] = lab
        if not ok:
            continue
        fids = [x['fact_id'] for x in f['value']['facts']]
        trace = {'question': r['question'],
                 'source_contexts': [{'context_id': d['unit_id'], 'text': d['text']}
                                     for d in r['documents']]}
        lab, _ = diagnose_with_sharding({'facts': f['value']['facts'],
                                         'support_sets': f['value']['support_sets']},
                                        carriers_for(labs, fids), trace, correct=False)
        stage.setdefault(r['protocol'], Counter())[STAGE.get(lab, lab)] += 1
    staged = sum(sum(c.values()) for c in stage.values())

    def fsha(rel):
        return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()

    gen_at_cap = [k for k in gen_fail if ('facts', k) in at_cap]
    cell_fail = Counter(rowsp[k] for k in gen_fail)
    res = {'dir': a.dir,
           'gen_fail_at_cap': len(gen_at_cap),
           'gen_fail_other': len(gen_fail) - len(gen_at_cap),
           'gen_fail_by_cell': dict(cell_fail),
           'rule_sha': fsha('rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'),
           'caps_sha': fsha('rebuttal/pilots/prereg/Proxy-support-caps-v1.json'), 'traces': len(rows), 'scored_traces': n,
           'with_extraction': sum(1 for r in rows if r.get('has_extraction')),
           'truncated': n_trunc, 'truncation_rate': overall['truncation_rate'],
           'truncation_ci': overall['truncation_ci'],
           'generation_failed': len(gen_fail),
           'generation_failure_rate': overall['generation_failure_rate'],
           'generation_failure_causes': dict(Counter(
               'no_usable_output' if not (facts.get(k) or {}).get('value')
               else 'invalid_source_ids_or_shape' for k in gen_fail)),
           'equiv_failed': len(eq_fail),
           'overall': overall, 'by_protocol': by_prot,
           'stage_distribution': {k: dict(v) for k, v in stage.items()},
           'staged_traces': staged, 'spend_usd': spend,
           'line_cap_usd': man.get('line_cap_usd'), 'chunk_usd': man.get('chunk_usd')}
    (out / 'results.json').write_text(json.dumps(res, indent=1))
    write_report(out, res, stage)
    print(json.dumps(res, indent=1))


def write_report(out, res, stage):
    def pct(v):
        return '—' if v is None else '%.1f%%' % (100 * v)

    def ci(v):
        return '' if not v else '[%s, %s]' % ('%.1f%%' % (100 * v[0]), '%.1f%%' % (100 * v[1]))

    o = res['overall']
    man = json.loads((out / 'build_manifest.json').read_text())
    bench = (json.loads((out / 'population.json').read_text())[0].get('benchmark') or 'MQ')
    name = {'MQ': 'MuSiQue', 'SB': 'Silo-Bench'}.get(bench, bench)
    prompt_note = (' Facts prompt `proxy_facts_prompt_v2.json`, the granularity fix (sha `%s...`).'
                   % man['facts_prompt_sha256'][:8] if 'v2' in (man.get('facts_prompt') or '')
                   else '')
    lines = [
        '# %s proxy-support population rate (%d traces, amended caps)' % (name, res['traces']),
        '',
        '2026-11-15. Rule `Proxy-support-pilot-v1.md` (sha `%s...`) with amendment 1, caps '
        '`Proxy-support-caps-v1.json` (sha `%s...`: facts 8,000, equivalence 8,000, labeller 8,192). '
        'Population: all %d %s main-table traces. Qwen3-235B generates the facts '
        'from the question and the source shards; Gemini 3.6 Flash checks them against the gold supports; '
        'Haiku 5.5 labels the extraction pool and the board. Spend **$%.6f**.%s'
        % (res.get('rule_sha', '')[:8], res.get('caps_sha', '')[:8], res['traces'], name,
           res['spend_usd'], prompt_note),
        '',
        '## Truncation',
        '',
        '**%d/%d traces = %s %s** ended with a stage exhausting its attempts with the completion at its '
        'cap. The 2%% stop rule: %s.'
        % (res['truncated'], res['scored_traces'], pct(res['truncation_rate']),
           ci(res['truncation_ci']),
           'not triggered' if (res['truncation_rate'] or 0) <= 0.02 else 'TRIGGERED — run should stop'),
        '',
        'Generation failures: %d (%s). Equivalence-call failures: %d.'
        % (res['generation_failed'], pct(res['generation_failure_rate']), res['equiv_failed']),
        '',
        'Of the %d generation failures, %d were cut at the output cap and %d are shape or source-id '
        'rejections by the frozen parser or normaliser (a bare fact object with no wrapper, a flat map '
        'whose entries repeat `fact_id`, source ids carrying `[agent-0][Document: ...]` decoration). '
        'By cell: %s.'
        % (res['generation_failed'], res['gen_fail_at_cap'], res['gen_fail_other'],
           ', '.join('%s %d' % (k, v) for k, v in sorted(res['gen_fail_by_cell'].items()))),
        '',
        '## Population equivalence against the gold supports',
        '',
        '| cell | traces | generation failures | facts | equivalent | match [95% CI] | cluster CI |',
        '| --- | ---: | ---: | ---: | ---: | --- | --- |',
    ]
    for prot, x in res['by_protocol'].items():
        lines.append('| %s | %d | %d | %d | %d | %s %s | %s |'
                     % (prot, x['traces'], x['generation_failed'], x['facts'], x['equivalent'],
                        pct(x['rate']), ci(x['cp_ci']), ci(x['cluster_ci'])))
    lines.append('| **all** | %d | %d | %d | %d | **%s %s** | **%s** |'
                 % (o['traces'], o['generation_failed'], o['facts'], o['equivalent'],
                    pct(o['rate']), ci(o['cp_ci']), ci(o['cluster_ci'])))
    lines += ['',
              'CP = Clopper-Pearson over facts; cluster = instance-cluster bootstrap, 2,000 draws, seed 43.',
              '',
              '## Audit stage distribution',
              '',
              'Relay traces with a valid fact set and both checkpoint labels: %d of %d traces with an '
              'extraction checkpoint.' % (res['staged_traces'], res['with_extraction']),
              '',
              '| protocol | extraction | transmission | sharding | aggregation |',
              '| --- | ---: | ---: | ---: | ---: |']
    for proto, c in sorted(stage.items()):
        lines.append('| %s | %s |' % (proto, ' | '.join(
            str(c.get(s, 0)) for s in ('extraction', 'transmission', 'sharding', 'aggregation'))))
    lines += ['',
              '**No stage agreement is reported for these traces.** They carry no gold audit stage: the '
              'audit\'s matcher records cover a different 800-instance MuSiQue cohort (0 keys match), so '
              'the table is a distribution of the proxy\'s own labels.',
              '',
              '## Spend', '',
              'Run directory total $%.6f (all `calls.jsonl` result records).' % res['spend_usd']]
    if man.get('line_cap_usd'):
        prior = man.get('prior_line_spend_usd') or 0.0
        lines += ['', '## Line accounting against the $%.1f cap' % man['line_cap_usd'], '',
                  '| component | spend |', '| --- | ---: |',
                  '| prior line spend | %.6f |' % prior,
                  '| **this run** | **%.6f** |' % res['spend_usd'],
                  '| **line total** | **%.6f** |' % (prior + res['spend_usd']),
                  '| **remaining** | **%.6f** |' % (man['line_cap_usd'] - prior - res['spend_usd']),
                  '']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()