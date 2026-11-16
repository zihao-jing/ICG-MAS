"""Injection experiment: sharding-loss and extraction-loss failures with known stage.

Rule `rebuttal/pilots/prereg/Injection-v1.md`, frozen before any case is generated.

    ./run.sh python -m scripts.injection_experiment --build
    ./run.sh python -m scripts.injection_experiment --pilot

The pilot stops before the full run so the projection can be reported.
"""
import argparse
import copy
import hashlib
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import scripts.b5_attribution_2x2 as B
from scripts.answer_equiv import last_object
from scripts.per_fact_points_build import atomize
from scripts.per_fact_points_run import parse as parse_atoms
from scripts.r1_qwen import coordinate_stage
from scripts.run_e1_anchor_matcher import adapt
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages
from src.audit.critical_fact_validation import load_run, reconstruct_states_and_scores
from src.audit.matcher_v2 import (CARRIER_PROMPT, carrier_schema, strict_parse,
                                  structured_call)
from src.audit.official_adapters import parse_r1, r1_prompt
from src.audit.sharding_check import fact_status, sharding_diagnosis, diagnose_with_sharding
from src.audit.semantic_matcher import validate_carriers
from src.protocols.relay import (_AGGREGATION_SYSTEM, _EXTRACTION_SYSTEM, _SCORING_SYSTEM,
                                 _build_evidence_board_prompt, _build_extraction_prompt,
                                 _build_scoring_prompt, _parse_units, _topk_select,
                                 extract_answer)
from src.eval.evaluate import answer_f1, normalize
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Injection-v1.md'
SHARD_RULE = ROOT / 'rebuttal/pilots/prereg/Sharding-presence-semantic-v1.md'
ATOM_PROMPT = ROOT / 'rebuttal/pilots/prereg/per_fact_points_prompt_v1.json'
R1_RULE = ROOT / 'rebuttal/pilots/prereg/R1-coordinate-stage-map.md'
JUDGE_PROMPT = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/attribution_prompt_v1.json'
OUT = ROOT / 'rebuttal/pilots/20261115_injection'
BUILD = OUT / 'build_manifest.json'
CASES = OUT / 'cases.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
QWEN = 'qwen/qwen3-235b-a22b-2507'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE = {
    QWEN: (0.14e-6, 0.80e-6),
    GEMINI: (0.75e-6, 3.75e-6),
    HAIKU: (0.10e-6, 0.50e-6),
    'google/gemma-4-31b-it': (0.20e-6, 0.40e-6),
    'openai/gpt-4o-mini': (0.15e-6, 0.60e-6),
}
CAP = 4.00
SEED = 20261115
K = 3
MAX_ATTEMPTS = 40


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Ledger:
    def __init__(self, path, cap):
        self.path = Path(path)
        self.cap = cap
        self.rows = ([json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]
                     if self.path.exists() else [])
        self.done = {r['call_id']: r for r in self.rows
                     if r.get('event') == 'result' and r.get('success')}
        self.spent = sum(r.get('cost_usd') or 0.0 for r in self.rows if r.get('event') == 'result')

    def call(self, key, model, messages, max_tokens=4096, temperature=0, response_format=None):
        pin, pout = PRICE[model]
        cid = sha('|'.join([key, model, json.dumps(messages, sort_keys=True), str(max_tokens),
                            json.dumps(response_format, sort_keys=True)]))
        if cid in self.done:
            return self.done[cid]['content']
        est_in = math.ceil(sum(len(str(m.get('content', ''))) for m in messages) / 4)
        if self.spent + est_in * pin + max_tokens * pout > self.cap:
            raise RuntimeError('cap')
        intent = {'event': 'intent', 'call_id': cid, 'key': key, 'model': model,
                  'prompt_sha256': sha(json.dumps(messages, sort_keys=True)),
                  'max_tokens': max_tokens, 'temperature': temperature, 'time': time.time()}
        with self.path.open('a') as f:
            f.write(json.dumps(intent) + '\n')
        t = time.monotonic()
        try:
            if model == GEMINI:
                system = '\n'.join(str(m.get('content', '')) for m in messages
                                   if m.get('role') == 'system')
                user = '\n'.join(str(m.get('content', '')) for m in messages
                                 if m.get('role') != 'system')
                resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                                 max_tokens=max_tokens, temperature=temperature,
                                                 metadata={'pilot': 'injection'}))
                usage = resp.usage or {}
                content = resp.content or '' if resp.success else ''
                if not resp.success:
                    raise RuntimeError(resp.error or 'single_request failed')
            else:
                from utility.apis.openrouter_api import _get_client
                client = _get_client().with_options(max_retries=0)
                extra = {'response_format': response_format} if response_format else {}
                raw = client.chat.completions.create(model=model, messages=messages,
                                                     temperature=temperature, max_tokens=max_tokens,
                                                     seed=42, **extra).model_dump()
                usage = raw.get('usage') or {}
                content = raw['choices'][0]['message'].get('content') or ''
            cost = (usage.get('prompt_tokens', est_in) * pin
                    + usage.get('completion_tokens', 0) * pout)
            row = dict(intent, event='result', success=True, content=content, usage=usage,
                       cost_usd=round(cost, 8), seconds=time.monotonic() - t)
        except Exception as exc:
            row = dict(intent, event='result', success=False, content='',
                       error=type(exc).__name__ + ': ' + str(exc), cost_usd=0.0,
                       seconds=time.monotonic() - t)
        with self.path.open('a') as f:
            f.write(json.dumps(row) + '\n')
        self.rows.append(row)
        self.spent += row.get('cost_usd') or 0.0
        if not row['success']:
            raise RuntimeError(row['error'])
        self.done[cid] = row
        return content


