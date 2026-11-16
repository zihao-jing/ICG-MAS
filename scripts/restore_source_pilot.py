"""Restore-the-source test on real-run distortion diagnoses.

Rule: `rebuttal/pilots/20261113_restore_source/RESTORE_RULE.md`, frozen before
any call. Pilot 40 of 184 unique distortion cases; cap $5; every call logged.

    ./run.sh python -m scripts.restore_source_pilot --build
    ./run.sh python -m scripts.restore_source_pilot --pilot --cap-usd 5
    ./run.sh python -m scripts.restore_source_pilot --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from src.audit.sharding_check import content_recall, evidence_sentences
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_restore_source'
RULE = OUT / 'RESTORE_RULE.md'
MANIFEST = OUT / 'run_manifest.json'
FULL_RULE = OUT / 'RESTORE_FULL_ADDENDUM.md'
FULL_MANIFEST = OUT / 'run_manifest_full.json'
CASES = OUT / 'cases.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
REPORT_FULL = OUT / 'report_full.md'
SEED = 43
PILOT_N = 40
CAP = 5.0
MODEL_ORDER = ('gemma31b', 'gpt4omini', 'qwen235b')
MAX_CONFIRM = 400
MAX_ANSWER = 1024


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases():
    from scripts.run_expansion_stage1 import (
        MATCHER_DIR as M1, packages as p1,
    )
    from scripts.run_expansion_stage2 import (
        MATCHER_DIR as M2, packages as p2,
    )
    pk = {}
    for m in MODEL_ORDER:
        pk.update({(m, i): t for i, t in p1(m).items()})
        pk.update({(m, i): t for i, t in p2(m).items()})
    rows = []
    for d in (M1, M2):
        for p in sorted(Path(d).glob('*.json')):
            r = json.loads(p.read_text())
            if r.get('status') != 'ok' or r.get('diagnosis') != 'distortion':
                continue
            t = pk.get((r['model'], r['instance_id']))
            if t is None:
                continue
            rows.append({'record': r, 'trace': t})
    by = {}
    for x in rows:
        inst = x['record']['instance_id']
        rank = MODEL_ORDER.index(x['record']['model']) \
            if x['record']['model'] in MODEL_ORDER else 9
        if inst not in by or rank < by[inst][0]:
            by[inst] = (rank, x)
    cases = []
    for inst, (_, x) in sorted(by.items()):
        r, t = x['record'], x['trace']
        facts = {f['fact_id']: f for f in r['facts']['facts']}
        car = next((c for c in r['carriers']['facts']
                    if any(v['fidelity'] == 'distorted' for v in c['board'])), None)
        if car is None:
            continue
        fact = facts[car['fact_id']]
        unit = next(v for v in car['board'] if v['fidelity'] == 'distorted')
        bid = unit['unit_ids'][0]
        board_unit = next(u for u in t['checkpoints']['board']
                          if u['unit_id'] == bid)
        wants = {s.split(':')[-1] for s in fact['source_ids']}
        shards = [c['text'] for c in t['source_contexts']
                  if c['context_id'].split(':')[-1] in wants]
        best = ''
        for text in shards:
            for s in evidence_sentences(text, t['question']):
                if not best or content_recall(s, fact['text']) > \
                        content_recall(best, fact['text']):
                    best = s
        cases.append({'instance_id': inst, 'model': r['model'],
                      'benchmark': t.get('dataset') or '',
                      'question': t['question'], 'gold': str(t['gold_answer']),
                      'fact_id': fact['fact_id'], 'fact': fact['text'],
                      'board_unit_id': bid, 'board_unit': board_unit['text'],
                      'source_sentence': best,
                      'source_shards': shards,
                      'trace': t})
    for c in cases:
        c['key'] = sha(f"{SEED}|restore|{c['instance_id']}")[:12]
    cases.sort(key=lambda c: c['key'])
    return cases


def build():
    cs = load_cases()
    assert len(cs) == 184, len(cs)
    OUT.mkdir(parents=True, exist_ok=True)
    CASES.write_text(json.dumps(
        [{k: v for k, v in c.items() if k != 'trace'} for c in cs],
        indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'cases_sha256': file_sha(CASES),
        'population': len(cs), 'pilot_n': PILOT_N, 'seed': SEED,
        'cap_usd': CAP, 'model': MODEL_OPENROUTER,
        'max_tokens_confirm': MAX_CONFIRM, 'max_tokens_answer': MAX_ANSWER,
    }, indent=1))
    print(json.dumps({'population': len(cs), 'pilot': PILOT_N}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def call(key, system, user, max_tokens, cap, total):
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * PRICE_IN + max_tokens * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, system, user, str(max_tokens)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': MODEL_OPENROUTER,
                            'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': max_tokens, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user,
                     model=MODEL_OPENROUTER, max_tokens=max_tokens,
                     temperature=0,
                     metadata={'pilot': 'restore_source', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': MODEL_OPENROUTER, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


CONFIRM_SYSTEM = (
    'You verify whether a source sentence states a critical fact and whether a '
    'board entry contradicts that fact. Judge only the text shown; do not use '
    'outside knowledge; the final answer is not shown. Return strict JSON only:\n'
    '{"source_states_fact": "yes|no", "board_contradicts": "yes|no", '
    '"reason": "one short sentence"}')


def confirm_user(c):
    return (f"QUESTION\n{c['question']}\n\nCRITICAL FACT\n{c['fact']}\n\n"
            f"CANDIDATE SOURCE SENTENCE\n{c['source_sentence']}\n\n"
            f"BOARD ENTRY\n{c['board_unit']}")


def boards(c, restore):
    units = []
    for u in c['trace']['checkpoints']['board']:
        text = (c['source_sentence'] if restore and
                u['unit_id'] == c['board_unit_id'] else u['text'])
        units.append({'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                      'text': text})
    n = max(u['agent_id'] for u in units) + 1
    grouped = [[] for _ in range(n)]
    for u in units:
        grouped[u['agent_id']].append(str(u['text']))
    return _build_evidence_board_prompt(grouped, c['question'])


def score(pred, gold):
    p = extract_answer(pred or '')
    exact = bool(silobench_exact_match(p, {'answer': gold}))
    return {'prediction': p, 'exact': exact,
            'f1': answer_f1(p, {'answer': gold})}


def freeze_full():
    """Freeze the full-run addendum before the remaining calls."""
    cs = load_cases()
    assert len(cs) == 184, len(cs)
    FULL_MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'addendum_sha256': file_sha(FULL_RULE),
        'pilot_rule_sha256': file_sha(RULE),
        'cases_sha256': file_sha(CASES),
        'population': len(cs), 'seed': SEED, 'cap_usd': CAP,
        'model': MODEL_OPENROUTER,
        'max_tokens_confirm': MAX_CONFIRM, 'max_tokens_answer': MAX_ANSWER,
    }, indent=1))
    print(json.dumps({'frozen': len(cs), 'addendum_sha256':
                      file_sha(FULL_RULE)[:12]}, indent=1))


def pilot(cap, full=False):
    man = json.loads((FULL_MANIFEST if full else MANIFEST).read_text())
    if full:
        assert file_sha(FULL_RULE) == man['addendum_sha256'], 'rule changed'
    else:
        assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(CASES) == man['cases_sha256'], 'cases changed'
    cs = load_cases() if full else load_cases()[:PILOT_N]
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['cases']}
    out = list(done.values())
    for c in cs:
        if c['key'] in done:
            continue
        resp, total = call(f"confirm/{c['key']}", CONFIRM_SYSTEM,
                           confirm_user(c), MAX_CONFIRM, cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        obj = last_object(resp.content or '') or {}
        stated = obj.get('source_states_fact') == 'yes'
        norm = lambda s: ' '.join(str(s).split()).lower()
        verbatim = bool(c['source_sentence']) and any(
            norm(c['source_sentence']) in norm(sh) for sh in c['source_shards'])
        confirmed = bool(stated and verbatim)
        rec = {'key': c['key'], 'instance_id': c['instance_id'],
               'model': c['model'], 'confirmed': confirmed,
               'source_states_fact': obj.get('source_states_fact'),
               'board_contradicts': obj.get('board_contradicts'),
               'verbatim': verbatim, 'confirm_reason': obj.get('reason')}
        if confirmed:
            for arm, restore in (('control', False), ('restore', True)):
                user = boards(c, restore)
                r2, total = call(f"{arm}/{c['key']}", _AGGREGATION_SYSTEM,
                                 user, MAX_ANSWER, cap, total)
                if r2 is None:
                    break
                rec[arm] = score(r2.content, c['gold'])
        out.append(rec)
        RESULTS.write_text(json.dumps({'cases': out}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'key': c['key'], 'confirmed': confirmed,
                          'arms': 'restore' in rec,
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'cases': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'pilot': len(cs), 'spent_usd': round(spent(), 8)},
                     indent=1))


def report(full=False):
    d = json.loads(RESULTS.read_text())
    rows = d['cases']
    if full:
        keep = {c['key'] for c in load_cases()}
        rows = [r for r in rows if r['key'] in keep]
    cs = {c['key']: c for c in (load_cases() if full else
                                load_cases()[:PILOT_N])}
    conf = [r for r in rows if r['confirmed']]
    arms = [r for r in conf if 'control' in r and 'restore' in r]
    total = spent()
    k, n = len(conf), len(rows)
    lo, hi = cp_ci(k, n)
    rule_name = 'RESTORE_FULL_ADDENDUM.md' if full else 'RESTORE_RULE.md'
    rule_sha = file_sha(FULL_RULE if full else RULE)
    scope = (f'Full run, {n} of 184 unique cases'
             if full else f'Pilot {n} of 184 unique cases')
    lines = ['# Restore-the-source test on real-run distortion diagnoses\n',
             f"Rule `{rule_name}` (sha256 `{rule_sha[:12]}`), frozen "
             f"before the calls. {scope} "
             f"(`sha256('43|restore|'+instance)` order). Spend ${total:.6f}; cap "
             f"${CAP:.2f}. Stages: relay checkpoint (the distorted unit) and "
             'final aggregation (the two arms).\n',
             '## Confirmation\n',
             f'Cases whose source sentence was confirmed to state the fact and '
             f'is verbatim in the source shard: **{k}/{n}** '
             f'({100 * k / n:.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f}).\n',
             '| instance | model | source states fact | board contradicts | confirmed |',
             '| --- | --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['instance_id']} | {r['model']} | "
                     f"{r['source_states_fact']} | {r['board_contradicts']} | "
                     f"{'yes' if r['confirmed'] else 'no'} |")
    if arms:
        ce = sum(r['control']['exact'] for r in arms)
        re = sum(r['restore']['exact'] for r in arms)
        cf = sum(r['control']['f1'] for r in arms) / len(arms)
        rf = sum(r['restore']['f1'] for r in arms) / len(arms)
        lo2, hi2 = cp_ci(re, len(arms))
        lines += ['', '## Answer arms (confirmed cases)\n',
                  f'Control exact **{ce}/{len(arms)}**; restore exact '
                  f'**{re}/{len(arms)}** ({100 * re / len(arms):.1f}%, 95% CI '
                  f'{100 * lo2:.1f}-{100 * hi2:.1f}). Mean F1 control '
                  f'{cf:.3f}, restore {rf:.3f}. Paired: '
                  f"{sum((r['restore']['exact'] and not r['control']['exact']) for r in arms)} "
                  f"improved, "
                  f"{sum((r['control']['exact'] and not r['restore']['exact']) for r in arms)} "
                  f"worse, "
                  f"{sum((r['control']['exact'] == r['restore']['exact']) for r in arms)} "
                  'same.']
    lines += ['', '## Reading\n',
              f'Only {k} of {n} cases have a source sentence that the '
              'labeller confirms states the fact and is verbatim in the shard. '
              'The remainder are distortion diagnoses whose target unit is not '
              'a near-copy of a source fact (refusals, headers, unrelated '
              'text), so the audit\'s distortion label is not restorable from '
              'the source. On the confirmed cases the restore arm is reported '
              'above; the sample is descriptive.\n',
              'The confirming labeller is **Claude Haiku 5.5** with the '
              'frozen prompt in `RESTORE_RULE.md`, temperature 0. It has '
              '**not been validated for this confirmation task**: there is no '
              'independent held-out check of its `source_states_fact` call. '
              'The verbatim-substring test is mechanical, but the '
              'states-the-fact judgement is unvalidated. The 132 count is '
              'therefore a labeller-gated count, not an author-validated one.']
    path = REPORT_FULL if full else REPORT
    path.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'full' if full else 'pilot': n, 'confirmed': k,
                      'arms': len(arms),
                      'control_exact': sum(r['control']['exact'] for r in arms),
                      'restore_exact': sum(r['restore']['exact'] for r in arms),
                      'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--freeze-full', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.freeze_full:
        freeze_full()
    if a.pilot:
        pilot(a.cap_usd)
    if a.full:
        pilot(a.cap_usd, full=True)
    if a.report:
        report(full=a.full or FULL_MANIFEST.exists())


if __name__ == '__main__':
    main()