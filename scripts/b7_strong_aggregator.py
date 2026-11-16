"""B7: direct-insertion rerun with Opus 5.5 as the aggregator.

Rule `rebuttal/pilots/prereg/B7-strong-aggregator-insertion.md`, frozen before any call.
Boards and inserted facts are the earlier 59-case set; only the answering model changes.

    ./run.sh python -m scripts.b7_strong_aggregator --build
    ./run.sh python -m scripts.b7_strong_aggregator --run
    ./run.sh python -m scripts.b7_strong_aggregator --score
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from src.eval.evaluate import answer_f1, normalize
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_b7_strong_aggregator'
RULE = ROOT / 'rebuttal/pilots/prereg/B7-strong-aggregator-insertion.md'
SRC = ROOT / 'rebuttal/pilots/20261112_missing_fact_repair/direct_insertion'
CASES = SRC / 'cases.json'
SRC_MANIFEST = SRC / 'prompt_manifest.json'
EARLIER = SRC / 'answers.jsonl'
MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
ANSWERS = OUT / 'answers.jsonl'
SCORE = OUT / 'score.json'
REPORT = OUT / 'report.md'
MODEL = 'anthropic/claude-opus-5.5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
ANSWER_TOKENS = 1024
CAP = 3.0
CHUNK = 0.9
SEED = 43


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
         'source_answers_sha256': file_sha(EARLIER),
         'answer_prompt_sha256': sha(_AGGREGATION_SYSTEM),
         'model': MODEL, 'max_tokens': ANSWER_TOKENS, 'temperature': 0,
         'cap_usd': CAP, 'chunk_usd': CHUNK, 'cases': 59, 'calls_planned': 118}
    MANIFEST.write_text(json.dumps(m, indent=1))
    print(json.dumps(m, indent=1))


def check():
    m = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == m['rule_sha256'], 'rule changed'
    assert file_sha(CASES) == m['source_cases_sha256'], 'source cases changed'
    assert file_sha(EARLIER) == m['source_answers_sha256'], 'source answers changed'
    return m


def board_user(case, board):
    grouped = [[] for _ in range(case['n_agents'])]
    for u in board:
        grouped[int(u['agent_id'])].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, case['question'])


def call(key, user, cap, total):
    pin, pout = PRICE
    est_in = math.ceil((len(_AGGREGATION_SYSTEM) + len(user)) / 4)
    if total + est_in * pin + ANSWER_TOKENS * pout > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'cost_usd': 0.0})
        return None, total
    cid = sha('|'.join([key, MODEL, sha(_AGGREGATION_SYSTEM), sha(user), str(ANSWER_TOKENS)]))
    log({'event': 'intent', 'key': key, 'call_id': cid, 'model': MODEL,
         'system_sha256': sha(_AGGREGATION_SYSTEM), 'user_sha256': sha(user),
         'max_tokens': ANSWER_TOKENS, 'temperature': 0})
    from utility.apis.router import single_request
    resp = single_request(APIRequest(system_query=_AGGREGATION_SYSTEM, user_query=user,
                                     model=MODEL, max_tokens=ANSWER_TOKENS,
                                     temperature=0,
                                     metadata={'pilot': 'b7_strong_aggregator', 'key': key}))
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
    """Paired bootstrap over cases (one instance per case), 2,000 draws, seed 43."""
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
    new = [json.loads(l) for l in ANSWERS.read_text().splitlines() if l.strip()]
    old = [json.loads(l) for l in EARLIER.read_text().splitlines() if l.strip()]
    N = {(r['instance_id'], r['arm']): r for r in new}
    O = {(r['instance_id'], r['arm']): r for r in old}
    ids = [c for c in cases if (c, 'control') in N and (c, 'insert') in N
           and (c, 'control') in O and (c, 'insert') in O]
    def contained(ans, case):
        na = set(normalize(str(ans)))
        golds = [case['gold']] + list(case.get('aliases') or [])
        return float(any(set(normalize(str(g))) <= na for g in golds if normalize(str(g))))

    out = {'n': len(ids), 'spend_usd': round(spent(), 6)}
    for arm in ('control', 'insert'):
        k = int(sum(N[(i, arm)]['exact'] for i in ids))
        ko = int(sum(O[(i, arm)]['exact'] for i in ids))
        lo, hi = cp_ci(k, len(ids))
        cnew = sum(contained(N[(i, arm)]['answer'], cases[i]) for i in ids)
        cold = sum(contained(O[(i, arm)]['answer'], cases[i]) for i in ids)
        out[arm] = {'new': k, 'old': ko, 'cp_ci': [lo, hi],
                    'paired_new_minus_old': boot([(N[(i, arm)]['exact'], O[(i, arm)]['exact'])
                                                  for i in ids]),
                    'contain_new': int(cnew), 'contain_old': int(cold),
                    'paired_contain_new_minus_old': boot(
                        [(contained(N[(i, arm)]['answer'], cases[i]),
                          contained(O[(i, arm)]['answer'], cases[i])) for i in ids])}
    out['insert_minus_control_new'] = boot([(N[(i, 'insert')]['exact'],
                                             N[(i, 'control')]['exact']) for i in ids])
    out['insert_minus_control_old'] = boot([(O[(i, 'insert')]['exact'],
                                             O[(i, 'control')]['exact']) for i in ids])
    out['flips_insert_new_vs_old'] = {
        'worse': sum(1 for i in ids if N[(i, 'insert')]['exact'] < O[(i, 'insert')]['exact']),
        'better': sum(1 for i in ids if N[(i, 'insert')]['exact'] > O[(i, 'insert')]['exact'])}
    out['by_label'] = {}
    for label in ('present', 'partial', 'absent'):
        kk = [i for i in ids if cases[i]['label'] == label]
        if kk:
            out['by_label'][label] = {
                'n': len(kk), 'new_insert': int(sum(N[(i, 'insert')]['exact'] for i in kk)),
                'old_insert': int(sum(O[(i, 'insert')]['exact'] for i in kk)),
                'new_control': int(sum(N[(i, 'control')]['exact'] for i in kk)),
                'old_control': int(sum(O[(i, 'control')]['exact'] for i in kk))}
    SCORE.write_text(json.dumps(out, indent=1))
    write_report(out, m)
    print(json.dumps(out, indent=1))


def write_report(res, man):
    def pct(k, n):
        return '%d/%d (%.1f%%)' % (k, n, 100.0 * k / n) if n else '—'

    def d(t):
        v, lo, hi = t
        return '%+.3f [%+.3f, %+.3f]' % (v, lo, hi)

    ins, ctl = res['insert'], res['control']
    lines = ['# B7: direct insertion re-answered by a stronger aggregator',
             '',
             '2026-11-15. Rule `B7-strong-aggregator-insertion.md` (sha `%s...`). Same 59 cases, boards and '
             'inserted facts as the earlier direct-insertion run; only the answering model changes, to Opus 5.5, '
             'in both arms. Spend $%.6f, cap $3.00.' % (man['rule_sha256'][:8], res['spend_usd']),
             '',
             '| arm | earlier model | Opus 5.5 | Opus exact 95% CI | paired Opus minus earlier [95% CI] |',
             '| --- | --- | --- | --- | --- |',
             '| insert (fact supplied) | %s | %s | %.3f-%.3f | %s |'
             % (pct(ins['old'], res['n']), pct(ins['new'], res['n']), *ins['cp_ci'],
                d(ins['paired_new_minus_old'])),
             '| control (board only) | %s | %s | %.3f-%.3f | %s |'
             % (pct(ctl['old'], res['n']), pct(ctl['new'], res['n']), *ctl['cp_ci'],
                d(ctl['paired_new_minus_old'])),
             '',
             'Within the Opus run, insert minus control: %s. In the earlier run: %s.'
             % (d(res['insert_minus_control_new']), d(res['insert_minus_control_old'])),
             'Insert arm flips under Opus vs the earlier model: %d worse, %d better.'
             % (res['flips_insert_new_vs_old']['worse'], res['flips_insert_new_vs_old']['better']),
             '',
             '## By presence label (insert arm)',
             '',
             '| label | n | earlier model | Opus 5.5 | control, earlier / Opus |',
             '| --- | ---: | ---: | ---: | --- |']
    for label in ('present', 'partial', 'absent'):
        b = res['by_label'].get(label)
        if not b:
            continue
        lines.append('| %s | %d | %d | %d | %d / %d |'
                     % (label, b['n'], b['old_insert'], b['new_insert'],
                        b['old_control'], b['new_control']))
    lines += ['',
              '## Secondary check: gold contained in the answer text (post-hoc)',
              '',
              'The frozen exact rule scores `About 11,900 people.` as wrong against `11,900`. The stronger '
              'aggregator is more verbose, so exact match also measures answer format. This secondary counter '
              '(post-hoc, not the arm\'s scoring rule) counts a case when the gold or an alias appears inside '
              'the extracted answer.',
              '',
              '| arm | earlier model | Opus 5.5 | paired Opus minus earlier [95% CI] |',
              '| --- | --- | --- | --- |',
              '| insert (fact supplied) | %s | %s | %s |'
              % (pct(ins['contain_old'], res['n']), pct(ins['contain_new'], res['n']),
                 d(ins['paired_contain_new_minus_old'])),
              '| control (board only) | %s | %s | %s |'
              % (pct(ctl['contain_old'], res['n']), pct(ctl['contain_new'], res['n']),
                 d(ctl['paired_contain_new_minus_old'])),
              '',
              'Scoring: frozen exact rule (`answer_f1 == 1.0` with aliases); paired bootstrap over cases, 2,000 '
              'draws, seed 43; Clopper-Pearson intervals on counts.',
              '',
              '## What this cannot show',
              '',
              'The insert arm supplies the missing fact verbatim, so it remains an oracle upper bound, not an '
              'achievable repair. The two counters disagree because exact match also scores answer format; '
              'neither says the fact can be routed or extracted without oracle text. Containment can also be '
              'true when the answer lists several candidates or restates the question, so it is an upper '
              'bound on correctness, not a scoring rule.',
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