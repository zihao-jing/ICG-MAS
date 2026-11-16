"""Piece 2 pilot: presence-based main-table columns with the validated label.

Rule: `rebuttal/pilots/20261113_main_table_presence/PILOT_RULE.md`, frozen
before any call. Models, benchmarks and protocols from the paper's main table
(`tab:audit_combined.tex`). Old columns are the frozen lexical rule recomputed
on the same traces; new columns are the V9 per-fact presence labels (Claude
Haiku 5.5). The fidelity column is not redone here.

    ./run.sh python -m scripts.main_table_presence_redo --build
    ./run.sh python -m scripts.main_table_presence_redo --pilot --cap-usd 5
    ./run.sh python -m scripts.main_table_presence_redo --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_labeller import MAX_TOKENS, parse, render
from scripts.answer_equiv import last_object
from src.audit.critical_fact_validation import build_trace_packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_main_table_presence'
RULE = OUT / 'PILOT_RULE.md'
PROMPT = ROOT / 'rebuttal/pilots/20261113_label_validation_v9/per_fact_prompt_v9.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.50 / 1_000_000
MAX_LAB = 4096
SEED = 43
CAP = 5.0
PILOT_PER_GROUP = 2
PROTOCOLS = ['summary_exchange', 'random_relay', 'score_ranked_relay',
             'redundancy_aware_relay']
RUNS = {
    'qwen235b': [('silobench', 'results/run_qwen235b_n5', 5),
                 ('silobench', 'results/run_qwen235b_n10', 10),
                 ('musique', 'results/run_qwen235b_musique', None)],
    'mistrals': [('silobench', 'results/run_mistrals', 5),
                 ('silobench', 'results/run_mistrals_n10', 10),
                 ('musique', 'results/run_musique_mistrals', None)],
    'qwen36f': [('silobench', 'results/run_20260523_214416', 5),
                ('silobench', 'results/run_silobench_n10', 10),
                ('musique', 'results/run_musique_100', None)],
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = []
    for model, specs in RUNS.items():
        for dataset, run, n_agents in specs:
            for proto in PROTOCOLS:
                ps = build_trace_packages(
                    dataset=dataset, run_dir=run, protocol=proto,
                    source_id=run, n_agents=n_agents)
                for p in ps:
                    facts = [{'fact_id': f'f{i+1}', 'text': s['text'],
                              'support_id': s['support_id']}
                             for i, s in enumerate(p['source_supports'])]
                    for cp, name in (('extraction', 'extraction pool'),
                                     ('board', 'shared board')):
                        if cp not in p['checkpoints']:
                            continue
                        rows.append({
                            'key': f'{model}|{run}|{proto}|{p["instance_id"]}|{cp}',
                            'model': model, 'run': run, 'dataset': dataset,
                            'n_agents': n_agents, 'protocol': proto,
                            'instance_id': p['instance_id'], 'checkpoint': cp,
                            'checkpoint_name': name, 'question': p['question'],
                            'facts': facts,
                            'entries': [{'unit_id': u['unit_id'],
                                         'agent_id': u['agent_id'],
                                         'text': u['text']}
                                        for u in p['checkpoints'][cp]],
                            'answer_correct': bool(p['answer_correct'])})
    rows.sort(key=lambda x: x['key'])
    # pilot: two instances per (model, dataset, n_agents)
    groups = {}
    for r in rows:
        groups.setdefault((r['model'], r['dataset'], r['n_agents']),
                          set()).add(r['instance_id'])
    pilot_ids = {}
    for g, ids in groups.items():
        pilot_ids[g] = sorted(ids, key=lambda i: sha(f'43|pres|{i}'))[
            :PILOT_PER_GROUP]
    pilot = [r['key'] for r in rows
             if r['instance_id'] in pilot_ids[
                 (r['model'], r['dataset'], r['n_agents'])]]
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'prompt_system_sha256': sha(json.loads(PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP),
        'rows': len(rows), 'traces': len({(r['model'], r['run'],
                                          r['protocol'], r['instance_id'])
                                          for r in rows}),
        'pilot_calls': len(pilot), 'pilot_cap_usd': CAP,
        'pilot_per_group': PILOT_PER_GROUP, 'seed': SEED,
        'model': HAIKU, 'pilot_keys': sorted(pilot)}, indent=1))
    print(json.dumps({'rows': len(rows), 'pilot_calls': len(pilot),
                      'groups': len(groups),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, system, user, cap):
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_LAB * PRICE_OUT
    if spent() + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None
    cid = sha('|'.join([key, HAIKU, system, user, str(MAX_LAB)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_LAB,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=HAIKU,
                     max_tokens=MAX_LAB, temperature=0,
                     metadata={'pilot': 'main_table_presence', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp


def pilot(cap, workers=6):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = {r['key']: r for r in json.loads(POP.read_text())}
    keys = man['pilot_keys']
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [rows[k] for k in keys if k not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * PRICE_IN + MAX_LAB * PRICE_OUT for r in chunk)
        if spent() + reserve > cap:
            print(json.dumps({'stopped': 'cap'}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"pres/{r['key']}", spec['system'],
                              render(r), cap): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse(resp.content,
                            {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {k: r[k] for k in
                                  ('key', 'model', 'run', 'dataset',
                                   'n_agents', 'protocol', 'instance_id',
                                   'checkpoint', 'facts', 'answer_correct')}
                done[r['key']]['labeller'] = lab
        RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(keys),
                          'spent_usd': round(spent(), 6)}), flush=True)
    print(json.dumps({'calls': len(done), 'spent_usd': round(spent(), 8)},
                     indent=1))


def old_metrics(r, facts, entries):
    gold = [(f.get('support_id', f['fact_id']), f['text']) for f in facts]
    trans = [u['text'] for u in entries]
    a = align_gold_to_transmitted(gold, trans)
    n = len(a)
    covered = sum(1 for x in a if x['covered'])
    cr = covered / n if n else 1.0
    return {'cr': cr, 'om': 1 - cr, 'complete': covered == n}


def report():
    items = json.loads(RESULTS.read_text())['items']
    pop = {r['key']: r for r in json.loads(POP.read_text())}
    ncalls = sum(1 for l in CALLS.read_text().splitlines()
                 if l.strip() and json.loads(l).get('event') == 'result')
    spend = spent()
    cells = {}
    for r in items:
        if not r.get('labeller'):
            continue
        cp = r['checkpoint']
        carried = sum(1 for f in r['facts']
                      if r['labeller'].get(f['fact_id'], {}).get('status')
                      in ('present', 'partial'))
        n = len(r['facts'])
        cr = carried / n if n else 1.0
        old = old_metrics(r, r['facts'], pop[r['key']]['entries'])
        key = (r['model'], r['dataset'], r['protocol'], cp)
        c = cells.setdefault(key, {'n': 0, 'old_cr': 0.0, 'new_cr': 0.0,
                                   'old_complete': 0, 'new_complete': 0,
                                   'wrong': 0, 'old_af': 0, 'new_af': 0})
        c['n'] += 1
        c['old_cr'] += old['cr']
        c['new_cr'] += cr
        c['old_complete'] += int(old['complete'])
        c['new_complete'] += int(carried == n)
        if not r['answer_correct']:
            c['wrong'] += 1
            c['old_af'] += int(old['complete'])
            c['new_af'] += int(carried == n)
    lines = [
        '# Piece 2 pilot: presence-based main-table columns\n',
        f"Rule `PILOT_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); prompt "
        f"`per_fact_prompt_v9.json` (sha256 `{file_sha(PROMPT)[:12]}`); "
        f"{len(items)} pilot calls, spend ${spend:.6f}, cap $5.00. Stage: "
        f"relay checkpoints (extraction and board). New labels are the V9 "
        f"per-fact presence label (Claude Haiku 5.5); old labels are the "
        f"frozen lexical rule on the same traces. Fidelity is **not** redone "
        f"here and is marked unvalidated.\n",
        '| model | benchmark | protocol | cp | n | CR old | CR new | Om old | Om new | complete old | complete new | AF old | AF new |',
        '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key in sorted(cells):
        c = cells[key]
        m, d, p, cp = key
        lines.append(
            f"| {m} | {d} | {p} | {cp} | {c['n']} | "
            f"{c['old_cr']/c['n']:.3f} | {c['new_cr']/c['n']:.3f} | "
            f"{1-c['old_cr']/c['n']:.3f} | {1-c['new_cr']/c['n']:.3f} | "
            f"{c['old_complete']/c['n']:.3f} | {c['new_complete']/c['n']:.3f} | "
            f"{c['old_af']/c['n']:.3f} | {c['new_af']/c['n']:.3f} |")
    lines += ['', '## Full-run estimate\n',
              f"Scored pilot cases: {len(items)}; logged calls: {ncalls} (64 were "
              f"retried after a 2000-token truncation; max_tokens raised to "
              f"4096 for the scored run). Full run: 3 models x (52 Silo-Bench "
              f"+ 100 MuSiQue) traces x (3 relay protocols x 2 checkpoints "
              f"+ summary exchange x 1 board checkpoint) = 3,192 calls. At "
              f"the pilot cost per call "
              f"(${spend/max(ncalls,1):.6f} over all logged calls), estimated full "
              f"cost **${spend/max(ncalls,1)*3192:.2f}**; the estimate may "
              f"rise with 4096-token outputs, so the proposed cap is "
              f"**$5.00 per stage**. No full run starts without approval.\n"]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cells': len(cells), 'calls': len(items),
                      'spend': round(spend, 6),
                      'full_estimate_usd': round(
                          spend / max(ncalls, 1) * 3192, 3)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'pilot', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd, a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()