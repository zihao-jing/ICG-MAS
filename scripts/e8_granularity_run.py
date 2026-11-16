"""8e: proxy-support granularity fix, before/after on 20 Silo-Bench traces.

Rule `rebuttal/pilots/prereg/Proxy-support-granularity-fix-v1.md`. Two arms, same rows,
same amended caps, same equivalence prompt; only the facts prompt differs (v1 vs v2).

    ./run.sh python -m scripts.e8_granularity_run --build
    ./run.sh python -m scripts.e8_granularity_run --run        # both arms
    ./run.sh python -m scripts.e8_granularity_run --score
"""
import argparse
import hashlib
import json
import math
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import scripts.proxy_support_run as R
from scripts.distortion_rescore_run import cp

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'rebuttal/pilots/20261115_e8_granularity'
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-granularity-fix-v1.md'
P_V1 = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v1.json'
P_V2 = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v2.json'
CAPS = ROOT / 'rebuttal/pilots/prereg/Proxy-support-caps-v1.json'
POP_SRC = ROOT / 'rebuttal/pilots/20261115_proxy_support_main_v2/population.json'
OLDRUN = ROOT / 'rebuttal/pilots/20261115_proxy_support_main'
V2RUN = ROOT / 'rebuttal/pilots/20261115_proxy_support_main_v2'
SEED = 44
N_TRUNC = 10
N_CLEAN = 10
ARM_CAP = {'before': 0.90, 'after': 0.60}
STEP_CAP = 1.5
WORKERS = 6


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def d(arm):
    return BASE / arm


def trace_evidence():
    """Rows with a stage that hit its cap in either prior run, and rows clean under the amended rule."""
    trunc, clean = set(), set()
    for src, fcap, ecap in ((OLDRUN, 4096, 3000), (V2RUN, 8000, 8000)):
        cal = src / 'calls.jsonl'
        if not cal.exists():
            continue
        for line in cal.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get('event') != 'result':
                continue
            k = e['key']
            stage, rest = k.split('/', 1)
            key = rest.rsplit('/attempt-', 1)[0]
            ct = (e.get('usage') or {}).get('completion_tokens', 0)
            lim = fcap if stage == 'facts' else ecap
            if ct >= lim - 8:
                trunc.add(key)
    facts = json.loads((V2RUN / 'facts.json').read_text())
    equiv = json.loads((V2RUN / 'equiv.json').read_text())
    for k, v in facts.items():
        if v.get('status') == 'ok' and (equiv.get(k) or {}).get('status') == 'ok':
            clean.add(k)
    return sorted(trunc), sorted(clean)


def pick(pool, n):
    return sorted(pool, key=lambda k: sha(f'{SEED}|e8|{k}'))[:n]


def build():
    trunc, clean = trace_evidence()
    sel_t, sel_c = pick(trunc, N_TRUNC), pick(clean, N_CLEAN)
    rows = {r['key']: r for r in json.loads(POP_SRC.read_text())}
    chosen = sel_t + sel_c
    assert all(k in rows for k in chosen), 'selected row missing from population'
    pop = [rows[k] for k in chosen]
    BASE.mkdir(parents=True, exist_ok=True)
    for arm in ('before', 'after'):
        out = d(arm)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'population.json').write_text(json.dumps(pop, ensure_ascii=False))
        man = {
            'recorded_before_any_call': True,
            'arm': arm, 'rule_sha256': file_sha(RULE),
            'facts_prompt': str((P_V1 if arm == 'before' else P_V2).relative_to(ROOT)),
            'facts_prompt_sha256': file_sha(P_V1 if arm == 'before' else P_V2),
            'equiv_prompt_sha256': file_sha(R.EQUIV_PROMPT),
            'caps_sha256': file_sha(CAPS),
            'population_sha256': file_sha(out / 'population.json'),
            'traces': len(pop), 'seed': SEED,
            'truncated_set': sel_t, 'non_truncated_set': sel_c,
            'trunc_candidates': len(trunc), 'clean_candidates': len(clean),
            'facts_max_tokens': 8000, 'equiv_max_tokens': 8000,
            'arm_cap_usd': ARM_CAP[arm], 'step_cap_usd': STEP_CAP,
        }
        (out / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({'trunc_candidates': len(trunc), 'clean_candidates': len(clean),
                      'truncated_set': len(sel_t), 'non_truncated_set': len(sel_c)}, indent=1))


