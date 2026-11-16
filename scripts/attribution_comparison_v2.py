"""Who&When-style stage attribution on known-stage cases.

Rule: `rebuttal/pilots/20261113_attribution_comparison/ATTRIBUTION_RULE_V2.md`,
frozen before any call. 30 injected distortions (known stage transmission) +
59 missing-fact instances (39 extraction, 20 sharding). Gemini 3.6 Flash
judge; cap $0.50 pilot and $2.00 full.

    ./run.sh python -m scripts.attribution_comparison --build
    ./run.sh python -m scripts.attribution_comparison --pilot --cap-usd 0.50
    ./run.sh python -m scripts.attribution_comparison --run --cap-usd 2
    ./run.sh python -m scripts.attribution_comparison --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.run_expansion_stage2 import packages
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_attribution_comparison'
SRC = ROOT / 'rebuttal/pilots/20261113_injected_distortion'
SHARD = ROOT / 'rebuttal/pilots/20261113_sharding_diagnosis/results.json'
RULE = OUT / 'ATTRIBUTION_RULE_V2.md'
PROMPT = OUT / 'attribution_prompt_v1.json'
CASES = OUT / 'cases_v2.json'
MANIFEST = OUT / 'run_manifest_v2.json'
CALLS = OUT / 'calls_v2.jsonl'
RESULTS = OUT / 'results_v2.json'
REPORT = OUT / 'report.md'
SEED = 43
MAX_OUT = 8192
CAP = 2.0
STAGES = {'sharding', 'extraction', 'transmission', 'aggregation'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trunc(s, n=500):
    return s if len(s) <= n else s[:n] + ' ...'


def render_case(c):
    q = c['question']
    parts = [f'QUESTION\n{q}\n']
    parts.append('SOURCE SHARDS BY AGENT')
    for a, text in c['source'].items():
        parts.append(f'[agent {a}] {trunc(text)}')
    for label, cp in (('EXTRACTION POOL', 'extraction'),
                      ('TRANSMITTED EVIDENCE', 'transmission'),
                      ('SHARED BOARD', 'board')):
        parts.append(f'\n{label}')
        for u in c[cp]:
            parts.append(f'[{u["unit_id"]}] (agent {u["agent_id"]}) '
                         f'{trunc(u["text"])}')
    parts.append(f'\nFINAL ANSWER (incorrect)\n{c["answer"]}')
    return '\n'.join(parts)


def build():
    accepted = json.loads((SRC / 'accepted.json').read_text())['accepted']
    answers = [json.loads(l) for l in
               (SRC / 'answers.jsonl').read_text().splitlines() if l.strip()]
    # accepted uses instance_id/model/unit_id; match corrupt answers by name
    ans_by = {(a['instance_id'], a['model'], a['unit_id']): a
              for a in answers if a['arm'] == 'corrupt'}
    rows = []
    for c in accepted:
        m, inst = c['model'], c['instance_id']
        t = packages(m)[inst]
        a = ans_by[(inst, m, c['unit_id'])]
        bid = c['unit_id']
        tid = bid.replace('board:', 'transmission:', 1)
        board = [dict(u) for u in t['checkpoints']['board']]
        trans = [dict(u) for u in t['checkpoints']['transmission']]
        for u in board:
            if u['unit_id'] == bid:
                u['text'] = c['corrupt']
        for u in trans:
            if u['unit_id'] == tid:
                u['text'] = c['corrupt']
        rows.append({'key': f'inj/{m}/{inst}', 'population': 'injected',
                     'known_stage': 'transmission', 'question': t['question'],
                     'source': {s['agent_id']: s['text']
                                for s in t['source_supports']},
                     'extraction': t['checkpoints']['extraction'],
                     'transmission': trans, 'board': board,
                     'answer': str(a['answer'])})
    cohort_all = json.loads(SHARD.read_text())['cohort_traces']
    by_inst = {}
    for r in cohort_all:
        by_inst.setdefault(r['instance_id'], []).append(r)
    cohort = [min(v, key=lambda x: sha('43|attr-v2|' + x['instance_id']
                                        + '|' + x['fact_id']))
              for v in by_inst.values()]
    for r in cohort:
        m, inst = r['model'], r['instance_id']
        t = packages(m)[inst]
        rows.append({'key': f'coh/{m}/{inst}', 'population': 'cohort',
                     'known_stage': 'sharding' if r['new'].startswith(
                         'sharding') else 'extraction',
                     'question': t['question'],
                     'source': {s['agent_id']: s['text']
                                for s in t['source_supports']},
                     'extraction': t['checkpoints']['extraction'],
                     'transmission': t['checkpoints']['transmission'],
                     'board': t['checkpoints']['board'],
                     'answer': str(t['baseline_prediction'])})
    rows.sort(key=lambda x: sha('43|attr|' + x['key']))
    assert len(rows) == 89, len(rows)
    CASES.write_text(json.dumps(rows, ensure_ascii=False))
    pilot = [x['key'] for x in rows[:10]]
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True, 'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'system_sha256': sha(json.loads(PROMPT.read_text())['system']),
        'cases_sha256': file_sha(CASES), 'n': len(rows), 'seed': SEED,
        'pilot_keys': pilot, 'cap_pilot_usd': 0.50, 'cap_usd': CAP,
        'model': 'google/gemini-3.6-flash'}, indent=1, ensure_ascii=False))
    print(json.dumps({'cases': len(rows), 'injected': 30, 'cohort': len(cohort),
                      'pilot': len(pilot),
                      'cases_sha256': file_sha(CASES)[:12]}, indent=1))


def call(key, system, user, cap, total):
    pin, pout = price(json.loads(PROMPT.read_text())['model'])
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + MAX_OUT * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None
    cid = sha('|'.join([key, system, user, str(MAX_OUT)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': json.loads(PROMPT.read_text())['model'],
                            'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_OUT,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user,
                     model=json.loads(PROMPT.read_text())['model'],
                     max_tokens=MAX_OUT, temperature=0,
                     metadata={'pilot': 'attribution_comparison', 'key': key,
                               'openrouter_reasoning': True})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'success': resp.success, 'error': resp.error,
                            'content': resp.content, 'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp


def parse(content):
    obj = last_object(content or '')
    if not isinstance(obj, dict):
        return None
    st = str(obj.get('stage', '')).lower()
    if st not in STAGES:
        return None
    return {'stage': st, 'agent': obj.get('agent'),
            'reason': str(obj.get('reason', ''))[:200]}


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def execute(cap, only_pilot=False):
    man = json.loads(MANIFEST.read_text())
    assert man['recorded_before_first_call']
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(CASES) == man['cases_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(CASES.read_text())
    if only_pilot:
        keep = set(man['pilot_keys'])
        rows = [r for r in rows if r['key'] in keep]
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
                if r.get('judge')}
    total = spent()
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), 6):
        chunk = todo[i:i + 6]
        reserve = sum(math.ceil((len(spec['system']) + len(render_case(r))) /
                                4) * price(spec['model'])[0] +
                      MAX_OUT * price(spec['model'])[1] for r in chunk)
        if total + reserve > cap:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(call, r['key'], spec['system'],
                              render_case(r), cap, total): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                done[r['key']] = {'key': r['key'],
                                  'population': r['population'],
                                  'known_stage': r['known_stage'],
                                  'judge': parse(resp.content)
                                  if resp and resp.success else None}
        total = spent()
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1,
                                  ensure_ascii=False))
    print(json.dumps({'scored': sum(1 for r in done.values()
                                    if r.get('judge')),
                      'spent_usd': round(total, 8)}, indent=1))


def report():
    rows = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
            if r.get('judge')}
    spend = spent()
    groups = {}
    for r in rows.values():
        groups.setdefault(r['population'], []).append(r)
    lines = ['# Published-style stage attribution on known-stage cases\n',
             f"Rule `ATTRIBUTION_RULE_V2.md` (sha256 `{file_sha(RULE)[:12]}`), "
             f"prompt `attribution_prompt_v1.json` (sha256 "
             f"`{file_sha(PROMPT)[:12]}`), Gemini 3.6 Flash. "
             f"{len(rows)} of 89 cases scored; spend **${spend:.6f}**, caps "
             f"$0.50 pilot / $2.00 full.\n",
             '| population | known stage | n | judge correct | accuracy [95% CI] |',
             '| --- | --- | ---: | ---: | --- |']
    for pop in ('injected', 'cohort'):
        rs = groups.get(pop, [])
        k = sum(r['judge']['stage'] == r['known_stage'] for r in rs)
        n = len(rs)
        lo, hi = cp_ci(k, n) if n else (0, 0)
        lines.append(f"| {pop} | {'transmission' if pop == 'injected' else 'extraction/sharding'} | "
                     f"{n} | {k} | {k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}] |")
    allr = list(rows.values())
    k = sum(r['judge']['stage'] == r['known_stage'] for r in allr)
    n = len(allr)
    lo, hi = cp_ci(k, n) if n else (0, 0)
    lines += ['', f"**Overall judge stage accuracy {k}/{n} = {k / n:.3f} "
              f"[{lo:.3f}, {hi:.3f}]**.\n",
              '| known \\ judge | sharding | extraction | transmission | aggregation |',
              '| --- | ---: | ---: | ---: | ---: |']
    for ks in ('sharding', 'extraction', 'transmission'):
        cells = [sum(1 for r in allr if r['known_stage'] == ks
                     and r['judge']['stage'] == js)
                 for js in ('sharding', 'extraction', 'transmission',
                            'aggregation')]
        lines.append(f"| {ks} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    # Measured comparison rows on the same 89 cases: audit's own diagnosis
    # (separate frozen run) and the lexical checkpoint-drop baseline. The
    # earlier definitional audit row (30/30, 59/59) is dropped, and
    # always-aggregation is dropped as definitional.
    from scripts.method_comparison import baseline
    audit = {r['key']: r for r in json.loads(
        (ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/'
         'audit_results.json').read_text())['items']}

    def lex(c):
        t = {'source_supports': [{'text': v} for v in c['source'].values()],
             'checkpoints': {'extraction': c['extraction'],
                             'board': c['board']}}
        return baseline(t)

    cases = {c['key']: c for c in json.loads(CASES.read_text())}
    methods = {
        'Who&When-style judge (Gemini 3.6 Flash)':
            lambda c: rows[c['key']]['judge']['stage']
            if c['key'] in rows else None,
        'audit, measured (Qwen-235B matcher + diagnosis)':
            lambda c: audit[c['key']]['audit_stage']
            if c['key'] in audit else None,
        'lexical checkpoint-drop baseline': lambda c: lex(c),
    }
    lines += ['', '## Comparison (measured on the same 89 cases)\n',
              '| method | injected (n=30) | cohort (n=59) | overall (n=89) |',
              '| --- | --- | --- | --- |']

    def cell(pop, fn):
        rs = [c for c in cases.values()
              if (pop is None or c['population'] == pop)]
        got = [(fn(c), c['known_stage']) for c in rs]
        got = [(a, b) for a, b in got if a is not None]
        k = sum(a == b for a, b in got)
        n = len(got)
        lo, hi = cp_ci(k, n) if n else (0, 0)
        return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]" if n else "n/a"

    for name, fn in methods.items():
        lines.append(f"| {name} | {cell('injected', fn)} | "
                     f"{cell('cohort', fn)} | {cell(None, fn)} |")
    lines += ['', 'The audit row is a **real run** of the audit\'s own diagnosis: '
              'for the 59 cohort cases, `diagnose_with_sharding` on the frozen '
              'Stage-2 matcher records (zero calls); for the 30 injected cases, '
              'the audit matcher (`matcher_v2`, Qwen-235B) rerun on the '
              'corrupted board plus the same diagnosis (spend $0.025289, cap '
              '$0.50). The earlier definitional audit row (30/30, 59/59) is '
              'dropped; always-aggregation is dropped as definitional.\n',
              'Caveat: the cohort truth is the frozen input-presence rule and '
              'the audit uses the same 0.8/0.4 content-recall check, so its '
              '44/59 cohort figure is a consistency check against a shared '
              'rule, not independent accuracy; 14 of its 15 cohort errors are '
              'cases where the frozen label is a manual adjudication over that '
              'rule. The injected 26/30 row is independent: truth by '
              'construction, audit sees only the corrupted trace.\n',
              'The judge is an LLM with a frozen prompt, not the published '
              'method\'s released code; the stage vocabulary is the audit\'s, '
              'extended with sharding. The comparison is descriptive.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'overall': [k, n, k / n if n else 0],
                      'injected': [sum(1 for r in groups.get('injected', [])
                                       if r['judge']['stage'] == 'transmission'),
                                   len(groups.get('injected', []))],
                      'cohort': [sum(1 for r in groups.get('cohort', [])
                                     if r['judge']['stage'] == r['known_stage']),
                                 len(groups.get('cohort', []))],
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        execute(a.cap_usd, only_pilot=True)
    if a.run:
        execute(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()