def tokens(text):
    return {t for t in normalize(text) if t.isalnum()}


def overlap(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def sentences(text):
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p.strip()]


def records():
    out = {}
    for p in MATCHER_DIR.glob('*.json'):
        r = json.loads(p.read_text())
        if r.get('status') == 'ok':
            out[(r['model'], r['instance_id'])] = r
    return out


def eligible(recs):
    out = []
    for (model, inst), r in recs.items():
        if not r.get('answer_correct'):
            continue
        cs = r['carriers']['facts']
        good = True
        for c in cs:
            for cp in ('extraction', 'board'):
                if not c[cp] or any(x['fidelity'] != 'faithful' for x in c[cp]):
                    good = False
        if good:
            out.append((sha(f'injection-v1|{SEED}|{model}|{inst}'), model, inst))
    return {m: [i for _, mm, i in sorted(x for x in out if x[1] == m)] for m in MODELS}


def unit_map(pkg):
    out = {}
    for cp in ('extraction', 'transmission', 'board'):
        for u in pkg['checkpoints'][cp]:
            out[u['unit_id']] = u['text']
    return out


def plan_sharding(pkg, rec):
    units = unit_map(pkg)
    cars = {c['fact_id']: c for c in rec['carriers']['facts']}
    for fact in sorted(rec['facts']['facts'], key=lambda x: x['fact_id']):
        fid = fact['fact_id']
        car = cars[fid]
        ext = [u for u in car['extraction'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        if not ext:
            continue
        uid = ext[0]['unit_ids'][0]
        agent = int(re.search(r':a(\d+):', uid).group(1))
        utext = units.get(uid, '')
        if not utext:
            continue
        ctx = next((c['text'] for c in pkg['source_contexts'] if c['agent_id'] == agent), '')
        best, best_s = 0.0, None
        for sup in pkg['source_supports']:
            if sup['agent_id'] != agent:
                continue
            for s in sentences(sup['text']):
                ov = overlap(utext, s)
                if ov > best:
                    best, best_s = ov, s
        if best <= 0 or not best_s or best_s not in ctx:
            continue
        return {'fact_id': fid, 'fact': fact['text'], 'agent': agent, 'unit_id': uid,
                'unit_text': utext, 'sentence': best_s, 'overlap': round(best, 3),
                'source_ids': fact['source_ids']}
    return None


def plan_extraction(pkg, rec):
    units = unit_map(pkg)
    cars = {c['fact_id']: c for c in rec['carriers']['facts']}
    trans = {a: [u['text'] for u in pkg['checkpoints']['transmission'] if u['agent_id'] == a]
             for a in {u['agent_id'] for u in pkg['checkpoints']['transmission']}}
    for fact in sorted(rec['facts']['facts'], key=lambda x: x['fact_id']):
        fid = fact['fact_id']
        car = cars[fid]
        ext = [u for u in car['extraction'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        board = [u for u in car['board'] if u['fidelity'] == 'faithful' and u['unit_ids']]
        if not ext or not board:
            continue
        uids = [u for c in ext for u in c['unit_ids']]
        agent = int(re.search(r':a(\d+):', uids[0]).group(1))
        texts = [units.get(u, '') for u in uids]
        if not all(texts) or not all(t in trans.get(agent, []) for t in texts):
            continue
        return {'fact_id': fid, 'fact': fact['text'], 'agent': agent, 'unit_ids': uids,
                'unit_texts': texts, 'source_ids': fact['source_ids']}
    return None


def build():
    """Candidate lists fixed before any call (rule Injection-v1, 'Sharding' and 'Extraction' sections).

    Sharding: the first MAX_ATTEMPTS plan-ok instances in the model's order.
    Extraction: the first MAX_ATTEMPTS plan-ok instances in the model's order that are not among the
    sharding candidates, so no base instance is used for both types whatever the outcomes.
    """
    recs = records()
    el = eligible(recs)
    pk = {m: packages(m) for m in MODELS}
    picks = {}
    for m in MODELS:
        shard = []
        for inst in el[m]:
            if len(shard) >= MAX_ATTEMPTS:
                break
            if (p := plan_sharding(pk[m][inst], recs[(m, inst)])):
                shard.append({'model': m, 'instance': inst, 'type': 'sharding',
                              'plan': p, 'base_f1': pk[m][inst]['answer_f1']})
        excluded = {x['instance'] for x in shard}
        extr = []
        for inst in el[m]:
            if len(extr) >= MAX_ATTEMPTS:
                break
            if inst in excluded:
                continue
            if (p := plan_extraction(pk[m][inst], recs[(m, inst)])):
                extr.append({'model': m, 'instance': inst, 'type': 'extraction',
                             'plan': p, 'base_f1': pk[m][inst]['answer_f1']})
        picks[m] = {'sharding': shard, 'extraction': extr}
    man = {'recorded_before_any_call': False,
           'note': ('Re-built after the off-rule pilot (offrule_v0/). The rule file is unchanged; '
                    'extraction candidates were previously taken from a shared loop and did not follow '
                    'the rule order. Off-rule calls remain in calls.jsonl and are counted in the spend.'),
           'candidate_rule': 'sharding: first 40 plan-ok in order; extraction: first 40 plan-ok in order '
                             'excluding the sharding candidates',
           'rule_sha256': file_sha(RULE), 'shard_rule_sha256': file_sha(SHARD_RULE),
           'atom_prompt_sha256': file_sha(ATOM_PROMPT),
           'r1_rule_sha256': file_sha(R1_RULE), 'judge_prompt_sha256': file_sha(JUDGE_PROMPT),
           'map_sha': '2015e084', 'matcher_records_dir': str(MATCHER_DIR.relative_to(ROOT)),
           'models': MODELS, 'seed': SEED, 'cap_usd': CAP, 'max_attempts': MAX_ATTEMPTS,
           'eligible_by_model': {m: len(el[m]) for m in MODELS},
           'picked': picks}
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({'eligible': man['eligible_by_model'],
                      'picked': {m: {t: len(picks[m][t]) for t in picks[m]} for m in picks},
                      'first': {m: {t: picks[m][t][0]['instance'] if picks[m][t] else None
                                    for t in picks[m]} for m in picks}}, indent=1))


def load_scores(model):
    results, responses = load_run(ROOT / 'rebuttal/results/batch1/expansion_stage2' / f'relay_{model}')
    return reconstruct_states_and_scores(responses)


def ids_for(agent, units, prefix='extraction'):
    return [{'unit_id': f'{prefix}:a{agent}:u{i}', 'agent_id': agent, 'text': t}
            for i, t in enumerate(units)]


def selected_with_ids(units, scores, k=K):
    ranked = sorted(zip(units, scores), key=lambda x: x[1].get('overall', 0.0), reverse=True)[:k]
    return [u for u, _ in ranked]


def make_case(model_key, inst, typ, plan, ledger):
    model = MODELS[model_key]
    pkg = copy.deepcopy(packages(model_key)[inst])
    rec = records()[(model_key, inst)]
    facts = rec['facts']
    trace = pkg
    q = trace['question']
    scores = load_scores(model_key)[1].get(inst, {})
    own = plan['agent']
    if typ == 'sharding':
        for c in trace['source_contexts']:
            if c['agent_id'] == own:
                c['text'] = c['text'].replace(plan['sentence'], '', 1)
        ctx = next(c['text'] for c in trace['source_contexts'] if c['agent_id'] == own)
        raw = ledger.call(f'rerun/{model}/{inst}/extract', model,
                          [{'role': 'system', 'content': _EXTRACTION_SYSTEM},
                           {'role': 'user', 'content': _build_extraction_prompt(ctx, q, K)}],
                          max_tokens=2048)
        new_units = _parse_units(raw, K)
        new_scores = []
        for i, u in enumerate(new_units):
            sraw = ledger.call(f'rerun/{model}/{inst}/score/{i}', model,
                               [{'role': 'system', 'content': _SCORING_SYSTEM},
                                {'role': 'user', 'content': _build_scoring_prompt(q, u)}],
                               max_tokens=128)
            try:
                new_scores.append(json.loads(sraw))
            except Exception:
                new_scores.append({'overall': 0.5})
        own_sel = selected_with_ids(new_units, new_scores)
        trace['checkpoints']['extraction'] = [
            u for u in trace['checkpoints']['extraction'] if u['agent_id'] != own]
        trace['checkpoints']['extraction'] += ids_for(own, new_units)
    else:
        units = [u for u in trace['checkpoints']['extraction'] if u['agent_id'] == own]
        keep, keep_scores = [], []
        for i, u in enumerate(units):
            if u['unit_id'] in plan['unit_ids']:
                continue
            keep.append(u)
            sc = (scores.get(own) or [])
            keep_scores.append(sc[i] if i < len(sc) else {'overall': 0.5})
        own_sel = selected_with_ids([u['text'] for u in keep], keep_scores)
        trace['checkpoints']['extraction'] = [
            u for u in trace['checkpoints']['extraction'] if u['agent_id'] != own] + keep
    agents = sorted({u['agent_id'] for u in trace['checkpoints']['extraction']})
    sel = {}
    for a in agents:
        if a == own:
            sel[a] = own_sel
        else:
            sel[a] = [u['text'] for u in trace['checkpoints']['transmission'] if u['agent_id'] == a]
    selected = [sel[a] for a in agents]
    araw = ledger.call(f'rerun/{model}/{inst}/aggregate', model,
                       [{'role': 'system', 'content': _AGGREGATION_SYSTEM},
                        {'role': 'user', 'content': _build_evidence_board_prompt(selected, q)}],
                       max_tokens=4096)
    pred = extract_answer(araw)
    f1 = answer_f1(pred, {'answer': pkg['gold_answer']})
    trace['checkpoints']['transmission'] = [
        {'unit_id': f'transmission:a{a}:u{i}', 'agent_id': a, 'text': t}
        for a in agents for i, t in enumerate(sel[a])]
    trace['checkpoints']['board'] = [
        {'unit_id': u['unit_id'].replace('transmission', 'board', 1), 'agent_id': u['agent_id'],
         'text': u['text']} for u in trace['checkpoints']['transmission']]
    trace['answer_text'] = pred
    trace['answer_f1'] = f1
    trace['answer_correct'] = f1 >= 1.0
    return trace, facts, f1


def carrier_step(ledger, key, trace, facts, model):
    def valid(x):
        validate_carriers(x, facts, trace)
        for row in x['facts']:
            for cp in ('extraction', 'board'):
                for c in row[cp]:
                    if c['role'] == 'joint' and len(c['unit_ids']) < 2:
                        raise ValueError('Joint carrier needs at least two units')
    payload = {'question': trace['question'], 'facts': facts,
               'source_contexts': trace['source_contexts'],
               'extraction': trace['checkpoints']['extraction'],
               'board': trace['checkpoints']['board']}
    return structured_call(ledger, key, model, CARRIER_PROMPT, payload,
                           carrier_schema(facts, trace), valid)


def statement_label(ledger, key, fact, trace):
    spec = json.loads(ATOM_PROMPT.read_text())
    atoms, kind = atomize(fact['text'])
    by_id = {x['context_id']: x['text'] for x in trace['source_contexts']}
    want = {s.split(':')[-1] for s in fact['source_ids']}
    entries = '\n'.join(f'[{k}] {v}' for k, v in by_id.items() if k.split(':')[-1] in want)
    user = spec['user'].format(question=trace['question'], fact=fact['text'],
                               atoms='\n'.join(f'a{i}: {t}' for i, t in enumerate(atoms, 1)),
                               entries=entries)
    raw = ledger.call(key, HAIKU,
                      [{'role': 'system', 'content': spec['system']},
                       {'role': 'user', 'content': user}], max_tokens=4096)
    lab = parse_atoms(raw or '', {f'a{i}' for i in range(1, len(atoms) + 1)})
    if lab is None:
        return 'invalid'
    vals = [v['status'] for v in lab.values()]
    if all(x == 'present' for x in vals):
        return 'present'
    if all(x == 'absent' for x in vals):
        return 'absent'
    return 'partial'


def audit_cell(ledger, scope, trace, facts, model, fixed):
    car = carrier_step(ledger, f'{scope}/carriers/{model}', trace, facts, model)
    if car.get('status') != 'ok':
        return None
    carriers = car['value']
    old, _ = diagnose_with_sharding(facts, carriers, trace, correct=False)
    if not fixed or old != 'extraction_omission':
        return B.stage_of(old)
    status, chosen = fact_status(facts, carriers)
    missing = [f for f in chosen if status[f] == 'extraction_omission']
    by_id = {x['fact_id']: x for x in facts['facts']}
    labels = []
    for fid in missing:
        labels.append(statement_label(ledger, f'{scope}/shard/{model}/{fid}',
                                      by_id[fid], trace))
    return B.stage_of(sharding_diagnosis(old, set(labels)))


def judge_case(trace):
    return {'question': trace['question'],
            'source': {str(c['agent_id']): c['text'] for c in trace['source_contexts']},
            'extraction': trace['checkpoints']['extraction'],
            'transmission': trace['checkpoints']['transmission'],
            'board': trace['checkpoints']['board'],
            'answer': trace['answer_text']}


def judge_cell(ledger, scope, trace, model):
    spec = json.loads(JUDGE_PROMPT.read_text())
    user = B.render_judge(spec, judge_case(trace))
    raw = ledger.call(f'{scope}/judge/{model}', model,
                      [{'role': 'system', 'content': spec['system']},
                       {'role': 'user', 'content': user}], max_tokens=2048)
    obj = last_object(raw or '')
    st = str((obj or {}).get('stage', '')).lower()
    return st if st in ('extraction', 'sharding', 'transmission', 'aggregation') else None


def r1_cell(ledger, scope, trace, model):
    msgs, steps = r1_prompt(trace=trace, gold=False)
    user = msgs[0]['content'] if isinstance(msgs[0], dict) else msgs[0]
    if isinstance(user, list):
        user = '\n'.join(b.get('text', '') for b in user if isinstance(b, dict))
    raw = ledger.call(f'{scope}/r1/{model}', model,
                      [{'role': 'user', 'content': user}], max_tokens=4096)
    parsed = parse_r1(raw or '', steps)
    n = len(trace['source_contexts'])
    return coordinate_stage(parsed.get('step'), n), parsed.get('mode')


def methods(ledger, scope, trace, facts):
    out = {}
    for name, model in (('audit_qwen_old', QWEN), ('audit_gemini_old', GEMINI)):
        out[name] = audit_cell(ledger, scope + '/' + name, trace, facts, model, fixed=False)
    for name, model in (('audit_qwen_fix', QWEN), ('audit_gemini_fix', GEMINI)):
        out[name] = audit_cell(ledger, scope + '/' + name, trace, facts, model, fixed=True)
    out['judge_qwen'] = judge_cell(ledger, scope, trace, QWEN)
    out['judge_gemini'] = judge_cell(ledger, scope, trace, GEMINI)
    out['r1_qwen'], out['r1_qwen_mode'] = r1_cell(ledger, scope, trace, QWEN)
    out['r1_gemini'], out['r1_gemini_mode'] = r1_cell(ledger, scope, trace, GEMINI)
    return out


def pilot():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    ledger = Ledger(CALLS, CAP)
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'cases': []}
    done = {(r['model'], r['instance'], r['type']) for r in res['cases']}
    for typ in ('sharding', 'extraction'):
        for m in MODELS:
            kept = sum(1 for r in res['cases'] if r['type'] == typ and r['model'] == m
                       and r['kept'])
            if kept:
                continue
            attempts = 0
            for case in man['picked'][m][typ]:
                if attempts >= MAX_ATTEMPTS:
                    break
                key = (m, case['instance'], typ)
                if key in done:
                    continue
                attempts += 1
                trace, facts, f1 = make_case(m, case['instance'], typ, case['plan'], ledger)
                rec = {'model': m, 'instance': case['instance'], 'type': typ,
                       'plan': case['plan'], 'answer': trace['answer_text'],
                       'f1': f1, 'kept': f1 < 1.0}
                if rec['kept']:
                    rec['methods'] = methods(ledger, f'case/{typ}/{m}/{case["instance"]}',
                                             trace, facts)
                res['cases'].append(rec)
                res['spend_usd'] = round(ledger.spent, 6)
                RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
                print(json.dumps({'type': typ, 'model': m, 'instance': case['instance'],
                                  'f1': round(f1, 3), 'kept': rec['kept'],
                                  'spent': round(ledger.spent, 6)}), flush=True)
                if rec['kept']:
                    break
    kept = [r for r in res['cases'] if r['kept']]
    n_kept = len(kept)
    proj = ledger.spent / n_kept * 60 if n_kept else None
    print(json.dumps({'kept': n_kept, 'attempts': len(res['cases']),
                      'spend_usd': round(ledger.spent, 6),
                      'projection_full_60_usd': round(proj, 4) if proj else None}, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot()