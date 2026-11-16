"""E4 pool matcher pass: the frozen `semantic-dev-v2` run once per held-out trace (240 traces).

Scope approved 2026-11-09: the 80 held-out instances of the locked n80 manifest x 3 models. The cohort
rule of E4-v7 is applied only to define the case list (all wrong k=1 traces + at most 15 correct controls
per model per benchmark); every trace is scored so the cap choice can be audited. No outcome is read.

Frozen matcher, unchanged: `src.audit.matcher_v2.match_trace`, including its own bounded-regeneration
rule (3 attempts per logical call). Calls are logged by the append-only ledger; a trace that fails at
the 4,096-token cap or after its attempts stays unscored with the reason and is not retried or repaired.

  python -m scripts.run_e4_pool_matcher --execute

Output: rebuttal/results/batch1/E4_pool_matcher
"""
import argparse, datetime, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.matcher_v2 import match_trace, PROMPT_SHA256, VERSION
from src.audit.pilot_common import CallLedger, digest, freeze
from scripts.run_e1_anchor_matcher import CFG_PATH as MATCHER_CFG, adapt, e1_call
from scripts.build_final_author_packet import packages

PREREG = Path('rebuttal/pilots/prereg/E4-v7.md')
CFG = Path('rebuttal/pilots/configs/E4-pool-matcher.json')
N80 = Path('rebuttal/pilots/20261108_review6/e1_n80_locked_manifest.json')
TOPUP = Path('rebuttal/results/batch1/E1_matcher_anchor_topup')
OUT = Path('rebuttal/results/batch1/E4_pool_matcher')
SEED = 42


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bench(p):
    if p['dataset'] == 'musique':
        return 'MQ'
    suffix = str(p['source_id']).rsplit('_', 1)[-1]
    return 'SB-' + suffix.lstrip('n')


def items():
    ids = {i for v in json.loads(N80.read_text())['strata'].values() for i in v['ids']}
    pk = packages(ids)
    out = []
    for (model, inst), p in pk.items():
        t = adapt(p)
        out.append({'instance': inst, 'model': model, 'benchmark': bench(p),
                    'answer_correct': bool(p['answer_correct']), 'trace': t})
    out.sort(key=lambda r: digest(['E4-pool-matcher', SEED, r['instance'], r['model']]))
    return out


def cohort(rs):
    """E4-v7 cohort rule: all wrong k=1 traces, at most 15 correct controls per model x benchmark."""
    chosen, omitted = [], []
    by = defaultdict(list)
    for r in rs:
        by[(r['model'], r['benchmark'])].append(r)
    for cell in sorted(by):
        wrong = [r for r in by[cell] if not r['answer_correct']]
        right = sorted([r for r in by[cell] if r['answer_correct']],
                       key=lambda r: digest(['E4-control', SEED, r['instance'], r['model']]))
        chosen += wrong + right[:15]
        omitted += right[15:]
    return chosen, omitted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--config', default=str(CFG))
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    mcfg = json.loads(MATCHER_CFG.read_text())
    assert cfg['prereg_sha256'] == sha(PREREG), 'pre-registration changed since it was frozen'
    assert cfg['matcher_config_sha256'] == sha(MATCHER_CFG)
    assert mcfg['matcher_frozen'] is True
    assert PROMPT_SHA256 == cfg['prompt_sha256'] == mcfg['prompt_sha256']
    assert VERSION == cfg['version'] == mcfg['version']
    assert cfg['model'] == mcfg['model'] and cfg['temperature'] == mcfg['temperature'] == 0
    assert cfg['max_tokens'] == mcfg['max_tokens'] == 4096
    assert cfg['seed'] == mcfg['seed'] == SEED
    for p, h in mcfg['code_sha256'].items():
        assert sha(p) == h, f'frozen matcher code changed: {p}'
    top = json.loads((TOPUP / 'summary.json').read_text())
    assert top['ok'] == 6 and top['failed'] == 0, 'anchor top-up must be complete before E4 starts'
    rs = items()
    case, omitted = cohort(rs)
    case_keys = {(r['instance'], r['model']) for r in case}
    # Continuation: reuse records that finished (ok, or a genuine matcher failure). A record written
