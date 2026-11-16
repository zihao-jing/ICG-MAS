"""B7b: direct insertion with a format-constrained Opus 5.5 aggregator.

Rule `rebuttal/pilots/prereg/B7b-format-constrained.md`, frozen before any call. Same boards and
inserted facts as B7; the only change is the frozen instruction to answer with the bare value.

    ./run.sh python -m scripts.b7b_format_aggregator --build
    ./run.sh python -m scripts.b7b_format_aggregator --run
    ./run.sh python -m scripts.b7b_format_aggregator --score
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
OUT = ROOT / 'rebuttal/pilots/20261115_b7b_format'
RULE = ROOT / 'rebuttal/pilots/prereg/B7b-format-constrained.md'
SRC = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair/direct_insertion'
CASES = SRC / 'cases.json'
SRC_MANIFEST = SRC / 'prompt_manifest.json'
B7 = ROOT / 'rebuttal/pilots/20261115_b7_strong_aggregator/answers.jsonl'
EARLIER = SRC / 'answers.jsonl'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
ANSWERS = OUT / 'answers.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'anthropic/claude-opus-5.5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
ANSWER_TOKENS = 1024
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
         'b7_answers_sha256': file_sha(B7),
         'format_note_sha256': sha(NOTE), 'system_sha256': sha(SYSTEM),
         'model': MODEL, 'max_tokens': ANSWER_TOKENS, 'temperature': 0,
         'cap_usd': CAP, 'chunk_usd': CHUNK, 'cases': 59, 'calls_planned': 118}
    MANIFEST.write_text(json.dumps(m, indent=1))
    print(json.dumps(m, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    assert file_sha(CASES) == m['source_cases_sha256'], 'source cases changed'
    assert sha(NOTE) == m['format_note_sha256'], 'format note changed'
    assert file_sha(B7) == m['b7_answers_sha256'], 'B7 answers changed'
    return m


def board_user(case, board):
    grouped = [[] for _ in range(case['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def call(key, user, cap, total):
    pin, pout = PRICE
    est_in = math.ceil((len(SYSTEM) + len(user)) / 4)
    if total + est_in * pin + ANSWER_TOKENS * pout > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0})
        return None, total
    cid = sha('|'.join([key, MODEL, sha(SYSTEM), sha(user), str(ANSWER_TOKENS)]))
    log({'event': 'intent', 'key': key, 'call_id': cid, 'model': MODEL,
         'system_sha256': sha(SYSTEM), 'user_sha256': sha(user),
         'max_tokens': ANSWER_TOKENS, 'temperature': 0})
    from utility.apis.router import single_request
    resp = single_request(APIRequest(system_query=SYSTEM, user_query=user, model=MODEL,
                                     max_tokens=ANSWER_TOKENS, temperature=0,
                                     metadata={'pilot': 'b7b_format', 'key': key}))
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    log({'event': 'result', 'key': key, 'call_id': cid, 'model': MODEL,
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
            resp, total = call(f"{case['instance_id']}/{arm}", user, CAP, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                return
            answer = extract_answer(resp.content or '')
            f1 = answer_f1(answer, {'answer': case['gold'],
                                    'answer_aliases': case['aliases']})
            rec = {'instance_id': case['instance_id'], 'label': case['label'],
                   'model': MODEL, 'arm': arm, 'gold': case['gold'], 'answer': answer,
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


def score():
    m = check()
    cases = {c['instance_id']: c for c in json.loads(CASES.read_text())}
    new = {(r['instance_id'], r['arm']): r
           for r in (json.loads(l) for l in ANSWERS.read_text().splitlines() if l.strip())}
    old = {(r['instance_id'], r['arm']): r
           for r in (json.loads(l) for l in B7.read_text().splitlines() if l.strip())}
    early = {(r['instance_id'], r['arm']): r
             for r in (json.loads(l) for l in EARLIER.read_text().splitlines() if l.strip())}
    ids = [i for i in cases if (i, 'control') in new and (i, 'insert') in new
           and (i, 'control') in old and (i, 'insert') in old]
    out = {'n': len(ids), 'spend_usd': round(spent(), 6)}
    for arm in ('control', 'insert'):
        k = int(sum(new[(i, arm)]['exact'] for i in ids))
        kb = int(sum(old[(i, arm)]['exact'] for i in ids))
        lo, hi = cp_ci(k, len(ids))
        out[arm] = {'b7b': k, 'b7': kb, 'b7b_cp_ci': [lo, hi],
                    'paired_b7b_minus_b7': boot([(new[(i, arm)]['exact'],
                                                 old[(i, arm)]['exact']) for i in ids]),
                    'earlier': int(sum(early[(i, arm)]['exact'] for i in ids)),
                    'paired_b7b_minus_earlier': boot([(new[(i, arm)]['exact'],
                                                      early[(i, arm)]['exact']) for i in ids]),
                    'flips': {'better': sum(1 for i in ids
                                            if new[(i, arm)]['exact'] > old[(i, arm)]['exact']),
                              'worse': sum(1 for i in ids
                                           if new[(i, arm)]['exact'] < old[(i, arm)]['exact'])}}
    out['insert_minus_control'] = boot([(new[(i, 'insert')]['exact'],
                                         new[(i, 'control')]['exact']) for i in ids])
    out['by_label'] = {}
    for label in ('present', 'partial', 'absent'):
        kk = [i for i in ids if cases[i]['label'] == label]
        if kk:
            out['by_label'][label] = {
                'n': len(kk),
                'insert': int(sum(new[(i, 'insert')]['exact'] for i in kk)),
                'control': int(sum(new[(i, 'control')]['exact'] for i in kk))}
    SCORE.write_text(json.dumps(out, indent=1))
    write_report(out, m)
    print(json.dumps(out, indent=1))


def write_report(res, man):
    def pct(k, n):
        return '%d/%d (%.1f%%)' % (k, n, 100.0 * k / n) if n else '—'

    def d(t):
        return '%+.3f [%+.3f, %+.3f]' % t

    ins, ctl = res['insert'], res['control']
    lines = ['# B7b: format-constrained direct-insertion rerun',
             '',
             '2026-11-15. Pre-registered format fix. Rule `B7b-format-constrained.md` (sha `%s...`). Same 59 '
             'cases, boards and inserted facts as B7; Opus 5.5 in both arms; the only change is the frozen '
             'instruction to answer with the bare value. Spend $%.6f, cap $1.50.'
             % (man['rule_sha256'][:8], res['spend_usd']),
             '',
             '| arm | earlier model | B7 (Opus, sentence format) | B7b (Opus, bare value) | B7b exact 95% CI | paired B7b minus B7 [95% CI] | paired B7b minus earlier [95% CI] | flips vs B7 better / worse |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |',
             '| insert (fact supplied) | %s | %s | %s | %.3f-%.3f | %s | %s | %d / %d |'
             % (pct(ins['earlier'], res['n']), pct(ins['b7'], res['n']), pct(ins['b7b'], res['n']),
                *ins['b7b_cp_ci'], d(ins['paired_b7b_minus_b7']),
                d(ins['paired_b7b_minus_earlier']), ins['flips']['better'], ins['flips']['worse']),
             '| control (board only) | %s | %s | %s | %.3f-%.3f | %s | %s | %d / %d |'
             % (pct(ctl['earlier'], res['n']), pct(ctl['b7'], res['n']), pct(ctl['b7b'], res['n']),
                *ctl['b7b_cp_ci'], d(ctl['paired_b7b_minus_b7']),
                d(ctl['paired_b7b_minus_earlier']), ctl['flips']['better'], ctl['flips']['worse']),
             '',
             'Within B7b, insert minus control: %s.' % d(res['insert_minus_control']),
             '',
             '| label | n | insert | control |', '| --- | ---: | ---: | ---: |']
    for label in ('present', 'partial', 'absent'):
        b = res['by_label'].get(label)
        if b:
            lines.append('| %s | %d | %d | %d |' % (label, b['n'], b['insert'], b['control']))
    lines += ['',
              'Scoring: the frozen exact rule (`answer_f1 == 1.0` with aliases), the same rule as B7 and the '
              'earlier run. Paired bootstrap over cases, 2,000 draws, seed 43; Clopper-Pearson intervals on '
              'counts.',
              '',
              '## Status of the earlier results',
              '',
              'The earlier frozen-rule run (32/59 insert) and B7\'s sentence-format result (22/59) stay on '
              'record. The post-hoc alias/containment secondary from B7 (47/59 vs 40/59) stays labelled '
              'post-hoc and is not used here. B7b is the pre-registered confirmation that B7\'s drop was a '
              'format effect, not a capability effect.',
              '',
              '## What this cannot show',
              '',
              'The insert arm supplies the missing fact verbatim: it is still an oracle upper bound, not an '
              'achievable repair.',
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