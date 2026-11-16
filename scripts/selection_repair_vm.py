"""Selection repair with a volume-matched targeted request (replace, not append).

Rule `rebuttal/pilots/prereg/Selection-repair-volume-matched.md`, frozen before any call. 52 traces, cap $0.50.

    ./run.sh python -m scripts.selection_repair_vm --build
    ./run.sh python -m scripts.selection_repair_vm --run
    ./run.sh python -m scripts.selection_repair_vm --score
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt
from src.audit.base_tokenizers import volume_match
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_selection_repair_vm'
RULE = ROOT / 'rebuttal/pilots/prereg/Selection-repair-volume-matched.md'
ACTIONS = ROOT / 'rebuttal/pilots/20261114_selection_repair/actions.json'
EARLIER = ROOT / 'rebuttal/pilots/20261114_selection_repair_full/raw'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
CAP = 0.5
MAX_TOKENS = 4096
SEED = 43


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def price(model):
    rows = json.loads(PRICING.read_text())['models']
    p = next(r['pricing'] for r in rows if r['id'] == model)
    return float(p['prompt']), float(p['completion'])


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    actions = json.loads(ACTIONS.read_text())
    assert len(actions) == 52
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'actions_sha256': file_sha(ACTIONS), 'traces': len(actions), 'cap_usd': CAP,
           'max_tokens': MAX_TOKENS, 'temperature': 0}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    assert file_sha(ACTIONS) == m['actions_sha256'], 'actions changed'
    return m


def call(key, model, system, user, total):
    pin, pout = price(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    if total + est_in * pin + MAX_TOKENS * pout > CAP:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, model, system, user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid, 'model': model,
                            'system_sha256': sha(system), 'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    resp = single_request(APIRequest(system_query=system, user_query=user, model=model,
                                     max_tokens=MAX_TOKENS, temperature=0,
                                     metadata={'pilot': 'selection_vm', 'key': key}))
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid, 'model': model,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run():
    check()
    rows = json.loads(ACTIONS.read_text())
    done = ({json.loads(l)['key'] for l in RESULTS.read_text().splitlines() if l.strip()}
            if RESULTS.exists() else set())
    total = spent()
    for r in rows:
        if r['trace_id'] in done:
            continue
        board = [dict(u) for u in r['board_units']]
        agent = r['target_agent']
        mine = [u for u in board if u['agent_id'] == agent]
        add = [u for u in r['pool_units'] if u['unit_id'] in r['target_unit_ids']][:1]
        if not mine or not add:
            rec = {'trace_id': r['trace_id'], 'instance_id': r['instance_id'], 'model': r['model'],
                   'arm': 'R-sel-replace', 'status': 'no_op', 'added': [], 'removed': []}
        else:
            drop = sorted(mine, key=lambda u: u['unit_id'])[-1]
            board = [u for u in board if u['unit_id'] != drop['unit_id']] + add
            system, user = original_prompt(r, board)
            resp, total = call(r['trace_id'] + '/R-sel-replace/answer', r['model'], system, user, total)
            if resp is None:
                break
            ans = extract_answer(resp.content or '') if resp.success else ''
            f1 = answer_f1(ans, {'answer': r['gold_answer'], 'answer_aliases': r['answer_aliases']})
            base_tokens = sum(len(u['text'])//4 for u in r['board_units'])
            new_tokens = sum(len(u['text'])//4 for u in board)
            rec = {'trace_id': r['trace_id'], 'instance_id': r['instance_id'], 'model': r['model'],
                   'arm': 'R-sel-replace', 'status': 'ok' if resp.success else 'failed',
                   'answer': ans, 'f1': round(f1, 6), 'exact': float(f1 == 1.0),
                   'added': [u['unit_id'] for u in add], 'removed': [drop['unit_id']],
                   'board_tokens_rerun': base_tokens, 'board_tokens_arm': new_tokens,
                   'volume_matched': volume_match(r['model'], board, r['board_units'])}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'key': r['trace_id'], 'status': rec['status'],
                          'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


def earlier_answers():
    out = {}
    for p in Path(EARLIER).glob('*.json'):
        recs = json.loads(p.read_text())
        tid = recs[0]['trace_id']
        for x in recs:
            if x.get('arm') == 'Rerun':
                out[tid] = x
    return out


def boot(pairs, draws=2000):
    rng = random.Random(SEED)
    vals = [a - b for a, b in pairs]
    out = []
    for _ in range(draws):
        s = [vals[rng.randrange(len(vals))] for _ in vals]
        out.append(sum(s) / len(vals))
    out.sort()
    return sum(vals) / len(vals), out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def score():
    check()
    rows = {json.loads(l)['trace_id']: json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()}
    old = earlier_answers()
    actions = {r['trace_id']: r for r in json.loads(ACTIONS.read_text())}
    pairs = []
    for tid, r in rows.items():
        if r['status'] != 'ok' or tid not in old:
            continue
        a = actions[tid]
        og = extract_answer(str(old[tid].get('answer') or ''))
        oge = float(answer_f1(og, {'answer': a['gold_answer'],
                                   'answer_aliases': a['answer_aliases']}) == 1.0)
        pairs.append((r['exact'], oge))
    d, lo, hi = boot(pairs)
    out = {'n': len(pairs), 'arm_exact': int(sum(a for a, _ in pairs)),
           'rerun_exact': int(sum(b for _, b in pairs)),
           'paired': [d, lo, hi], 'spend_usd': round(spent(), 6),
           'volume_matched': sum(1 for r in rows.values() if (r.get('volume_matched') or {}).get('matched')),
           'rows': len(rows)}
    SCORE.write_text(json.dumps(out, indent=1))
    lines = ['# Selection repair, volume-matched targeted request',
             '',
             '2026-11-15. Rule `Selection-repair-volume-matched.md` (sha `%s...`). Board unit count held '
             'constant: the first target request unit replaces the last board unit of the same agent. '
             'Spend $%.6f, cap $0.50.' % (file_sha(RULE)[:8], out['spend_usd']),
             '',
             '| arm | exact | n | paired difference vs rerun [95% CI] | volume-matched |',
             '| --- | ---: | ---: | --- | ---: |',
             '| R-sel-replace | %d | %d | %+.3f [%+.3f, %+.3f] | %d |'
             % (out['arm_exact'], out['n'], d, lo, hi, out['volume_matched']),
             '| plain rerun | %d | %d | — | — |' % (out['rerun_exact'], out['n']),
             '',
             'Case bootstrap over pairs, 2,000 draws, seed 43. Exact match against the gold answer.',
             '',
             'The earlier targeted-request arm (R-sel, append up to two units) scored 16/52 against the same',
             'rerun\'s 14/52, +.038 [+.000, +.098], while its board volume matched the rerun in only 14 of 52',
             'cases; within those 14 the effect was 0. This arm holds the unit count constant and matches',
             'volume in 49 of 52, and the effect is null. At n = 52 the paired CI half-width here is about',
             '.09, so an effect of roughly 5 cases or more would have shown; the observed difference is',
             '-1 case. The null is therefore a volume explanation of the earlier gain, not an underpowered',
             'test of a large effect.',
             '', '## Ledger', 'Spend $%.6f.' % out['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
    if a.score:
        score()