# after the first ledger cap was reached made no call and is rescored now; genuine failures never are.
    done = set()
    if OUT.exists():
        for p in (OUT / 'matcher').glob('*.json'):
            r = json.loads(p.read_text())
            if r.get('status') == 'ok' or 'Call cap reached' not in str(r.get('error', '')):
                done.add(p.stem)
    rs = [r for r in rs if digest(['E4-pool-matcher', SEED, r['instance'], r['model']]) not in done]
    print(json.dumps({'traces': len(rs), 'cohort': len(case), 'omitted_controls': len(omitted),
                      'wrong': sum(not r['answer_correct'] for r in case),
                      'controls': sum(r['answer_correct'] for r in case),
                      'per_cell': {f'{m}|{b}': {'case': sum(1 for r in case if (r['model'], r['benchmark']) == (m, b))}
                                   for m in sorted({r['model'] for r in rs})
                                   for b in sorted({r['benchmark'] for r in rs})},
                      'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'matcher').mkdir(exist_ok=True)
    if not (OUT / 'cohort.json').exists():
        freeze(OUT / 'cohort.json', {'rule': 'all wrong k=1 traces + at most 15 correct controls per model x benchmark',
                                     'case': [{'instance': r['instance'], 'model': r['model'], 'benchmark': r['benchmark'],
                                               'answer_correct': r['answer_correct']} for r in case],
                                     'omitted_controls': [{'instance': r['instance'], 'model': r['model'],
                                                           'benchmark': r['benchmark']} for r in omitted],
                                     'frozen_utc': utc(), 'frozen_before_outcomes': True})
    ledger = CallLedger(OUT, cfg, PREREG, cfg['max_calls'])
    counts = {'planned': len(rs), 'attempted': 0, 'ok': 0, 'failed': 0, 'failed_keys': [],
              'failed_error_types': Counter(), 'case_planned': len(case), 'case_ok': 0, 'case_failed': 0,
              'case_failed_keys': [], 'label_status': 'matcher_labels_only_no_outcomes'}
    per = defaultdict(lambda: {'traces': 0, 'ok': 0, 'failed': 0})
    try:
        for n, r in enumerate(rs, 1):
            key = digest(['E4-pool-matcher', SEED, r['instance'], r['model']])
            cell = f"{r['model']}|{r['benchmark']}"
            counts['attempted'] += 1
            per[cell]['traces'] += 1
            rec = {'instance_id': r['instance'], 'model': r['model'], 'benchmark': r['benchmark'],
                   'answer_correct': r['answer_correct'], 'in_cohort': (r['instance'], r['model']) in case_keys,
                   'matcher_frozen': True}
            try:
                result = match_trace(ledger, key, r['trace'], cfg['model'])
                rec.update(result)
                if result['status'] == 'ok':
                    diag = diagnose_result(result, r['answer_correct'])
                    rec['diagnosis'] = diag
                    rec['trace_call'] = e1_call(diag)
                    counts['ok'] += 1
                    per[cell]['ok'] += 1
                    if rec['in_cohort']:
                        counts['case_ok'] += 1
                else:
                    counts['failed'] += 1
                    per[cell]['failed'] += 1
                    counts['failed_keys'].append(key)
                    counts['failed_error_types']['schema_exhausted'] += 1
                    if rec['in_cohort']:
                        counts['case_failed'] += 1
                        counts['case_failed_keys'].append(key)
            except Exception as exc:
                rec.update({'status': 'failed', 'value': None, 'error': type(exc).__name__ + ': ' + str(exc),
                            'failure_stage': 'call'})
                counts['failed'] += 1
                per[cell]['failed'] += 1
                counts['failed_keys'].append(key)
                counts['failed_error_types'][type(exc).__name__] += 1
                if rec['in_cohort']:
                    counts['case_failed'] += 1
                    counts['case_failed_keys'].append(key)
            freeze(OUT / 'matcher' / f"{key}.json", rec)
            print(f"{n}/{len(rs)} {'ok' if rec['status'] == 'ok' else 'failed'} {r['model']} "
                  f"{r['benchmark']} {r['instance']} {utc()}", flush=True)
    finally:
        ledger.close()
    res = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [x for x in res if x['event'] == 'result']
    recs = [json.loads(p.read_text()) for p in sorted((OUT / 'matcher').glob('*.json'))]
    allper = defaultdict(lambda: {'traces': 0, 'ok': 0, 'failed': 0})
    for r in recs:
        cell = f"{r['model']}|{r['benchmark']}"
        allper[cell]['traces'] += 1
        allper[cell]['ok' if r['status'] == 'ok' else 'failed'] += 1
    counts.update({'attempted': len(recs), 'ok': sum(r['status'] == 'ok' for r in recs),
                   'failed': sum(r['status'] != 'ok' for r in recs),
                   'case_ok': sum(r['status'] == 'ok' and r['in_cohort'] for r in recs),
                   'case_failed': sum(r['status'] != 'ok' and r['in_cohort'] for r in recs),
                   'calls_dispatched': len(res), 'calls_failed': sum(not x['success'] for x in res),
                   'cost_usd': round(sum(x.get('cost_usd') or 0 for x in res), 6), 'end_utc': utc(),
                   'per_model_benchmark': dict(allper), 'failed_error_types': dict(counts['failed_error_types']),
                   'runner_sha256': sha(__file__), 'config_sha256': digest(cfg),
                   'prereg_sha256': sha(PREREG), 'matcher_config_sha256': sha(MATCHER_CFG),
                   'freeze': {'version': VERSION, 'prompt_sha256': PROMPT_SHA256,
                              'frozen_utc': mcfg['frozen_utc'], 'model': mcfg['model'],
                              'temperature': mcfg['temperature'], 'max_tokens': mcfg['max_tokens']}})
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=2) + '\n')
    print(json.dumps({k: counts[k] for k in ('planned', 'ok', 'failed', 'case_planned', 'case_ok',
                                             'case_failed', 'calls_dispatched', 'calls_failed', 'cost_usd')}))


def diagnose_result(result, correct):
    from src.audit.semantic_matcher import diagnose
    return diagnose(result['facts'], result['carriers'], correct=correct)


if __name__ == '__main__':
    main()