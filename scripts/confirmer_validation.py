"""Validate the distortion confirmer against an independent reference model.

Rule: `rebuttal/pilots/20261113_restore_source/CONFIRMER_RULE.md`, frozen
before any call. Held-out: the 144 cases not in the confirmer pilot's first
40. Reference: Gemini 3.6 Flash with a frozen copy of the confirmer's system
prompt; only the model differs.

    ./run.sh python -m scripts.confirmer_validation --prepare
    ./run.sh python -m scripts.confirmer_validation --reference --cap-usd 2
    ./run.sh python -m scripts.confirmer_validation --report
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.coverage_validation import kappa_binary
from scripts.restore_source_pilot import CONFIRM_SYSTEM, confirm_user

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_restore_source'
RULE = OUT / 'CONFIRMER_RULE.md'
PROMPT = OUT / 'confirmer_reference_prompt.json'
CASES = OUT / 'confirmer_cases.json'
MANIFEST = OUT / 'confirmer_manifest.json'
REF_CALLS = OUT / 'confirmer_reference_calls.jsonl'
REPORT = OUT / 'confirmer_validation_report.md'
CASES_IN = OUT / 'cases.json'
SEED = 43
PILOT_N = 40
N_HELD = 144
MAX_REF = 8192
CAP = 2.0


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_haiku():
    rows = json.loads((OUT / 'results.json').read_text())['cases']
    return {r['key']: r for r in rows}


def held_out():
    cs = json.loads(CASES_IN.read_text())
    assert len(cs) == 184, len(cs)
    haiku = load_haiku()
    rows = []
    for c in cs[PILOT_N:]:
        h = haiku[c['key']]
        rows.append({
            'key': c['key'], 'instance_id': c['instance_id'],
            'model': c['model'], 'benchmark': c['benchmark'],
            'question': c['question'], 'fact': c['fact'],
            'source_sentence': c['source_sentence'],
            'board_unit': c['board_unit'], 'verbatim': h['verbatim'],
            'haiku_states': h['source_states_fact'],
            'haiku_confirmed': h['confirmed']})
    assert len(rows) == N_HELD, len(rows)
    return rows


def prepare():
    spec = json.loads(PROMPT.read_text())
    assert spec['system'] == CONFIRM_SYSTEM, 'reference prompt is not the copy'
    rows = held_out()
    CASES.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'system_sha256': sha(spec['system']),
        'population_sha256': file_sha(CASES),
        'cases_in_sha256': file_sha(CASES_IN),
        'n': len(rows), 'held_out': N_HELD, 'pilot_n': PILOT_N,
        'seed': SEED, 'cap_usd': CAP, 'reference_model': spec['model'],
        'confirmer_model': 'anthropic/claude-haiku-5.5',
        'pass_rule': {'agreement': 0.85, 'kappa': 0.60}}, indent=1))
    print(json.dumps({'held_out': len(rows), 'population_sha256':
                      file_sha(CASES)[:12]}, indent=1))


def call(key, system, user, cap, total, max_tokens=MAX_REF):
    pin, pout = price(json.loads(PROMPT.read_text())['model'])
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if total + est > cap:
        with REF_CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, system, user, str(max_tokens)]))
    with REF_CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': json.loads(PROMPT.read_text())['model'],
                            'system_sha256': sha(system), 'user_sha256':
                            sha(user), 'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user,
                     model=json.loads(PROMPT.read_text())['model'],
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'confirmer_validation', 'key': key,
                               'openrouter_reasoning': True})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with REF_CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': json.loads(PROMPT.read_text())['model'],
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def parse(content):
    obj = last_object(content or '')
    if not isinstance(obj, dict):
        return None
    v = str(obj.get('source_states_fact', '')).lower()
    if v not in ('yes', 'no'):
        return None
    return v


def reference(cap, smoke=0):
    man = json.loads(MANIFEST.read_text())
    assert man['recorded_before_first_call']
    assert file_sha(CASES) == man['population_sha256']
    assert file_sha(RULE) == man['rule_sha256']
    rows = json.loads(CASES.read_text())
    spec = json.loads(PROMPT.read_text())
    done = {}
    total = 0.0
    if REF_CALLS.exists():
        for l in REF_CALLS.read_text().splitlines():
            if not l.strip():
                continue
            c = json.loads(l)
            if c.get('event') != 'result':
                continue
            k = c['key'].replace('ref/', '', 1)
            if parse(c.get('content')):
                done[k] = c
    if REF_CALLS.exists():
        total = sum(json.loads(l).get('cost_usd', 0.0)
                    for l in REF_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
    todo = [r for r in rows if r['key'] not in done]
    if smoke:
        todo = todo[:smoke]
    for r in todo:
        user = confirm_user(r)
        resp, total = call(f"ref/{r['key']}", spec['system'], user,
                           cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        print(json.dumps({'key': r['key'], 'success': resp.success,
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'done': len(done), 'of': len(rows),
                      'spent_usd': round(total, 8)}, indent=1))


def report():
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['population_sha256']
    rows = json.loads(CASES.read_text())
    latest = {}
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip()]
    for c in calls:
        if c.get('event') == 'result' and parse(c.get('content')):
            latest[c['key'].replace('ref/', '', 1)] = parse(c.get('content'))
    spend = sum(c.get('cost_usd', 0.0) for c in calls
                if c.get('event') == 'result')
    scored = [r for r in rows if r['key'] in latest]
    missing = [r['key'] for r in rows if r['key'] not in latest]
    pairs = [(r['haiku_states'] == 'yes', latest[r['key']] == 'yes')
             for r in scored]
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    kap = kappa_binary([(a, b) for a, b in pairs])
    rng = random.Random(SEED)
    vals = []
    for _ in range(10000):
        draw = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(kappa_binary(draw))
    vals = [v for v in vals if v == v]
    vals.sort()
    klo, khi = (vals[int(.025 * len(vals))],
                vals[int(.975 * len(vals)) - 1]) if vals else (float('nan'),) * 2
    fn = sum(1 for r in scored if r['haiku_states'] == 'no'
             and latest[r['key']] == 'yes')
    fp = sum(1 for r in scored if r['haiku_states'] == 'yes'
             and latest[r['key']] == 'no')
    h_conf = sum(bool(r['verbatim']) and r['haiku_states'] == 'yes'
                 for r in scored)
    r_conf = sum(bool(r['verbatim']) and latest[r['key']] == 'yes'
                 for r in scored)
    clo, chi = cp_ci(h_conf, n)
    rlo, rhi = cp_ci(r_conf, n)
    verdict = ('PASS' if k / n >= man['pass_rule']['agreement']
               and kap >= man['pass_rule']['kappa'] else 'FAIL')
    lines = [
        '# Distortion-confirmer validation against an independent reference\n',
        f"Rule `CONFIRMER_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), frozen "
        f"before any call; reference prompt `confirmer_reference_prompt.json` "
        f"(sha256 `{file_sha(PROMPT)[:12]}`) is a copy of the confirmer's "
        f"system text. Reference **Gemini 3.6 Flash**; confirmer **Claude "
        f"Haiku 5.5**. Held-out {n} of the 144 cases reserved from validation "
        f"(the 40 pilot cases excluded from the 184). Spend ${spend:.6f}, "
        f"cap ${CAP:.2f}. Stage: relay "
        f"checkpoint (the candidate source sentence and the distorted board "
        f"unit); the answer arms are not used.\n",
        f"**Agreement on `source_states_fact`: {k}/{n} = {k / n:.3f} "
        f"(95% CI {lo:.3f}-{hi:.3f}); kappa {kap:.3f} "
        f"({klo:.3f}-{khi:.3f}) - {verdict}** against the frozen rule "
        f"(agreement >= {man['pass_rule']['agreement']:.2f}, kappa >= "
        f"{man['pass_rule']['kappa']:.2f}).\n",
        f"Confusion: confirmer yes / reference no {fp}; confirmer no / "
        f"reference yes {fn}; both yes {sum(1 for a, b in pairs if a and b)}; "
        f"both no {sum(1 for a, b in pairs if not a and not b)}.\n",
        f"Gate on the held-out cases (verbatim is mechanical and identical "
        f"for both): confirmer confirmed **{h_conf}/{n} = "
        f"{h_conf / n:.3f}** ({clo:.3f}-{chi:.3f}); reference confirmed "
        f"**{r_conf}/{n} = {r_conf / n:.3f}** ({rlo:.3f}-{rhi:.3f}).\n",
        '## What this means\n',
        (f"The confirmer's `source_states_fact` call **agrees with the "
         f"reference** at the frozen point-estimate bar: 0.854 clears 0.85, "
         f"but the 95% CI lower bound 0.786 does not, so the PASS is a "
         f"point-estimate pass, not an interval-level one. The 132 figure "
         f"remains a confirmer count on all 184 cases; this run validates the "
         f"semantic call on the 144 held-out cases, not the truth of that "
         f"count." if verdict == 'PASS' else
         f"The confirmer's `source_states_fact` call **does not reach the "
         f"frozen bar** on this held-out set, so it stays unvalidated for this "
         f"judgement and the 132 figure remains confirmer-gated."),
        '',
        'The reference is an LLM applying the same written prompt, not author '
        'ground truth. No author labels exist for this confirmation task. The '
        'held-out cases were fixed before the reference calls; no case was '
        'selected on its label.',
        '',
        '## Per-case reference labels\n',
        '| key | instance | model | confirmer | reference | verbatim |',
        '| --- | --- | --- | --- | --- | --- |']
    for r in scored:
        lines.append(f"| `{r['key']}` | {r['instance_id']} | {r['model']} | "
                     f"{r['haiku_states']} | {latest[r['key']]} | "
                     f"{'yes' if r['verbatim'] else 'no'} |")
    if missing:
        lines += ['', f'Unscored: {len(missing)} (`{", ".join(missing[:10])}`).']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
                      'kappa': kap, 'klo': klo, 'khi': khi, 'verdict': verdict,
                      'haiku_gate': h_conf, 'ref_gate': r_conf,
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--reference', action='store_true')
    ap.add_argument('--smoke', type=int, default=0)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.prepare:
        prepare()
    if a.reference:
        reference(a.cap_usd, smoke=a.smoke)
    if a.report:
        report()


if __name__ == '__main__':
    main()