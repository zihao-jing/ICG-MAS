"""Full MuSiQue presence run for the main table (validated label, MuSiQue only).

Rule: `rebuttal/pilots/20261113_musique_presence_full/FULL_RULE.md`, frozen
before any call. All three main-table models, all four communication
protocols, both relay checkpoints; 100 instances per model. Old columns are
the frozen lexical rule; new columns are the V9 per-fact presence label
(Claude Haiku 5.5). Cap $5.00; every call logged.

    ./run.sh python -m scripts.musique_presence_full --build
    ./run.sh python -m scripts.musique_presence_full --run --cap-usd 5
    ./run.sh python -m scripts.musique_presence_full --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.compute_audit_metrics import align_gold_to_transmitted
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.per_fact_labeller import parse, render
from src.audit.critical_fact_validation import build_trace_packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_musique_presence_full'
RULE = OUT / 'FULL_RULE.md'
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
BOOT = 2000
PROTOCOLS = ['summary_exchange', 'random_relay', 'score_ranked_relay',
             'redundancy_aware_relay']
RUNS = {'qwen235b': 'results/run_qwen235b_musique',
        'mistrals': 'results/run_musique_mistrals',
        'qwen36f': 'results/run_musique_100'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = []
    for model, run in RUNS.items():
        for proto in PROTOCOLS:
            ps = build_trace_packages(dataset='musique', run_dir=run,
                                      protocol=proto, source_id=run,
                                      n_agents=None)
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
                        'model': model, 'run': run, 'protocol': proto,
                        'instance_id': p['instance_id'], 'checkpoint': cp,
                        'checkpoint_name': name, 'question': p['question'],
                        'facts': facts,
                        'entries': [{'unit_id': u['unit_id'],
                                     'agent_id': u['agent_id'],
                                     'text': u['text']}
                                    for u in p['checkpoints'][cp]],
                        'answer_correct': bool(p['answer_correct'])})
    rows.sort(key=lambda x: x['key'])
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'rows': len(rows), 'traces': len({(r['model'], r['protocol'],
                                          r['instance_id']) for r in rows}),
        'cap_usd': CAP, 'seed': SEED, 'model': HAIKU}, indent=1))
    print(json.dumps({'rows': len(rows),
                      'traces': len({(r['model'], r['protocol'],
                                     r['instance_id']) for r in rows}),
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
                     metadata={'pilot': 'musique_presence_full', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * PRICE_IN
        + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp


def run(cap, workers=6):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [r for r in rows if r['key'] not in done]
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
                                  ('key', 'model', 'run', 'protocol',
                                   'instance_id', 'checkpoint', 'facts',
                                   'answer_correct')}
                done[r['key']]['labeller'] = lab
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(), 6)}), flush=True)
    print(json.dumps({'calls': len(done), 'spent_usd': round(spent(), 8)},
                     indent=1))


def old_metrics(facts, entries):
    gold = [(f.get('support_id', f['fact_id']), f['text']) for f in facts]
    a = align_gold_to_transmitted(gold, [u['text'] for u in entries])
    n = len(a)
    covered = sum(1 for x in a if x['covered'])
    return {'cr': covered / n if n else 1.0,
            'complete': covered == n}


def boot_ci(clusters, metric):
    rng = random.Random(SEED)
    keys = sorted(clusters)
    vals = []
    for _ in range(BOOT):
        draw = []
        for _ in keys:
            draw += clusters[keys[rng.randrange(len(keys))]]
        v = metric(draw)
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]) \
        if vals else (float('nan'), float('nan'))


def report():
    pop = {r['key']: r for r in json.loads(POP.read_text())}
    items = json.loads(RESULTS.read_text())['items']
    spend = spent()
    cells = {}
    for r in items:
        if not r.get('labeller'):
            continue
        nf = len(r['facts'])
        carried = sum(1 for f in r['facts']
                      if r['labeller'].get(f['fact_id'], {}).get('status')
                      in ('present', 'partial'))
        old = old_metrics(r['facts'], pop[r['key']]['entries'])
        c = cells.setdefault((r['model'], r['protocol'], r['checkpoint']), {
            'traces': {}, 'old_facts': 0, 'new_facts': 0,
            'old_carry': 0, 'new_carry': 0})
        c['traces'][r['instance_id']] = {
            'old_complete': int(old['complete']),
            'new_complete': int(carried == nf),
            'wrong': int(not r['answer_correct']),
            'correct': int(r['answer_correct']),
            'nf': nf, 'old_cover': old['cr'] * nf, 'new_cover': carried}
        c['old_facts'] += nf
        c['new_facts'] += nf
        c['old_carry'] += old['cr'] * nf
        c['new_carry'] += carried

    lines = [
        '# Full MuSiQue presence run (main table, presence only)\n',
        f"Rule `FULL_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); prompt "
        f"`per_fact_prompt_v9.json` (sha256 `{file_sha(PROMPT)[:12]}`); "
        f"3 models x 100 instances x 4 protocols x checkpoints = {len(items)} "
        f"calls, spend ${spend:.6f}, cap $5.00. Stage: relay checkpoints. Old "
        f"= frozen lexical rule on the same traces; new = V9 per-fact "
        f"presence label (Claude Haiku 5.5), validated on MuSiQue only. "
        f"Fidelity/Dist is not redone here and stays unvalidated. **Every new "
        f"coverage cell below is central-claim presence: measured coverage and "
        f"critical recall are upper bounds, measured loss and omission are "
        f"lower bounds; not full sub-claim coverage.**\n",
        '| model | protocol | cp | n | CR old | CR new* | Om old | Om new* | complete old | complete new* | AF old | AF new* |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
        '', '* central-claim presence: CR is an upper bound, omission a '
        'lower bound.']
    for key in sorted(cells):
        c = cells[key]
        m, p, cp = key
        tr = c['traces']
        n = len(tr)
        old_cr = c['old_carry'] / c['old_facts'] if c['old_facts'] else 1.0
        new_cr = c['new_carry'] / c['new_facts'] if c['new_facts'] else 1.0
        old_comp = sum(x['old_complete'] for x in tr.values()) / n
        new_comp = sum(x['new_complete'] for x in tr.values()) / n
        old_af = sum(1 for x in tr.values()
                     if x['wrong'] and x['old_complete']) / n
        new_af = sum(1 for x in tr.values()
                     if x['wrong'] and x['new_complete']) / n
        lines.append(
            f"| {m} | {p} | {cp} | {n} | {old_cr:.3f} | {new_cr:.3f} | "
            f"{1-old_cr:.3f} | {1-new_cr:.3f} | {old_comp:.3f} | "
            f"{new_comp:.3f} | {old_af:.3f} | {new_af:.3f} |")
    # pooled per checkpoint with cluster-bootstrap CIs
    lines += ['', '## Pooled by checkpoint, 95% CIs (instance-cluster bootstrap, 2,000 draws)\n',
              'All new-column cells: central-claim presence; CR upper bound, omission '
              'lower bound.\n',
              '| cp | metric | old [95% CI] | new [95% CI] |',
              '| --- | --- | --- | --- |']
    for cp in ('extraction', 'board'):
        rows_cp = [r for r in items if r['checkpoint'] == cp
                   and r.get('labeller')]
        if not rows_cp:
            continue
        cl_old_cr = {}
        cl_new_cr = {}
        cl_old_comp = {}
        cl_new_comp = {}
        cl_old_af = {}
        cl_new_af = {}
        for r in rows_cp:
            inst = r['instance_id']
            nf = len(r['facts'])
            carried = sum(1 for f in r['facts']
                          if r['labeller'].get(f['fact_id'], {}).get('status')
                          in ('present', 'partial'))
            old = old_metrics(r['facts'], pop[r['key']]['entries'])
            cl_old_cr.setdefault(inst, []).append((round(old['cr'] * nf), nf))
            cl_new_cr.setdefault(inst, []).append((carried, nf))
            cl_old_comp.setdefault(inst, []).append(int(old['complete']))
            cl_new_comp.setdefault(inst, []).append(int(carried == nf))
            cl_old_af.setdefault(inst, []).append(
                int((not r['answer_correct']) and old['complete']))
            cl_new_af.setdefault(inst, []).append(
                int((not r['answer_correct']) and carried == nf))
        def ratio(d):
            n = sum(x[1] for x in d)
            return sum(x[0] for x in d) / n if n else 1.0
        def mean(d):
            return sum(d) / len(d) if d else float('nan')
        for name, a, b, fn in (
                ('CR', cl_old_cr, cl_new_cr, ratio),
                ('complete', cl_old_comp, cl_new_comp, mean),
                ('AF', cl_old_af, cl_new_af, mean)):
            oa = fn([x for v in a.values() for x in v]) if name == 'CR' \
                else fn([x for v in a.values() for x in v])
            na = fn([x for v in b.values() for x in v]) if name == 'CR' \
                else fn([x for v in b.values() for x in v])
            oci = boot_ci(a, fn)
            nci = boot_ci(b, fn)
            lines.append(f"| {cp} | {name} | {oa:.3f} [{oci[0]:.3f}, "
                         f"{oci[1]:.3f}] | {na:.3f} [{nci[0]:.3f}, "
                         f"{nci[1]:.3f}] |")
    # per-cell CIs (board and extraction) for CR, complete and AF
    lines += ['', '## Per-cell 95% CIs (instance-cluster bootstrap, 2,000 draws)\n',
              'All new-column cells: central-claim presence; CR upper bound, omission '
              'lower bound.\n',
              '| model | protocol | cp | CR old [CI] | CR new [CI] | complete old [CI] | complete new [CI] | AF old [CI] | AF new [CI] |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for key in sorted(cells):
        c = cells[key]
        m, p_, cp = key
        tr = c['traces']
        def cr_m(d):
            n = sum(x['nf'] for x in d)
            return sum(x['old_cover'] for x in d) / n if n else 1.0
        def cr_n(d):
            n = sum(x['nf'] for x in d)
            return sum(x['new_cover'] for x in d) / n if n else 1.0
        def mean_key(k):
            return lambda d: sum(x[k] for x in d) / len(d)
        def cellci(old_fn, new_fn, old_key=None, new_key=None):
            if old_key:
                ov = [old_fn(v) for v in tr.values()]
                nv = [new_fn(v) for v in tr.values()]
            else:
                ov = [old_fn(v) for v in tr.values()]
                nv = [new_fn(v) for v in tr.values()]
            o = sum(ov) / len(ov) if len(ov) else float('nan')
            n = sum(nv) / len(nv) if len(nv) else float('nan')
            return o, n
        # CR clusters are (cover, nf) tuples per trace
        old_cr = {i: [(x['old_cover'], x['nf'])] for i, x in tr.items()}
        new_cr = {i: [(x['new_cover'], x['nf'])] for i, x in tr.items()}
        def ratio(d):
            nn = sum(y[1] for y in d)
            return sum(y[0] for y in d) / nn if nn else 1.0
        oc = ratio([y for v in old_cr.values() for y in v])
        nc = ratio([y for v in new_cr.values() for y in v])
        oci = boot_ci(old_cr, ratio)
        nci = boot_ci(new_cr, ratio)
        oldc = {i: [x['old_complete']] for i, x in tr.items()}
        newc = {i: [x['new_complete']] for i, x in tr.items()}
        def mean(d):
            return sum(d) / len(d) if d else float('nan')
        ocomp = mean([y for v in oldc.values() for y in v])
        ncomp = mean([y for v in newc.values() for y in v])
        occi = boot_ci(oldc, mean)
        ncci = boot_ci(newc, mean)
        olda = {i: [x['wrong'] and x['old_complete']] for i, x in tr.items()}
        newa = {i: [x['wrong'] and x['new_complete']] for i, x in tr.items()}
        oaf = mean([int(y) for v in olda.values() for y in v])
        naf = mean([int(y) for v in newa.values() for y in v])
        oaci = boot_ci({i: [int(y) for y in v] for i, v in olda.items()}, mean)
        naci = boot_ci({i: [int(y) for y in v] for i, v in newa.items()}, mean)
        lines.append(
            f"| {m} | {p_} | {cp} | {oc:.3f} [{oci[0]:.3f}, {oci[1]:.3f}] | "
            f"{nc:.3f} [{nci[0]:.3f}, {nci[1]:.3f}] | "
            f"{ocomp:.3f} [{occi[0]:.3f}, {occi[1]:.3f}] | "
            f"{ncomp:.3f} [{ncci[0]:.3f}, {ncci[1]:.3f}] | "
            f"{oaf:.3f} [{oaci[0]:.3f}, {oaci[1]:.3f}] | "
            f"{naf:.3f} [{naci[0]:.3f}, {naci[1]:.3f}] |")
    lines += ['', 'No fidelity number is reported here. The Silo-Bench presence '
              'label was validated separately (report in '
              '`20261113_sb_presence_validation`); its rows are not part of this '
              'MuSiQue run. All coverage figures are **central-claim presence**, '
              'not full sub-claim coverage: the ceiling check found sub-claims '
              'missing in 10/10 checked cases.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cells': len(cells), 'calls': len(items),
                      'spend_usd': round(spend, 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'run', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.run:
        run(a.cap_usd, a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()