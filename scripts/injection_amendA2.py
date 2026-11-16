"""Injection experiment, amendment A2. Rule: rebuttal/pilots/prereg/Injection-v1-amendment-A2.md.

    ./.conda-env/bin/python -m scripts.injection_amendA2 --build
    ./.conda-env/bin/python -m scripts.injection_amendA2 --pilot

Reuses the injection and rerun logic of scripts.injection_amendA (make_case) and the methods of
scripts.injection_experiment (v0). Sharding plans and the residue check are new in this file.
Earlier pilot outputs are read only as call caches and counted toward the cap.
"""
import argparse
import functools
import json
import re
from pathlib import Path

import scripts.injection_experiment as X
import scripts.injection_amendA as A
from scripts.injection_experiment import MODELS, QWEN, CAP, file_sha

ROOT = Path(__file__).resolve().parent.parent
AMEND = ROOT / 'rebuttal/pilots/prereg/Injection-v1-amendment-A2.md'
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA2'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
OLD_CALLS = [ROOT / 'rebuttal/pilots/20261115_injection/calls.jsonl',
             ROOT / 'rebuttal/pilots/20261115_injection_amendA/calls.jsonl']
MAX_ATTEMPTS = 120
PILOT_QUOTA = 1
COVER = 0.6
SCAFFOLD = re.compile(r'^(Question:|You hold the following evidence|\[Document:)')


class Ledger(X.Ledger):
    """Earlier call logs are read-only caches and count toward the cap."""

    def __init__(self, path, cap, old_paths):
        super().__init__(path, cap)
        self.carried = 0.0
        for p in old_paths:
            for l in Path(p).read_text().splitlines():
                if not l.strip():
                    continue
                r = json.loads(l)
                if r.get('event') != 'result':
                    continue
                self.carried += r.get('cost_usd') or 0.0
                if r.get('success'):
                    self.done.setdefault(r['call_id'], r)
        self.spent += self.carried


