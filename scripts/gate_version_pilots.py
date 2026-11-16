"""Frozen gate-version pilots on the 33 present instances.

v2a content-token recall: `GATE_V2A_RULE.md` (re-gate of frozen v1 extraction;
new answer calls only for newly delivered cases).
Tabular prompt: `TABLE_PROMPT_RULE.md` (new locator prompt, unchanged v1 gate).

v1 numbers come from `extraction_fix/` and stay on record unchanged.

    ./run.sh python -m scripts.gate_version_pilots --v2a --cap-usd 5
    ./run.sh python -m scripts.gate_version_pilots --tabular-cases
    ./run.sh python -m scripts.gate_version_pilots --tabular --cap-usd 5
    ./run.sh python -m scripts.gate_version_pilots --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci, price
from src.audit.e4_fix_gates import delivery_gate
from src.audit.e4_fix_gates_v2 import delivery_gate_v2
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer, is_refusal
from src.protocols.relay import (
    _AGGREGATION_SYSTEM, _build_evidence_board_prompt, _parse_units,
)
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair'
RULE_V2A = PILOT / 'GATE_V2A_RULE.md'
RULE_TAB = PILOT / 'TABLE_PROMPT_RULE.md'
EX = PILOT / 'extraction_fix'
EX_CASES = EX / 'cases.json'
EX_DELIVERY = EX / 'delivery.json'
EX_ANSWERS = EX / 'answers.jsonl'
V2A = PILOT / 'gate_v2a'
TAB = PILOT / 'tabular_prompt'
TAB_CASES = TAB / 'cases.json'
TAB_MANIFEST = TAB / 'prompt_manifest.json'
MAX_UNITS = 3
EXTRACT_TOKENS = 512
ANSWER_TOKENS = 1024
TABULAR_IDS = {'2hop__619265_45326', '2hop__435184_84856',
               '4hop3__131775_29339_508306_70744'}

TAB_SYSTEM = (
    "You are a careful evidence locator.\n"
    "You are given a question, a target claim, and a document.\n"
    "The document may contain prose or tables.\n"
    "Return up to 3 verbatim spans from the document that state or directly "
    "support the target claim. A span may be a sentence or a table row.\n"
    "Rules:\n"
    "- Copy each span exactly as it appears; do not paraphrase, merge, or add "
    "comments.\n"
    "- If the support is in a table, include the row and the column header or "
    "headers needed to read it, exactly as they appear.\n"
    "- Output a numbered list, one span per line.\n"
    "- If nothing in the document supports the claim, output exactly: NONE"
)
TAB_USER = (
    "Question: {question}\n\n"
    "Target claim: {fact}\n\n"
    "Document:\n{context}\n\n"
    "Return up to 3 verbatim spans from the document that state or directly "
    "support the target claim."
)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(path, rec):
    with path.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()


def spent(path):
    if not path.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in path.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def caller(tag, logpath):
    def call(key, case, system, user, max_tokens, cap, total, phase):
        pin, pout = price(case['model'])
        est_in = math.ceil((len(system) + len(user)) / 4)
        est = est_in * pin + max_tokens * pout
        if total + est > cap:
            log(logpath, {'event': 'skipped', 'key': key, 'reason': 'cap',
                          'cost_usd': 0.0, 'phase': phase})
            return None, total
        call_id = sha('|'.join([key, case['model'], sha(system), sha(user),
                                str(max_tokens)]))
        log(logpath, {'event': 'intent', 'key': key, 'call_id': call_id,
                      'model': case['model'], 'phase': phase,
                      'system_sha256': sha(system), 'user_sha256': sha(user),
                      'max_tokens': max_tokens, 'temperature': 0})
        from utility.apis.openrouter_api import single_request
        req = APIRequest(system_query=system, user_query=user, model=case['model'],
                         max_tokens=max_tokens, temperature=0,
                         metadata={'pilot': tag, 'key': key, 'phase': phase})
        resp = single_request(req)
        usage = resp.usage or {}
        cost = (usage.get('prompt_tokens', est_in) * pin
                + usage.get('completion_tokens', 0) * pout)
        log(logpath, {'event': 'result', 'key': key, 'call_id': call_id,
                      'model': case['model'], 'phase': phase,
                      'success': resp.success, 'error': resp.error,
                      'content': resp.content, 'usage': usage,
                      'cost_usd': round(cost, 8)})
        return resp, total + cost
    return call


def answer_case(case, board):
    grouped = [[] for _ in range(case['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def v1_bundle():
    cases = {c['instance_id']: c for c in json.loads(EX_CASES.read_text())}
    delivery = {d['instance_id']: d for d in json.loads(EX_DELIVERY.read_text())['cases']}
    ans = read_jsonl(EX_ANSWERS)
    by = {}
    for a in ans:
        by.setdefault(a['arm'], {}).setdefault(a['instance_id'], a)
    return cases, delivery, by.get('board_only', {}), by.get('repair', {})


# ---------------------------------------------------------------- v2a

def run_v2a(cap):
    V2A.mkdir(parents=True, exist_ok=True)
    cases, delivery, _, _ = v1_bundle()
    man = json.loads((EX / 'prompt_manifest.json').read_text())
    assert file_sha(EX_CASES) == man['cases_sha256'], 'v1 cases changed'
    out = []
    for inst, d in delivery.items():
        c = cases[inst]
        g = delivery_gate_v2(' '.join(d['units']), c['fact'], c['question'])
        out.append({'instance_id': inst, 'model': c['model'], 'fact': c['fact'],
                    'units': d['units'], 'delivered_v1': d['delivered'],
                    'delivered': g['ok'], 'recall': g['recall'],
                    'reasons': g['reasons']})
    (V2A / 'delivery_v2.json').write_text(json.dumps({
        'rule_sha256': file_sha(RULE_V2A),
        'v1_cases_sha256': man['cases_sha256'],
        'recorded_before_first_answer_call': True,
        'cases': out}, indent=1, ensure_ascii=False))
    new = [x for x in out if x['delivered'] and not x['delivered_v1']]
    total = spent(V2A / 'calls.jsonl')
    prev = {(a['instance_id'], a['arm']) for a in read_jsonl(V2A / 'answers.jsonl')}
    call = caller('gate_v2a', V2A / 'calls.jsonl')
    for x in new:
        c = cases[x['instance_id']]
        if (c['instance_id'], 'repair') in prev:
            continue
        board = c['board'] + [{'agent_id': c['target_agent'],
                               'unit_id': f'R-v2a:{j}', 'text': u}
                              for j, u in enumerate(x['units'])]
        resp, total = call(f"{c['instance_id']}/repair-v2a", c, _AGGREGATION_SYSTEM,
                           answer_case(c, board), ANSWER_TOKENS, cap, total, 'answer')
        if resp is None:
            continue
        ans = extract_answer(resp.content or '')
        f1 = answer_f1(ans, {'answer': c['gold'], 'answer_aliases': c['aliases']})
        log(V2A / 'answers.jsonl', {
            'instance_id': c['instance_id'], 'model': c['model'], 'arm': 'repair',
            'gold': c['gold'], 'answer': ans, 'refusal': is_refusal(ans),
            'f1': round(f1, 6), 'exact': float(f1 == 1.0), 'raw': resp.content})
    print(json.dumps({'v2a_delivered': sum(x['delivered'] for x in out),
                      'newly_delivered': len(new),
                      'new_calls': len(read_jsonl(V2A / 'answers.jsonl')),
                      'spent_usd': round(spent(V2A / 'calls.jsonl'), 8)}, indent=1))


# ------------------------------------------------------- tabular prompt

def build_tab_cases():
    cases, _, _, _ = v1_bundle()
    out = []
    for c in cases.values():
        out.append({**c,
                    'extract_system': TAB_SYSTEM,
                    'extract_user': TAB_USER.format(question=c['question'],
                                                    fact=c['fact'],
                                                    context=c['target_context'])})
    out.sort(key=lambda c: c['instance_id'])
    TAB.mkdir(parents=True, exist_ok=True)
    assert not (TAB / 'calls.jsonl').exists(), 'refusing to freeze after calls exist'
    TAB_CASES.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    TAB_MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule': str(RULE_TAB.relative_to(ROOT)),
        'rule_sha256': file_sha(RULE_TAB),
        'system_sha256': sha(TAB_SYSTEM),
        'cases_sha256': file_sha(TAB_CASES),
        'model_temperature': 0, 'max_units': MAX_UNITS,
        'per_case': {c['instance_id']: {'extract_user_sha256': sha(c['extract_user'])}
                     for c in out}}, indent=1))
    print(json.dumps({'cases': len(out), 'rule_sha256': file_sha(RULE_TAB),
                      'system_sha256': sha(TAB_SYSTEM),
                      'cases_sha256': file_sha(TAB_CASES)}, indent=1))


def run_tab(cap):
    man = json.loads(TAB_MANIFEST.read_text())
    assert file_sha(TAB_CASES) == man['cases_sha256'], 'cases changed'
    cases = json.loads(TAB_CASES.read_text())
    total = spent(TAB / 'calls.jsonl')
    call = caller('tabular_prompt', TAB / 'calls.jsonl')
    out = []
    for c in cases:
        resp, total = call(f"{c['instance_id']}/R-tab", c, c['extract_system'],
                           c['extract_user'], EXTRACT_TOKENS, cap, total, 'extract')
        if resp is None:
            out.append({'instance_id': c['instance_id'], 'delivered': False,
                        'recall': 0.0, 'reasons': ['call cap reached'], 'units': []})
            continue
        units = _parse_units(resp.content or '', MAX_UNITS)
        g = delivery_gate(' '.join(units), c['fact'], c['question'])
        out.append({'instance_id': c['instance_id'], 'model': c['model'],
                    'fact': c['fact'], 'units': units, 'delivered': g['ok'],
                    'recall': g['recall'], 'reasons': g['reasons'],
                    'raw': resp.content})
    (TAB / 'delivery.json').write_text(json.dumps({
        'cases': out, 'spent_usd': round(spent(TAB / 'calls.jsonl'), 8),
        'cap_usd': cap}, indent=1, ensure_ascii=False))
    call2 = caller('tabular_prompt', TAB / 'calls.jsonl')
    total = spent(TAB / 'calls.jsonl')
    prev = {(a['instance_id'], a['arm']) for a in read_jsonl(TAB / 'answers.jsonl')}
    for x in out:
        if not x['delivered'] or (x['instance_id'], 'repair') in prev:
            continue
        c = next(y for y in cases if y['instance_id'] == x['instance_id'])
        board = c['board'] + [{'agent_id': c['target_agent'],
                               'unit_id': f'R-tab:{j}', 'text': u}
                              for j, u in enumerate(x['units'])]
        resp, total = call2(f"{c['instance_id']}/repair-tab", c, _AGGREGATION_SYSTEM,
                            answer_case(c, board), ANSWER_TOKENS, cap, total, 'answer')
        if resp is None:
            continue
        ans = extract_answer(resp.content or '')
        f1 = answer_f1(ans, {'answer': c['gold'], 'answer_aliases': c['aliases']})
        log(TAB / 'answers.jsonl', {
            'instance_id': c['instance_id'], 'model': c['model'], 'arm': 'repair',
            'gold': c['gold'], 'answer': ans, 'refusal': is_refusal(ans),
            'f1': round(f1, 6), 'exact': float(f1 == 1.0), 'raw': resp.content})
    print(json.dumps({'delivered': sum(x['delivered'] for x in out),
                      'new_calls': len(read_jsonl(TAB / 'answers.jsonl')),
                      'spent_usd': round(spent(TAB / 'calls.jsonl'), 8)}, indent=1))


# ---------------------------------------------------------------- report

def _ci(k, n):
    lo, hi = cp_ci(k, n)
    return f'{lo:.3f}-{hi:.3f}'


def _n(s):
    import re
    return ' '.join(re.findall(r'[a-z0-9]+', str(s).lower()))


def report():
    cases, v1d, _, _ = v1_bundle()
    v1_ans = read_jsonl(EX_ANSWERS)
    control = {a['instance_id']: a for a in v1_ans if a['arm'] == 'board_only'}
    v1repair = {a['instance_id']: a for a in v1_ans if a['arm'] == 'repair'}
    v1_delivered = {i for i, d in v1d.items() if d['delivered']}
    v1_exact = int(sum(a['exact'] for a in v1repair.values()))
    c18 = [control[i] for i in v1_delivered]
    c18e = int(sum(a['exact'] for a in c18))

    lines = ['# Gate-version pilots: report\n',
             'Frozen rules: `GATE_V2A_RULE.md` (content-token recall) and '
             '`TABLE_PROMPT_RULE.md` (tabular locator). v1 (`EXTRACTION_FIX_RULE.md`) '
             'is unchanged and reported beside both.\n',
             '## v1 on record (33 present instances)\n',
             f"- Delivery {len(v1_delivered)}/33, CI {_ci(len(v1_delivered), 33)}.",
             f"- Repair exact {v1_exact}/{len(v1repair)} (v1-delivered cases only), "
             f"CI {_ci(v1_exact, len(v1repair))}.",
             f"- Board-only control on those same {len(c18)} cases: {c18e}/{len(c18)}, "
             f"CI {_ci(c18e, len(c18))}.\n"]

    # v2a
    d2 = json.loads((V2A / 'delivery_v2.json').read_text())
    rows = d2['cases']
    v2_del = {x['instance_id'] for x in rows if x['delivered']}
    newly = v2_del - v1_delivered
    lost = v1_delivered - v2_del
    new_ans = {a['instance_id']: a for a in read_jsonl(V2A / 'answers.jsonl')}
    combined = dict(v1repair)
    combined.update(new_ans)
    k2 = len(v2_del)
    e2 = int(sum(combined[i]['exact'] for i in v2_del if i in combined))
    ctrl2 = [control[i] for i in v2_del]
    c2e = int(sum(a['exact'] for a in ctrl2))
    lines += ['## v2a: content-token recall (same extraction, new gate)\n',
              f"| version | delivered | 95% CI | repair exact (delivered set) | pair control exact |",
              f"| --- | ---: | --- | --- | --- |",
              f"| v1 | {len(v1_delivered)}/33 | {_ci(len(v1_delivered), 33)} | "
              f"{v1_exact}/{len(v1repair)} | {c18e}/{len(c18)} |",
              f"| v2a | {k2}/33 | {_ci(k2, 33)} | {e2}/{len(v2_del)} "
              f"({_ci(e2, len(v2_del))}) | {c2e}/{len(ctrl2)} |",
              f"\nNewly delivered by v2a: {len(newly)} "
              f"({', '.join(sorted(newly)) or 'none'}); lost: {len(lost)} "
              f"({', '.join(sorted(lost)) or 'none'}). "
              f"New answer calls: {len(new_ans)}; spend "
              f"${spent(V2A / 'calls.jsonl'):.6f}.\n",
              '| case | v1 recall | v2a recall | v1 | v2a | v2a answer | exact |',
              '| --- | ---: | ---: | --- | --- | --- | ---: |']
    for x in sorted(rows, key=lambda z: z['instance_id']):
        a = combined.get(x['instance_id'], {}) if x['delivered'] else {}
        lines.append(f"| {x['instance_id']} | {v1d[x['instance_id']]['recall']:.3f} "
                     f"| {x['recall']:.3f} | "
                     f"{'PASS' if x['delivered_v1'] else 'blocked'} | "
                     f"{'PASS' if x['delivered'] else 'blocked'} | "
                     f"{str(a.get('answer','—'))[:55]} | {a.get('exact',0):.0f} |")
    lines += ['',
              'Right-content, exact-fail answers under v2a (normalized gold is a '
              'substring of the answer; scored 0 by the frozen rule, listed '
              'separately):',
              '| case | gold | answer |', '| --- | --- | --- |']
    for i in sorted(v2_del):
        a = combined.get(i, {})
        if a and not a.get('exact') and _n(a['gold']) in _n(a['answer']):
            lines.append(f"| {i} | {a['gold']} | {a['answer']} |")
    lines.append('')

    # tabular
    if (TAB / 'delivery.json').exists():
        td = json.loads((TAB / 'delivery.json').read_text())['cases']
        tdel = {x['instance_id'] for x in td if x['delivered']}
        tnew = tdel - v1_delivered
        tlost = v1_delivered - tdel
        tans = {a['instance_id']: a for a in read_jsonl(TAB / 'answers.jsonl')}
        kt = len(tdel)
        et = int(sum(tans[i]['exact'] for i in tdel if i in tans))
        ct = [control[i] for i in tdel]
        cte = int(sum(a['exact'] for a in ct))
        lines += ['\n## Tabular locator prompt (unchanged v1 gate)\n',
                  f"| version | delivered | 95% CI | repair exact (delivered set) | pair control exact |",
                  f"| --- | ---: | --- | --- | --- |",
                  f"| v1 | {len(v1_delivered)}/33 | {_ci(len(v1_delivered), 33)} | "
                  f"{v1_exact}/{len(v1repair)} | {c18e}/{len(c18)} |",
                  f"| tabular prompt | {kt}/33 | {_ci(kt, 33)} | {et}/{len(tdel)} "
                  f"({_ci(et, len(tdel))}) | {cte}/{len(ct)} |",
                  f"\nNewly delivered: {len(tnew)} "
                  f"({', '.join(sorted(tnew)) or 'none'}); lost: {len(tlost)} "
                  f"({', '.join(sorted(tlost)) or 'none'}). Spend "
                  f"${spent(TAB / 'calls.jsonl'):.6f}.\n",
                  '| tabular case | v1 delivery | new delivery | new units |',
                  '| --- | --- | --- | --- |']
        tby = {x['instance_id']: x for x in td}
        for i in sorted(TABULAR_IDS):
            x = tby.get(i, {})
            lines.append(f"| {i} | {'PASS' if v1d.get(i,{}).get('delivered') else 'blocked'} "
                         f"| {'PASS' if x.get('delivered') else 'blocked'} | "
                         f"{' / '.join(u[:60] for u in x.get('units', []))[:180] or '—'} |")
        lines += ['', '| case | new delivery | v1 delivery | new answer | exact |',
                  '| --- | --- | --- | --- | ---: |']
        for x in sorted(td, key=lambda z: z['instance_id']):
            a = tans.get(x['instance_id'], {})
            lines.append(f"| {x['instance_id']} | "
                         f"{'PASS' if x['delivered'] else 'blocked'} | "
                         f"{'PASS' if v1d[x['instance_id']]['delivered'] else 'blocked'} | "
                         f"{str(a.get('answer','—'))[:55]} | {a.get('exact',0):.0f} |")
        lines += ['', 'Right-content, exact-fail answers under the tabular prompt '
                  '(listed separately; scored 0 by the frozen rule):',
                  '| case | gold | answer |', '| --- | --- | --- |']
        for i in sorted(tdel):
            a = tans.get(i, {})
            if a and not a.get('exact') and _n(a['gold']) in _n(a['answer']):
                lines.append(f"| {i} | {a['gold']} | {a['answer']} |")

    lines += ['', '## Reading\n',
              'Both versions keep v1 on record; neither replaces it. v2a isolates '
              'the gate term on identical extraction output. The tabular prompt '
              'changes the locator only, with the v1 gate and scoring held fixed. '
              'Exact scoring remains the outcome; delivery is a gate result.']
    (PILOT / 'gate_versions_report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'v1_delivered': len(v1_delivered), 'v2a_delivered': k2,
                      'v2a_exact': e2, 'v2a_new': len(newly),
                      'tab_delivered': len(tdel) if (TAB / 'delivery.json').exists() else None,
                      'tab_exact': et if (TAB / 'delivery.json').exists() else None,
                      'tab_new': len(tnew) if (TAB / 'delivery.json').exists() else None},
                     indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v2a', action='store_true')
    ap.add_argument('--tabular-cases', action='store_true')
    ap.add_argument('--tabular', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.v2a:
        run_v2a(a.cap_usd)
    if a.tabular_cases:
        build_tab_cases()
    if a.tabular:
        run_tab(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()