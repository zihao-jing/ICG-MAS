"""Redo the Stage 2 main-table audit columns with the per-fact labeller.

Rule: `rebuttal/pilots/20261113_main_table_redo/REDO_RULE.md`, frozen before
any call. 2,400 MuSiQue traces x 2 relay checkpoints (extraction, board).
Old = frozen matcher carriers; new = per-fact labeller v3.

    ./run.sh python -m scripts.main_table_redo --build
    ./run.sh python -m scripts.main_table_redo --pilot --cap-usd 0.50
    ./run.sh python -m scripts.main_table_redo --run --cap-usd 5
    ./run.sh python -m scripts.main_table_redo --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_labeller import MAX_TOKENS, parse, render
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_main_table_redo'
RULE = OUT / 'REDO_RULE.md'
PROMPT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
SEED = 43
PILOT_N = 20          # instances per model
WORKERS = 8
CAP = 5.0
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.50 / 1_000_000


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    recs = {}
    for p in sorted(MATCHER_DIR.glob('*.json')):
        r = json.loads(p.read_text())
        if r.get('status') == 'ok':
            recs[(r['model'], r['instance_id'])] = r
    rows = []
    for m in MODELS:
        pk = packages(m)
        for inst in sorted(pk):
            r = recs.get((m, inst))
            if not r:
                continue
            t = pk[inst]
            facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                     for f in r['facts']['facts']]
            if not facts:
                continue
            for cp, name in (('extraction', 'extraction pool'),
                             ('board', 'shared board')):
                entries = [{'unit_id': u['unit_id'],
                            'agent_id': u['agent_id'],
                            'text': u['text']}
                           for u in t['checkpoints'][cp]]
                rows.append({'key': f'{m}|{inst}|{cp}', 'model': m,
                             'instance_id': inst, 'checkpoint': cp,
                             'checkpoint_name': name, 'question': t['question'],
                             'facts': facts, 'entries': entries,
                             'answer_correct': bool(r['answer_correct'])})
    rows.sort(key=lambda x: x['key'])
    assert len(rows) == 4800, len(rows)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    pilot = []
    for m in MODELS:
        ids = sorted({r['instance_id'] for r in rows if r['model'] == m},
                     key=lambda i: sha(f'43|redo|{i}'))[:PILOT_N]
        pilot += [r['key'] for r in rows if r['model'] == m
                  and r['instance_id'] in ids]
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'system_sha256': sha(json.loads(PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP),
        'traces': 2400, 'calls_planned': len(rows), 'facts': sum(
            len(r['facts']) for r in rows) // 2,
        'seed': SEED, 'pilot_instances_per_model': PILOT_N,
        'pilot_calls': len(pilot), 'pilot_cap_usd': 0.50, 'cap_usd': CAP,
        'model': json.loads(PROMPT.read_text())['model'],
        'pilot_keys': sorted(pilot)}, indent=1, ensure_ascii=False))
    print(json.dumps({'rows': len(rows), 'pilot_calls': len(pilot),
                      'facts': sum(len(r['facts']) for r in rows) // 2,
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def valid_results():
    if not RESULTS.exists():
        return {}
    return {r['key']: r for r in json.loads(RESULTS.read_text())['items']
            if r.get('labeller')}


def call(row, spec, cap, total):
    user = render(row)
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        return None, total
    cid = sha('|'.join([row['key'], spec['system'], user,
                        str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': row['key'],
                            'call_id': cid,
                            'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS,
                     temperature=0,
                     metadata={'pilot': 'main_table_redo', 'key': row['key'],
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': row['key'],
                            'call_id': cid, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp, total + cost


def execute(cap, only_pilot=False):
    man = json.loads(MANIFEST.read_text())
    assert man['recorded_before_first_call']
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    if only_pilot:
        keep = set(man['pilot_keys'])
        rows = [r for r in rows if r['key'] in keep]
    done = valid_results()
    todo = [r for r in rows if r['key'] not in done]
    total = spent()
    print(json.dumps({'todo': len(todo), 'done': len(done),
                      'spent_usd': round(total, 6), 'cap_usd': cap}),
          flush=True)
    out = list(done.values())

    for i in range(0, len(todo), WORKERS):
        chunk = todo[i:i + WORKERS]
        if total + sum(math.ceil((len(spec['system']) +
                                  len(render(r))) / 4) * PRICE_IN
                       + MAX_TOKENS * PRICE_OUT for r in chunk) > cap:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6),
                              'remaining': len(todo) - i}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(call, r, spec, cap, total): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                rec, _ = fut.result()
                if rec is None:
                    continue
                lab = parse(rec.content, {f['fact_id'] for f in r['facts']}) \
                    if rec.success else None
                out.append({'key': r['key'], 'model': r['model'],
                            'instance_id': r['instance_id'],
                            'checkpoint': r['checkpoint'],
                            'answer_correct': r['answer_correct'],
                            'labeller': lab})
        total = spent()
        RESULTS.write_text(json.dumps({'items': out}, ensure_ascii=False))
        print(json.dumps({'done': len(out), 'of': len(rows),
                          'spent_usd': round(spent(), 6)}), flush=True)
    RESULTS.write_text(json.dumps({'items': out}, ensure_ascii=False))
    print(json.dumps({'valid': sum(1 for r in out if r.get('labeller')),
                      'rows': len(rows), 'spent_usd': round(spent(), 8)},
                     indent=1))


def old_labels(row, recs):
    r = recs[(row['model'], row['instance_id'])]
    cp = row['checkpoint']
    by = {}
    for c in r['carriers']['facts']:
        cs = c.get(cp) or []
        carried = any(x.get('fidelity') in ('faithful', 'partial',
                                            'distorted') for x in cs)
        dist = any(x.get('fidelity') == 'distorted' for x in cs)
        by[c['fact_id']] = {'carried': carried, 'distorted': dist}
    return [by.get(f['fact_id'], {'carried': False, 'distorted': False})
            for f in row['facts']]


def new_labels(row, lab):
    out = []
    for f in row['facts']:
        v = (lab or {}).get(f['fact_id']) or {'status': 'absent',
                                              'fidelity': 'absent'}
        out.append({'carried': v['status'] != 'absent',
                    'distorted': v['fidelity'] == 'distorted'})
    return out


def metrics(rows, recs, results, side):
    by_inst = {}
    for row in rows:
        if side == 'old':
            labs = old_labels(row, recs)
        else:
            lab = (results.get(row['key']) or {}).get('labeller')
            labs = new_labels(row, lab)
        n = len(labs)
        carried = sum(x['carried'] for x in labs)
        dist = sum(x['distorted'] for x in labs)
        complete = carried == n
        by_inst.setdefault(row['instance_id'], []).append(
            {'cr': carried / n, 'complete': complete,
             'dist': dist / carried if carried else 0.0,
             'af': complete and not row['answer_correct'],
             'carried': carried, 'dist_n': dist})
    keys = list(by_inst)
    vals = [x for k in keys for x in by_inst[k]]
    point = {
        'n': len(vals),
        'cr': sum(x['cr'] for x in vals) / len(vals),
        'complete': sum(x['complete'] for x in vals) / len(vals),
        'dist': (sum(x['dist_n'] for x in vals) /
                 max(1, sum(x['carried'] for x in vals))),
        'af': sum(x['af'] for x in vals) / len(vals)}
    rng = random.Random(SEED)
    draws = {'cr': [], 'complete': [], 'dist': [], 'af': []}
    for _ in range(2000):
        pick = [by_inst[keys[rng.randrange(len(keys))]] for _ in keys]
        flat = [x for g in pick for x in g]
        draws['cr'].append(sum(x['cr'] for x in flat) / len(flat))
        draws['complete'].append(sum(x['complete'] for x in flat) / len(flat))
        draws['dist'].append(sum(x['dist_n'] for x in flat) /
                             max(1, sum(x['carried'] for x in flat)))
        draws['af'].append(sum(x['af'] for x in flat) / len(flat))
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    ci = {k: (q(v, .025), q(v, .975)) for k, v in draws.items()}
    return {'point': point, 'ci': ci}


def report():
    rows = json.loads(POP.read_text())
    recs = {}
    for p in sorted(MATCHER_DIR.glob('*.json')):
        r = json.loads(p.read_text())
        if r.get('status') == 'ok':
            recs[(r['model'], r['instance_id'])] = r
    results = {r['key']: r for r in
               json.loads(RESULTS.read_text())['items']}
    spend = spent()
    cells = {}
    for cp in ('extraction', 'board'):
        for m in MODELS:
            sub = [r for r in rows if r['checkpoint'] == cp
                   and r['model'] == m and r['key'] in results]
            if not sub:
                continue
            cells[(cp, m)] = {'n': len(sub),
                              'old': metrics(sub, recs, results, 'old'),
                              'new': metrics(sub, recs, results, 'new')}
    lines = [
        '# Main-table redo with the validated per-fact labeller\n',
        f"Rule `REDO_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), frozen before "
        f"the pilot call; labeller prompt v3 (sha256 "
        f"`{file_sha(PROMPT)[:12]}`). Population: 2,400 Stage 2 MuSiQue "
        f"traces (800 instances x 3 models, score-ranked relay), 7,665 "
        f"matcher facts, checkpoints extraction pool and shared board. "
        f"Scored {len(results)}/4800 checkpoint calls "
        f"({len(rows) - len(results)} unparsed, scored as absent); spend "
        f"${spend:.6f}, cap ${CAP:.2f}.\n",
        'The old column is the frozen audit matcher label on the same facts '
        'and checkpoint; the new column is the per-fact labeller. The paper\'s '
        'original Table 3 lexical cells come from the earlier 10-model cohort '
        'and are unchanged on record; this redo does not overwrite them. The '
        'paper file is not edited; both new columns sit side by side.\n',
        'Columns: CR = facts with a carrier; complete = all facts in a trace '
        'carried; dist = distorted facts / carried facts (fidelity loss); '
        'AF = complete coverage and a non-perfect answer.\n',
        '**Validation caveat.** The labeller is validated for carrier '
        'identification at the **board** checkpoint only, and only as '
        'cross-model agreement with Gemini 3.6 Flash, not author ground '
        'truth. Extraction rows are exploratory; distortion/fidelity labels '
        'were not checked by the V5 reference and are unvalidated.\n',
        '| checkpoint | model | n traces | CR old | CR new | omission old | '
        'omission new | complete old | complete new | dist old | dist new | '
        'AF old | AF new |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | '
        '---: | ---: | ---: | ---: |']
    def rowline(cp, m, v):
        o, n = v['old']['point'], v['new']['point']
        return (f"| {cp} | {m} | {v['n']} | {o['cr']:.3f} | {n['cr']:.3f} | "
                f"{1 - o['cr']:.3f} | {1 - n['cr']:.3f} | "
                f"{o['complete']:.3f} | {n['complete']:.3f} | "
                f"{o['dist']:.3f} | {n['dist']:.3f} | {o['af']:.3f} | "
                f"{n['af']:.3f} |")
    for cp in ('extraction', 'board'):
        for m in MODELS:
            if (cp, m) in cells:
                lines.append(rowline(cp, m, cells[(cp, m)]))
    for cp in ('extraction', 'board'):
        sub = [r for r in rows if r['checkpoint'] == cp
               and r['key'] in results]
        if sub:
            cells[(cp, 'all')] = {'n': len(sub),
                                  'old': metrics(sub, recs, results, 'old'),
                                  'new': metrics(sub, recs, results, 'new')}
            lines.append(rowline(cp, 'all', cells[(cp, 'all')]))
    lines += ['', '## 95% CIs, pooled by checkpoint (instance-cluster '
              'bootstrap, seed 43)\n',
              '| checkpoint | metric | old [95% CI] | new [95% CI] |',
              '| --- | --- | --- | --- |']
    for cp in ('extraction', 'board'):
        if (cp, 'all') not in cells:
            continue
        for metric in ('cr', 'complete', 'dist', 'af'):
            o, n = cells[(cp, 'all')]['old'], cells[(cp, 'all')]['new']
            lines.append(
                f"| {cp} | {metric} | {o['point'][metric]:.3f} "
                f"[{o['ci'][metric][0]:.3f}, {o['ci'][metric][1]:.3f}] | "
                f"{n['point'][metric]:.3f} "
                f"[{n['ci'][metric][0]:.3f}, {n['ci'][metric][1]:.3f}] |")
    lines += ['', '## MuSiQue answer equivalence (hand-checked by two '
              'readers, not author-validated)\n',
              'From `rebuttal/pilots/20261113_musique_equiv/report.md`. These '
              'cells cover the earlier 400-call Qwen-235B main table, not the '
              'Stage 2 population above; they are not applied to its AF '
              'column.\n',
              '| protocol | exact | check | delta |',
              '| --- | ---: | ---: | ---: |',
              '| summary_exchange | 19.0% | 53.0% | +34.0 |',
              '| random_relay | 24.0% | 49.0% | +25.0 |',
              '| score_ranked_relay | 28.0% | 53.0% | +25.0 |',
              '| redundancy_aware_relay | 24.0% | 50.0% | +26.0 |',
              '| **pooled** | **23.8%** | **51.2%** | **+27.4** |',
              '',
              'The check is confirmed by two hand-check readers, not by '
              'author labels; exact cells stay on record unchanged.\n',
              '## Reading\n',
              'The board rows are the validated comparison; extraction rows '
              'are exploratory and fidelity columns are unvalidated. The '
              'labeller and the matcher differ in both directions, so the '
              'redo reports both and does not replace the matcher column.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cells': {f'{cp}|{m}': {
        'old_af': cells[(cp, m)]['old']['point']['af'],
        'new_af': cells[(cp, m)]['new']['point']['af'],
        'old_cr': cells[(cp, m)]['old']['point']['cr'],
        'new_cr': cells[(cp, m)]['new']['point']['cr']}
        for (cp, m) in cells}, 'spent_usd': round(spend, 8)}, indent=1))


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