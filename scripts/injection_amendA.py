"""Injection experiment, amendment A. Rule: rebuttal/pilots/prereg/Injection-v1-amendment-A.md.

    ./.conda-env/bin/python -m scripts.injection_amendA --build
    ./.conda-env/bin/python -m scripts.injection_amendA --pilot

Reuses the call wrapper, carrier step, methods and judge/R1 cells of scripts.injection_experiment (v0).
The v0 pilot outputs in rebuttal/pilots/20261115_injection/ are not read or changed here, except that the
v0 call log is read as a cache and counted toward the $4 cap.
"""
import argparse
import copy
import functools
import json
import re
from pathlib import Path

import scripts.injection_experiment as X
from scripts.injection_experiment import MAX_ATTEMPTS, MODELS, QWEN, CAP, file_sha, sha

ROOT = Path(__file__).resolve().parent.parent
AMEND = ROOT / 'rebuttal/pilots/prereg/Injection-v1-amendment-A.md'
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
OLD_CALLS = ROOT / 'rebuttal/pilots/20261115_injection/calls.jsonl'
PILOT_QUOTA = 1          # kept cases per model and type in the pilot
COVER = 0.5              # sentence coverage threshold for sharding deletion


class Ledger(X.Ledger):
    """v0 ledger: the v0 call log is a read-only cache and counts toward the cap."""

    def __init__(self, path, cap, old_path):
        super().__init__(path, cap)
        old = [json.loads(l) for l in Path(old_path).read_text().splitlines() if l.strip()]
        self.carried = sum(r.get('cost_usd') or 0.0 for r in old if r.get('event') == 'result')
        self.spent += self.carried
        for r in old:
            if r.get('event') == 'result' and r.get('success'):
                self.done.setdefault(r['call_id'], r)


@functools.lru_cache(maxsize=None)
def recs():
    return X.records()


@functools.lru_cache(maxsize=None)
def pkgs(model_key):
    return X.packages(model_key)


@functools.lru_cache(maxsize=None)
def scores_for(model_key):
    return X.load_scores(model_key)[1]


def content(text):
    return {t for t in X.tokens(text) if len(t) > 2}


