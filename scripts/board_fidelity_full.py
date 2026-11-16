"""Board strict-fidelity full run, staged at $5 per invocation.

Population: all 1,824 board rows in the frozen piece-2 population. The 150-row
pilot (`20261114_board_fidelity_pilot`) is reused for the same keys; the label,
model and prompt are identical. Each invocation of `--run --cap-usd 5` spends
at most $5; the driver repeats until the population is labelled or no progress
is made. Natural-case kappa and the wide constructed interval are reported;
Dist stays unvalidated.

    ./run.sh python -m scripts.board_fidelity_full --build
    ./run.sh python -m scripts.board_fidelity_full --run --cap-usd 5
    ./run.sh python -m scripts.board_fidelity_full --report
"""
import argparse
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.per_fact_labeller import parse, render

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261113_main_table_presence'
PILOT = ROOT / 'rebuttal/pilots/20261114_board_fidelity_pilot'
OUT = ROOT / 'rebuttal/pilots/20261114_board_fidelity_full'
PROMPT = ROOT / 'rebuttal/pilots/20261113_label_validation_v10/per_fact_prompt_v10.json'
RULE = OUT / 'RUN_RULE.md'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
OPUS = 'anthropic/claude-opus-5.5'
PRICE_IN = 4.0 / 1_000_000
PRICE_OUT = 20.0 / 1_000_000
MAX_LAB = 2500
SEED = 43
MAX_ATTEMPTS = 3
ROWS = 1824


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = [r for r in json.loads((SRC / 'population.json').read_text())
            if r['checkpoint'] == 'board']
    assert len(rows) == ROWS, len(rows)
    rows.sort(key=lambda r: r['key'])
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    pilot = {}
    pfile = PILOT / 'results.json'
    if pfile.exists():
        for r in json.loads(pfile.read_text())['items']:
            if r.get('labeller'):
                pilot[r['key']] = r
    seeded = [r for r in rows if r['key'] in pilot]
    out = []
    for r in seeded:
        p = pilot[r['key']]
        out.append({k: r[k] for k in ('key', 'model', 'dataset', 'protocol',
                                      'instance_id', 'checkpoint', 'facts',
                                      'answer_correct')} | {
                         'labeller': p['labeller'], 'attempts': 1,
                         'from_pilot': True})
    if out and not RESULTS.exists():
        RESULTS.write_text(json.dumps({'items': out}, indent=1,
                                      ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_full_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'rows': len(rows), 'seeded_from_pilot': len(out),
        'model': OPUS, 'max_tokens': MAX_LAB, 'stage_cap_usd': 5.0,
        'max_attempts': MAX_ATTEMPTS,
        'natural_kappa': [0.721, 0.429, 0.930],
        'constructed_kappa': 0.641,
        'dist_constructed_kappa': 0.467,
        'dist_status': 'unvalidated'}, indent=1))
    print(json.dumps({'rows': len(rows), 'seeded': len(out),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, system, user):
    est_in = math.ceil((len(system) + len(user)) / 4)
    cid = sha('|'.join([key, OPUS, system, user, str(MAX_LAB)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': OPUS, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_LAB,
                            'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=OPUS,
                     max_tokens=MAX_LAB, temperature=0,
                     metadata={'pilot': 'board_fidelity_full', 'key': key,
                               'openrouter_reasoning': True})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * PRICE_IN
        + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': OPUS, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp


def run(stage_cap, workers=16):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if RESULTS.exists():
        for r in json.loads(RESULTS.read_text())['items']:
            if r.get('labeller') or r.get('attempts', 0) >= MAX_ATTEMPTS:
                done[r['key']] = r
    todo = [r for r in rows if r['key'] not in done]
    base = spent()
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * PRICE_IN + MAX_LAB * PRICE_OUT for r in chunk)
        if spent() - base + reserve > stage_cap:
            print(json.dumps({'stopped': 'stage_cap',
                              'stage_spent_usd': round(spent() - base, 6)}),
                  flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"bfid/{r['key']}", spec['system'],
                              render(r)): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse(resp.content,
                            {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                prev = done.get(r['key'])
                attempts = (prev.get('attempts', 0) if prev else 0) + 1
                done[r['key']] = {k: r[k] for k in
                                  ('key', 'model', 'dataset', 'protocol',
                                   'instance_id', 'checkpoint', 'facts',
                                   'answer_correct')}
                done[r['key']]['labeller'] = lab
                done[r['key']]['attempts'] = attempts
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'stage_spent_usd': round(spent() - base, 6),
                          'total_spent_usd': round(spent(), 6)}), flush=True)
    print(json.dumps({'done': len(done), 'of': len(rows),
                      'stage_spent_usd': round(spent() - base, 6),
                      'total_spent_usd': round(spent(), 8)}, indent=1))


def report():
    man = json.loads(MANIFEST.read_text())
    items = json.loads(RESULTS.read_text())['items']
    valid = [r for r in items if r.get('labeller')]
    spend = spent()
    fact_total = {'faithful': 0, 'partial': 0, 'distorted': 0, 'absent': 0}
    nfact = 0
    for r in valid:
        for f in r['facts']:
            x = r['labeller'].get(f['fact_id'])
            if x:
                fact_total[x['fidelity']] = fact_total.get(x['fidelity'], 0) + 1
                nfact += 1
    by = {}
    for r in valid:
        cell = (r['dataset'], r['model'], r['protocol'])
        a = by.setdefault(cell, {'rows': 0, 'faithful': 0, 'facts': 0})
        a['rows'] += 1
        for f in r['facts']:
            x = r['labeller'].get(f['fact_id'])
            if x:
                a['facts'] += 1
                a['faithful'] += int(x['fidelity'] == 'faithful')
    lines = [
        '# Board strict-fidelity full run\n',
        f"Rule `RUN_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); prompt "
        f"`per_fact_prompt_v10.json` (sha256 `{file_sha(PROMPT)[:12]}`); "
        f"Claude Opus 5.5, max 2500, reasoning. {len(valid)} of {len(items)} "
        f"rows labelled "
        f"({sum(1 for r in items if not r.get('labeller'))} excluded after "
        f"{MAX_ATTEMPTS} attempts); {nfact} fact labels; spend "
        f"**${spend:.6f}**, staged at $5 per invocation. Stage: shared board.\n",
        f"Pre-run projection was **$43.92** (MuSiQue $21.59, Silo-Bench "
        f"$22.34). Full-run spend is **${spend:.6f}**; with the pilot's "
        f"$4.033836 the total is **${spend + 4.033836:.6f}**, "
        f"{'within' if spend + 4.033836 <= 50 else 'ABOVE'} the $50 stop "
        f"line.\n",
        '| fidelity | facts |', '| --- | ---: |']
    for k in ('faithful', 'partial', 'distorted', 'absent'):
        lines.append(f"| {k} | {fact_total.get(k, 0)} |")
    lines += ['', '## Faithful rate by cell\n',
              '| benchmark | model | protocol | rows | facts | faithful | rate |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for cell in sorted(by):
        d, m, p = cell
        a = by[cell]
        rate = a['faithful'] / a['facts'] if a['facts'] else 0.0
        lines.append(f"| {d} | {m} | {p} | {a['rows']} | {a['facts']} | "
                     f"{a['faithful']} | {rate:.3f} |")
    lines += ['', '## Validation caveats\n',
              '- Natural board cases (V10): **158/163 = .969 [.930, .990]**, '
              'kappa **.721 [.429, .930]**.',
              '- Constructed distortions, all 37: **.946 [.818, .993]**, '
              'kappa **.641**; the constructed interval is **wide**.',
              '- Secondary "distorted vs not" on constructed cases: **.865**, '
              'kappa **.467**; **Dist stays unvalidated**.',
              '', 'Every fidelity cell carries these caveats: the label is '
              'validated on natural board cases at kappa .721 [.429, .930], '
              'the constructed interval is wide, and Dist is unvalidated. '
              'Coverage/CR remain upper bounds, loss/omission lower bounds '
              'where presence is reported.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'labelled': len(valid), 'of': len(items),
                      'facts': nfact, 'fidelity': fact_total,
                      'spend_usd': round(spend, 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'run', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=5.0)
    ap.add_argument('--workers', type=int, default=16)
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