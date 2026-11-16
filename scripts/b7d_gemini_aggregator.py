"""B7d: bare-value insertion rerun with Gemini 3.6 Flash (paper model).

Rule `rebuttal/pilots/prereg/B7d-paper-model-aggregator.md`, frozen before any call. Same boards and facts as
the original direct-insertion run; the model returns to the trace's own, and the frozen bare-value
instruction is kept from B7b.

    ./run.sh python -m scripts.b7c_earlier_model_format --build
    ./run.sh python -m scripts.b7c_earlier_model_format --run
    ./run.sh python -m scripts.b7c_earlier_model_format --score
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_b7d_gemini'
RULE = ROOT / 'rebuttal/pilots/prereg/B7d-paper-model-aggregator.md'
SRC = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair/direct_insertion'
CASES = SRC / 'cases.json'
SRC_MANIFEST = SRC / 'prompt_manifest.json'
EARLIER = SRC / 'answers.jsonl'
B7 = ROOT / 'rebuttal/pilots/20261115_b7_strong_aggregator/answers.jsonl'
B7B = ROOT / 'rebuttal/pilots/20261115_b7b_format/answers.jsonl'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
ANSWERS = OUT / 'answers.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
ANSWER_TOKENS = 1024
MODEL = 'google/gemini-3.6-flash'
PRICE = (0.75 / 1e6, 3.75 / 1e6)
CAP = 1.5
CHUNK = 0.9
SEED = 43
NOTE = ('For this run, output the answer value only: one line with exactly the answer span, in the form a '
        'gold answer would take (a name, a number, a date, or a short phrase), with no label, no prefix and '
        'no explanation. If the units are insufficient, output exactly: Insufficient information.')
SYSTEM = _AGGREGATION_SYSTEM + '\n\n' + NOTE


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def build():
    man = json.loads(SRC_MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256'], 'source cases changed'
    OUT.mkdir(parents=True, exist_ok=True)
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    m = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
         'source_cases_sha256': file_sha(CASES),
         'earlier_answers_sha256': file_sha(EARLIER),
         'b7_answers_sha256': file_sha(B7), 'b7b_answers_sha256': file_sha(B7B),
         'format_note_sha256': sha(NOTE), 'system_sha256': sha(SYSTEM),
         'models': MODEL, 'max_tokens': ANSWER_TOKENS, 'temperature': 0,
         'cap_usd': CAP, 'chunk_usd': CHUNK, 'cases': 59, 'calls_planned': 118}
    MANIFEST.write_text(json.dumps(m, indent=1))
    print(json.dumps(m, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    assert file_sha(CASES) == m['source_cases_sha256'], 'source cases changed'
    assert sha(NOTE) == m['format_note_sha256'], 'format note changed'
    assert file_sha(EARLIER) == m['earlier_answers_sha256'], 'earlier answers changed'
    assert file_sha(B7) == m['b7_answers_sha256'], 'B7 answers changed'
    assert file_sha(B7B) == m['b7b_answers_sha256'], 'B7b answers changed'
    return m


def board_user(case, board):
    grouped = [[] for _ in range(case['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def call(key, model, user, cap, total):
    pin, pout = PRICE
    est_in = math.ceil((len(SYSTEM) + len(user)) / 4)
    if total + est_in * pin + ANSWER_TOKENS * pout > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0})
        return None, total
    cid = sha('|'.join([key, model, sha(SYSTEM), sha(user), str(ANSWER_TOKENS)]))
    log({'event': 'intent', 'key': key, 'call_id': cid, 'model': model,
         'system_sha256': sha(SYSTEM), 'user_sha256': sha(user),
         'max_tokens': ANSWER_TOKENS, 'temperature': 0})
    from utility.apis.openrouter_api import single_request
    resp = single_request(APIRequest(system_query=SYSTEM, user_query=user, model=model,
                                     max_tokens=ANSWER_TOKENS, temperature=0,
                                     metadata={'pilot': 'b7c_earlier_model', 'key': key}))
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    log({'event': 'result', 'key': key, 'call_id': cid, 'model': model,
         'success': resp.success, 'error': resp.error, 'content': resp.content,
         'usage': usage, 'cost_usd': round(cost, 8)})
    return resp, total + cost


def run():
    check()
    cases = json.loads(CASES.read_text())
    done = set()
    if ANSWERS.exists():
        for l in ANSWERS.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done.add((r['instance_id'], r['arm']))
    total = spent()
    chunk, start = 1, total
    print(json.dumps({'todo': 118 - len(done), 'spent': round(total, 6)}), flush=True)
    for case in cases:
        for arm, board in (('control', case['control_board']), ('insert', case['insert_board'])):
            if (case['instance_id'], arm) in done:
                continue
            if total - start > CHUNK:
                over = total - start > 1.0
                print(json.dumps({'chunk': chunk, 'spend': round(total - start, 6),
                                  'overrun': over}), flush=True)
                if over:
                    print(json.dumps({'stop': 'chunk overrun'}))
                    return
                chunk += 1
                start = total
                print(json.dumps({'chunk': chunk, 'start': round(start, 6)}), flush=True)
            user = board_user(case, board)
            resp, total = call(f"{case['instance_id']}/{arm}", MODEL, user, CAP, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                return
            answer = extract_answer(resp.content or '')
            f1 = answer_f1(answer, {'answer': case['gold'],
                                    'answer_aliases': case['aliases']})
            rec = {'instance_id': case['instance_id'], 'label': case['label'],
                   'model': case['model'], 'arm': arm, 'gold': case['gold'], 'answer': answer,
                   'f1': round(f1, 6), 'exact': float(f1 == 1.0),
                   'raw': resp.content, 'success': resp.success}
            with ANSWERS.open('a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            print(json.dumps({'key': f"{case['instance_id']}/{arm}",
                              'exact': rec['exact'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6),
                      'answered': len(ANSWERS.read_text().splitlines())}))


def boot(pairs, draws=2000):
    rng = random.Random(SEED)
    vals = [a - b for a, b in pairs]
    out = []
    for _ in range(draws):
        s = [vals[rng.randrange(len(vals))] for _ in vals]
        out.append(sum(s) / len(vals))
    out.sort()
    return sum(vals) / len(vals), out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def load(path):
    return {(r['instance_id'], r['arm']): r
            for r in (json.loads(l) for l in path.read_text().splitlines() if l.strip())}


def score():
    m = check()
    cases = {c['instance_id']: c for c in json.loads(CASES.read_text())}
    new, old, b7, b7b = load(ANSWERS), load(EARLIER), load(B7), load(B7B)
    ids = [i for i in cases if all((i, a) in d for a in ('control', 'insert')
                                   for d in (new, old, b7, b7b))]
    out = {'n': len(ids), 'spend_usd': round(spent(), 6)}
    for arm in ('control', 'insert'):
        k = int(sum(new[(i, arm)]['exact'] for i in ids))
        lo, hi = cp_ci(k, len(ids))
        out[arm] = {'b7c': k, 'earlier': int(sum(old[(i, arm)]['exact'] for i in ids)),
                    'b7': int(sum(b7[(i, arm)]['exact'] for i in ids)),
                    'b7b': int(sum(b7b[(i, arm)]['exact'] for i in ids)),
                    'b7c_cp_ci': [lo, hi]}
    def pair(d1, d2, arm='insert'):
        return boot([(d1[(i, arm)]['exact'], d2[(i, arm)]['exact']) for i in ids])
    out['effects'] = {
        'format_earlier': pair(new, old), 'format_opus': pair(b7b, b7),
        'model_bare': pair(b7b, new), 'model_sentence': pair(b7, old)}
    out['within_insert_minus_control'] = boot([(new[(i, 'insert')]['exact'],
                                                new[(i, 'control')]['exact']) for i in ids])
    out['by_label'] = {}
    for label in ('present', 'partial', 'absent'):
        kk = [i for i in ids if cases[i]['label'] == label]
        if kk:
            out['by_label'][label] = {'n': len(kk),
                                      'insert': int(sum(new[(i, 'insert')]['exact'] for i in kk)),
                                      'control': int(sum(new[(i, 'control')]['exact'] for i in kk))}
    SCORE.write_text(json.dumps(out, indent=1))
    write_report(out, m)
    print(json.dumps(out, indent=1))


def write_report(res, man):
    def d(t):
        return '%+.3f [%+.3f, %+.3f]' % t

    ins, ctl = res['insert'], res['control']
    lines = ['# B7d: bare-value insertion rerun with a paper model (Gemini 3.6 Flash)',
             '',
             '2026-11-15. Rule `B7d-paper-model-aggregator.md` (sha `%s...`). Same 59 cases, boards and inserted '
             'facts as the original run; Gemini 3.6 Flash in both arms with the bare-value instruction. Spend '
             '$%.6f, cap $1.50.' % (man['rule_sha256'][:8], res['spend_usd']),
             '',
             '| arm | earlier trace model, sentence | Gemini 3.6 Flash, bare value | Gemini exact 95% CI | '
             'paired Gemini minus earlier [95% CI] |',
             '| --- | --- | --- | --- | --- |',
             '| insert (fact supplied) | %d/%d | %d/%d | %.3f-%.3f | %s |'
             % (ins['earlier'], res['n'], ins['b7c'], res['n'], *ins['b7c_cp_ci'],
                d(res['effects']['format_earlier'])),
             '| control (board only) | %d/%d | %d/%d | — | — |'
             % (ctl['earlier'], res['n'], ctl['b7c'], res['n']),
             '',
             '| effect | paired difference [95% CI] |',
             '| --- | --- |',
             '| Gemini bare value minus original trace model (model + format together) | %s |'
             % d(res['effects']['format_earlier']),
             '| model at bare format, Opus minus Gemini | %s |' % d(res['effects']['model_bare']),
             '| format at Opus, B7b minus B7 | %s |' % d(res['effects']['format_opus']),
             '| model at sentence format, Opus minus earlier | %s |' % d(res['effects']['model_sentence']),
             '',
             'Within the Gemini run, insert minus control: %s.'
             % d(res['within_insert_minus_control']),
             '',
             '| label | n | insert | control |', '| --- | ---: | ---: | ---: |']
    for label in ('present', 'partial', 'absent'):
        b = res['by_label'].get(label)
        if b:
            lines.append('| %s | %d | %d | %d |' % (label, b['n'], b['insert'], b['control']))
    lines += ['',
              'Scoring: frozen exact rule (`answer_f1 == 1.0` with aliases). Paired bootstrap over cases, 2,000 '
              'draws, seed 43; Clopper-Pearson intervals on counts.',
              '',
              '## Status of the Opus runs',
              '',
              'B7 (Opus, sentence format) and B7b (Opus, bare value) remain on record as **not usable** for '
              'paper-subject claims: Opus is the project labeller and reference model.',
              '',
              '## What this cannot show',
              '',
              'The insert arm supplies the missing fact verbatim, so it measures what the board could answer, '
              'not what routing or extraction can deliver.',
              '',
              '## Ledger', 'Spend $%.6f.' % res['spend_usd']]
    REPORT.write_text('\n'.join(lines) + '\n')


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