def segments(text):
    out = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or SCAFFOLD.match(line):
            continue
        out += [s.strip() for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
    return out


def content(text):
    return {t for t in X.tokens(text) if len(t) > 2}


def plan_sharding(pkg, rec):
    cars = {c['fact_id']: c for c in rec['carriers']['facts']}
    for fact in sorted(rec['facts']['facts'], key=lambda x: x['fact_id']):
        fid = fact['fact_id']
        ext = [u for u in cars[fid]['extraction'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        if not ext:
            continue
        owner = int(re.search(r':a(\d+):', ext[0]['unit_ids'][0]).group(1))
        F = content(fact['text'])
        if not F:
            continue
        targets = []
        for c in pkg['source_contexts']:
            for s in segments(c['text']):
                cov = len(F & content(s)) / len(F)
                if cov >= COVER:
                    targets.append({'agent': c['agent_id'], 'sentence': s, 'coverage': round(cov, 3)})
        if any(t['agent'] == owner for t in targets):
            return {'fact_id': fid, 'fact': fact['text'], 'owner': owner,
                    'unit_id': ext[0]['unit_ids'][0], 'targets': targets,
                    'source_ids': fact['source_ids']}
    return None


plan_extraction = A.plan_extraction  # unchanged rule (amendment A)


@functools.lru_cache(maxsize=None)
def recs():
    return X.records()


@functools.lru_cache(maxsize=None)
def pkgs(model_key):
    return X.packages(model_key)


def build():
    el = X.eligible(recs())
    candidates = {}
    for m in MODELS:
        shard = []
        for inst in el[m]:
            if len(shard) >= MAX_ATTEMPTS:
                break
            if (p := plan_sharding(pkgs(m)[inst], recs()[(m, inst)])):
                shard.append({'model': m, 'instance': inst, 'type': 'sharding', 'plan': p})
        excluded = {x['instance'] for x in shard}
        extr = []
        for inst in el[m]:
            if len(extr) >= MAX_ATTEMPTS:
                break
            if inst in excluded:
                continue
            if (p := plan_extraction(pkgs(m)[inst], recs()[(m, inst)])):
                extr.append({'model': m, 'instance': inst, 'type': 'extraction', 'plan': p})
        candidates[m] = {'sharding': shard, 'extraction': extr}
    man = {'recorded_before_any_call': True,
           'rule_file': str(AMEND.relative_to(ROOT)),
           'rule_sha256': file_sha(AMEND),
           'code_file': str(Path(__file__).resolve().relative_to(ROOT)),
           'code_sha256': file_sha(Path(__file__)),
           'carried_calls': [str(p.relative_to(ROOT)) for p in OLD_CALLS],
           'cap_usd': CAP, 'max_attempts': MAX_ATTEMPTS, 'pilot_quota_per_model_type': PILOT_QUOTA,
           'models': MODELS, 'eligible_by_model': {m: len(el[m]) for m in MODELS},
           'candidates': candidates}
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({'eligible': man['eligible_by_model'],
                      'candidates': {m: {t: len(candidates[m][t]) for t in candidates[m]} for m in candidates},
                      'first': {m: {t: candidates[m][t][0]['instance'] if candidates[m][t] else None
                                    for t in candidates[m]} for m in candidates},
                      'rule_sha256': man['rule_sha256'], 'code_sha256': man['code_sha256']}, indent=1))


def residue(ledger, key, trace, facts, fid):
    """Validated presence labeller, residue = any non-absent extraction-pool copy."""
    car = X.carrier_step(ledger, key, trace, facts, QWEN)
    if car.get('status') != 'ok':
        return {'status': 'labeller_failed', 'residual_units': None}
    f = next(x for x in car['value']['facts'] if x['fact_id'] == fid)
    units = sorted({(u, c['fidelity']) for c in f['extraction'] if c['fidelity'] != 'absent'
                    for u in c['unit_ids']})
    return {'status': 'ok', 'residual_units': [list(x) for x in units]}


def pilot():
    man = json.loads(BUILD.read_text())
    assert file_sha(AMEND) == man['rule_sha256'], 'rule changed'
    assert file_sha(Path(__file__)) == man['code_sha256'], 'code changed'
    ledger = Ledger(CALLS, CAP, OLD_CALLS)
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'cases': []}
    done = {(r['model'], r['instance'], r['type']) for r in res['cases']}
    for typ in ('sharding', 'extraction'):
        for m in MODELS:
            tried = sum(1 for r in res['cases'] if r['type'] == typ and r['model'] == m)
            kept = sum(1 for r in res['cases'] if r['type'] == typ and r['model'] == m and r['kept'])
            for case in man['candidates'][m][typ]:
                if kept >= PILOT_QUOTA or tried >= MAX_ATTEMPTS:
                    break
                if (m, case['instance'], typ) in done:
                    continue
                tried += 1
                trace, facts, f1, meta = A.make_case(m, case['instance'], typ, case['plan'], ledger)
                rec = {'model': m, 'instance': case['instance'], 'type': typ, 'plan': case['plan'],
                       'answer': trace['answer_text'], 'f1': f1, 'meta': meta, 'check': None,
                       'kept': False}
                if f1 < 1.0:
                    rec['check'] = residue(ledger, f'amA2-check/{typ}/{m}/{case["instance"]}', trace,
                                           facts, case['plan']['fact_id'])
                    rec['kept'] = rec['check']['status'] == 'ok' and not rec['check']['residual_units']
                if rec['kept']:
                    rec['methods'] = X.methods(ledger, f'case/{typ}/{m}/{case["instance"]}', trace, facts)
                    kept += 1
                res['cases'].append(rec)
                res['spend_usd'] = round(ledger.spent, 6)
                RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
                print(json.dumps({'type': typ, 'model': m, 'instance': case['instance'],
                                  'f1': round(f1, 3),
                                  'check': (rec['check'] or {}).get('status'),
                                  'residual': (rec['check'] or {}).get('residual_units'),
                                  'deleted': len(meta.get('deleted_sentences', meta.get('removed_units', []))),
                                  'kept': rec['kept'], 'spent': round(ledger.spent, 6)}), flush=True)
    print(json.dumps({'spend_usd_total_incl_earlier': round(ledger.spent, 6),
                      'spend_usd_amendA2': round(ledger.spent - ledger.carried, 6)}, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot()
