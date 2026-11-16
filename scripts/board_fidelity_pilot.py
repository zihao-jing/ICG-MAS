"""Board strict-fidelity pilot: 150 rows, Opus 5.5, cap $5.

Rule: `rebuttal/pilots/20261114_board_fidelity_pilot/PILOT_RULE.md`, frozen
before any call. Uses the V10 strict-fidelity prompt and the parse of the
per-fact labeller.

    ./run.sh python -m scripts.board_fidelity_pilot --build
    ./run.sh python -m scripts.board_fidelity_pilot --run --cap-usd 5
    ./run.sh python -m scripts.board_fidelity_pilot --report
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
OUT = ROOT / 'rebuttal/pilots/20261114_board_fidelity_pilot'
RULE = OUT / 'PILOT_RULE.md'
PROMPT = ROOT / 'rebuttal/pilots/20261113_label_validation_v10/per_fact_prompt_v10.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
OPUS = 'anthropic/claude-opus-5.5'
PRICE_IN = 4.0 / 1_000_000
PRICE_OUT = 20.0 / 1_000_000
MAX_LAB = 2500
CAP = 5.0
SEED = 43
N_MQ = 75
N_SB = 75
FULL_BOARD_ROWS = 1824


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = [r for r in json.loads((SRC / 'population.json').read_text())
            if r['checkpoint'] == 'board']
    chosen = []
    for bench, n in (('musique', N_MQ), ('silobench', N_SB)):
        cand = [r for r in rows if r['dataset'] == bench]
        cand.sort(key=lambda r: sha('43|bfid|' + r['key']))
        # round-robin over (model, protocol) cells by hash order
        cells = {}
        for r in cand:
            cells.setdefault((r['model'], r['protocol']), []).append(r)
        keys = sorted(cells, key=lambda k: sha('43|bfidcell|' + '|'.join(k)))
        idx = {k: 0 for k in keys}
        picked = []
        while len(picked) < n:
            for k in keys:
                if len(picked) == n:
                    break
                i = idx[k]
                if i < len(cells[k]):
                    picked.append(cells[k][i])
                    idx[k] = i + 1
        chosen += picked
    assert len(chosen) == 150, len(chosen)
    chosen.sort(key=lambda r: r['key'])
    assert len({r['key'] for r in chosen}) == 150
    POP.write_text(json.dumps(chosen, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'rows': len(chosen),
        'benchmark': {b: sum(1 for r in chosen if r['dataset'] == b)
                      for b in ('musique', 'silobench')},
        'cells': len({(r['model'], r['protocol'], r['dataset'])
                      for r in chosen}),
        'model': OPUS, 'max_tokens': MAX_LAB, 'cap_usd': CAP,
        'full_board_rows': FULL_BOARD_ROWS}, indent=1))
    print(json.dumps({'rows': len(chosen),
                      'musique': sum(1 for r in chosen
                                     if r['dataset'] == 'musique'),
                      'silobench': sum(1 for r in chosen
                                       if r['dataset'] == 'silobench'),
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
                     metadata={'pilot': 'board_fidelity',
                               'key': key,
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


def run(cap, workers=4):
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
            futs = {ex.submit(call, f"bfid/{r['key']}", spec['system'],
                              render(r), cap): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse(resp.content,
                            {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {k: r[k] for k in
                                  ('key', 'model', 'dataset', 'protocol',
                                   'instance_id', 'checkpoint', 'facts',
                                   'answer_correct')}
                done[r['key']]['labeller'] = lab
        RESULTS.write_text(json.dumps({'items': list(done.values())},
                                      indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(), 6)}), flush=True)
    print(json.dumps({'calls': len(done), 'spent_usd': round(spent(), 8)},
                     indent=1))


def report():
    man = json.loads(MANIFEST.read_text())
    items = json.loads(RESULTS.read_text())['items']
    valid = [r for r in items if r.get('labeller')]
    spend = spent()
    per_case = spend / len(items) if items else 0.0
    calls = {}
    if CALLS.exists():
        calls = {json.loads(l)['key']: json.loads(l)
                 for l in CALLS.read_text().splitlines()
                 if l.strip() and json.loads(l).get('event') == 'result'}
    ds = {}
    for r in items:
        c = calls.get('bfid/' + r['key'])
        if c:
            a = ds.setdefault(r['dataset'], [0.0, 0])
            a[0] += c.get('cost_usd', 0.0)
            a[1] += 1
    rows_ds = {'musique': 1200, 'silobench': 624}
    proj = sum(ds[d][0] / ds[d][1] * rows_ds[d] for d in ds if ds[d][1])
    counts = {'faithful': 0, 'partial': 0, 'distorted': 0, 'absent': 0}
    nfact = 0
    for r in valid:
        for f in r['facts']:
            x = r['labeller'].get(f['fact_id'])
            if x:
                counts[x['fidelity']] = counts.get(x['fidelity'], 0) + 1
                nfact += 1
    lines = [
        '# Board strict-fidelity pilot\n',
        f"Rule `PILOT_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); prompt "
        f"`per_fact_prompt_v10.json` (sha256 `{file_sha(PROMPT)[:12]}`); "
        f"Claude Opus 5.5, max 2500, reasoning enabled. Pilot stopped at "
        f"{len(items)} of 150 sampled rows"
        f" ({'cap' if len(items) < 150 else 'all sampled'}); {len(valid)} "
        f"parsed, {nfact} fact labels; spend "
        f"**${spend:.6f}**, cap $5.00. Stage: shared board.\n",
        f"Price per case **${per_case:.6f}**; projection for all "
        f"{FULL_BOARD_ROWS} board rows **${proj:.2f}**, which is **above the "
        f"approved ~$32** (per-benchmark: MuSiQue 1,200 rows "
        f"~${ds['musique'][0] / ds['musique'][1] * 1200 if 'musique' in ds else 0:.2f}, "
        f"Silo-Bench 624 rows "
        f"~${ds['silobench'][0] / ds['silobench'][1] * 624 if 'silobench' in ds else 0:.2f}). "
        f"The full run is not started; stages would be at most $5 each.\n",
        '| fidelity | facts |', '| --- | ---: |']
    for k in ('faithful', 'partial', 'distorted', 'absent'):
        lines.append(f"| {k} | {counts.get(k, 0)} |")
    lines += ['', '## Validation record carried into this pilot\n',
              '- Natural board cases (V10): **158/163 = .969 [.930, .990]**, '
              'kappa **.721 [.429, .930]**.',
              '- Constructed distortions, all 37: **.946 [.818, .993]**, '
              'kappa **.641**; the constructed interval is **wide**.',
              '- The secondary "distorted vs not" label on constructed cases '
              'is **.865**, kappa **.467**, and **Dist stays unvalidated**.',
              '', 'The pilot adds no new validation claim. The full board run '
              'starts only after review; every fidelity cell will carry the '
              'natural-case kappa and the unvalidated-Dist caveat. Coverage '
              'and critical recall remain upper bounds, loss and omission '
              'lower bounds wherever presence labels are reported.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'parsed': len(valid), 'of': len(items),
                      'per_case_usd': round(per_case, 6),
                      'projected_usd': round(proj, 2),
                      'spend_usd': round(spend, 6),
                      'fidelity': counts}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'run', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--cap-usd', type=float, default=CAP)
    ap.add_argument('--workers', type=int, default=4)
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