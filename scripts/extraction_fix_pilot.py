"""Extraction-fix pilot: targeted re-extraction on the present slice of the
Stage 2 clean missing-fact cohort.

Rule: `rebuttal/pilots/20261112_missing_fact_repair/EXTRACTION_FIX_RULE.md`,
frozen before any call. Delivery first; the answer step refuses to run
without the delivery file.

    ./run.sh python -m scripts.extraction_fix_pilot --cases
    ./run.sh python -m scripts.extraction_fix_pilot --extract --cap-usd 5
    ./run.sh python -m scripts.extraction_fix_pilot --answers --cap-usd 5
    ./run.sh python -m scripts.extraction_fix_pilot --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.build_e4_manifest import spans  # noqa: F401  (kept for audit)
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.run_expansion_stage2 import MODELS, packages
from src.audit.e4_fix_gates import delivery_gate
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer, is_refusal
from src.protocols.relay import (
    _AGGREGATION_SYSTEM, _build_evidence_board_prompt, _parse_units,
)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
PRESENCE = PILOT / 'presence.json'
OUT = PILOT / 'extraction_fix'
CASES = OUT / 'cases.json'
MANIFEST = OUT / 'prompt_manifest.json'
CALLS = OUT / 'calls.jsonl'
DELIVERY = OUT / 'delivery.json'
DELIVERY_MD = OUT / 'delivery_check.md'
ANSWERS = OUT / 'answers.jsonl'
REPORT = OUT / 'report.md'
MAX_UNITS = 3
EXTRACT_TOKENS = 512
ANSWER_TOKENS = 1024

SYSTEM = (
    "You are a careful evidence locator.\n"
    "You are given a question, a target claim, and a document.\n"
    "Return up to 3 sentences copied verbatim from the document that state or "
    "directly support the target claim.\n"
    "Rules:\n"
    "- Copy each sentence exactly as it appears; do not paraphrase, merge "
    "sentences, or add comments.\n"
    "- A sentence must mention the entities in the claim and the relation the "
    "claim asserts.\n"
    "- Output a numbered list, one sentence per line.\n"
    "- If no sentence supports the claim, output exactly: NONE"
)
USER_T = (
    "Question: {question}\n\n"
    "Target claim: {fact}\n\n"
    "Document:\n{context}\n\n"
    "Return up to 3 verbatim sentences from the document that state or "
    "directly support the target claim."
)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_cases():
    d = json.loads(PRESENCE.read_text())
    present = [i for i in d['instances'] if i['label'] == 'present']
    pk = {m: packages(m) for m in MODELS}
    cases = []
    for i in present:
        p = pk[i['model']][i['instance_id']]
        board = [{'agent_id': u['agent_id'], 'unit_id': u['unit_id'], 'text': u['text']}
                 for u in p['checkpoints']['board']]
        context = next(s['text'] for s in p['source_contexts']
                       if s['agent_id'] == i['target_agent'])
        cases.append({
            'instance_id': i['instance_id'], 'model': MODELS[i['model']],
            'fact': i['fact'], 'target_agent': i['target_agent'],
            'question': p['question'], 'gold': p['gold_answer'],
            'aliases': p.get('answer_aliases') or [],
            'n_agents': len(p['source_contexts']), 'board': board,
            'target_context': context,
            'extract_system': SYSTEM,
            'extract_user': USER_T.format(question=p['question'], fact=i['fact'],
                                          context=context),
        })
    assert len(cases) == len(present), (len(cases), len(present))
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    CASES.write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule': str((PILOT / 'EXTRACTION_FIX_RULE.md').relative_to(ROOT)),
        'rule_sha256': file_sha(PILOT / 'EXTRACTION_FIX_RULE.md'),
        'system_sha256': sha(SYSTEM),
        'cases_sha256': file_sha(CASES),
        'model_temperature': 0,
        'max_units': MAX_UNITS,
        'per_case': {c['instance_id']: {
            'extract_user_sha256': sha(c['extract_user'])} for c in cases},
    }, indent=1))
    print(json.dumps({'cases': len(cases), 'cases_sha256': file_sha(CASES),
                      'system_sha256': sha(SYSTEM)}, indent=1))


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


def call(key, case, system, user, max_tokens, cap, spent_now, phase):
    pin, pout = price(case['model'])
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if spent_now + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0,
             'phase': phase})
        return None, spent_now
    call_id = sha('|'.join([key, case['model'], sha(system), sha(user),
                            str(max_tokens)]))
    log({'event': 'intent', 'key': key, 'call_id': call_id,
         'model': case['model'], 'phase': phase, 'system_sha256': sha(system),
         'user_sha256': sha(user), 'max_tokens': max_tokens, 'temperature': 0})
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=case['model'],
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'extraction_fix', 'key': key, 'phase': phase})
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
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    out, total = [], spent()
    for case in rows:
        key = case['instance_id'] + '/R-ext-targeted'
        resp, total = call(key, case, case['extract_system'], case['extract_user'],
                           EXTRACT_TOKENS, cap, total, 'extract')
        if resp is None:
            out.append({'instance_id': case['instance_id'], 'model': case['model'],
                        'fact': case['fact'], 'gold': case['gold'],
                        'delivered': False, 'recall': 0.0,
                        'reasons': ['call cap reached'], 'units': [], 'raw': None})
            continue
        units = _parse_units(resp.content or '', MAX_UNITS)
        gate = delivery_gate(' '.join(units), case['fact'], case['question'])
        out.append({'instance_id': case['instance_id'], 'model': case['model'],
                    'fact': case['fact'], 'gold': case['gold'], 'units': units,
                    'delivered': gate['ok'], 'recall': gate['recall'],
                    'reasons': gate['reasons'], 'raw': resp.content,
                    'success': resp.success})
    DELIVERY.write_text(json.dumps({'cases': out, 'spent_usd': round(spent(), 8),
                                    'cap_usd': cap}, indent=1, ensure_ascii=False))
    k = sum(x['delivered'] for x in out)
    lo, hi = cp_ci(k, len(out))
    lines = ['# Extraction-fix pilot: targeted delivery check (R2)\n',
             'Rule: `EXTRACTION_FIX_RULE.md`. Delivery read first; no answer call '
             'was made before this file existed.\n',
             f"Delivered **{k}/{len(out)}**, exact 95% CI {lo:.3f}-{hi:.3f}; "
             f"spend ${spent():.6f} against a ${cap:.2f} cap.\n",
             '| case | model | fact | extracted units | recall | gate | reasons |',
             '| --- | --- | --- | --- | ---: | --- | --- |']
    for x in out:
        units = ' / '.join(u[:80] for u in x['units']) or '—'
        lines.append(f"| {x['instance_id']} | {x['model'].split('/')[-1]} | "
                     f"{x['fact'][:70]} | {units[:230]} | {x['recall']:.3f} | "
                     f"{'PASS' if x['delivered'] else 'blocked'} | "
                     f"{'; '.join(x['reasons']) or '—'} |")
    lines += ['', 'The board-only control is run after this file; repair answers '
              'only for PASS cases.']
    DELIVERY_MD.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(out), 'delivered': k,
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
        units = delivery[inst]['units'] if delivery[inst]['delivered'] else []
        arms = [('board_only', case['board'])]
        if units:
            repair_board = case['board'] + [
                {'agent_id': case['target_agent'], 'unit_id': f'R-ext:{j}',
                 'text': u} for j, u in enumerate(units)]
            arms.append(('repair', repair_board))
        for arm, board in arms:
            if (inst, arm) in done:
                continue
            user = board_user(case, board)
            key = f'{inst}/{arm}'
            resp, total = call(key, case, _AGGREGATION_SYSTEM, user,
                               ANSWER_TOKENS, cap, total, 'answer')
            if resp is None:
                continue
            answer = extract_answer(resp.content or '')
            f1 = answer_f1(answer, {'answer': case['gold'],
                                    'answer_aliases': case['aliases']})
            rec = {'instance_id': inst, 'model': case['model'], 'arm': arm,
                   'gold': case['gold'], 'answer': answer,
                   'refusal': is_refusal(answer), 'f1': round(f1, 6),
                   'exact': float(f1 == 1.0), 'raw': resp.content,
                   'success': resp.success,
                   'delivered': bool(units)}
            with ANSWERS.open('a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                f.flush()
    print(json.dumps({'answered': len(existing_answer_keys()),
                      'spent_usd': round(spent(), 8)}, indent=1))


def do_report():
    delivery = json.loads(DELIVERY.read_text())
    rows = delivery['cases']
    ans = [json.loads(l) for l in ANSWERS.read_text().splitlines() if l.strip()] \
        if ANSWERS.exists() else []
    by_arm = {}
    for a in ans:
        by_arm.setdefault(a['arm'], []).append(a)
    k = sum(x['delivered'] for x in rows)
    dlo, dhi = cp_ci(k, len(rows))
    control = by_arm.get('board_only', [])
    repair = by_arm.get('repair', [])
    ce = int(sum(a['exact'] for a in control))
    clo, chi = cp_ci(ce, len(control))
    re = int(sum(a['exact'] for a in repair))
    rlo, rhi = cp_ci(re, len(repair))
    paired = [(a['instance_id'], b['exact']) for a in repair
              for b in control if b['instance_id'] == a['instance_id']]
    better = sum(1 for a in repair for b in control
                 if a['instance_id'] == b['instance_id'] and a['exact'] > b['exact'])
    worse = sum(1 for a in repair for b in control
                if a['instance_id'] == b['instance_id'] and a['exact'] < b['exact'])
    # Paired control on the same cases the repair arm was called on.
    delivered_ids = {a['instance_id'] for a in repair}
    control_paired = [a for a in control if a['instance_id'] in delivered_ids]
    cpe = int(sum(a['exact'] for a in control_paired))
    cplo, cphi = cp_ci(cpe, len(control_paired))
    # Right content, failed exact match: gold appears in the answer as a
    # normalized substring. Reported separately; not a repair failure.
    import re as _re

    def _n(s):
        return ' '.join(_re.findall(r'[a-z0-9]+', str(s).lower()))

    content_ok = [a for a in repair if a['exact'] < 1 and _n(a['gold']) in _n(a['answer'])]
    lines = ['# Extraction-fix pilot: report\n',
             'Rule: `EXTRACTION_FIX_RULE.md`; targeted extraction on the 33 present '
             'instances of the Stage 2 clean cohort. Oracle-targeted: the missing claim '
             'is given to the locator. Delivery was read and written before any answer.\n',
             '## Delivery (unchanged R2 gate)\n',
             f"Delivered **{k}/{len(rows)}**, exact 95% CI {dlo:.3f}-{dhi:.3f}.\n",
             '| case | model | recall | gate | units |',
             '| --- | --- | ---: | --- | --- |']
    for x in rows:
        lines.append(f"| {x['instance_id']} | {x['model'].split('/')[-1]} | "
                     f"{x['recall']:.3f} | {'PASS' if x['delivered'] else 'blocked'} | "
                     f"{' / '.join(u[:70] for u in x['units'])[:200] or '—'} |")
    near = [x for x in rows if not x['delivered'] and 0.7 <= x['recall'] < 0.8]
    low = [x for x in rows if not x['delivered'] and 0 < x['recall'] < 0.7]
    none = [x for x in rows if not x['delivered'] and x['recall'] == 0]
    tab = {'2hop__619265_45326', '2hop__435184_84856', '4hop3__131775_29339_508306_70744'}
    lines += ['', '### Why delivery failed\n',
              f"- Verbatim sentence just below the gate (0.70-0.79): {len(near)} cases "
              f"({', '.join(x['instance_id'] for x in near)}). The locator returned the "
              f"stating sentence, but the R2 full-token recall includes function words "
              f"('was born on' vs '(born'), so a correct sentence is blocked.",
              f"- Sentence found but low recall: {len(low)} cases "
              f"({', '.join(x['instance_id'] for x in low)}).",
              f"- Locator returned NONE: {len(none)} cases "
              f"({', '.join(x['instance_id'] for x in none)}); "
              f"{len(tab & {x['instance_id'] for x in none})} of these are tabular "
              f"evidence, which is not sentence-shaped.\n",
              '## Scoring (frozen exact answer_f1)\n',
              f"- Board-only control: **{ce}/{len(control)}** exact, 95% CI "
              f"{clo:.3f}-{chi:.3f}.",
              f"- Repair arm: **{re}/{len(repair)}** exact, 95% CI "
              f"{rlo:.3f}-{rhi:.3f} (called only for delivered cases).",
              f"- Board-only control restricted to those same {len(control_paired)} "
              f"cases: **{cpe}/{len(control_paired)}** exact, 95% CI "
              f"{cplo:.3f}-{cphi:.3f}. This is the paired control for the repair arm.",
              f"- Paired: repair better in **{better}** cases, worse in **{worse}**.\n",
              '### Right content, failed exact match (reported separately)\n',
              'These answers state the gold (the normalized gold is a substring of the '
              'answer) but carry extra words, so the frozen exact rule scores them 0. '
              'They are not repair failures and are excluded from the failure count; '
              'they are scored exactly as the frozen rule requires and shown here '
              f'beside it. Found: {len(content_ok)}.\n',
              '| case | gold | answer | paired control |',
              '| --- | --- | --- | --- |']
    for a in content_ok:
        c = next((x for x in control_paired
                  if x['instance_id'] == a['instance_id']), {})
        lines.append(f"| {a['instance_id']} | {str(a['gold'])[:50]} | "
                     f"{str(a['answer'])[:80]} | {str(c.get('answer','—'))[:60]} |")
    lines += ['',
              '| case | gold | board-only answer | exact | repair answer | exact |',
              '| --- | --- | --- | ---: | --- | ---: |']
    control_by = {a['instance_id']: a for a in control}
    repair_by = {a['instance_id']: a for a in repair}
    for x in rows:
        c = control_by.get(x['instance_id'], {})
        r = repair_by.get(x['instance_id'], {})
        lines.append(f"| {x['instance_id']} | {str(x['gold'])[:50]} | "
                     f"{str(c.get('answer','—'))[:60]} | "
                     f"{c.get('exact', 0):.0f} | "
                     f"{str(r.get('answer','—'))[:60]} | "
                     f"{r.get('exact', 0):.0f} |")
    lines += ['', '## Cost\n',
              f"Spend ${spent():.6f} against a $5.00 cap. Every intent and result is "
              f"in `calls.jsonl`.\n",
              '## Reading\n',
              'The delivery rate says how often a targeted pass recovers the stated '
              'claim. The board-only/repair pair is the frozen scoring result, not a '
              'claim about the model\'s general evidence use.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'delivered': k, 'n': len(rows),
                      'control_exact': ce, 'control_n': len(control),
                      'repair_exact': re, 'repair_n': len(repair),
                      'control_paired_exact': cpe, 'control_paired_n': len(control_paired),
                      'content_ok_not_exact': len(content_ok),
                      'better': better, 'worse': worse,
                      'spent_usd': round(spent(), 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', action='store_true')
    ap.add_argument('--extract', action='store_true')
    ap.add_argument('--answers', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.cases:
        build_cases()
    if a.extract:
        do_extract(a.cap_usd)
    if a.answers:
        do_answers(a.cap_usd)
    if a.report:
        do_report()


if __name__ == '__main__':
    main()