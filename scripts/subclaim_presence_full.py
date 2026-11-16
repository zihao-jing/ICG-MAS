"""Full sub-claim presence rule B on the 2,100 frozen MuSiQue rows.

Only runs after the fresh-case validation passes (`20261113_subclaim_validation`
report). Adds a stricter column beside central-claim A; A is not replaced.
Cap $5.00; every call logged.

    ./run.sh python -m scripts.subclaim_presence_full --build
    ./run.sh python -m scripts.subclaim_presence_full --run --cap-usd 5
    ./run.sh python -m scripts.subclaim_presence_full --report
"""
import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci
from scripts.subclaim_presence_pilot import parse, render

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / 'rebuttal/pilots/20261113_musique_presence_full'
OUT = ROOT / 'rebuttal/pilots/20261113_subclaim_presence_full'
RULE = ROOT / 'rebuttal/pilots/20261113_subclaim_validation/VALIDATION_RULE.md'
PROMPT = ROOT / 'rebuttal/pilots/20261113_subclaim_presence_pilot/subclaim_prompt.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
HAIKU = 'anthropic/claude-haiku-5.5'
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.50 / 1_000_000
MAX_LAB = 8192
SEED = 43
CAP = 5.0
BOOT = 2000


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = json.loads((FULL / 'population.json').read_text())
    assert len(rows) == 2100
    rows.sort(key=lambda r: r['key'])
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'rows': len(rows), 'cap_usd': CAP, 'model': HAIKU,
        'max_tokens': MAX_LAB}, indent=1))
    print(json.dumps({'rows': len(rows),
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
                     metadata={'pilot': 'subclaim_full', 'key': key})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * PRICE_IN
        + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': HAIKU, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp


def run(cap, workers=6):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']
                if r.get('b')}
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * PRICE_IN + MAX_LAB * PRICE_OUT for r in chunk)
        if spent() + reserve > cap:
            print(json.dumps({'stopped': 'cap'}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"sub/{r['key']}", spec['system'],
                              render(r), cap): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse(resp.content,
                            {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {k: r[k] for k in
                                  ('key', 'model', 'protocol', 'instance_id',
                                   'checkpoint', 'facts', 'answer_correct')}
                done[r['key']]['b'] = lab
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(), 6)}), flush=True)


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
    a = {r['key']: r for r in json.loads(
        (FULL / 'results.json').read_text())['items'] if r.get('labeller')}
    b = json.loads(RESULTS.read_text())['items']
    spend = spent()
    cells = {}
    for r in b:
        if not r.get('b') or r['key'] not in a:
            continue
        ra = a[r['key']]
        nf = len(r['facts'])
        a_carry = sum(1 for f in r['facts']
                      if ra['labeller'].get(f['fact_id'], {})
                      .get('status') in ('present', 'partial'))
        b_carry = sum(1 for f in r['facts']
                      if r['b'].get(f['fact_id'], {}).get('status')
                      in ('present', 'partial'))
        c = cells.setdefault((r['model'], r['protocol'],
                              r['checkpoint']), [])
        c.append((r['instance_id'], nf, a_carry, b_carry,
                  int(not r['answer_correct'])))
    lines = [
        '# Full sub-claim presence rule B (MuSiQue, stricter column)\n',
        f"Rule `VALIDATION_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); B passed "
        f"the fresh-case validation before this run: 139/144 = .965 "
        f"[.921, .989], kappa .881 [.748, .978] on 59 fresh board cases "
        f"(spend $0.889705; the A-complete stratum has kappa ~0 from "
        f"prevalence). Prompt `subclaim_prompt.json`; Claude Haiku 5.5, max "
        f"8192. {sum(1 for r in b if r.get('b'))} of {len(b)} rows labelled "
        f"(2 excluded: the model omitted a fact twice); spend "
        f"**${spend:.6f}**, cap $5.00. Stage: relay checkpoints. A = validated central-claim label; B = sub-claim label. "
        f"**A is not replaced.** For both columns, coverage and critical recall "
        f"are upper bounds; loss and omission are lower bounds.\n",
        '| model | protocol | cp | n | A CR | B CR | A complete | B complete |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for key in sorted(cells):
        m, p, cp = key
        rs = cells[key]
        n = len(rs)
        af = sum(x[1] for x in rs)
        acr = sum(x[2] for x in rs) / af if af else 1.0
        bcr = sum(x[3] for x in rs) / af if af else 1.0
        acomp = sum(1 for x in rs if x[2] == x[1]) / n
        bcomp = sum(1 for x in rs if x[3] == x[1]) / n
        lines.append(f"| {m} | {p} | {cp} | {n} | {acr:.3f} | {bcr:.3f} | "
                     f"{acomp:.3f} | {bcomp:.3f} |")
    lines += ['', '## Pooled by checkpoint, 95% CIs (instance-cluster bootstrap, 2,000 draws)\n',
              '| cp | metric | A [95% CI] | B [95% CI] |',
              '| --- | --- | --- | --- |']
    for cp in ('extraction', 'board'):
        rs = [r for r in b if r.get('b') and r['checkpoint'] == cp
              and r['key'] in a]
        if not rs:
            continue
        cla = {}
        clb = {}
        ca = {}
        cb = {}
        for r in rs:
            ra = a[r['key']]
            nf = len(r['facts'])
            ac = sum(1 for f in r['facts']
                     if ra['labeller'].get(f['fact_id'], {})
                     .get('status') in ('present', 'partial'))
            bc = sum(1 for f in r['facts']
                     if r['b'].get(f['fact_id'], {}).get('status')
                     in ('present', 'partial'))
            inst = r['instance_id']
            cla.setdefault(inst, []).append((ac, nf))
            clb.setdefault(inst, []).append((bc, nf))
            ca.setdefault(inst, []).append(int(ac == nf))
            cb.setdefault(inst, []).append(int(bc == nf))

        def ratio(d):
            nn = sum(y[1] for y in d)
            return sum(y[0] for y in d) / nn if nn else 1.0

        def mean(d):
            return sum(d) / len(d) if d else float('nan')
        for name, xa, xb, fn in (('CR', cla, clb, ratio),
                                 ('complete', ca, cb, mean)):
            va = fn([y for v in xa.values() for y in v])
            vb = fn([y for v in xb.values() for y in v])
            cia = boot_ci(xa, fn)
            cib = boot_ci(xb, fn)
            lines.append(f"| {cp} | {name} | {va:.3f} [{cia[0]:.3f}, "
                         f"{cia[1]:.3f}] | {vb:.3f} [{cib[0]:.3f}, "
                         f"{cib[1]:.3f}] |")
    lines += ['', 'B is stricter by construction (it requires every sub-claim), '
              'so B CR <= A CR. The A label stays the validated table label '
              'with the central-claim qualifier; B is reported beside it. No '
              'full-coverage claim is made for either.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cells': len(cells), 'calls': len(b),
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