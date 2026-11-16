"""F38: cause-driven repairs. Rule: rebuttal/pilots/prereg/F38-cause-driven-repairs-rule.md (frozen before any call).

    .conda-env/bin/python -m scripts.f38_repairs --plan            # populations, no calls
    .conda-env/bin/python -m scripts.f38_repairs --run A|B|C       # one fix per process
    .conda-env/bin/python -m scripts.f38_repairs --summary A|B|C
"""
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import scripts.b6_repairs as W
import scripts.restore_equiv_gemini as RE
from scripts.audit_diagnosis_89 import packages, records
from scripts.missing_fact_repair_pilot import price
from src.audit.e4_fix_gates import delivery_gate, recall
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
from src.protocols.relay import (_AGGREGATION_SYSTEM, _build_evidence_board_prompt,
                                 _parse_units)
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_f38_repairs'
RESTORE_CASES = P / '20261113_restore_source/cases.json'
RESTORE_RESULTS = P / '20261116_restore_equiv_gemini/restore_results.jsonl'
RECHECK_RESULTS = P / '20261116_b6_audit_recheck/results.jsonl'
RECHECK_ITEMS = P / '20261116_b6_audit_recheck/items.json'
ROUTED_RESULTS = P / '20261116_b6_audit_routed/results.jsonl'
ROUTED_CALLS = P / '20261116_b6_audit_routed/calls.jsonl'
CAP = 10.0
ANSWER_TOKENS = 1024
MAX_UNITS = W.MAX_UNITS
EXTRACT_TOKENS = W.EXTRACT_TOKENS
MODEL_IDS = W.MODEL_IDS
GATE_RECALL = 0.8


_REC = None


def R():
    global _REC
    if _REC is None:
        _REC = records()
    return _REC


def read_jsonl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ---------- flags from the matcher record (audit's own carriers) ----------

def fact_flags(rec):
    """fid -> {'status', 'distorted_units', 'owner', 'text'}; status present|distorted|absent."""
    texts = {f['fact_id']: f for f in rec['facts']['facts']}
    out = {}
    for f in rec['carriers']['facts']:
        fid = f['fact_id']
        bs = f.get('board', [])
        fids = [b.get('fidelity') for b in bs]
        if any(x in ('faithful', 'partial') for x in fids):
            st = 'present'
        elif 'distorted' in fids:
            st = 'distorted'
        else:
            st = 'absent'
        du = [u for b in bs if b.get('fidelity') == 'distorted' for u in b.get('unit_ids', [])]
        src = texts[fid]['source_ids'][0] if fid in texts else ''
        out[fid] = {'status': st, 'distorted_units': du,
                    'owner': src.split('agent-')[-1] if 'agent-' in src else src.split(':')[-1],
                    'text': texts[fid]['text'] if fid in texts else ''}
    return out


# ---------- model calls ----------

def price_checker():
    return price(RE.MODEL)


def call_paper(key, model, system, user, max_tokens, total):
    return W.call(key, model, system, user, max_tokens, CAP, total)


def check_equiv(key, question, gold, answer, total):
    spec = RE.load_prompt()
    user = f"QUESTION\n{question}\n\nGOLD ANSWER\n{gold}\n\nSYSTEM ANSWER\n{answer}"
    pin, pout = price_checker()
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    if total + est_in * pin + RE.MAX_TOKENS * pout > CAP:
        return None, total
    req = APIRequest(system_query=spec['system'], user_query=user, model=RE.MODEL,
                     max_tokens=RE.MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'f38', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with W.CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': 'check/' + key, 'model': RE.MODEL,
                            'success': resp.success, 'content': resp.content,
                            'cost_usd': round(cost, 8)}, ensure_ascii=False) + '\n')
    return RE.parse(resp.content if resp.success else ''), total + cost


def answer(key, pkg, model, board_units, extra, total):
    """board_units: list of (agent, text); extra: list of (agent, text) appended."""
    by = {}
    for a, t in board_units + extra:
        by.setdefault(str(a), []).append(t)
    order = sorted(by, key=lambda x: (len(x), x))
    prompt = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
    resp, total = call_paper(key, MODEL_IDS[model], _AGGREGATION_SYSTEM, prompt, ANSWER_TOKENS, total)
    if resp is None:
        return None, total
    ans = extract_answer(resp.content or '') if resp.success else ''
    return ans, total


TARGET_SYSTEM = ('You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, '
                 'summarise, or add words. If no sentence states the target fact, write NONE.')


def sentences(text):
    import re
    return [t.strip() for t in re.split(r'(?<=[.!?])\s+', text) if t.strip()]


