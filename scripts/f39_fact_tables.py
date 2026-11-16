"""Fact tables for the stage-naming exploration (step 39). Zero model calls.

For each known-cause case (82 runs = 41 cases x 2 backbones; plus the 89-case set), build the audit's own
fact table from the stored records:
  - audit facts (fact_id, text, source_ids) and the audit's carrier record per backbone (old rule);
  - the intended fact: injected cases use the uncorrupted sentence (`original` in accepted.json);
    deleted-fact cases use the plan fact (`plan.fact` in 20261115_injection_amendA3/results.json);
    cohort cases use the presence-check target fact (presence.json);
  - the match of the intended fact to an audit fact by content recall >= 0.8, unique best. A run with no
    unique match is EXCLUDED and the reason is recorded. No fact is guessed.

Named (A3 rule, fixed here): the audit names the lost fact when the matched fact carries no `faithful` or
`partial` status at either checkpoint (extraction or board), i.e. it is absent or distorted at the point the
audit reports.

    .conda-env/bin/python scripts/f39_fact_tables.py
Output: rebuttal/pilots/20261116_stage_naming/fact_tables.json
"""
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_diagnosis_89 import accepted, records  # noqa: E402
from scripts.repair_presence_check import content_recall  # noqa: E402

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'
CASES_V2 = P / '20261113_attribution_comparison/cases_v2.json'
INJ_MATCHER = P / '20261113_audit_diagnosis_89/matcher_run/calls.jsonl'
B2X2_CALLS = P / '20261115_b5_attribution_2x2/calls.jsonl'
A3_RESULTS = P / '20261115_injection_amendA3/results.json'
A3_CALLS = P / '20261115_injection_amendA3/calls.jsonl'
A2_CALLS = P / '20261115_injection_amendA2/calls.jsonl'  # carried by the A3 ledger (replayed calls)
PRESENCE = P / '20261112_missing_fact_repair/presence.json'
QWEN = 'qwen/qwen3-235b-a22b-2507'
GEMINI = 'google/gemini-3.6-flash'
# Deleted-fact keep set (step 10c), from 20261115_injection_amendA3/keep_rule_decisions.md
DELETED_DROP = {'2hop__826864_17335', '2hop__434218_29898', '2hop__189094_612080',
                '2hop__301587_233146', '3hop2__88342_93066_90766', '3hop1__163654_503371_21711'}
MATCH_MIN = 0.8
BACKBONES = ('qwen', 'gemini')


STRICT = '--strict' in sys.argv  # amendment 1: parse model output with the pipeline's strict_parse
if STRICT:
    from src.audit.matcher_v2 import strict_parse as _strict


def parse(text):
    if STRICT:
        try:
            return _strict(text)
        except Exception:
            return None
    for f in (json.loads, ast.literal_eval):
        try:
            return f(text)
        except Exception:
            pass
    return None


