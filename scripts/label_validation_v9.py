"""V9: revalidate presence and fidelity with the boundary procedure in both prompts.

Rule: `rebuttal/pilots/20261113_label_validation_v9/LABEL_RULE_V9.md`, frozen
before any call. Reference Gemini 3.6 Flash applies the labeller prompt v4
verbatim; labels are frozen before the Claude Haiku 5.5 calls. 60 fresh
MuSiQue instances x 2 checkpoints.

    ./run.sh python -m scripts.label_validation_v9 --build
    ./run.sh python -m scripts.label_validation_v9 --reference --cap-usd 2
    ./run.sh python -m scripts.label_validation_v9 --freeze-reference
    ./run.sh python -m scripts.label_validation_v9 --labeller --cap-usd 0.5
    ./run.sh python -m scripts.label_validation_v9 --report
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
from scripts.per_fact_labeller import MAX_TOKENS, parse as parse_lab
from scripts.per_fact_labeller import render
from scripts.run_e1_anchor_matcher import anchor_ids
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_label_validation_v9'
RUN_V5 = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RUN_V6 = ROOT / 'rebuttal/pilots/20261113_label_validation_v6'
RUN_V7 = ROOT / 'rebuttal/pilots/20261113_label_validation_v7'
RUN_V8 = ROOT / 'rebuttal/pilots/20261113_label_validation_v8'
RULE = OUT / 'LABEL_RULE_V9.md'
PROMPT = OUT / 'v9_reference_prompt.json'
POP = OUT / 'population_v9.json'
BUILD = OUT / 'v9_build_manifest.json'
REF_MANIFEST = OUT / 'v9_reference_manifest.json'
REF_LABELS = OUT / 'reference_labels_v9.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
LAB_CALLS = OUT / 'calls_v9.jsonl'
LAB_RESULTS = OUT / 'results_v9.json'
REPORT = OUT / 'v9_report.md'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
SEED = 43
N = 60
MAX_REF = 8192
CAP_REF = 2.0
CAP_LAB = 0.5
STATUS = {'present', 'partial', 'absent'}
FID = {'faithful', 'partial', 'distorted', 'absent'}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    recs = {}
    for p in sorted(MATCHER_DIR.glob('*.json')):
        r = json.loads(p.read_text())
        if r.get('status') != 'ok':
            continue
        recs[(r['model'], r['instance_id'])] = r
    pk = {m: packages(m) for m in MODELS}
    v5 = {r['instance_id'] for r in
          json.loads((RUN_V5 / 'population_v5.json').read_text())}
    v6 = {r['instance_id'] for r in
          json.loads((RUN_V6 / 'population_v6.json').read_text())}
    v7 = {r['instance_id'] for r in
          json.loads((RUN_V7 / 'population_v7.json').read_text())}
    v8 = {r['instance_id'] for r in
          json.loads((RUN_V8 / 'population_v8.json').read_text())}
    used = set(anchor_ids()) | v5 | v6 | v7 | v8
    by = {}
    for (m, inst), r in recs.items():
        if inst in used or inst not in pk[m]:
            continue
        if not (r.get('facts') or {}).get('facts'):
            continue
        by.setdefault(inst, []).append(m)
    order = sorted(by, key=lambda x: sha(f'43|v9|{x}'))
    rows = []
    for inst in order[:N]:
        m = sorted(by[inst])[int(sha(f'43|v9|model|{inst}'), 16) %
                               len(by[inst])]
        t = pk[m][inst]
        r = recs[(m, inst)]
        facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                 for f in r['facts']['facts']]
        for cp, name in (('extraction', 'extraction pool'),
                         ('board', 'shared board')):
            rows.append({'key': f'v9/{m}/{inst}/{cp}', 'instance_id': inst,
                         'model': m, 'checkpoint': cp,
                         'checkpoint_name': name, 'question': t['question'],
                         'facts': facts,
                         'entries': [{'unit_id': u['unit_id'],
                                      'agent_id': u['agent_id'],
                                      'text': u['text']}
                                     for u in t['checkpoints'][cp]]})
    assert len(rows) == 120, len(rows)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_sha256': file_sha(PROMPT),
        'system_sha256': sha(json.loads(PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP),
        'n': len(rows), 'instances': N, 'seed': SEED,
        'reference_model': GEMINI, 'labeller_model': HAIKU,
        'cap_reference_usd': CAP_REF, 'cap_labeller_usd': CAP_LAB},
        indent=1))
    print(json.dumps({'cases': len(rows), 'instances': N,
                      'population_sha256': file_sha(POP)[:12]}, indent=1))


def parse_ref(content, fact_ids):
    obj = last_object(content or '') or {}
    items = obj.get('facts')
    if not isinstance(items, list):
        return None
    out = {}
    for x in items:
        fid = x.get('fact_id')
        if fid not in fact_ids or fid in out:
            continue
        st = str(x.get('status', '')).lower()
        fi = str(x.get('fidelity', '')).lower()
        if st not in STATUS or fi not in FID:
            return None
        units = [u for u in (x.get('unit_ids') or []) if isinstance(u, str)]
        out[fid] = {'status': st, 'fidelity': fi,
                    'unit_ids': sorted(set(units)),
                    'reason': str(x.get('reason', ''))[:200]}
    return out if set(out) == fact_ids else None


def call(key, model, system, user, max_tokens, cap, total, path):
    if model == HAIKU:
        from scripts.pilot_llm_labeller import PRICE_IN, PRICE_OUT
        pin, pout = PRICE_IN, PRICE_OUT
    else:
        pin, pout = price(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if total + est > cap:
        with path.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None, total
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with path.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'label_validation_v9', 'key': key,
                               'openrouter_reasoning': model == GEMINI})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with path.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp, total + cost


def reference(cap, workers=6):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    total = 0.0
    if REF_CALLS.exists():
        for l in REF_CALLS.read_text().splitlines():
            if not l.strip():
                continue
            c = json.loads(l)
            if c.get('event') != 'result':
                continue
            k = c['key'].replace('ref/', '', 1)
            row = next((x for x in rows if x['key'] == k), None)
            if row and parse_ref(c.get('content'),
                                 {f['fact_id'] for f in row['facts']}):
                done[k] = c
        total = sum(json.loads(l).get('cost_usd', 0.0)
                    for l in REF_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * price(GEMINI)[0] + MAX_REF * price(GEMINI)[1]
                      for r in chunk)
        if total + reserve > cap:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6),
                              'remaining': len(todo) - i}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), MAX_REF, cap,
                              total, REF_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp, _ = fut.result()
                print(json.dumps({'key': r['key'],
                                  'success': bool(resp and resp.success)}),
                      flush=True)
        total = sum(json.loads(l).get('cost_usd', 0.0)
                    for l in REF_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
        print(json.dumps({'spent_usd': round(total, 6)}), flush=True)
    done = {r['key'] for r in rows
            if r['key'] in {json.loads(l)['key'].replace('ref/', '', 1)
                            for l in REF_CALLS.read_text().splitlines()
                            if l.strip() and json.loads(l).get('event') ==
                            'result'}}
    print(json.dumps({'reference_calls': len(done),
                      'spent_usd': round(total, 8)}, indent=1))


def freeze_reference():
    rows = json.loads(POP.read_text())
    calls = [json.loads(l) for l in REF_CALLS.read_text().splitlines()
             if l.strip() and json.loads(l).get('event') == 'result']
    by = {c['key']: c for c in calls}
    labels = {}
    for r in rows:
        c = by.get(f"ref/{r['key']}")
        if not c:
            raise SystemExit(f"missing reference call {r['key']}")
        lab = parse_ref(c.get('content'), {f['fact_id'] for f in r['facts']})
        if lab is None:
            raise SystemExit(f"unparsed reference {r['key']}")
        labels[r['key']] = lab
    REF_LABELS.write_text(json.dumps(
        {'_note': 'Gemini 3.6 Flash reference labels, frozen before Haiku calls',
         'model': GEMINI, 'labels': labels}, indent=1, ensure_ascii=False))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'n': len(labels)}, indent=1))
    print(json.dumps({'labels': len(labels),
                      'sha256': file_sha(REF_LABELS)[:12]}, indent=1))


def labeller(cap, workers=6):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads((ROOT / 'rebuttal/pilots/20261113_label_validation_v9/per_fact_prompt_v9.json').read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    total = 0.0
    if LAB_CALLS.exists():
        total = sum(json.loads(l).get('cost_usd', 0.0)
                    for l in LAB_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
    todo = [r for r in rows if r['key'] not in done]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * 0.10e-6 + MAX_TOKENS * 0.50e-6 for r in chunk)
        if total + reserve > cap:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"lab/{r['key']}", HAIKU, spec['system'],
                              render(r), MAX_TOKENS, cap, total,
                              LAB_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp, _ = fut.result()
                lab = parse_lab(resp.content,
                                {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {'key': r['key'],
                                  'instance_id': r['instance_id'],
                                  'model': r['model'],
                                  'checkpoint': r['checkpoint'],
                                  'facts': r['facts'], 'labeller': lab}
        total = sum(json.loads(l).get('cost_usd', 0.0)
                    for l in LAB_CALLS.read_text().splitlines()
                    if l.strip() and json.loads(l).get('event') == 'result')
        LAB_RESULTS.write_text(json.dumps({'items': list(done.values())},
                                          indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(total, 6)}), flush=True)
    LAB_RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1,
                                      ensure_ascii=False))
    print(json.dumps({'rows': len(rows),
                      'spent_usd': round(total, 8)}, indent=1))


def agree(pairs):
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    return {'n': n, 'k': k, 'agreement': k / n, 'lo': lo, 'hi': hi,
            'kappa': kappa_binary(pairs)}


def kappa_ci(pairs, cluster):
    rng = random.Random(SEED)
    groups = {}
    for p, c in zip(pairs, cluster):
        groups.setdefault(c, []).append(p)
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
    rows = {r['key']: r for r in
            json.loads(LAB_RESULTS.read_text())['items']}
    ref = json.loads(REF_LABELS.read_text())['labels']
    spend = sum(json.loads(l).get('cost_usd', 0.0)
                for p in (REF_CALLS, LAB_CALLS) if p.exists()
                for l in p.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result')
    bycp = {'extraction': [], 'board': []}
    for key, r in rows.items():
        if not r.get('labeller'):
            continue
        cp = r['checkpoint']
        for f in r['facts']:
            fid = f['fact_id']
            v = r['labeller'].get(fid)
            z = ref[key].get(fid)
            if not v or not z:
                continue
            bycp[cp].append({'inst': r['instance_id'],
                             'lab': v, 'ref': z, 'fact': fid})
    out = {}
    for cp in ('extraction', 'board'):
        items = bycp[cp]
        pres = [(x['lab']['status'] != 'absent',
                 x['ref']['status'] != 'absent') for x in items]
        pres_ci = agree(pres)
        fidel = [x for x in items
                 if x['lab']['status'] != 'absent'
                 and x['ref']['status'] != 'absent']
        faith = [(x['lab']['fidelity'] == 'faithful',
                  x['ref']['fidelity'] == 'faithful') for x in fidel]
        faith_ci = agree(faith)
        conf = {}
        for x in fidel:
            k = (x['ref']['fidelity'], x['lab']['fidelity'])
            conf[k] = conf.get(k, 0) + 1
        car_match = []
        for x in items:
            ru = set(x['ref']['unit_ids'])
            lu = set(x['lab']['unit_ids'])
            hit = (x['lab']['status'] == 'absent' if not ru else
                   (x['lab']['status'] != 'absent' and bool(lu & ru)))
            car_match.append(hit)
        # The V5 carrier rule is a match indicator, so it has no paired kappa.
        # Kappa is computed on the paired carrier-presence decision instead.
        car = [(x['lab']['status'] != 'absent',
                x['ref']['status'] != 'absent') for x in items]
        car_ci = agree(car)
        car_match_rate = sum(car_match) / len(car_match)
        out[cp] = {'presence': pres_ci,
                   'presence_kci': kappa_ci(pres, [x['inst'] for x in items]),
                   'fidelity': faith_ci,
                   'fidelity_kci': kappa_ci(faith,
                                            [x['inst'] for x in fidel]),
                   'carrier': car_ci,
                   'carrier_match_rate': car_match_rate,
                   'carrier_kci': kappa_ci(car, [x['inst'] for x in items]),
                   'conf': conf}
    def verdict(m, a, k):
        return 'PASS' if m['agreement'] >= a and m['kappa'] >= k else 'FAIL'
    lines = [
        '# V9 label re-validation with the boundary procedure in both prompts\n',
        f"Rule `LABEL_RULE_V9.md` (sha256 `{file_sha(RULE)[:12]}`); reference "
        f"labels `reference_labels_v9.json` (sha256 "
        f"`{file_sha(REF_LABELS)[:12]}`), frozen before the Haiku calls. "
        f"Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**, "
        f"prompt v9. 60 fresh MuSiQue instances x 2 checkpoints = 120 cases; "
        f"spend ${spend:.6f}, caps $2.00 reference + $0.50 labeller.\n",
        '**Carrier (board)**\n',
        f"V5 carrier match rate (unit intersection or both absent) "
        f"**{out['board']['carrier_match_rate']:.3f}**; paired carrier-"
        f"presence agreement **{out['board']['carrier']['k']}/"
        f"{out['board']['carrier']['n']} = "
        f"{out['board']['carrier']['agreement']:.3f}** (95% CI "
        f"{out['board']['carrier']['lo']:.3f}-"
        f"{out['board']['carrier']['hi']:.3f}); kappa "
        f"**{out['board']['carrier']['kappa']:.3f}** - **"
        f"{verdict(out['board']['carrier'], .80, .60)}** against 0.80/0.60.\n",
        '**Presence (extraction)**\n',
        f"Binary carried agreement **{out['extraction']['presence']['k']}/"
        f"{out['extraction']['presence']['n']} = "
        f"{out['extraction']['presence']['agreement']:.3f}** (95% CI "
        f"{out['extraction']['presence']['lo']:.3f}-"
        f"{out['extraction']['presence']['hi']:.3f}); kappa "
        f"**{out['extraction']['presence']['kappa']:.3f}** "
        f"({out['extraction']['presence_kci'][0]:.3f}-"
        f"{out['extraction']['presence_kci'][1]:.3f}) - **"
        f"{verdict(out['extraction']['presence'], .85, .60)}** against "
        f"0.85/0.60.\n",
        '**Fidelity (board, primary)**\n',
        f"Among facts both label carried, faithful agreement "
        f"**{out['board']['fidelity']['k']}/{out['board']['fidelity']['n']} = "
        f"{out['board']['fidelity']['agreement']:.3f}** (95% CI "
        f"{out['board']['fidelity']['lo']:.3f}-"
        f"{out['board']['fidelity']['hi']:.3f}); kappa "
        f"**{out['board']['fidelity']['kappa']:.3f}** "
        f"({out['board']['fidelity_kci'][0]:.3f}-"
        f"{out['board']['fidelity_kci'][1]:.3f}) - **"
        f"{verdict(out['board']['fidelity'], .85, .60)}** against 0.85/0.60.\n",
        f"Extraction fidelity (secondary): {out['extraction']['fidelity']['k']}/"
        f"{out['extraction']['fidelity']['n']} = "
        f"{out['extraction']['fidelity']['agreement']:.3f} "
        f"({out['extraction']['fidelity']['lo']:.3f}-"
        f"{out['extraction']['fidelity']['hi']:.3f}), kappa "
        f"{out['extraction']['fidelity']['kappa']:.3f}.\n",
        'Three-class confusion, board (reference, labeller):\n',
        '| reference \\ labeller | faithful | partial | distorted |',
        '| --- | ---: | ---: | ---: |']
    for rf in ('faithful', 'partial', 'distorted'):
        cells = [out['board']['conf'].get((rf, lf), 0)
                 for lf in ('faithful', 'partial', 'distorted')]
        lines.append(f"| {rf} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += ['', '## What this covers\n',
              'A PASS is cross-model agreement on these 120 MuSiQue cases, '
              'not author ground truth, and only at these checkpoints. A '
              'FAIL means the label is not used to replace an old column: the '
              'disagreements are read, the prompt is fixed, and the fixed '
              'prompt is re-validated on a fresh disjoint set.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'carrier_board': out['board']['carrier'],
                      'presence': out['extraction']['presence'],
                      'presence_kappa': out['extraction']['presence']['kappa'],
                      'fidelity_board': out['board']['fidelity'],
                      'fidelity_kappa': out['board']['fidelity']['kappa'],
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze-reference', 'labeller', 'report'):
        ap.add_argument('--' + f.replace('-', '_'), action='store_true',
                        dest=f.replace('-', '_'))
    ap.add_argument('--cap-usd', type=float, default=None)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.reference:
        reference(a.cap_usd or CAP_REF, a.workers)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.cap_usd or CAP_LAB, a.workers)
    if a.report:
        report()


if __name__ == '__main__':
    main()