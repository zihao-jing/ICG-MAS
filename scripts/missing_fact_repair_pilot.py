"""Missing-fact repair pilot: four R4-clean cases, delivery first.

Arms, in this order:
  1. R-ext  — re-extract up to 3 units from the target agent's own context
              (the frozen relay extraction prompt), then apply the R2 delivery
              gate. No answer call is made unless the gate passes.
  2. board-only control — answer from the original board, no repair.
  3. repair answer — only for cases whose R-ext text passed the gate.

The delivery check is written to disk before any answer call is made; the
`--answers` step refuses to run without that file. Frozen prompt hashes are
recorded in `prompt_manifest.json` by `--cases`, before the first call.

    ./run.sh python -m scripts.missing_fact_repair_pilot --cases
    ./run.sh python -m scripts.missing_fact_repair_pilot --extract --cap-usd 0.20
    ./run.sh python -m scripts.missing_fact_repair_pilot --answers --cap-usd 0.50
    ./run.sh python -m scripts.missing_fact_repair_pilot --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from src.audit.e4_fix_gates import delivery_gate
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer, is_refusal
from src.protocols.relay import (
    _AGGREGATION_SYSTEM, _EXTRACTION_SYSTEM, _build_evidence_board_prompt,
    _build_extraction_prompt, _parse_units,
)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
ACTIONS = ROOT / 'rebuttal/pilots/20261110_e4_phase1/actions_phase1.json'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
CASES = OUT / 'cases.json'
MANIFEST = OUT / 'prompt_manifest.json'
CALLS = OUT / 'calls.jsonl'
DELIVERY = OUT / 'delivery.json'
DELIVERY_MD = OUT / 'delivery_check.md'
ANSWERS = OUT / 'answers.jsonl'
REPORT = OUT / 'report.md'
MAX_UNITS = 3
ANSWER_TOKENS = 1024
EXTRACT_TOKENS = 512

# The four traces that pass R2/R3/R4 (README section 6); the two (f) traces use
# the corrected facts from R4_rebuild.json.
SPECS = [
    {'trace_id': 'd314e01ff324783979b1dfe7af71dbdab25a45014f9384e92c63af63657ee820',
     'instance_id': '2hop__280583_229757', 'model': 'google/gemma-4-31b-it',
     'fact': 'Amy Poehler is married to Will Arnett.', 'source': 'frozen f2'},
    {'trace_id': '4970cc790f4b5ff455207c2ad1671ec11e7143bf39e259fbac056ec8e17af666',
     'instance_id': '2hop__142621_225454', 'model': 'google/gemma-4-31b-it',
     'fact': 'Hollywood Records is the record label of Jordan Pruitt.', 'source': 'frozen f3'},
    {'trace_id': '40206eddfa03f411facf80867258b55726092e0dc7e6e8535d3621e3c4be284a',
     'instance_id': '2hop__28287_89399', 'model': 'openai/gpt-4o-mini',
     'fact': 'Mr. Lawrence is the voice of Plankton.', 'source': 'R4 rebuild'},
    {'trace_id': '0ac91156d030af4222ecad88e99e2a57d632236775edacbddffcbd5afc10f39e',
     'instance_id': '4hop1__802394_153080_33897_81096', 'model': 'qwen/qwen3-235b-a22b-2507',
     'fact': 'Mario Andretti won the Indy car race in Phoenix in 1993, his final career victory.',
     'source': 'R4 rebuild'},
]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def price(model):
    rows = json.loads(PRICING.read_text())['models']
    p = next(r['pricing'] for r in rows if r['id'] == model)
    return float(p['prompt']), float(p['completion'])


def action_for(trace_id):
    return next(a for a in json.loads(ACTIONS.read_text()) if a['trace_id'] == trace_id)


def board_prompt(record, board):
    grouped = [[] for _ in range(record['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _AGGREGATION_SYSTEM, _build_evidence_board_prompt(grouped, record['question'])


def build_cases():
    rows = []
    for spec in SPECS:
        a = action_for(spec['trace_id'])
        board = [{'agent_id': u['agent_id'], 'text': u['text'], 'unit_id': u['unit_id']}
                 for u in a['board_units']]
        context = next(s['text'] for s in a['source_contexts']
                       if s['agent_id'] == a['target_agent'])
        ext_user = _build_extraction_prompt(context, a['question'], MAX_UNITS)
        sys_a, user_a = board_prompt(a, board)
        rows.append({
            'trace_id': spec['trace_id'], 'instance_id': spec['instance_id'],
            'model': spec['model'], 'fact': spec['fact'], 'fact_source': spec['source'],
            'gold': a['gold_answer'], 'aliases': a.get('answer_aliases') or [],
            'question': a['question'], 'n_agents': a['n_agents'],
            'target_agent': a['target_agent'], 'board': board,
            'target_context': context,
            'extract_system': _EXTRACTION_SYSTEM, 'extract_user': ext_user,
            'answer_system': sys_a, 'answer_user': user_a,
        })
    OUT.mkdir(parents=True, exist_ok=True)
    CASES.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'extraction_system_sha256': sha(_EXTRACTION_SYSTEM),
        'aggregation_system_sha256': sha(_AGGREGATION_SYSTEM),
        'cases_sha256': file_sha(CASES),
        'model_temperature': 0,
        'max_units': MAX_UNITS,
        'per_case': {r['instance_id']: {
            'extract_user_sha256': sha(r['extract_user']),
            'answer_user_sha256': sha(r['answer_user'])} for r in rows},
    }, indent=1))
    print(json.dumps({'cases': len(rows), 'cases_sha256': file_sha(CASES),
                      'manifest': str(MANIFEST.relative_to(ROOT))}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()


def call(key, case, system, user, max_tokens, cap, spent_now, phase):
    pin, pout = price(case['model'])
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if spent_now + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0, 'phase': phase})
        return None, spent_now
    call_id = sha('|'.join([key, case['model'], sha(system), sha(user), str(max_tokens)]))
    log({'event': 'intent', 'key': key, 'call_id': call_id, 'model': case['model'],
         'phase': phase, 'system_sha256': sha(system), 'user_sha256': sha(user),
         'max_tokens': max_tokens, 'temperature': 0})
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=case['model'],
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'missing_fact_repair', 'key': key, 'phase': phase})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    log({'event': 'result', 'key': key, 'call_id': call_id, 'model': case['model'],
         'phase': phase, 'success': resp.success, 'error': resp.error,
         'content': resp.content, 'usage': usage, 'cost_usd': round(cost, 8)})
    return resp, spent_now + cost


def do_extract(cap):
    rows = json.loads(CASES.read_text())
    assert file_sha(CASES) == json.loads(MANIFEST.read_text())['cases_sha256'], 'cases changed'
    out, total = [], spent()
    for case in rows:
        key = case['instance_id'] + '/R-ext'
        resp, total = call(key, case, case['extract_system'], case['extract_user'],
                           EXTRACT_TOKENS, cap, total, 'extract')
        if resp is None:
            out.append({'instance_id': case['instance_id'], 'model': case['model'],
                        'delivered': False, 'recall': 0.0, 'reasons': ['call cap reached'],
                        'units': [], 'raw': None})
            continue
        units = _parse_units(resp.content or '', MAX_UNITS)
        g = delivery_gate(' '.join(units), case['fact'], case['question'])
        out.append({'instance_id': case['instance_id'], 'model': case['model'],
                    'fact': case['fact'], 'gold': case['gold'], 'units': units,
                    'delivered': g['ok'], 'recall': g['recall'], 'reasons': g['reasons'],
                    'raw': resp.content, 'success': resp.success})
    DELIVERY.write_text(json.dumps({'cases': out, 'spent_usd': round(spent(), 8),
                                    'cap_usd': cap}, indent=1, ensure_ascii=False))
    lines = ['# Missing-fact repair: delivery check (R2)\n',
             'Run before any answer call. A case may proceed to a repair answer only if '
             'the re-extracted units contain the target fact at recall >= 0.8 and are not '
             'a question, header, refusal or data list.\n',
             f"Cases: {len(out)}; delivered: **{sum(x['delivered'] for x in out)}/{len(out)}**; "
             f"spend ${spent():.6f}.\n",
             '| case | model | fact | extracted units | recall | gate | reasons |',
             '| --- | --- | --- | --- | ---: | --- | --- |']
    for x in out:
        units = ' / '.join(u[:90] for u in x['units']) or '—'
        lines.append(f"| {x['instance_id']} | {x['model'].split('/')[-1]} | {x['fact'][:80]} | "
                     f"{units[:260]} | {x['recall']:.3f} | "
                     f"{'PASS' if x['delivered'] else 'blocked'} | {'; '.join(x['reasons']) or '—'} |")
    lines += ['', 'No answer was called for a blocked case. The board-only control is run '
              'separately, after this file exists.']
    DELIVERY_MD.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(out), 'delivered': sum(x['delivered'] for x in out),
                      'recalls': [x['recall'] for x in out],
                      'spent_usd': round(spent(), 8)}, indent=1))


def existing_answer_keys():
    out = set()
    if ANSWERS.exists():
        for l in ANSWERS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                out.add((r['instance_id'], r['arm']))
    return out


def do_answers(cap):
    assert DELIVERY_MD.exists() and DELIVERY.exists(), 'run --extract first'
    cases = {r['instance_id']: r for r in json.loads(CASES.read_text())}
    delivery = {r['instance_id']: r for r in json.loads(DELIVERY.read_text())['cases']}
    done = existing_answer_keys()
    total = spent()
    for inst, case in cases.items():
        unit_rows = delivery[inst]['units'] if delivery[inst]['delivered'] else []
        arms = [('board_only', case['board'])]
        if unit_rows:
            repair_board = case['board'] + [
                {'agent_id': case['target_agent'], 'unit_id': f'R-ext:{j}', 'text': u}
                for j, u in enumerate(unit_rows)]
            arms.append(('repair', repair_board))
        for arm, board in arms:
            if (inst, arm) in done:
                continue
            system, user = case['answer_system'], board_prompt(case, board)[1]
            key = f'{inst}/{arm}'
            resp, total = call(key, case, system, user, ANSWER_TOKENS, cap, total, 'answer')
            if resp is None:
                continue
            answer = extract_answer(resp.content or '')
            f1 = answer_f1(answer, {'answer': case['gold'],
                                    'answer_aliases': case['aliases']})
            rec = {'instance_id': inst, 'model': case['model'], 'arm': arm,
                   'gold': case['gold'], 'answer': answer,
                   'refusal': is_refusal(answer), 'f1': round(f1, 6),
                   'exact': float(f1 == 1.0), 'raw': resp.content,
                   'success': resp.success, 'cost_usd': None}
            with ANSWERS.open('a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
    print(json.dumps({'answered': len(existing_answer_keys()),
                      'spent_usd': round(spent(), 8)}, indent=1))


# ---------------------------------------------------------------- statistics
def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def solve(f, lo, hi, target, decreasing=False):
    for _ in range(80):
        mid = (lo + hi) / 2
        if (f(mid) > target) if decreasing else (f(mid) < target):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_ci(k, n, alpha=0.05):
    k, n = int(k), int(n)
    if n == 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p),
                                  1e-12, 1 - 1e-12, alpha / 2)
    hi = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p),
                                  1e-12, 1 - 1e-12, alpha / 2, decreasing=True)
    return lo, hi


def report():
    cases = {r['instance_id']: r for r in json.loads(CASES.read_text())}
    delivery = {r['instance_id']: r for r in json.loads(DELIVERY.read_text())['cases']}
    answers = {}
    if ANSWERS.exists():
        for l in ANSWERS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                answers[(r['instance_id'], r['arm'])] = r
    order = list(cases)
    n = len(order)
    delivered = sum(delivery[i]['delivered'] for i in order)
    dlo, dhi = cp_ci(delivered, n)
    control = [answers.get((i, 'board_only')) for i in order]
    control = [c for c in control if c]
    cok = int(sum(c['exact'] for c in control))
    clo, chi = cp_ci(cok, len(control)) if control else (0.0, 1.0)
    repair = [answers.get((i, 'repair')) for i in order]
    repair = [r for r in repair if r]
    rok = int(sum(r['exact'] for r in repair))
    rlo, rhi = cp_ci(rok, len(repair)) if repair else (0.0, 1.0)
    lines = ['# Missing-fact repair pilot: four R4-clean cases\n',
             'Frozen runner `scripts/missing_fact_repair_pilot.py`; prompts recorded in '
             f"`prompt_manifest.json` before the first call (extraction system "
             f"`{json.loads(MANIFEST.read_text())['extraction_system_sha256']}`, aggregation "
             f"system `{json.loads(MANIFEST.read_text())['aggregation_system_sha256']}`). "
             'Model identifiers are the paper models, temperature 0.\n',
             '## Design\n',
             'R-ext re-extracts up to 3 units from the target agent\'s own context with the '
             'frozen relay extraction prompt. The R2 delivery gate is applied to those units '
             'before any answer call. The board-only control answers from the original board '
             'with no repair. The repair answer is run only for a delivered case, from the '
             'original board plus the extracted units. This is the repair arm as specified in '
             'README section 6; the four cases are the R4-clean cohort (two frozen facts, two '
             'rebuilt facts from `R4_rebuild.json`).\n',
             '## Delivery check (run first)\n',
             f"Delivered **{delivered}/{n}**, exact 95% CI {dlo:.3f}-{dhi:.3f}.\n",
             '| case | model | recall | gate | reasons | extracted units |',
             '| --- | --- | ---: | --- | --- | --- |']
    for i in order:
        d = delivery[i]
        units = ' / '.join(u[:100] for u in d['units']) or '—'
        lines.append(f"| {i} | {cases[i]['model'].split('/')[-1]} | {d['recall']:.3f} | "
                     f"{'PASS' if d['delivered'] else 'blocked'} | "
                     f"{'; '.join(d['reasons']) or '—'} | {units[:280]} |")
    lines += ['', 'No repair answer was called for a blocked case, so its repair outcome '
              'does not exist to score. Reading the board-only control is reported below; '
              'it was run only after this file was written.\n',
              '## Scoring check\n',
              f"Repair answers called: {len(repair)} (of {n} cases; delivered {delivered}). "
              f"Scored exact **{rok}/{len(repair)}**. Board-only control: exact **{cok}/{len(control)}** "
              f"(95% CI {clo:.3f}-{chi:.3f}).\n",
              '| case | arm | gold | answer | refusal | F1 | exact |',
              '| --- | --- | --- | --- | --- | ---: | ---: |']
    for (i, arm), r in sorted(answers.items(), key=lambda x: (order.index(x[0][0]), x[0][1])):
        lines.append(f"| {i} | {arm} | {r['gold']} | {str(r['answer'])[:160]} | "
                     f"{'yes' if r['refusal'] else 'no'} | {r['f1']:.3f} | {int(r['exact'])} |")
    lines += ['', '## Wrong answers read against the gold\n']
    wrong = [r for r in control if not r['exact']] + [r for r in repair if not r['exact']]
    if not wrong:
        lines.append('None: every scored answer is exact.')
    for r in wrong:
        lines += [f"- `{r['instance_id']}` / {r['arm']}: gold **{r['gold']}**, answer "
                  f"\"{str(r['answer'])[:200]}\", F1 {r['f1']:.3f}"
                  f"{' (refusal)' if r['refusal'] else ''}."]
    lines += ['', '## Cost\n',
              f"New calls: ${spent():.6f} against a $1.00 pilot cap. Calls are in "
              f"`{CALLS.relative_to(ROOT)}`; no call was made for a blocked case.\n",
              '## Reading\n']
    if delivered == 0:
        lines.append('The delivery step, not the model\'s use of evidence, blocks the pilot: '
                     'in none of the four clean cases does re-extraction from the target '
                     'agent\'s own context return the target fact. The repair method as '
                     'specified never reaches its answer step, so the missing-fact repair '
                     'experiment remains untestable in this cohort. The board-only control '
                     'still shows whether the cases need the fact at all.')
    else:
        lines.append(f'Delivery passes in {delivered} of {n} cases; only those can test the '
                     'repair. The rest are blocked before the answer call.')
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'delivered': delivered, 'n': n, 'ci_delivery': [round(dlo, 3), round(dhi, 3)],
                      'control_exact': f'{cok}/{len(control)}',
                      'repair_exact': f'{rok}/{len(repair)}',
                      'spent_usd': round(spent(), 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', action='store_true')
    ap.add_argument('--extract', action='store_true')
    ap.add_argument('--answers', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=1.0)
    a = ap.parse_args()
    if a.cases:
        build_cases()
    if a.extract:
        do_extract(a.cap_usd)
    if a.answers:
        do_answers(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()