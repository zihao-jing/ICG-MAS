"""Step 20b: re-check the 21 extraction repairs the word-overlap gate rejected, with the validated presence rule.

The re-extracted units are already stored in `20261115_b6_repairs/calls.jsonl` (no new extraction call).
For each rejected case, one labeller call applies the validated per-fact presence prompt
(`20261113_label_validation_v9/v9_reference_prompt.json`, the reference prompt that the v9 validation used) to the
re-extracted units. A case whose label is present or partial counts as "the fact came back". For those cases the
answer step runs once, with the original board plus the cited units, as in the B6 run loop.

Labeller: google/gemini-3.6-flash (the independent reference in the validation). The validated labeller itself is
claude-haiku-5.5, which is outside the permitted model list, so it is not called.

    ./.conda-env/bin/python -m scripts.b6_gate_recheck --build
    ./.conda-env/bin/python -m scripts.b6_gate_recheck --run
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import scripts.b6_repairs as W
from scripts.missing_fact_repair_pilot import price
from scripts.per_fact_labeller import parse as parse_label
from scripts.per_fact_labeller import render
from src.audit.e4_fix_gates import delivery_gate
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from src.protocols.base import extract_answer
from src.eval.evaluate import answer_f1
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
B6 = ROOT / 'rebuttal/pilots/20261115_b6_repairs'
OUT = ROOT / 'rebuttal/pilots/20261116_b6_gate_recheck'
PROMPT = ROOT / 'rebuttal/pilots/20261113_label_validation_v9/v9_reference_prompt.json'
LABEL_MODEL = 'google/gemini-3.6-flash'
CAP = 0.5
LABEL_TOKENS = 2000
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def b6_rows():
    return [json.loads(l) for l in (B6 / 'results.jsonl').read_text().splitlines() if l.strip()]


def rejected():
    return [r for r in b6_rows() if r['stage'] == 'extraction' and r['status'] == 'undelivered']


def extraction_content(key, fid):
    """Last stored result for the B6 extraction call of this case."""
    content = None
    for l in (B6 / 'calls.jsonl').read_text().splitlines():
        if not l.strip():
            continue
        c = json.loads(l)
        if c.get('event') == 'result' and c.get('key') == f'extract/{key}/{fid}':
            content = c.get('content')
    return content


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = rejected()
    prompt = json.loads(PROMPT.read_text())
    items = []
    for r in rows:
        content = extraction_content(r['key'], r['fact_id'])
        units = W._parse_units(content or '', W.MAX_UNITS)
        items.append({'key': r['key'], 'fact_id': r['fact_id'], 'model': r['model'],
                      'instance': r['instance'], 'units': units, 'owner': W.owners(r)[0],
                      'fact_text': r['fact_text'], 'orig_correct': r['orig_correct']})
    man = {'recorded_before_any_call': True, 'cases': len(items),
           'rule': 'validated presence prompt v9 (reference), Gemini labeller; answer step as B6',
           'prompt_path': str(PROMPT.relative_to(ROOT)), 'prompt_sha256': sha(prompt['system']),
           'label_model': LABEL_MODEL, 'cap_usd': CAP,
           'items_sha256': sha(json.dumps(items, sort_keys=True, ensure_ascii=False))}
    (OUT / 'items.json').write_text(json.dumps(items, ensure_ascii=False, indent=1))
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps({k: man[k] for k in ('cases', 'prompt_sha256', 'items_sha256')}))
    print(json.dumps({'units_per_case': [len(i['units']) for i in items],
                      'empty_cases': sum(1 for i in items if not i['units'])}))


def call(key, model, system, user, max_tokens, cap, total):
    pin, pout = price(model) if model == LABEL_MODEL else W.PRICE[model]
    est_in = math.ceil((len(system) + len(user)) / 4)
    if total + est_in * pin + max_tokens * pout > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap'}) + '\n')
        return None, total
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': model,
                            'max_tokens': max_tokens, 'temperature': 0}) + '\n')
    req = APIRequest(system_query=system, user_query=user, model=model, max_tokens=max_tokens,
                     temperature=0, metadata={'pilot': 'b6_gate_recheck', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'success': resp.success,
                            'error': resp.error, 'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run():
    man = json.loads(MANIFEST.read_text())
    items = json.loads((OUT / 'items.json').read_text())
    prompt = json.loads(PROMPT.read_text())
    assert sha(prompt['system']) == man['prompt_sha256'], 'prompt changed'
    done = {json.loads(l)['key'] for l in RESULTS.read_text().splitlines()} if RESULTS.exists() else set()
    total = spent()
    for it in items:
        key = f"{it['key']}/{it['fact_id']}"
        if key in done:
            continue
        units = [{'unit_id': f'repair:{i}', 'agent_id': it['owner'], 'text': u}
                 for i, u in enumerate(it['units'], 1)]
        row = {'question': W.packages(it['model'])[it['instance']]['question'],
               'facts': [{'fact_id': it['fact_id'], 'text': it['fact_text']}],
               'checkpoint_name': 're-extracted units', 'entries': units}
        system = prompt['system']
        user = render(row)
        resp, total = call(f'label/{key}', LABEL_MODEL, system, user, LABEL_TOKENS, CAP, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse_label(resp.content if resp.success else '', {it['fact_id']}) or {}
        status = lab.get(it['fact_id'], {}).get('status')
        cited = [u['text'] for u in units if u['unit_id'] in (lab.get(it['fact_id'], {}).get('unit_ids') or [])]
        rec = {'key': key, 'model': it['model'], 'instance': it['instance'], 'fact_id': it['fact_id'],
               'label_status': status, 'label_fidelity': lab.get(it['fact_id'], {}).get('fidelity'),
               'cited_units': len(cited), 'fact_came_back': status in ('present', 'partial'),
               'orig_correct': it['orig_correct'], 'repair_answer': None, 'repair_correct': False,
               'gate_ok_on_cited': [delivery_gate(u, it['fact_text'], row['question'])['ok'] for u in cited]}
        if rec['fact_came_back'] and cited:
            pkg = W.packages(it['model'])[it['instance']]
            by = W.board_by_agent(pkg)
            by.setdefault(it['owner'], []).extend(cited)
            order = sorted(by, key=lambda x: (len(x), x))
            prompt_ans = _build_evidence_board_prompt([by[a] for a in order], pkg['question'])
            resp2, total = call(f'answer/{key}', W.MODEL_IDS[it['model']], _AGGREGATION_SYSTEM,
                                prompt_ans, W.ANSWER_TOKENS, CAP, total)
            if resp2 is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            ans = extract_answer(resp2.content or '') if resp2.success else ''
            rec['repair_answer'] = ans
            rec['repair_correct'] = answer_f1(ans, {'answer': pkg['gold_answer']}) >= 1.0
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'key': key, 'label': status, 'came_back': rec['fact_came_back'],
                          'repair_correct': rec['repair_correct'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    build() if a.build else run()


if __name__ == '__main__':
    main()