def plan_sharding(pkg, rec):
    cars = {c['fact_id']: c for c in rec['carriers']['facts']}
    for fact in sorted(rec['facts']['facts'], key=lambda x: x['fact_id']):
        fid = fact['fact_id']
        ext = [u for u in cars[fid]['extraction'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        if not ext:
            continue
        uid = ext[0]['unit_ids'][0]
        owner = int(re.search(r':a(\d+):', uid).group(1))
        F = content(fact['text'])
        if not F:
            continue
        targets = []
        for c in pkg['source_contexts']:
            for s in X.sentences(c['text']):
                cov = len(F & content(s)) / len(F)
                if cov >= COVER:
                    targets.append({'agent': c['agent_id'], 'sentence': s, 'coverage': round(cov, 3)})
        if any(t['agent'] == owner for t in targets):
            return {'fact_id': fid, 'fact': fact['text'], 'owner': owner, 'unit_id': uid,
                    'targets': targets, 'source_ids': fact['source_ids']}
    return None


def plan_extraction(pkg, rec):
    cars = {c['fact_id']: c for c in rec['carriers']['facts']}
    pool = {u['unit_id']: u for u in pkg['checkpoints']['extraction']}
    trans = {}
    for u in pkg['checkpoints']['transmission']:
        trans.setdefault(u['agent_id'], set()).add(u['text'])
    for fact in sorted(rec['facts']['facts'], key=lambda x: x['fact_id']):
        fid = fact['fact_id']
        car = cars[fid]
        ext = [u for u in car['extraction'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        board = [u for u in car['board'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        if not ext or not board:
            continue
        uids = sorted({u for c in ext for u in c['unit_ids']})
        if not all(u in pool for u in uids):
            continue
        if not any(pool[u]['text'] in trans.get(pool[u]['agent_id'], set()) for u in uids):
            continue
        return {'fact_id': fid, 'fact': fact['text'], 'unit_ids': uids,
                'agents': sorted({pool[u]['agent_id'] for u in uids}),
                'unit_texts': [pool[u]['text'] for u in uids], 'source_ids': fact['source_ids']}
    return None


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
           'v0_calls_carried_usd': round(X.Ledger(OLD_CALLS, CAP).spent, 6),
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


def base_texts(pkg, a):
    return [u['text'] for u in pkg['checkpoints']['transmission'] if u['agent_id'] == a]


def make_case(model_key, inst, typ, plan, ledger):
    model = MODELS[model_key]
    base = pkgs(model_key)[inst]
    pkg = copy.deepcopy(base)
    rec = recs()[(model_key, inst)]
    q = pkg['question']
    scores = scores_for(model_key).get(inst, {})
    base_pool = base['checkpoints']['extraction']
    agents = sorted({u['agent_id'] for u in base_pool})
    meta = {}
    if typ == 'sharding':
        changed = sorted({t['agent'] for t in plan['targets']})
        for c in pkg['source_contexts']:
            for t in plan['targets']:
                if t['agent'] == c['agent_id']:
                    c['text'] = c['text'].replace(t['sentence'], '')
        selections, new_units = {}, {}
        for a in agents:
            if a not in changed:
                selections[a] = base_texts(base, a)
                new_units[a] = [u for u in base_pool if u['agent_id'] == a]
                continue
            ctx = next(c['text'] for c in pkg['source_contexts'] if c['agent_id'] == a)
            raw = ledger.call(f'amA/{model_key}/{inst}/a{a}/extract', model,
                              [{'role': 'system', 'content': X._EXTRACTION_SYSTEM},
                               {'role': 'user', 'content': X._build_extraction_prompt(ctx, q, X.K)}],
                              max_tokens=2048)
            units = X._parse_units(raw, X.K)
            sc = []
            for i, u in enumerate(units):
                sraw = ledger.call(f'amA/{model_key}/{inst}/a{a}/score/{i}', model,
                                   [{'role': 'system', 'content': X._SCORING_SYSTEM},
                                    {'role': 'user', 'content': X._build_scoring_prompt(q, u)}],
                                   max_tokens=128)
                try:
                    sc.append(json.loads(sraw))
                except Exception:
                    sc.append({'overall': 0.5})
            selections[a] = X.selected_with_ids(units, sc)
            new_units[a] = X.ids_for(a, units)
        pool = [u for a in agents for u in new_units[a]]
        meta = {'changed_agents': changed,
                'deleted_sentences': [{'agent': t['agent'], 'coverage': t['coverage']}
                                      for t in plan['targets']]}
    else:
        removed = set(plan['unit_ids'])
        pool = [u for u in base_pool if u['unit_id'] not in removed]
        selections = {}
        for a in agents:
            base_units = [u for u in base_pool if u['agent_id'] == a]
            if not any(u['unit_id'] in removed for u in base_units):
                selections[a] = base_texts(base, a)
                continue
            sc_list = scores.get(a) or []
            keep, keep_sc = [], []
            for i, u in enumerate(base_units):
                if u['unit_id'] in removed:
                    continue
                keep.append(u['text'])
                keep_sc.append(sc_list[i] if i < len(sc_list) else {'overall': 0.5})
            selections[a] = X.selected_with_ids(keep, keep_sc)
        meta = {'removed_units': sorted(removed)}
    selected = [selections[a] for a in agents]
    araw = ledger.call(f'amA/{model_key}/{inst}/aggregate', model,
                       [{'role': 'system', 'content': X._AGGREGATION_SYSTEM},
                        {'role': 'user', 'content': X._build_evidence_board_prompt(selected, q)}],
                       max_tokens=4096)
    pred = X.extract_answer(araw)
    f1 = X.answer_f1(pred, {'answer': base['gold_answer']})
    pkg['checkpoints']['extraction'] = pool
    pkg['checkpoints']['transmission'] = [
        {'unit_id': f'transmission:a{a}:u{i}', 'agent_id': a, 'text': t}
        for a in agents for i, t in enumerate(selections[a])]
    pkg['checkpoints']['board'] = [
        {'unit_id': u['unit_id'].replace('transmission', 'board', 1), 'agent_id': u['agent_id'],
         'text': u['text']} for u in pkg['checkpoints']['transmission']]
    pkg['answer_text'] = pred
    pkg['answer_f1'] = f1
    pkg['answer_correct'] = f1 >= 1.0
    return pkg, rec['facts'], f1, meta


def residue(ledger, key, trace, facts, fid):
    """Validated presence labeller (Qwen-235B carrier step) on the injected trace."""
    car = X.carrier_step(ledger, key, trace, facts, QWEN)
    if car.get('status') != 'ok':
        return {'status': 'labeller_failed', 'faithful_units': None}
    f = next(x for x in car['value']['facts'] if x['fact_id'] == fid)
    fu = sorted({u for c in f['extraction'] if c['fidelity'] == 'faithful' for u in c['unit_ids']})
    return {'status': 'ok', 'faithful_units': fu}


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
                key = (m, case['instance'], typ)
                if key in done:
                    continue
                tried += 1
                trace, facts, f1, meta = make_case(m, case['instance'], typ, case['plan'], ledger)
                rec = {'model': m, 'instance': case['instance'], 'type': typ, 'plan': case['plan'],
                       'answer': trace['answer_text'], 'f1': f1, 'meta': meta, 'check': None,
                       'kept': False}
                if f1 < 1.0:
                    rec['check'] = residue(ledger, f'amA-check/{typ}/{m}/{case["instance"]}', trace,
                                           facts, case['plan']['fact_id'])
                    rec['kept'] = (rec['check']['status'] == 'ok'
                                   and len(rec['check']['faithful_units']) == 0)
                if rec['kept']:
                    rec['methods'] = X.methods(ledger, f'case/{typ}/{m}/{case["instance"]}',
                                               trace, facts)
                    kept += 1
                res['cases'].append(rec)
                res['spend_usd'] = round(ledger.spent, 6)
                RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
                print(json.dumps({'type': typ, 'model': m, 'instance': case['instance'],
                                  'f1': round(f1, 3),
                                  'check': (rec['check'] or {}).get('status'),
                                  'faithful_units': (rec['check'] or {}).get('faithful_units'),
                                  'kept': rec['kept'], 'spent': round(ledger.spent, 6)}), flush=True)
    summary = {}
    for typ in ('sharding', 'extraction'):
        for m in MODELS:
            rs = [r for r in res['cases'] if r['type'] == typ and r['model'] == m]
            summary[f'{m}/{typ}'] = {'attempts': len(rs),
                                     'answer_wrong': sum(r['f1'] < 1.0 for r in rs),
                                     'check_pass': sum(r['kept'] for r in rs),
                                     'kept': sum(r['kept'] for r in rs)}
    print(json.dumps({'summary': summary, 'spend_usd_total_incl_v0': round(ledger.spent, 6),
                      'spend_usd_amendA': round(ledger.spent - ledger.carried, 6)}, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot()
