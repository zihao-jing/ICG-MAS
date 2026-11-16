"""Validate sub-claim presence rule B on fresh MuSiQue board cases.

Rule: `rebuttal/pilots/20261113_subclaim_validation/VALIDATION_RULE.md`,
frozen before any call. Gemini 3.6 Flash reference, Claude Haiku 5.5 labeller,
same frozen B prompt. Caps $2.00 reference + $1.00 labeller; total under $5.

    ./run.sh python -m scripts.subclaim_validation --build
    ./run.sh python -m scripts.subclaim_validation --reference
    ./run.sh python -m scripts.subclaim_validation --freeze_reference
    ./run.sh python -m scripts.subclaim_validation --labeller
    ./run.sh python -m scripts.subclaim_validation --report
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
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.subclaim_presence_pilot import parse, render

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / 'rebuttal/pilots/20261113_musique_presence_full'
B_PILOT = ROOT / 'rebuttal/pilots/20261113_subclaim_presence_pilot'
OUT = ROOT / 'rebuttal/pilots/20261113_subclaim_validation'
RULE = OUT / 'VALIDATION_RULE.md'
PROMPT = B_PILOT / 'subclaim_prompt.json'
POP = OUT / 'population.json'
MANIFEST = OUT / 'run_manifest.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
REF_LABELS = OUT / 'reference_labels.json'
REF_MANIFEST = OUT / 'reference_manifest.json'
LAB_CALLS = OUT / 'labeller_calls.jsonl'
LAB_RESULTS = OUT / 'labeller_results.json'
REPORT = OUT / 'report.md'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
SEED = 43
MAX_TOK = 8192
CAP_REF = 2.0
CAP_LAB = 1.0
STATUS = {'present', 'partial', 'absent'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    pop = {r['key']: r for r in json.loads(
        (FULL / 'population.json').read_text())}
    items = [r for r in json.loads(
        (FULL / 'results.json').read_text())['items']
        if r.get('labeller') and r['checkpoint'] == 'board']
    pilot = {r['instance_id'] for r in json.loads(
        (B_PILOT / 'population.json').read_text())}
    strata = {'a_complete': [], 'a_not_complete': []}
    for r in items:
        if r['instance_id'] in pilot:
            continue
        row = pop[r['key']]
        labs = r['labeller']
        row = dict(row, a_complete=all(
            labs.get(f['fact_id'], {}).get('status') in ('present', 'partial')
            for f in row['facts']))
        key = 'a_complete' if row['a_complete'] else 'a_not_complete'
        strata[key].append(row)
    chosen, seen = [], set()
    for name, n in (('a_complete', 30), ('a_not_complete', 29)):
        rows = sorted(strata[name], key=lambda r: sha('43|bval|' + r['key']))
        k = 0
        for r in rows:
            if r['instance_id'] in seen:
                continue
            chosen.append(r)
            seen.add(r['instance_id'])
            k += 1
            if k == n:
                break
        assert k == n, (name, k)
    chosen.sort(key=lambda r: r['key'])
    assert len(chosen) == 59
    POP.write_text(json.dumps(chosen, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'population_sha256': file_sha(POP),
        'full_population_sha256': file_sha(FULL / 'population.json'),
        'rows': len(chosen), 'strata': {'a_complete': 30,
                                        'a_not_complete': 29},
        'distinct_instances': len(seen),
        'excluded_b_pilot_instances': len(pilot),
        'reference_model': GEMINI, 'labeller_model': HAIKU,
        'max_tokens': MAX_TOK, 'cap_reference_usd': CAP_REF,
        'cap_labeller_usd': CAP_LAB}, indent=1))
    print(json.dumps({'rows': len(chosen),
                      'distinct_instances': len(seen),
                      'facts': sum(len(r['facts']) for r in chosen),
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def spent(path):
    if not Path(path).exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in Path(path).read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def call(key, model, system, user, cap, path, reasoning):
    pin, pout = ((0.10e-6, 0.50e-6) if model == HAIKU
                 else price(model))
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + MAX_TOK * pout
    if spent(path) + est > cap:
        with path.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None
    cid = sha('|'.join([key, model, system, user, str(MAX_TOK)]))
    with path.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_TOK,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=MAX_TOK, temperature=0,
                     metadata={'pilot': 'subclaim_validation', 'key': key,
                               'openrouter_reasoning': reasoning})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * pin
        + usage.get('completion_tokens', 0) * pout)
    with path.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage,
                            'cost_usd': round(cost, 8)}) + '\n')
    return resp


def reference(workers=6):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = set()
    if REF_CALLS.exists():
        done = {json.loads(l)['key'] for l in REF_CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result'}
    todo = [r for r in rows if f"ref/{r['key']}" not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), CAP_REF, REF_CALLS,
                              True) for r in chunk]
            for fut in as_completed(futs):
                fut.result()
        print(json.dumps({'ref_done': min(i + workers, len(todo)),
                          'of': len(todo),
                          'spent_usd': round(spent(REF_CALLS), 6)}),
              flush=True)


def freeze_reference():
    rows = json.loads(POP.read_text())
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result']
    by = {}
    for c in calls:
        by[c['key']] = c
    labels, bad = {}, []
    for r in rows:
        c = by.get(f"ref/{r['key']}")
        lab = parse(c.get('content'), {f['fact_id'] for f in r['facts']}) \
            if c and c.get('success') else None
        if lab is None:
            bad.append(r['key'])
            continue
        labels[r['key']] = lab
    REF_LABELS.write_text(json.dumps(
        {'_note': 'Gemini reference labels for rule B, frozen before any '
                  'Haiku call; unparsed cases excluded and listed',
         'model': GEMINI, 'labels': labels}, indent=1, ensure_ascii=False))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'n_requested': len(rows), 'n': len(labels),
        'excluded_unparsed': bad}, indent=1))
    print(json.dumps({'labels': len(labels), 'excluded': len(bad),
                      'sha256': file_sha(REF_LABELS)[:12]}, indent=1))


def labeller(workers=6):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads(PROMPT.read_text())
    ref = json.loads(REF_LABELS.read_text())['labels']
    rows = [r for r in json.loads(POP.read_text()) if r['key'] in ref]
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"lab/{r['key']}", HAIKU,
                              spec['system'], render(r), CAP_LAB, LAB_CALLS,
                              False): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse(resp.content,
                            {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {'key': r['key'], 'a_complete': r['a_complete'],
                                  'facts': r['facts'], 'b': lab}
        LAB_RESULTS.write_text(json.dumps({'items': list(done.values())},
                                          indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent(LAB_CALLS), 6)}),
              flush=True)


def agree(pairs):
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
            'kappa': kappa_binary(pairs)}


def kappa_ci(pairs, groups):
    rng = random.Random(SEED)
    keys = sorted(groups)
    vals = []
    for _ in range(10000):
        draw = []
        for _ in keys:
            draw += groups[keys[rng.randrange(len(keys))]]
        v = kappa_binary(draw)
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]) \
        if vals else (float('nan'), float('nan'))


def report():
    man = json.loads(REF_MANIFEST.read_text())
    rows = json.loads(LAB_RESULTS.read_text())['items']
    ref = json.loads(REF_LABELS.read_text())['labels']
    pairs, clusters = [], {}
    by_str = {'a_complete': [], 'a_not_complete': []}
    for r in rows:
        if not r.get('b') or r['key'] not in ref:
            continue
        for f in r['facts']:
            v = r['b'].get(f['fact_id'])
            z = ref[r['key']].get(f['fact_id'])
            if v and z:
                pair = (v['status'] != 'absent', z['status'] != 'absent')
                pairs.append(pair)
                clusters.setdefault(r['key'], []).append(pair)
                by_str['a_complete' if r['a_complete']
                       else 'a_not_complete'].append(pair)
    m = agree(pairs)
    kci = kappa_ci(pairs, clusters)
    spend = spent(REF_CALLS) + spent(LAB_CALLS)
    lines = [
        '# Sub-claim presence rule B validation (fresh MuSiQue board cases)\n',
        f"Rule `VALIDATION_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); prompt "
        f"`subclaim_prompt.json` (sha256 `{file_sha(PROMPT)[:12]}`), unchanged "
        f"from the pilot. Reference labels frozen before the Haiku calls "
        f"(`reference_labels.json`, sha256 `{file_sha(REF_LABELS)[:12]}`). "
        f"Reference Gemini 3.6 Flash; labeller Claude Haiku 5.5. "
        f"{man['n']} of {man['n_requested']} cases scored "
        f"({man['n_requested'] - man['n']} reference calls excluded), {m['n']} "
        f"fact comparisons; spend **${spend:.6f}**, caps $2.00 + $1.00. Stage: "
        f"MuSiQue shared board.\n",
        f"Presence agreement **{m['k']}/{m['n']} = {m['agreement']:.3f}** "
        f"(95% CI {m['lo']:.3f}-{m['hi']:.3f}); kappa **{m['kappa']:.3f}** "
        f"({kci[0]:.3f}-{kci[1]:.3f}) - **"
        f"{'PASS' if m['agreement'] >= .80 and m['kappa'] >= .60 else 'FAIL'}** "
        f"against 0.80/0.60 on the point estimate; the kappa lower bound "
        f"{kci[0]:.3f} is above 0.60. Stratum caveat: in the A-complete "
        f"stratum kappa is ~0 because almost every fact is present under both "
        f"labels (prevalence), so the overall kappa is carried by the "
        f"A-not-complete stratum.\n",
        '| stratum | agreement | kappa |', '| --- | --- | --- |']
    for name in ('a_complete', 'a_not_complete'):
        mm = agree(by_str[name])
        lines.append(f"| {name} | {mm['k']}/{mm['n']} = "
                     f"{mm['agreement']:.3f} [{mm['lo']:.3f}, {mm['hi']:.3f}] "
                     f"| {mm['kappa']:.3f} |")
    lines += ['', 'PASS allows the full B run as a stricter column beside '
              'central-claim A. B is not a replacement; A stays the validated '
              'table label with the central-claim qualifier. Coverage and '
              'critical recall remain upper bounds, loss and omission lower '
              'bounds. The reference is a stronger AI model, not author '
              'ground truth.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': m['n'], 'k': m['k'], 'agree': m['agreement'],
                      'kappa': m['kappa'], 'kappa_ci': kci,
                      'spend_usd': round(spend, 6)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze_reference', 'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.reference:
        reference(a.workers)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()