def best_sentence(passages, fact_text):
    """(recall, passage) of the single sentence across passages that best matches the fact."""
    best = (0.0, None)
    for pas in passages:
        for t in sentences(pas['text']):
            r = recall(t, fact_text)
            if r > best[0]:
                best = (r, pas)
    return best


def target_user(passage, fact_text, question):
    return ('Passage:\n%s\n\nTarget fact: %s\nQuestion: %s\n\nCopy the sentence(s) from the passage that state '
            'the target fact (the same claim, even with different wording). Copy each one exactly. Number them '
            '1..3. If no sentence states it, write NONE.' % (passage, fact_text, question))


def verbatim(key, pkg, model, owner, fact_text, total):
    """Targeted verbatim re-read (amendment 1) from the owner's passage with the best sentence."""
    sup = [s for s in pkg['source_supports'] if str(s['agent_id']) == str(owner)]
    if not sup:
        return [], [], total
    r, best = best_sentence(sup, fact_text)
    if best is None:
        best = sup[0]
    user = target_user(best['text'], fact_text, pkg['question'])
    resp, total = call_paper('f38/' + key, MODEL_IDS[model], TARGET_SYSTEM, user, EXTRACT_TOKENS, total)
    if resp is None:
        return None, None, total
    units = _parse_units(resp.content or '', MAX_UNITS) if resp.success else []
    delivered = [u for u in units if delivery_gate(u, fact_text, pkg['question'])['ok']]
    return delivered, units, total


def board_of(pkg):
    return [(u['agent_id'], u['text']) for u in pkg['checkpoints']['board']]


def board_ids(pkg):
    return [(u['unit_id'], u['agent_id'], u['text']) for u in pkg['checkpoints']['board']]


# ---------- populations ----------

def pop_A():
    rs = {c['key']: c for c in json.loads(RESTORE_CASES.read_text())}
    rows = []
    for r in read_jsonl(RESTORE_RESULTS):
        if r['arm'] != 'restore' or r['verdict'] != 'NOT_EQUIVALENT':
            continue
        c = rs[r['key']]
        rec = R().get((c['model'], c['instance_id']))
        if rec is None:
            grp, flags = 'A4', None
        else:
            flags = fact_flags(rec)
            absent = [f for f, v in flags.items() if v['status'] == 'absent']
            dist = [f for f, v in flags.items() if v['status'] == 'distorted']
            grp = 'A3' if absent else ('A2' if len(dist) >= 2 else 'A1')
        rows.append({'key': c['instance_id'] + '|' + c['model'], 'group': grp, 'model': c['model'],
                     'instance': c['instance_id'], 'restore_fact': c['fact_id'],
                     'restore_unit': c['board_unit_id'], 'restore_sentence': c['source_sentence'],
                     'flags': flags})
    return rows


def pop_B():
    rows = []
    ann = {}
    for c in read_jsonl(ROUTED_CALLS):
        if c.get('event') == 'result':
            ann[c['key']] = c
    rec_res = read_jsonl(RECHECK_RESULTS)
    items = {i['key'] + '/' + i['fact_id']: i for i in json.loads(RECHECK_ITEMS.read_text())}
    pk = {m: packages(m) for m in MODEL_IDS}
    for r in read_jsonl(ROUTED_RESULTS):
        if r['status'] != 'delivered':
            continue
        p = pk[r['model']][r['instance']]
        a = ann.get(f"answer/{r['key']}/{r['fact_id']}")
        ans = extract_answer(a['content'] or '') if a else ''
        if answer_f1(ans, {'answer': p['gold_answer']}) >= 1.0:
            continue
        ext = [c for c in read_jsonl(ROUTED_CALLS)
               if c.get('event') == 'result' and c['key'] == f"extract/{r['key']}/{r['fact_id']}"]
        units = _parse_units(ext[-1]['content'] or '', MAX_UNITS) if ext else []
        cited = [u for u in units if delivery_gate(u, r['fact_text'], p['question'])['ok']]
        rows.append({'src': 'gate', 'key': r['key'], 'fact_id': r['fact_id'], 'model': r['model'],
                     'instance': r['instance'], 'repair_units': cited})
    for r in rec_res:
        if not (r['fact_came_back'] and not r['repair_correct']):
            continue
        it = items[r['key']]
        gate_units = [u for u in it['units'] if delivery_gate(u, it['fact_text'], None)['ok']]
        rows.append({'src': 'recheck', 'key': r['key'].rsplit('/', 1)[0], 'fact_id': r['fact_id'], 'model': r['model'],
                     'instance': r['instance'], 'repair_units': gate_units})
    for x in rows:
        rec = R().get((x['model'], x['instance']))
        flags = fact_flags(rec) if rec else {}
        x['flags'] = flags
        x['distorted'] = [f for f, v in flags.items() if v['status'] == 'distorted']
        x['group'] = 'B2' if x['distorted'] else 'B1'
    return rows


