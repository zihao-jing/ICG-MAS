"""Second-reader check on a sample of the MuSiQue equivalence hand-check.

Rule: `rebuttal/pilots/20261113_musique_equiv/SECOND_READER_RULE.md`, frozen
before any call. Cap $5; every call logged.

    ./run.sh python -m scripts.musique_second_reader --build
    ./run.sh python -m scripts.musique_second_reader --run --cap-usd 5
    ./run.sh python -m scripts.musique_second_reader --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.run_expansion_stage2 import packages
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_musique_equiv'
RULE = OUT / 'SECOND_READER_RULE.md'
CASES = OUT / 'cases.json'
ADJ = OUT / 'adjudication.json'
SAMPLE = OUT / 'second_sample.json'
CALLS = OUT / 'second_calls.jsonl'
RESULTS = OUT / 'second_results.json'
REPORT = OUT / 'second_reader.md'
MODEL = 'google/gemini-3.6-flash'
PRICE_IN, PRICE_OUT = 0.75 / 1_000_000, 3.75 / 1_000_000
MAX_TOKENS = 300
CAP = 5.0
FORCE = 'd9eca5f22c03'
N = 24

SYSTEM = (
    'You check whether a system answer is equivalent to a gold answer for a '
    'question. Equivalent means the answer gives the same entity, value, '
    'relation or set as the gold. Extra context is allowed when it does not '
    'change or contradict the answer. Formatting, numeral/word form, a title, '
    'spelling or a common abbreviation of the same entity counts as the same '
    'answer. Not equivalent means the answer omits a decisive value the '
    'question asks for, is vague or partial, gives a different answer, or '
    'contradicts the gold. Judge only the question, gold and answer. Return '
    'strict JSON only: {"equivalent": "yes|no", "reason": "one short sentence"}')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def build():
    cases = json.loads(CASES.read_text())
    by = {c['key']: c for c in cases}
    rest = sorted((c for c in cases if c['key'] != FORCE),
                  key=lambda c: sha(f"43|second|{c['key']}"))
    picked = [by[FORCE]] + rest[:N - 1]
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps(picked, indent=1, ensure_ascii=False))
    (OUT / 'second_manifest.json').write_text(json.dumps(
        {'rule_sha256': file_sha(RULE), 'sample_sha256': file_sha(SAMPLE),
         'recorded_before_first_call': True, 'n': len(picked),
         'model': MODEL, 'cap_usd': CAP}, indent=1))


def call(key, question, gold, answer, cap, total):
    user = (f"QUESTION\n{question}\n\nGOLD ANSWER\n{gold}\n\n"
            f"SYSTEM ANSWER\n{answer}")
    est_in = math.ceil((len(SYSTEM) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None, total
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'model': MODEL,
                            'system_sha256': sha(SYSTEM),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=SYSTEM, user_query=user, model=MODEL,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'musique_second_reader', 'key': key,
                               'openrouter_reasoning': True})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * PRICE_IN + \
        usage.get('completion_tokens', 0) * PRICE_OUT
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'model': MODEL,
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def run(cap):
    man = json.loads((OUT / 'second_manifest.json').read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(SAMPLE) == man['sample_sha256']
    sample = json.loads(SAMPLE.read_text())
    adj = {r['key']: r for r in json.loads(ADJ.read_text())}
    pk = {}
    for m in ('gemma31b', 'gpt4omini', 'qwen235b'):
        pk.update(packages(m))
    done = json.loads(RESULTS.read_text())['cases'] if RESULTS.exists() else []
    have = {r['key'] for r in done}
    total = spent()
    for c in sample:
        if c['key'] in have:
            continue
        t = pk.get(c['instance_id']) or {}
        q = t.get('question', '')
        resp, total = call(c['key'], q, c['gold'], c['answer'], CAP, total)
        if resp is None:
            break
        obj = last_object(resp.content or '') or {}
        v = obj.get('equivalent')
        done.append({'key': c['key'], 'instance_id': c['instance_id'],
                     'first': adj[c['key']]['verdict'],
                     'second': 'EQUIVALENT' if v == 'yes' else
                     ('NOT_EQUIVALENT' if v == 'no' else 'INVALID'),
                     'second_reason': obj.get('reason', ''),
                     'gold': c['gold'], 'answer': c['answer']})
        RESULTS.write_text(json.dumps({'cases': done}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'key': c['key'], 'second': done[-1]['second'],
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'cases': len(done), 'spent_usd': round(spent(), 8)},
                     indent=1))


def report():
    rows = json.loads(RESULTS.read_text())['cases']
    n = len(rows)
    agree = sum(r['first'] == r['second'] for r in rows)
    bad = [r for r in rows if r['second'] != r['first']]
    forced = next(r for r in rows if r['key'] == FORCE)
    passed = agree / n >= 0.90 and forced['second'] == 'NOT_EQUIVALENT'
    from scripts.missing_fact_repair_pilot import cp_ci
    lo, hi = cp_ci(agree, n)
    lines = ['# MuSiQue hand-check: second reader\n',
             f"Rule `SECOND_READER_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), "
             f"frozen before the calls. Gemini 3.6 Flash, {n}/74 cases "
             f"(the first reader's one failure force-included). Spend "
             f"${spent():.6f}.\n",
             f"Agreement with the first reader: **{agree}/{n} = "
             f"{agree / n:.3f}** (95% CI {lo:.3f}-{hi:.3f}). The forced "
             f"not-equivalent case is called **{forced['second']}** by the "
             f"second reader.\n",
             '| instance | first | second | gold | answer |', '| --- | --- | --- | --- | --- |']
    for r in rows:
        if r['first'] != r['second'] or r['key'] == FORCE:
            lines.append(f"| {r['instance_id']} | {r['first']} | "
                         f"{r['second']} | {r['gold'][:80]} | "
                         f"{r['answer'][:100]} |")
    lines += ['', '## Decision\n',
              ('**Second reader confirms the hand-check**: agreement >= 0.90 '
               'and the not-equivalent case confirmed. The 51.2% figure may be '
               'reported as hand-checked by two readers, not author-validated.'
               if passed else
               '**Second reader does not confirm the hand-check**: the 51.2% '
               'figure stays labelled "hand-check, unvalidated" and is not '
               'presented as a corrected cell.')]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': n, 'agree': agree, 'rate': agree / n,
                      'forced': forced['second'], 'passed': passed,
                      'spent_usd': spent()}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()