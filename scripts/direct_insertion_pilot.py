"""Direct-insertion pilot on the Stage 2 clean missing-fact cohort.

Rule: `rebuttal/pilots/20261112_missing_fact_repair/DIRECT_INSERTION_RULE.md`,
frozen before the first call. The missing fact is always delivered; this is an
oracle upper bound, not an achievable repair.

    ./run.sh python -m scripts.direct_insertion_pilot --cases
    ./run.sh python -m scripts.direct_insertion_pilot --run --pilot --cap-usd 5
    ./run.sh python -m scripts.direct_insertion_pilot --run --full --cap-usd 5
    ./run.sh python -m scripts.direct_insertion_pilot --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.run_expansion_stage2 import MODELS, packages
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer, is_refusal
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
PRESENCE = PILOT / 'presence.json'
RULE = PILOT / 'DIRECT_INSERTION_RULE.md'
OUT = PILOT / 'direct_insertion'
CASES = OUT / 'cases.json'
MANIFEST = OUT / 'prompt_manifest.json'
CALLS = OUT / 'calls.jsonl'
ANSWERS = OUT / 'answers.jsonl'
REPORT = OUT / 'report.md'
ANSWER_TOKENS = 1024
PILOT_N = 10


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_cases():
    d = json.loads(PRESENCE.read_text())
    pk = {m: packages(m) for m in MODELS}
    cases = []
    for i in d['instances']:
        p = pk[i['model']][i['instance_id']]
        board = [{'agent_id': u['agent_id'], 'unit_id': u['unit_id'], 'text': u['text']}
                 for u in p['checkpoints']['board']]
        insert = board + [{'agent_id': i['target_agent'], 'unit_id': 'R-ins:0',
                           'text': i['fact']}]
        cases.append({
            'instance_id': i['instance_id'], 'model': MODELS[i['model']],
            'label': i['label'], 'fact': i['fact'],
            'target_agent': i['target_agent'],
            'question': p['question'], 'gold': p['gold_answer'],
            'aliases': p.get('answer_aliases') or [],
            'n_agents': len(p['source_contexts']),
            'control_board': board, 'insert_board': insert,
        })
    cases.sort(key=lambda c: c['instance_id'])
    assert len(cases) == 59, len(cases)
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    CASES.write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule': str(RULE.relative_to(ROOT)),
        'rule_sha256': file_sha(RULE),
        'cases_sha256': file_sha(CASES),
        'model_temperature': 0,
        'max_tokens': ANSWER_TOKENS,
        'pilot_instances': [c['instance_id'] for c in cases[:PILOT_N]],
    }, indent=1))
    print(json.dumps({'cases': len(cases), 'rule_sha256': file_sha(RULE),
                      'cases_sha256': file_sha(CASES),
                      'pilot': [c['instance_id'] for c in cases[:PILOT_N]]}, indent=1))


def board_user(case, board):
    grouped = [[] for _ in range(case['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()


def call(key, case, user, cap, spent_now):
    pin, pout = price(case['model'])
    est_in = math.ceil((len(_AGGREGATION_SYSTEM) + len(user)) / 4)
    est = est_in * pin + ANSWER_TOKENS * pout
    if spent_now + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0,
             'phase': 'answer'})
        return None, spent_now
    call_id = sha('|'.join([key, case['model'], sha(_AGGREGATION_SYSTEM), sha(user),
                            str(ANSWER_TOKENS)]))
    log({'event': 'intent', 'key': key, 'call_id': call_id, 'model': case['model'],
         'phase': 'answer', 'system_sha256': sha(_AGGREGATION_SYSTEM),
         'user_sha256': sha(user), 'max_tokens': ANSWER_TOKENS, 'temperature': 0})
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=_AGGREGATION_SYSTEM, user_query=user,
                     model=case['model'], max_tokens=ANSWER_TOKENS, temperature=0,
                     metadata={'pilot': 'direct_insertion', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    log({'event': 'result', 'key': key, 'call_id': call_id, 'model': case['model'],
         'success': resp.success, 'error': resp.error, 'content': resp.content,
         'usage': usage, 'cost_usd': round(cost, 8)})
    return resp, spent_now + cost


def answered_keys():
    out = set()
    if ANSWERS.exists():
        for l in ANSWERS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                out.add((r['instance_id'], r['arm']))
    return out


def run(cap, full):
    cases = json.loads(CASES.read_text())
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    selected = cases if full else cases[:PILOT_N]
    done = answered_keys()
    total = spent()
    for case in selected:
        for arm, board in (('control', case['control_board']),
                           ('insert', case['insert_board'])):
            if (case['instance_id'], arm) in done:
                continue
            user = board_user(case, board)
            resp, total = call(f"{case['instance_id']}/{arm}", case, user, cap, total)
            if resp is None:
                continue
            answer = extract_answer(resp.content or '')
            f1 = answer_f1(answer, {'answer': case['gold'],
                                    'answer_aliases': case['aliases']})
            rec = {'instance_id': case['instance_id'], 'model': case['model'],
                   'label': case['label'], 'arm': arm, 'gold': case['gold'],
                   'answer': answer, 'refusal': is_refusal(answer),
                   'f1': round(f1, 6), 'exact': float(f1 == 1.0),
                   'raw': resp.content, 'success': resp.success}
            with ANSWERS.open('a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
    print(json.dumps({'mode': 'full' if full else 'pilot',
                      'selected': len(selected), 'answered_total': len(answered_keys()),
                      'spent_usd': round(spent(), 8)}, indent=1))


def report():
    cases = json.loads(CASES.read_text())
    man = json.loads(MANIFEST.read_text())
    ans = [json.loads(l) for l in ANSWERS.read_text().splitlines() if l.strip()]
    by = {(a['instance_id'], a['arm']): a for a in ans}
    pilot = {c['instance_id'] for c in cases[:PILOT_N]}
    lines = ['# Direct-insertion pilot: report\n',
             'Rule: `DIRECT_INSERTION_RULE.md`; the missing fact is supplied verbatim '
             'to the board, so it is always delivered. This is an oracle upper bound, '
             'not an achievable repair.\n',
             f"Rule sha256 `{man['rule_sha256']}`; cases sha256 "
             f"`{man['cases_sha256']}`. Spend ${spent():.6f} against a $5.00 cap.\n"]

    def block(name, ids):
        ctrl = [by[(i, 'control')] for i in ids if (i, 'control') in by]
        ins = [by[(i, 'insert')] for i in ids if (i, 'insert') in by]
        ce = int(sum(a['exact'] for a in ctrl))
        ie = int(sum(a['exact'] for a in ins))
        clo, chi = cp_ci(ce, len(ctrl))
        ilo, ihi = cp_ci(ie, len(ins))
        better = sum(1 for i in ids if (i, 'insert') in by and (i, 'control') in by
                     and by[(i, 'insert')]['exact'] > by[(i, 'control')]['exact'])
        worse = sum(1 for i in ids if (i, 'insert') in by and (i, 'control') in by
                    and by[(i, 'insert')]['exact'] < by[(i, 'control')]['exact'])
        lines.extend([f"## {name}\n",
                      f"| arm | exact | n | exact 95% CI |",
                      f"| --- | ---: | ---: | --- |",
                      f"| control (board only) | {ce} | {len(ctrl)} | {clo:.3f}-{chi:.3f} |",
                      f"| insert (fact supplied) | {ie} | {len(ins)} | {ilo:.3f}-{ihi:.3f} |",
                      f"\nPaired: insert better in **{better}**, worse in **{worse}**.\n"])
        return ce, len(ctrl), ie, len(ins)

    all_ids = [c['instance_id'] for c in cases]
    answered_ids = {i for i, _ in by}
    block('Pilot (10 instances)', [i for i in all_ids if i in pilot])
    if len(answered_ids) == len(cases):
        block('Full cohort (59 instances)', all_ids)
    else:
        block(f'All answered so far ({len(answered_ids)} instances)', all_ids)
        lines += [f"Full cohort (59) is not run: {len(cases) - len(answered_ids)} "
                  f"instances are unanswered, and the full run starts only after this "
                  f"pilot is reviewed.\n"]
    lines += [f"Delivery: the insert arm supplies the fact in **{len(cases)}/"
              f"{len(cases)}** cases by construction (no gate); the control arm adds "
              f"no unit and, under the R4 diagnosis that selected this cohort, no "
              f"board unit carries the targeted fact.\n"]
    for label in ('present', 'partial', 'absent'):
        block(f'Presence label: {label}', [c['instance_id'] for c in cases
                                           if c['label'] == label])

    lines += ['## Per case\n',
              '| case | model | presence | gold | control answer | exact | insert answer | exact |',
              '| --- | --- | --- | --- | --- | ---: | --- | ---: |']
    for c in cases:
        i = c['instance_id']
        a = by.get((i, 'control'), {})
        b = by.get((i, 'insert'), {})
        lines.append(f"| {i} | {c['model'].split('/')[-1]} | {c['label']} | "
                     f"{str(c['gold'])[:40]} | {str(a.get('answer','—'))[:55]} | "
                     f"{a.get('exact',0):.0f} | {str(b.get('answer','—'))[:55]} | "
                     f"{b.get('exact',0):.0f} |")
    lines += ['', '## Reading\n',
              'The insert arm is the board answerer with the fact guaranteed. The '
              'difference from the extraction-fix repair arm is the cost of '
              're-extraction and the R2 gate. On the 20 absent instances it is only '
              'an oracle bound; those cases stay recorded as misdiagnosed.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'answered': len(ans), 'spent_usd': round(spent(), 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.cases:
        build_cases()
    if a.run:
        run(a.cap_usd, full=not a.pilot)
    if a.report:
        report()


if __name__ == '__main__':
    main()