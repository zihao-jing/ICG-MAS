"""Stage attribution on known-stage cases: audit vs lexical-drop baseline.

Rule: `rebuttal/pilots/20261113_method_comparison/COMPARISON_RULE.md`, frozen
before this run. Zero model calls.

    ./run.sh python -m scripts.method_comparison
"""
import json
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from scripts.run_expansion_stage2 import MODELS, packages
from src.audit.e4_fix_gates import recall

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_method_comparison'
RULE = OUT / 'COMPARISON_RULE.md'
INJECTED = ROOT / 'rebuttal/pilots/20261113_injected_distortion/accepted.json'
PRESENCE = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair/presence.json'
MANIFEST = OUT / 'run_manifest.json'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
THRESH = 0.05


def file_sha(path):
    return __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()


def coverage(supports, units):
    if not supports or not units:
        return 0.0
    return sum(max(recall(u['text'], s['text']) for u in units)
               for s in supports) / len(supports)


def baseline(trace):
    supports = trace['source_supports']
    ext = trace['checkpoints']['extraction']
    board = trace['checkpoints']['board']
    d1 = 1.0 - coverage(supports, ext)
    d2 = coverage(supports, ext) - coverage(supports, board)
    if d1 >= THRESH and d1 >= d2:
        return 'extraction'
    if d2 >= THRESH:
        return 'transmission'
    return 'aggregation'


def acc(k, n):
    lo, hi = cp_ci(k, n)
    return {'k': k, 'n': n, 'acc': k / n if n else None,
            'lo': lo, 'hi': hi}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cat = json.loads(INJECTED.read_text())['accepted']
    pk = {m: packages(m) for m in MODELS}
    # injected: corrupted board
    inj = []
    for c in cat:
        t = pk[c['model']][c['instance_id']]
        board = [dict(u) for u in t['checkpoints']['board']]
        for u in board:
            if u['unit_id'] == c['unit_id']:
                u['text'] = c['corrupt']
        tt = {'source_supports': t['source_supports'],
              'checkpoints': {'extraction': t['checkpoints']['extraction'],
                              'board': board}}
        inj.append({'instance_id': c['instance_id'], 'truth': 'transmission',
                    'audit': 'transmission', 'baseline': baseline(tt),
                    'always_agg': 'aggregation'})
    # missing-fact cohort: first trace per instance
    p = json.loads(PRESENCE.read_text())['traces']
    chosen = {}
    order = ('gemma31b', 'gpt4omini', 'qwen235b')
    for r in p:
        inst = r['instance_id']
        if inst not in chosen or order.index(r['model']) < \
                order.index(chosen[inst]['model']):
            chosen[inst] = r
    coh = []
    for inst, r in sorted(chosen.items()):
        t = pk[r['model']][inst]
        truth = 'sharding' if r['label_final'] == 'absent' else 'extraction'
        audit_new = 'sharding' if truth == 'sharding' else 'extraction'
        coh.append({'instance_id': inst, 'truth': truth,
                    'audit_old': 'extraction', 'audit_new': audit_new,
                    'baseline': baseline(t), 'always_agg': 'aggregation'})
    res = {'injected': inj, 'cohort': coh,
           'scores': {}}
    n = len(inj)
    for name, key in (('audit', 'audit'), ('baseline', 'baseline'),
                      ('always_aggregation', 'always_agg')):
        res['scores'][f'injected/{name}'] = acc(
            sum(x[key] == x['truth'] for x in inj), n)
    n = len(coh)
    for name, key in (('audit_old', 'audit_old'), ('audit_new', 'audit_new'),
                      ('baseline', 'baseline'),
                      ('always_aggregation', 'always_agg')):
        res['scores'][f'cohort/{name}'] = acc(
            sum(x[key] == x['truth'] for x in coh), n)
    # cohort scored against the older truth "extraction for all"
    for name, key in (('audit_old', 'audit_old'), ('audit_new', 'audit_new'),
                      ('baseline', 'baseline')):
        res['scores'][f'cohort_extraction_truth/{name}'] = acc(
            sum(x[key] == 'extraction' for x in coh), n)
    RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps(
        {'rule_sha256': file_sha(RULE), 'recorded_before_first_run': True,
         'model_calls': 0, 'spend_usd': 0.0,
         'injected': len(inj), 'cohort': len(coh)}, indent=1))
    lines = ['# Stage attribution on known-stage cases (item 6)\n',
             f"Rule `COMPARISON_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), "
             'frozen before the comparison. Zero model calls; spend $0.000000. '
             'Stages: sharding, extraction, relay checkpoint, final '
             'aggregation.\n',
             '## Injected distortions (30, truth = relay checkpoint)\n',
             '| method | correct | accuracy (95% CI) |',
             '| --- | ---: | --- |']
    for name in ('audit', 'baseline', 'always_aggregation'):
        s = res['scores'][f'injected/{name}']
        lines.append(f"| {name.replace('_', ' ')} | {s['k']}/{s['n']} | "
                     f"{100 * s['acc']:.1f}% "
                     f"({100 * s['lo']:.1f}-{100 * s['hi']:.1f}) |")
    lines += ['', 'The audit\'s 30/30 here is **by construction**: the injected '
              'unit is the one the diagnosis names, so this set measures the '
              'baseline against a fixed audit label, not the audit\'s accuracy.\n',
              '## Missing-fact cohort (59, truth from the presence rule)\n',
              '| method | correct | accuracy (95% CI) |',
              '| --- | ---: | --- |']
    for name in ('audit_old', 'audit_new', 'baseline', 'always_aggregation'):
        s = res['scores'][f'cohort/{name}']
        lines.append(f"| {name.replace('_', ' ')} | {s['k']}/{s['n']} | "
                     f"{100 * s['acc']:.1f}% "
                     f"({100 * s['lo']:.1f}-{100 * s['hi']:.1f}) |")
    lines += ['', 'Against the older truth "extraction for all 59": audit old '
              + f"{res['scores']['cohort_extraction_truth/audit_old']['k']}/59, "
              'audit new '
              + f"{res['scores']['cohort_extraction_truth/audit_new']['k']}/59, "
              'baseline '
              + f"{res['scores']['cohort_extraction_truth/baseline']['k']}/59.\n",
              '## Reading\n',
              'The audit\'s **30/30 and 59/59 are consequences of the same '
              'rule that defines the stage**: the injected unit is the '
              'diagnosis by construction, and the cohort truth is the '
              'presence rule the item-9 check applies. They show the rule is '
              'applied consistently, not that the audit is accurate. The '
              'lexical-drop baseline uses the same checkpoints but no '
              'critical-fact labels; it cannot see a one-unit distortion that '
              'leaves most support tokens intact, and it has no '
              'input-presence check, so it misses the relay and sharding '
              'cases. The comparison is descriptive: it shows what the '
              'critical-fact labels and the input check add on these cases, '
              'and is not an independent accuracy estimate for the audit.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(res['scores'], indent=1))


if __name__ == '__main__':
    main()