def pop_C():
    items = {i['key'] + '/' + i['fact_id']: i for i in json.loads(RECHECK_ITEMS.read_text())}
    pk = {m: packages(m) for m in MODEL_IDS}
    rows = []
    for r in read_jsonl(RECHECK_RESULTS):
        if r['fact_came_back']:
            continue
        it = items[r['key']]
        p = pk[r['model']][r['instance']]
        ft, owner = it['fact_text'], str(it['owner'])
        own = best_sentence([s for s in p['source_supports'] if str(s['agent_id']) == owner], ft)[0]
        oth = best_sentence([s for s in p['source_supports'] if str(s['agent_id']) != owner], ft)[0]
        cls = 'C1' if own >= GATE_RECALL else ('C2' if oth >= GATE_RECALL else 'C3')
        rows.append({'key': r['key'].rsplit('/', 1)[0], 'fact_id': r['fact_id'], 'model': r['model'], 'instance': r['instance'],
                     'owner': owner, 'fact_text': ft, 'best_owner': round(own, 3),
                     'best_other': round(oth, 3), 'group': cls})
    return rows


# ---------- runs ----------

def run_A(rows, total):
    out = []
    for x in rows:
        key = f"A/{x['key']}"
        rec = R().get((x['model'], x['instance']))
        if x['instance'] not in packages(x['model']):
            out.append({'fix': 'A', 'key': x['key'], 'group': x['group'], 'status': 'no trace package for paper model; not run'})
            continue
        pkg = packages(x['model'])[x['instance']]
        board = board_ids(pkg)
        ctrl, total = answer(key + '/control', pkg, x['model'], board_of(pkg), [], total)
        if ctrl is None:
            break
        new = {u: (a, t) for u, a, t in board}
        new[x['restore_unit']] = (new[x['restore_unit']][0], x['restore_sentence'])
        actions = [{'fact': x['restore_fact'], 'action': 'restore confirmed source sentence'}]
        extra = []
        if rec:
            flags = x['flags']
            for fid, v in flags.items():
                if fid == x['restore_fact']:
                    continue
                if v['status'] == 'distorted':
                    dl, _, total = verbatim(key + '/' + fid, pkg, x['model'], v['owner'], v['text'], total)
                    if dl is None:
                        break
                    unit = v['distorted_units'][0] if v['distorted_units'] else None
                    if dl and unit in new:
                        new[unit] = (new[unit][0], dl[0])
                        actions.append({'fact': fid, 'action': 'verbatim replace', 'delivered': len(dl)})
                    else:
                        actions.append({'fact': fid, 'action': 'verbatim replace', 'delivered': len(dl or [])})
                elif v['status'] == 'absent':
                    dl, _, total = verbatim(key + '/' + fid, pkg, x['model'], v['owner'], v['text'], total)
                    if dl is None:
                        break
                    extra += [(v['owner'], t) for t in dl]
                    actions.append({'fact': fid, 'action': 'verbatim append', 'delivered': len(dl)})
        rep_units = [(a, t) for u, (a, t) in new.items()]
        rep, total = answer(key + '/repair', pkg, x['model'], rep_units, extra, total)
        if rep is None:
            break
        out.append({'fix': 'A', 'key': x['key'], 'group': x['group'], 'model': x['model'],
                    'instance': x['instance'], 'actions': actions, 'control_answer': ctrl,
                    'repair_answer': rep, 'gold': pkg['gold_answer'], 'question': pkg['question'],
                    'fact_flags': {k: v['status'] for k, v in (x['flags'] or {}).items()}})
        print(json.dumps({'key': x['key'], 'group': x['group'], 'spent': round(total, 5)}), flush=True)
    return out, total