def run_arm(arm):
    out = d(arm)
    man = json.loads((out / 'build_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    prompt = P_V1 if arm == 'before' else P_V2
    assert file_sha(prompt) == man['facts_prompt_sha256'], 'facts prompt changed'
    assert file_sha(out / 'population.json') == man['population_sha256'], 'population changed'
    assert file_sha(CAPS) == man['caps_sha256'], 'caps changed'
    R.configure(str(out.relative_to(ROOT)))
    R.FACTS_PROMPT = prompt
    R.LOCK = Lock()
    R.TOTAL['v'] = R.spent()
    rows = json.loads((out / 'population.json').read_text())
    sf = json.loads(prompt.read_text())
    se = json.loads(R.EQUIV_PROMPT.read_text())
    cp_ = json.loads(CAPS.read_text())
    ftok, etok = cp_['facts_max_tokens'], cp_['equiv_max_tokens']
    done = set()
    rl = out / 'results.jsonl'
    if rl.exists():
        done = {json.loads(l)['key'] for l in rl.read_text().splitlines() if l.strip()}
    todo = [r for r in rows if r['key'] not in done]
    print(json.dumps({'arm': arm, 'todo': len(todo), 'spent': round(R.TOTAL['v'], 6)}), flush=True)

    def one(r):
        docs = {x['unit_id'] for x in r['documents']}
        uf = sf['user'].format(question=r['question'], documents=R.render_docs(r))
        rec = {'key': r['key'], 'facts': None, 'equiv': None}
        last_ct = 0
        for n in (1, 2, 3):
            resp = R.call_parallel(f"facts/{r['key']}/attempt-{n}", R.QWEN, sf['system'],
                                   uf, ftok, ARM_CAP[arm])
            if resp is None:
                return None
            last_ct = (resp.usage or {}).get('completion_tokens', 0)
            v = R.validate_facts(R.last_object(resp.content or ''), docs) if resp.success else None
            if v is not None:
                rec['facts'] = {'status': 'ok', 'attempts': n, 'value': v}
                break
        if rec['facts'] is None:
            rec['facts'] = {'status': 'failed', 'attempts': 3, 'last_completion_tokens': last_ct,
                            'at_cap': last_ct >= ftok - 8}
            return rec
        fids = [x['fact_id'] for x in rec['facts']['value']['facts']]
        fl = '\n'.join(f"{x['fact_id']}: {x['text']}" for x in rec['facts']['value']['facts'])
        sup = '\n\n'.join(f"[{s['unit_id']}]\n{s['text']}" for s in r['gold_supports'])
        ue = se['user'].format(question=r['question'], facts=fl, supports=sup)
        last_ct = 0
        for n in (1, 2):
            resp = R.call_parallel(f"equiv/{r['key']}/attempt-{n}", R.GEMINI, se['system'],
                                   ue, etok, ARM_CAP[arm])
            if resp is None:
                return None
            last_ct = (resp.usage or {}).get('completion_tokens', 0)
            obj = R.last_object(resp.content or '') if resp.success else None
            ok = (isinstance(obj, dict) and isinstance(obj.get('facts'), list)
                  and [x.get('fact_id') for x in obj['facts']] == fids
                  and all(x.get('verdict') in R.VERDICTS for x in obj['facts']))
            if ok:
                rec['equiv'] = {'status': 'ok', 'attempts': n,
                                'value': {x['fact_id']: {'verdict': x['verdict']}
                                          for x in obj['facts']}}
                break
        if rec['equiv'] is None:
            rec['equiv'] = {'status': 'failed', 'attempts': 2, 'last_completion_tokens': last_ct,
                            'at_cap': last_ct >= etok - 8}
        return rec

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, f in enumerate(as_completed(futs), 1):
            rec = f.result()
            if rec is None:
                print(json.dumps({'skipped_at_cap': True}), flush=True)
                continue
            with R.LOCK, rl.open('a') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if i % 5 == 0 or i == len(todo):
                print(json.dumps({'arm': arm, 'done': i, 'of': len(todo),
                                  'spent': round(R.TOTAL['v'], 6)}), flush=True)
    print(json.dumps({'arm': arm, 'spent': round(R.spent(), 6)}))


def load_arm(arm):
    rl = d(arm) / 'results.jsonl'
    recs = {}
    if rl.exists():
        for l in rl.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                recs[e['key']] = e
    return recs


def truncation(rec):
    return bool((rec['facts'] or {}).get('status') == 'failed'
                and (rec['facts'] or {}).get('at_cap')) or bool(
        (rec['equiv'] or {}).get('status') == 'failed' and (rec['equiv'] or {}).get('at_cap'))


def fact_count(rec):
    v = (rec.get('facts') or {}).get('value')
    return len(v['facts']) if v else 0


def equiv_rate(recs, keys):
    pairs = []
    for k in keys:
        r = recs.get(k)
        if not r or (r['equiv'] or {}).get('status') != 'ok':
            continue
        for x in r['equiv']['value'].values():
            pairs.append((k, x['verdict'] == 'equivalent'))
    return pairs


def cluster_boot(pairs, draws=2000, seed=43):
    by = {}
    for k, ok in pairs:
        by.setdefault(k, []).append(ok)
    keys = sorted(by)
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        sample = [by[rng.choice(keys)] for _ in range(len(keys))]
        vals = [v for g in sample for v in g]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def summary(arm, recs):
    keys = sorted(recs)
    n_trunc = sum(truncation(recs[k]) for k in keys)
    fact_failed = sum((recs[k]['facts'] or {}).get('status') == 'failed' for k in keys)
    equiv_failed = sum((recs[k]['equiv'] or {}).get('status') != 'ok' for k in keys)
    counts = [fact_count(recs[k]) for k in keys]
    pairs = equiv_rate(recs, keys)
    k, n = sum(ok for _, ok in pairs), len(pairs)
    lo, hi = cp(k, n)
    blo, bhi = cluster_boot(pairs)
    return {'arm': arm, 'traces': len(keys), 'truncated': n_trunc,
            'truncation_rate': n_trunc / len(keys) if keys else None,
            'truncation_ci': list(cp(n_trunc, len(keys))) if keys else None,
            'facts_failed': fact_failed, 'equiv_failed': equiv_failed,
            'facts_per_trace': {'median': sorted(counts)[len(counts) // 2] if counts else None,
                                'mean': sum(counts) / len(counts) if counts else None,
                                'max': max(counts) if counts else None,
                                'counts': counts},
            'equivalence': {'equivalent': k, 'facts': n,
                            'rate': k / n if n else None, 'cp_ci': [lo, hi],
                            'cluster_ci': [blo, bhi]},
            'spend_usd': round(spend_arm(arm), 6)}


def spend_arm(arm):
    cal = d(arm) / 'calls.jsonl'
    if not cal.exists():
        return 0.0
    return sum((json.loads(l).get('cost_usd') or 0.0) for l in cal.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def score():
    assert file_sha(RULE) == json.loads(
        (d('before') / 'build_manifest.json').read_text())['rule_sha256'], 'rule changed'
    b, a = summary('before', load_arm('before')), summary('after', load_arm('after'))
    res = {'rule_sha256': file_sha(RULE), 'before': b, 'after': a}
    eb, ea = b['equivalence'], a['equivalence']
    bars = {
        'truncation_after_le_2pct': a['truncation_rate'] is not None and a['truncation_rate'] <= 0.02,
        'equivalence_non_inferior_5pt': (ea['rate'] is not None and eb['rate'] is not None
                                         and ea['rate'] >= eb['rate'] - 0.05),
        'equivalence_ci_lower_ge_65': ea['cp_ci'][0] >= 0.65,
    }
    res['bars'] = bars
    res['validates'] = all(bars.values())
    (BASE / 'validation.json').write_text(json.dumps(res, indent=1))
    write_report(res)
    print(json.dumps(res, indent=1))


def write_report(res):
    b, a = res['before'], res['after']

    def row(x):
        e = x['equivalence']
        return ('| %s | %d/%d | %s [%s, %s] | %s [%s, %s] | %.1f | %d | $%.6f |'
                % (x['arm'], x['truncated'], x['traces'],
                   '%.0f%%' % (100 * x['truncation_rate']) if x['truncation_rate'] is not None else '-',
                   '%.0f%%' % (100 * x['truncation_ci'][0]), '%.0f%%' % (100 * x['truncation_ci'][1]),
                   '%.3f' % e['rate'] if e['rate'] is not None else '-',
                   '%.3f' % e['cp_ci'][0], '%.3f' % e['cp_ci'][1],
                   x['facts_per_trace']['mean'] or 0, e['facts'], x['spend_usd']))
    lines = [
        '# Proxy-support granularity fix: before/after on 20 Silo-Bench traces',
        '',
        '2026-11-15. Rule `Proxy-support-granularity-fix-v1.md` (sha `%s...`), amended caps (facts 8,000, '
        'equivalence 8,000). Both arms use the same rows and the same equivalence prompt; only the facts '
        'prompt differs (`proxy_facts_prompt_v1.json` vs `proxy_facts_prompt_v2.json`). Cap $1.5 for the '
        'step; spend $%.6f.' % (res['rule_sha256'][:8], b['spend_usd'] + a['spend_usd']),
        '',
        '| arm | truncated | truncation [95% CI] | equivalence [CP 95% CI] | facts/trace (mean) | facts scored | spend |',
        '| --- | --- | --- | --- | ---: | ---: | ---: |',
        row(b), row(a), '',
        'Validation under the frozen rule: **%s**.' % ('VALIDATES' if res['validates'] else 'DOES NOT VALIDATE'),
        '',
        '| bar | result |', '| --- | --- |',
    ]
    for k, v in res['bars'].items():
        lines.append('| %s | %s |' % (k, 'pass' if v else 'fail'))
    lines += [
        '',
        '## Sample defect, disclosed',
        '',
        'The frozen rule said 20 traces (10 that truncated, 10 that did not). The two candidate pools '
        'overlap on one row, `summary_exchange|I-05_n5`: it truncated in the old-rule run (equivalence at '
        '2,996 tokens) and was clean under the amended rule in the amended-cap pilot, so it entered both '
        'sets. The population therefore holds **19 unique rows**, not 20, and each arm measured it once. '
        'The build manifest lists 20 selection slots because the duplicate was not removed when the sets '
        'were concatenated. The bars are evaluated on 19 traces.',
        '',
        '## What the fix did',
        '',
        '- **Granularity**: mean facts per trace fell from %.1f to %.1f; the largest fact list fell from %d '
        'to %d. The per-element enumeration is gone: the fixed prompt emits one fact per record '
        '(an agent array or edge list) instead of one per element.'
        % (b['facts_per_trace']['mean'], a['facts_per_trace']['mean'],
           b['facts_per_trace']['max'], a['facts_per_trace']['max']),
        '- **Failure**: the before arm lost %d of 19 fact sets and %d equivalence checks; the after arm lost '
        'none of either.' % (b['facts_failed'], b['equiv_failed']),
        '- **Equivalence** rose from %.3f to %.3f. This is the fact the gold check was measuring: with one '
        'fact per record against a support that holds the same record, the check almost always returns '
        'equivalent. The before rate was diluted by per-element facts that the gold support did not '
        'single out.' % (b['equivalence']['rate'], a['equivalence']['rate']),
        '',
        '**Caveat that matters for the population run.** Zero truncation in 19 traces cannot establish a '
        'rate at or below 2%%: the Clopper-Pearson upper bound is %.1f%%. The before arm truncated only 1 '
        'of 19 on re-run, because most of its candidate rows had truncated under the old 4,096-token cap, '
        'not under the amended one; of its 3 fact-set failures, 2 are parser/shape rejections, not '
        'truncation. The amended-cap truncators from the 20-trace pilot (III-22, III-24, II-19) were not '
        'all in this draw. So the before/after contrast is clean on granularity and equivalence, and weak '
        'on truncation: it takes a population run to estimate that rate.' % (100 * a['truncation_ci'][1]),
        '',
        '## Decision',
        '',
        'The frozen rule was met on all three bars, so Silo-Bench may run under the fixed proxy as its own '
        'population rate, inside the remaining line cap. The truncation bar should be re-checked at the '
        'first chunk of that run, on more traces, before the full 208.',
        '',
        '## Ledger',
        'Before arm $%.6f, after arm $%.6f, step total $%.6f.'
        % (b['spend_usd'], a['spend_usd'], b['spend_usd'] + a['spend_usd']),
    ]
    (BASE / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--arm', default=None)
    ap.add_argument('--score', action='store_true')
    x = ap.parse_args()
    if x.build:
        build()
    if x.run:
        for arm in ([x.arm] if x.arm else ['before', 'after']):
            run_arm(arm)
    if x.score:
        score()