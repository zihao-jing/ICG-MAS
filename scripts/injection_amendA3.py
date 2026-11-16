"""Injection experiment, amendment A3. Rule: rebuttal/pilots/prereg/Injection-v1-amendment-A3.md.

    ./.conda-env/bin/python -m scripts.injection_amendA3 --build
    nohup ./.conda-env/bin/python -m scripts.injection_amendA3 --run > rebuttal/pilots/20261115_injection_amendA3/run.log 2>&1 &

Reuses the sharding plan, segmentation, make_case and methods of scripts.injection_amendA2 / amendA /
injection_experiment. New here: the extraction plan removes every pool unit with fact coverage >= COVER in
addition to the base-faithful units; the quota is pooled across models (30 kept per type, 360 attempts per type).
Earlier call logs are read as caches and their spend counts toward the $4.00 cap. Call ids are content-hashed, so a
cached call is reused only when its prompt is identical.
"""
import argparse
import json
from pathlib import Path

import scripts.injection_experiment as X
import scripts.injection_amendA as A
import scripts.injection_amendA2 as A2
from scripts.injection_experiment import MODELS, QWEN, CAP, file_sha

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Injection-v1-amendment-A3.md'
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA3'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
CARRIED = [ROOT / 'rebuttal/pilots/20261115_injection/calls.jsonl',
           ROOT / 'rebuttal/pilots/20261115_injection_amendA/calls.jsonl',
           ROOT / 'rebuttal/pilots/20261115_injection_amendA2/calls.jsonl']
TARGET_KEPT = 30
MAX_ATTEMPTS_TYPE = 360
COVER = A2.COVER


class Ledger(X.Ledger):
    """Own log plus read-only caches from earlier logs; their successful calls count toward the cap."""

    def __init__(self, path, cap, carried_paths):
        super().__init__(path, cap)
        self.carried = 0.0
        for p in carried_paths:
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


def lexical_units(pkg, fact_text):
    F = A2.content(fact_text)
    if not F:
        return []
    out = []
    for u in pkg['checkpoints']['extraction']:
        if len(F & A2.content(u['text'])) / len(F) >= COVER:
            out.append(u['unit_id'])
    return sorted(out)


def plan_extraction_A3(pkg, rec):
    plan = A.plan_extraction(pkg, rec)
    if plan is None:
        return None
    lex = lexical_units(pkg, plan['fact'])
    uids = sorted(set(plan['unit_ids']) | set(lex))
    return {**plan, 'base_unit_ids': plan['unit_ids'], 'lexical_unit_ids': lex, 'unit_ids': uids}


def build():
    el = X.eligible(A2.recs())
    candidates = {}
    for m in MODELS:
        shard = []
        for inst in el[m]:
            if len(shard) >= 120:
                break
            if (p := A2.plan_sharding(A2.pkgs(m)[inst], A2.recs()[(m, inst)])):
                shard.append({'model': m, 'instance': inst, 'type': 'sharding', 'plan': p})
        excluded = {x['instance'] for x in shard}
        extr = []
        for inst in el[m]:
            if len(extr) >= 120:
                break
            if inst in excluded:
                continue
            if (p := plan_extraction_A3(A2.pkgs(m)[inst], A2.recs()[(m, inst)])):
                # removal test: no pool unit with fact coverage >= COVER may survive the A3 removal
                F = A2.content(p['fact'])
                left = [u['unit_id'] for u in A2.pkgs(m)[inst]['checkpoints']['extraction']
                        if u['unit_id'] not in set(p['unit_ids'])
                        and len(F & A2.content(u['text'])) / len(F) >= COVER]
                assert not left, (m, inst, left)
                extr.append({'model': m, 'instance': inst, 'type': 'extraction', 'plan': p})
        candidates[m] = {'sharding': shard, 'extraction': extr}
    # pooled order per type: rank 1 of each model, then rank 2, ...
    order = {}
    for typ in ('sharding', 'extraction'):
        seq = []
        for rank in range(120):
            for m in MODELS:
                if rank < len(candidates[m][typ]):
                    seq.append(candidates[m][typ][rank])
        order[typ] = [{'model': c['model'], 'instance': c['instance']} for c in seq]
    man = {'recorded_before_any_call': True,
           'rule_file': str(RULE.relative_to(ROOT)), 'rule_sha256': file_sha(RULE),
           'code_file': str(Path(__file__).resolve().relative_to(ROOT)),
           'code_sha256': file_sha(Path(__file__)),
           'carried_calls': [str(p.relative_to(ROOT)) for p in CARRIED],
           'cap_usd': CAP, 'target_kept_per_type': TARGET_KEPT, 'max_attempts_per_type': MAX_ATTEMPTS_TYPE,
           'models': MODELS, 'candidates': candidates, 'pooled_order': order}
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({'candidates': {m: {t: len(candidates[m][t]) for t in candidates[m]} for m in candidates},
                      'pooled_order_len': {t: len(order[t]) for t in order},
                      'rule_sha256': man['rule_sha256'], 'code_sha256': man['code_sha256']}, indent=1))


def run():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(Path(__file__)) == man['code_sha256'], 'code changed'
    ledger = Ledger(CALLS, CAP, CARRIED)
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'cases': []}
    done = {(r['model'], r['instance'], r['type']) for r in res['cases']}
    stopped = None
    try:
        for typ in ('extraction', 'sharding'):
            plans = {(c['model'], c['instance']): c for c in
                     (x for m in MODELS for x in man['candidates'][m][typ])}
            kept = sum(1 for r in res['cases'] if r['type'] == typ and r['kept'])
            tried = sum(1 for r in res['cases'] if r['type'] == typ)
            for item in man['pooled_order'][typ]:
                if kept >= TARGET_KEPT or tried >= MAX_ATTEMPTS_TYPE:
                    break
                m, inst = item['model'], item['instance']
                if (m, inst, typ) in done:
                    continue
                case = plans[(m, inst)]
                tried += 1
                trace, facts, f1, meta = A.make_case(m, inst, typ, case['plan'], ledger)
                rec = {'model': m, 'instance': inst, 'type': typ, 'plan': case['plan'],
                       'answer': trace['answer_text'], 'f1': f1, 'meta': meta, 'check': None,
                       'kept': False}
                if f1 < 1.0:
                    prefix = 'amA2-check' if typ == 'sharding' else 'amA3-check'
                    rec['check'] = A2.residue(ledger, f'{prefix}/{typ}/{m}/{inst}', trace, facts,
                                              case['plan']['fact_id'])
                    rec['kept'] = rec['check']['status'] == 'ok' and not rec['check']['residual_units']
                if rec['kept']:
                    rec['methods'] = X.methods(ledger, f'case/{typ}/{m}/{inst}', trace, facts)
                    kept += 1
                res['cases'].append(rec)
                done.add((m, inst, typ))
                res['spend_usd'] = round(ledger.spent, 6)
                RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
                print(json.dumps({'type': typ, 'model': m, 'instance': inst, 'f1': round(f1, 3),
                                  'check': (rec['check'] or {}).get('status'),
                                  'residual': (rec['check'] or {}).get('residual_units'),
                                  'kept': rec['kept'], 'kept_type': kept, 'tried_type': tried,
                                  'spent': round(ledger.spent, 6)}), flush=True)
    except RuntimeError as e:
        stopped = str(e)
    summary = {'stopped': stopped, 'spend_usd_total_incl_earlier': round(ledger.spent, 6),
               'spend_usd_amendA3': round(ledger.spent - ledger.carried, 6)}
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