def jsonl(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def agent_of_unit(uid):
    # unit ids look like 'extraction:a1:u2', 'board:a0:u0', 'gold:agent-1', 'agent-0'
    s = str(uid)
    if ':a' in s:
        return s.split(':a', 1)[1].split(':', 1)[0]
    if 'agent-' in s:
        return s.split('agent-', 1)[1]
    return None


def named(carrier_row):
    """carrier_row: {'extraction': [...], 'board': [...]} -> True if no faithful/partial carrier at either checkpoint."""
    for cp in ('extraction', 'board'):
        for c in carrier_row.get(cp, []) or []:
            if c.get('fidelity') in ('faithful', 'partial'):
                return False
    return True


def holder(carrier_row):
    agents = []
    for cp in ('extraction', 'board'):
        for c in carrier_row.get(cp, []) or []:
            agents += [agent_of_unit(u) for u in c.get('unit_ids', [])]
    return sorted({a for a in agents if a is not None})


def match(intended, facts):
    scored = sorted(((content_recall(f['text'], intended), f) for f in facts), key=lambda x: -x[0])
    if not scored or scored[0][0] < MATCH_MIN:
        return None, 'no audit fact reaches content recall 0.8', (scored[0][0] if scored else 0.0)
    if len(scored) > 1 and scored[1][0] >= MATCH_MIN and scored[1][0] == scored[0][0]:
        return None, 'two audit facts tie at the best recall', scored[0][0]
    return scored[0][1], 'ok', round(scored[0][0], 3)


def build_injected(ledger_matcher, b2x2):
    cases = [c for c in json.loads(CASES_V2.read_text()) if c['population'] == 'injected']
    acc = accepted()
    facts_by, qwen_c, gem_c = {}, {}, {}
    for r in ledger_matcher:
        if r.get('event') != 'result' or not r.get('success', True):
            continue
        k = r.get('key', '')
        if k.startswith('audit-inj/') and k.endswith('/facts/attempt-1'):
            facts_by[k[len('audit-inj/'):-len('/facts/attempt-1')]] = parse(r['content'])
        elif k.startswith('audit-inj/') and k.endswith('/carriers/attempt-1'):
            qwen_c[k[len('audit-inj/'):-len('/carriers/attempt-1')]] = parse(r['content'])
    for r in b2x2:
        if r.get('event') != 'result' or not r.get('success', True):
            continue
        k = r.get('key', '')
        if k.startswith('audita/inj/') and k.endswith('/carriers/attempt-1'):
            gem_c[k[len('audita/inj/'):-len('/carriers/attempt-1')]] = parse(r['content'])
    rows = []
    for c in cases:
        model, inst = c['key'].split('/')[1], c['key'].split('/')[2]
        ck = f'{model}/{inst}'
        a = acc.get((model, inst))
        intended = a['original'] if a else None
        base = {'key': c['key'], 'population': 'injected', 'model': model, 'instance': inst,
                'known_stage': c['known_stage'], 'intended_fact': intended, 'intended_source': 'accepted.json original'}
        if intended is None or ck not in facts_by or facts_by[ck] is None:
            rows.append({**base, 'excluded': 'no intended fact or no audit fact record'})
            continue
        facts = facts_by[ck]['facts']
        f, why, score = match(intended, facts)
        if f is None:
            rows.append({**base, 'excluded': why, 'match_recall': score})
            continue
        for bb, store in (('qwen', qwen_c), ('gemini', gem_c)):
            car = store.get(ck)
            if car is None:
                rows.append({**base, 'backbone': bb, 'excluded': 'no carrier record'})
                continue
            row = next((x for x in car['facts'] if x['fact_id'] == f['fact_id']), None)
            if row is None:
                rows.append({**base, 'backbone': bb, 'excluded': 'carrier record lacks matched fact id'})
                continue
            rows.append({**base, 'backbone': bb, 'matched_fact_id': f['fact_id'], 'matched_fact_text': f['text'],
                         'match_recall': score, 'audit_status': {cp: [c_['fidelity'] for c_ in row.get(cp, [])]
                                                                 for cp in ('extraction', 'board')},
                         'holder_agents': holder(row), 'named': named(row)})
    return rows


def build_deleted(matcher_recs, a3_calls):
    a3_calls = a3_calls + jsonl(A2_CALLS)
    res = json.loads(A3_RESULTS.read_text())
    kept = [c for c in res['cases'] if c.get('kept') in (True, 'True') and c['instance'] not in DELETED_DROP]
    by_key = {}
    for r in a3_calls:
        if r.get('event') != 'result' or not r.get('success', True):
            continue
        by_key[r['key']] = r
    rows = []
    for c in kept:
        m, inst, typ = c['model'], c['instance'], c['type']
        base = {'key': f"case/{typ}/{m}/{inst}", 'population': 'deleted', 'model': m, 'instance': inst,
                'known_stage': typ, 'intended_fact': c['plan']['fact'],
                'intended_source': 'injection_amendA3 results.json plan.fact', 'plan_fact_id': c['plan']['fact_id']}
        rec = matcher_recs.get((m, inst))
        if rec is None or not rec.get('facts'):
            rows.append({**base, 'excluded': 'no matcher facts record'})
            continue
        facts = rec['facts']['facts']
        f, why, score = match(c['plan']['fact'], facts)
        if f is None:
            rows.append({**base, 'excluded': why, 'match_recall': score})
            continue
        for bb, tag in (('qwen', QWEN), ('gemini', GEMINI)):
            key = f"case/{typ}/{m}/{inst}/audit_{bb}_old/carriers/{tag}/attempt-1"
            r = by_key.get(key)
            if r is None:
                rows.append({**base, 'backbone': bb, 'excluded': 'no carrier call logged'})
                continue
            car = parse(r['content'])
            row = next((x for x in car['facts'] if x['fact_id'] == f['fact_id']), None) if car else None
            if row is None:
                rows.append({**base, 'backbone': bb, 'excluded': 'carrier record lacks matched fact id'})
                continue
            rows.append({**base, 'backbone': bb, 'matched_fact_id': f['fact_id'], 'matched_fact_text': f['text'],
                         'match_recall': score, 'audit_status': {cp: [c_['fidelity'] for c_ in row.get(cp, [])]
                                                                 for cp in ('extraction', 'board')},
                         'holder_agents': holder(row), 'named': named(row)})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    matcher = jsonl(INJ_MATCHER)
    b2x2 = jsonl(B2X2_CALLS)
    a3 = jsonl(A3_CALLS)
    recs = {k: v for k, v in records().items()}
    inj = build_injected(matcher, b2x2)
    dele = build_deleted(recs, a3)
    rows = inj + dele
    out_name = 'fact_tables_strict.json' if STRICT else 'fact_tables.json'
    (OUT / out_name).write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print('wrote', out_name)
    runs = [r for r in rows if 'backbone' in r]
    excl_case = Counter(r['excluded'] for r in rows if 'excluded' in r)
    print(json.dumps({'case_rows': len({r['key'] for r in rows}),
                      'runs_with_table': len([r for r in runs if 'excluded' not in r]),
                      'runs_excluded': len([r for r in runs if 'excluded' in r]),
                      'case_level_excluded_reasons': dict(excl_case)}, indent=1))
    print(Counter((r['population'], r.get('named')) for r in runs if 'excluded' not in r))


if __name__ == '__main__':
    main()