def run_B(rows, total):
    out = []
    for x in rows:
        if x['group'] != 'B2':
            out.append({'fix': 'B', 'key': x['key'], 'fact_id': x['fact_id'], 'src': x['src'],
                        'group': 'B1', 'status': 'not applicable (no flagged loss left to re-read)'})
            continue
        pkg = packages(x['model'])[x['instance']]
        key = f"B/{x['key']}/{x['fact_id']}"
        ctrl, total = answer(key + '/control', pkg, x['model'], board_of(pkg), [], total)
        if ctrl is None:
            break
        new = {u: (a, t) for u, a, t in board_ids(pkg)}
        extra = []
        actions = []
        for fid in x['distorted']:
            v = x['flags'][fid]
            dl, _, total = verbatim(key + '/' + fid, pkg, x['model'], v['owner'], v['text'], total)
            if dl is None:
                break
            unit = v['distorted_units'][0] if v['distorted_units'] else None
            if dl and unit in new:
                new[unit] = (new[unit][0], dl[0])
            actions.append({'fact': fid, 'action': 'verbatim replace', 'delivered': len(dl or [])})
        owner_of_came_back = str(x['flags'][x['fact_id']]['owner']) if x['fact_id'] in x['flags'] else '0'
        extra = [(owner_of_came_back, t) for t in x['repair_units']]
        rep_units = [(a, t) for u, (a, t) in new.items()]
        rep, total = answer(key + '/repair', pkg, x['model'], rep_units, extra, total)
        if rep is None:
            break
        out.append({'fix': 'B', 'key': x['key'], 'fact_id': x['fact_id'], 'src': x['src'], 'group': 'B2',
                    'actions': actions, 'control_answer': ctrl, 'repair_answer': rep,
                    'gold': pkg['gold_answer'], 'question': pkg['question']})
        print(json.dumps({'B2': x['key'], 'spent': round(total, 5)}), flush=True)
    return out, total


def run_C(rows, total):
    out = []
    for x in rows:
        if x['group'] != 'C1':
            out.append({'fix': 'C', 'key': x['key'], 'fact_id': x['fact_id'], 'group': x['group'],
                        'status': 'reclassified, not re-run'})
            continue
        pkg = packages(x['model'])[x['instance']]
        key = f"C/{x['key']}/{x['fact_id']}"
        ctrl, total = answer(key + '/control', pkg, x['model'], board_of(pkg), [], total)
        if ctrl is None:
            break
        dl, _, total = verbatim(key, pkg, x['model'], x['owner'], x['fact_text'], total)
        if dl is None:
            break
        rep, total = answer(key + '/repair', pkg, x['model'], board_of(pkg),
                            [(x['owner'], t) for t in dl], total)
        if rep is None:
            break
        out.append({'fix': 'C', 'key': x['key'], 'fact_id': x['fact_id'], 'group': 'C1',
                    'delivered': len(dl), 'control_answer': ctrl, 'repair_answer': rep,
                    'gold': pkg['gold_answer'], 'question': pkg['question']})
        print(json.dumps({'C1': x['key'], 'delivered': len(dl), 'spent': round(total, 5)}), flush=True)
    return out, total


def score_rows(rows, total):
    scored = []
    for r in rows:
        if 'control_answer' not in r:
            scored.append(r)
            continue
        for arm in ('control', 'repair'):
            ans = r[arm + '_answer']
            v, total = check_equiv(f"{r['fix']}/{r['key']}/{r.get('fact_id', r.get('group'))}/{arm}",
                                   r['question'], r['gold'], ans, total)
            r[arm + '_equiv'] = v
            r[arm + '_f1_correct'] = answer_f1(ans, {'answer': r['gold']}) >= 1.0
        scored.append(r)
    return scored, total


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--plan', action='store_true')
    g.add_argument('--run', choices=['A', 'B', 'C'])
    g.add_argument('--summary', choices=['A', 'B', 'C'])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    W.CALLS = OUT / 'calls.jsonl'
    if a.plan:
        A = pop_A(); B = pop_B(); C = pop_C()
        print(json.dumps({'A': dict(Counter(x['group'] for x in A)),
                          'B': dict(Counter(x['group'] for x in B)),
                          'C': dict(Counter(x['group'] for x in C))}))
        (OUT / 'populations.json').write_text(json.dumps(
            {'A': A, 'B': B, 'C': C}, ensure_ascii=False, indent=1, default=str))
        return
    if a.run:
        W.CALLS = OUT / f'calls_{a.run}.jsonl'
        pops = json.loads((OUT / 'populations.json').read_text())
        rows = pops[a.run]
        fn = {'A': run_A, 'B': run_B, 'C': run_C}[a.run]
        total = 0.0
        res, total = fn(rows, total)
        res, total = score_rows(res, total)
        (OUT / f'results_{a.run}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(json.dumps({'fix': a.run, 'results': len(res), 'spent_usd': round(total, 6)}))


if __name__ == '__main__':
    main()
