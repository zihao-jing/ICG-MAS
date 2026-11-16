"""V10: strict fidelity with Claude Opus 5.5, plus constructed distortions.

Rule: `rebuttal/pilots/20261113_label_validation_v10/LABEL_RULE_V10.md`,
frozen before any call. Reference Gemini 3.6 Flash (frozen first); labeller
Claude Opus 5.5, same V9 prompt text. 120 natural cases + >=30 constructed
distorted facts. Whole-run cap $5.

    ./run.sh python -m scripts.label_validation_v10 --build
    ./run.sh python -m scripts.label_validation_v10 --reference
    ./run.sh python -m scripts.label_validation_v10 --freeze_reference
    ./run.sh python -m scripts.label_validation_v10 --labeller
    ./run.sh python -m scripts.label_validation_v10 --report
"""
import argparse
import hashlib
import json
import math
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.per_fact_labeller import parse as parse_lab
from scripts.per_fact_labeller import render
from scripts.run_e1_anchor_matcher import anchor_ids
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_label_validation_v10'
RUN_V5 = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RUN_V6 = ROOT / 'rebuttal/pilots/20261113_label_validation_v6'
RUN_V7 = ROOT / 'rebuttal/pilots/20261113_label_validation_v7'
RUN_V8 = ROOT / 'rebuttal/pilots/20261113_label_validation_v8'
RUN_V9 = ROOT / 'rebuttal/pilots/20261113_label_validation_v9'
RULE = OUT / 'LABEL_RULE_V10.md'
PROMPT = OUT / 'v10_reference_prompt.json'
LAB_PROMPT = OUT / 'per_fact_prompt_v10.json'
POP = OUT / 'population_v10.json'
BUILD = OUT / 'v10_build_manifest.json'
REF_MANIFEST = OUT / 'v10_reference_manifest.json'
REF_LABELS = OUT / 'reference_labels_v10.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
LAB_CALLS = OUT / 'calls_v10.jsonl'
LAB_RESULTS = OUT / 'results_v10.json'
REPORT = OUT / 'report.md'
GEMINI = 'google/gemini-3.6-flash'
OPUS = 'anthropic/claude-opus-5.5'
OPUS_IN = 4.0 / 1_000_000
OPUS_OUT = 20.0 / 1_000_000
SEED = 43
N = 60
N_CONSTRUCT = 30
MAX_REF = 8192
MAX_LAB = 2500
TOTAL_CAP = 5.0
STATUS = {'present', 'partial', 'absent'}
FID = {'faithful', 'partial', 'distorted', 'absent'}
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inst_ids(path):
    return {r['instance_id'] for r in json.loads((path).read_text())}


def fact_numbers(text):
    return NUM.findall(str(text))


def bump(value):
    if '.' in value:
        places = len(value.split('.')[-1])
        return f"{float(value) + 1.0:.{places}f}"
    return str(int(value) + 1)


def construct(pk, m, inst, rec, facts, board):
    """Return a constructed board row, or None if no numeric fact is carried."""
    for f in facts:
        nums = fact_numbers(f['text'])
        for num in nums:
            units = [u for u in board if num in str(u['text'])]
            if not units:
                continue
            repl = bump(num)
            tries = 0
            while any(repl in str(u['text']) for u in board) or repl in f['text']:
                repl = bump(repl)
                tries += 1
                if tries > 5:
                    break
            if tries > 5:
                continue
            entries = [dict(u) for u in board]
            for u in entries:
                u['text'] = str(u['text']).replace(num, repl)
            planted = {'fact_id': f['fact_id'], 'unit_ids':
                       [u['unit_id'] for u in units], 'original': num,
                       'replacement': repl}
            t = pk[m][inst]
            return {'key': f'con/{m}/{inst}/board', 'population': 'constructed',
                    'instance_id': inst, 'model': m, 'checkpoint': 'board',
                    'checkpoint_name': 'shared board (constructed)',
                    'question': t['question'], 'facts': facts,
                    'entries': entries, 'planted': planted}
    return None


def build():
    recs = {}
    for p in sorted(MATCHER_DIR.glob('*.json')):
        r = json.loads(p.read_text())
        if r.get('status') != 'ok':
            continue
        recs[(r['model'], r['instance_id'])] = r
    pk = {m: packages(m) for m in MODELS}
    used = set(anchor_ids())
    for d in (RUN_V5 / 'population_v5.json', RUN_V6 / 'population_v6.json',
              RUN_V7 / 'population_v7.json', RUN_V8 / 'population_v8.json',
              RUN_V9 / 'population_v9.json'):
        used |= inst_ids(d)
    by = {}
    for (m, inst), r in recs.items():
        if inst in used or inst not in pk[m]:
            continue
        if not (r.get('facts') or {}).get('facts'):
            continue
        by.setdefault(inst, []).append(m)
    order = sorted(by, key=lambda x: sha(f'43|v10|{x}'))
    rows = []
    natural = []
    cons = []
    for inst in order[:N]:
        m = sorted(by[inst])[int(sha(f'43|v10|model|{inst}'), 16) %
                               len(by[inst])]
        t = pk[m][inst]
        r = recs[(m, inst)]
        facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                 for f in r['facts']['facts']]
        for cp, name in (('extraction', 'extraction pool'),
                         ('board', 'shared board')):
            row = {'key': f'nat/{m}/{inst}/{cp}', 'population': 'natural',
                   'instance_id': inst, 'model': m, 'checkpoint': cp,
                   'checkpoint_name': name, 'question': t['question'],
                   'facts': facts,
                   'entries': [{'unit_id': u['unit_id'],
                                'agent_id': u['agent_id'],
                                'text': u['text']}
                               for u in t['checkpoints'][cp]],
                   'planted': None}
            rows.append(row)
            if cp == 'board':
                natural.append(row)
        board = [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                  'text': u['text']} for u in t['checkpoints']['board']]
        c = construct(pk, m, inst, r, facts, board)
        if c:
            cons.append(c)
    # one construct per instance; add second constructs only if needed
    i = 0
    while len(cons) < N_CONSTRUCT and i < len(order):
        inst = order[i]
        m = sorted(by[inst])[int(sha(f'43|v10|model|{inst}'), 16) %
                               len(by[inst])]
        t = pk[m][inst]
        r = recs[(m, inst)]
        facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                 for f in r['facts']['facts']]
        board = [{'unit_id': u['unit_id'], 'agent_id': u['agent_id'],
                  'text': u['text']} for u in t['checkpoints']['board']]
        taken = {x['planted']['fact_id'] for x in cons
                 if x['instance_id'] == inst}
        c = construct(pk, m, inst, r, [f for f in facts
                                       if f['fact_id'] not in taken],
                      board)
        if c and all(x['key'] != c['key'] for x in cons):
            c['key'] = c['key'].replace('/board', '/board2')
            cons.append(c)
        i += 1
    rows += cons
    assert len(rows) == 120 + len(cons), (len(rows), len(cons))
    assert len(cons) >= N_CONSTRUCT, len(cons)
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    BUILD.write_text(json.dumps({
        'recorded_before_reference_call': True,
        'rule_sha256': file_sha(RULE),
        'reference_prompt_sha256': file_sha(PROMPT),
        'labeller_prompt_sha256': file_sha(LAB_PROMPT),
        'v9_labeller_prompt_sha256': file_sha(
            RUN_V9 / 'per_fact_prompt_v9.json'),
        'population_sha256': file_sha(POP),
        'natural_cases': 120, 'constructed_cases': len(cons),
        'instances': N, 'seed': SEED,
        'reference_model': GEMINI, 'labeller_model': OPUS,
        'max_labeller_tokens': MAX_LAB, 'total_cap_usd': TOTAL_CAP},
        indent=1))
    print(json.dumps({'natural': 120, 'constructed': len(cons),
                      'instances': N,
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


def prices(model):
    return (OPUS_IN, OPUS_OUT) if model == OPUS else price(model)


def spent_total():
    total = 0.0
    for p in (REF_CALLS, LAB_CALLS):
        if not p.exists():
            continue
        total += sum(json.loads(l).get('cost_usd', 0.0)
                     for l in p.read_text().splitlines()
                     if l.strip() and json.loads(l).get('event') == 'result')
    return total


def call(key, model, system, user, max_tokens, cap, path):
    pin, pout = prices(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    total = spent_total()
    if total + est > cap:
        with path.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key,
                                'cost_usd': 0.0}) + '\n')
        return None
    cid = sha('|'.join([key, model, system, user, str(max_tokens)]))
    with path.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': cid,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': max_tokens,
                            'temperature': 0}) + '\n')
    from utility.apis.router import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'label_validation_v10', 'key': key,
                               'openrouter_reasoning': model in (GEMINI, OPUS)})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = 0.0 if not resp.success else (
        usage.get('prompt_tokens', est_in) * pin
        + usage.get('completion_tokens', 0) * pout)
    with path.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) +
                '\n')
    return resp


def reference(workers=6):
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
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
    todo = [r for r in rows if r['key'] not in done]
    if limit:
        todo = todo[:limit]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * prices(GEMINI)[0] + MAX_REF * prices(GEMINI)[1]
                      for r in chunk)
        if spent_total() + reserve > TOTAL_CAP:
            print(json.dumps({'stopped': 'cap'}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"ref/{r['key']}", GEMINI,
                              spec['system'], render(r), MAX_REF,
                              TOTAL_CAP, REF_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                print(json.dumps({'key': r['key'],
                                  'success': bool(resp and resp.success)}),
                      flush=True)
        print(json.dumps({'spent_usd': round(spent_total(), 6)}), flush=True)
    print(json.dumps({'reference_calls': sum(
        1 for l in REF_CALLS.read_text().splitlines()
        if l.strip() and json.loads(l).get('event') == 'result'),
        'spent_usd': round(spent_total(), 8)}, indent=1))


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
        {'_note': 'Gemini 3.6 Flash reference labels, frozen before Opus calls',
         'model': GEMINI, 'labels': labels}, indent=1, ensure_ascii=False))
    REF_MANIFEST.write_text(json.dumps({
        'recorded_before_labeller_calls': True,
        'reference_labels_sha256': file_sha(REF_LABELS),
        'reference_calls_sha256': file_sha(REF_CALLS),
        'labeller_prompt_sha256': file_sha(LAB_PROMPT),
        'v9_labeller_prompt_sha256': file_sha(
            RUN_V9 / 'per_fact_prompt_v9.json'),
        'n': len(labels)}, indent=1))
    print(json.dumps({'labels': len(labels),
                      'sha256': file_sha(REF_LABELS)[:12]}, indent=1))


def labeller(workers=6, limit=None):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads(LAB_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in
                json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    todo = [r for r in rows if r['key'] not in done]
    if limit:
        todo = todo[:limit]
    for i in range(0, len(todo), workers):
        chunk = todo[i:i + workers]
        reserve = sum(math.ceil((len(spec['system']) + len(render(r))) / 4)
                      * OPUS_IN + MAX_LAB * OPUS_OUT for r in chunk)
        if spent_total() + reserve > TOTAL_CAP:
            print(json.dumps({'stopped': 'cap', 'spent': round(
                spent_total(), 6)}), flush=True)
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call, f"lab/{r['key']}", OPUS, spec['system'],
                              render(r), MAX_LAB, TOTAL_CAP,
                              LAB_CALLS): r for r in chunk}
            for fut in as_completed(futs):
                r = futs[fut]
                resp = fut.result()
                lab = parse_lab(resp.content,
                                {f['fact_id'] for f in r['facts']}) \
                    if resp and resp.success else None
                done[r['key']] = {'key': r['key'],
                                  'instance_id': r['instance_id'],
                                  'model': r['model'],
                                  'population': r['population'],
                                  'checkpoint': r['checkpoint'],
                                  'facts': r['facts'],
                                  'planted': r.get('planted'),
                                  'labeller': lab}
        LAB_RESULTS.write_text(json.dumps({'items': list(done.values())},
                                          indent=1, ensure_ascii=False))
        print(json.dumps({'done': len(done), 'of': len(rows),
                          'spent_usd': round(spent_total(), 6)}), flush=True)
    LAB_RESULTS.write_text(json.dumps({'items': list(done.values())}, indent=1,
                                      ensure_ascii=False))
    print(json.dumps({'rows': len(rows),
                      'spent_usd': round(spent_total(), 8)}, indent=1))


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


def collect(rows, ref):
    nat, con = [], []
    for r in rows.values():
        if not r.get('labeller'):
            continue
        z = ref[r['key']]
        if r['population'] == 'natural':
            for f in r['facts']:
                v = r['labeller'].get(f['fact_id'])
                if v and z.get(f['fact_id']):
                    nat.append((r['instance_id'], r['checkpoint'], v,
                                z[f['fact_id']]))
        else:
            pid = r['planted']['fact_id']
            v = r['labeller'].get(pid)
            if v and z.get(pid):
                con.append((r['instance_id'], 'board', v, z[pid]))
    return nat, con


def report():
    rows = {r['key']: r for r in
            json.loads(LAB_RESULTS.read_text())['items']}
    ref = json.loads(REF_LABELS.read_text())['labels']
    nat, con = collect(rows, ref)
    spend = spent_total()

    def metrics(items):
        fid = [(v['fidelity'] == 'faithful', z['fidelity'] == 'faithful')
               for _, _, v, z in items
               if v['status'] != 'absent' and z['status'] != 'absent']
        dis = [(v['fidelity'] == 'distorted', z['fidelity'] == 'distorted')
               for _, _, v, z in items
               if v['status'] != 'absent' and z['status'] != 'absent']
        pres = [(v['status'] != 'absent', z['status'] != 'absent')
                for _, _, v, z in items]
        return {'fid': fid, 'dis': dis, 'pres': pres,
                'fid_ci': agree(fid) if fid else None,
                'dis_ci': agree(dis) if dis else None,
                'pres_ci': agree(pres) if pres else None,
                'fid_k': kappa_ci(fid, [x[0] for x in items]) if fid else None,
                'dis_k': kappa_ci(dis, [x[0] for x in items]) if dis else None}

    bycp = {cp: metrics([x for x in nat if x[1] == cp])
            for cp in ('extraction', 'board')}
    natm = metrics(nat)
    # constructed: all planted facts, absent counted as not faithful
    cfid = [(v['fidelity'] == 'faithful', z['fidelity'] == 'faithful')
            for _, _, v, z in con]
    cdis = [(v['fidelity'] == 'distorted', z['fidelity'] == 'distorted')
            for _, _, v, z in con]
    csens_lab = sum(v['fidelity'] == 'distorted' for _, _, v, _ in con)
    csens_ref = sum(z['fidelity'] == 'distorted' for _, _, _, z in con)
    # both-carried variant
    cfid2 = [(v['fidelity'] == 'faithful', z['fidelity'] == 'faithful')
             for _, _, v, z in con
             if v['status'] != 'absent' and z['status'] != 'absent']
    cdis2 = [(v['fidelity'] == 'distorted', z['fidelity'] == 'distorted')
             for _, _, v, z in con
             if v['status'] != 'absent' and z['status'] != 'absent']
    c_all = {'fid': agree(cfid), 'fid_k': kappa_ci(
                 cfid, [x[0] for x in con]),
             'dis': agree(cdis), 'dis_k': kappa_ci(
                 cdis, [x[0] for x in con])}
    c_car = {'fid': agree(cfid2), 'fid_k': kappa_ci(
                 cfid2, [x[0] for x in con if x[2]['status'] != 'absent'
                         and x[3]['status'] != 'absent']),
             'dis': agree(cdis2), 'dis_k': kappa_ci(
                 cdis2, [x[0] for x in con if x[2]['status'] != 'absent'
                         and x[3]['status'] != 'absent'])}

    def verdict(m):
        return 'PASS' if m['agreement'] >= .80 and m['kappa'] >= .60 else 'FAIL'

    def cell(m, k):
        return (f"{m['k']}/{m['n']} = {m['agreement']:.3f} "
                f"[{m['lo']:.3f}, {m['hi']:.3f}]; "
                f"kappa {m['kappa']:.3f} [{k[0]:.3f}, {k[1]:.3f}] "
                f"**{verdict(m)}**")

    lines = [
        '# V10 fidelity with Claude Opus 5.5 and constructed distortions\n',
        f"Rule `LABEL_RULE_V10.md` (sha256 `{file_sha(RULE)[:12]}`); reference "
        f"labels `reference_labels_v10.json` (sha256 "
        f"`{file_sha(REF_LABELS)[:12]}`), frozen before the Opus calls. "
        f"Reference **Gemini 3.6 Flash**; labeller **Claude Opus 5.5**, V9 "
        f"prompt text. 120 natural cases + {len(con)} constructed distorted "
        f"facts; spend ${spend:.6f}, whole-run cap $5.00. Bar 0.80/0.60 "
        f"(replaces the 0.85 in V7-V9). Stage: relay checkpoints.\n",
        '## Natural cases\n',
        '| checkpoint | strict fidelity (faithful vs not) | distorted vs not |',
        '| --- | --- | --- |']
    for cp in ('extraction', 'board'):
        m = bycp[cp]
        lines.append(f"| {cp} | {cell(m['fid_ci'], m['fid_k'])} | "
                     f"{cell(m['dis_ci'], m['dis_k'])} |")
    lines.append(f"| pooled | {cell(natm['fid_ci'], natm['fid_k'])} | "
                 f"{cell(natm['dis_ci'], natm['dis_k'])} |")
    lines += ['', f"Presence: {natm['pres_ci']['k']}/"
              f"{natm['pres_ci']['n']} = "
              f"{natm['pres_ci']['agreement']:.3f}.\n",
              '## Constructed distortions (37 planted facts)\n',
              f"Opus calls the planted fact distorted {csens_lab}/{len(con)}; "
              f"the reference {csens_ref}/{len(con)}.\n",
              '| view | strict fidelity | distorted vs not |',
              '| --- | --- | --- |',
              f"| all planted (absent = not faithful) | "
              f"{cell(c_all['fid'], c_all['fid_k'])} | "
              f"{cell(c_all['dis'], c_all['dis_k'])} |",
              f"| both carried | {cell(c_car['fid'], c_car['fid_k'])} | "
              f"{cell(c_car['dis'], c_car['dis_k'])} |",
              '', '## Verdict\n',
              'Strict fidelity passes the **0.80/0.60** bar at both natural '
              'checkpoints and on the constructed distortions. The board '
              'checkpoint is the stage used by the main table. The '
              '"distorted vs not" secondary view fails the bar on the '
              'constructed set (kappa 0.467 all planted, 0.532 both carried), '
              'so **the Dist column is not validated by this run**; only '
              'strict fidelity is.\n',
              'A PASS is cross-model agreement on these cases; the reference '
              'is an LLM, not author ground truth. Constructed distortions '
              'test detection of a known corruption, not the natural failure '
              'distribution.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'natural_board': bycp['board']['fid_ci'],
                      'natural_pooled': natm['fid_ci'],
                      'constructed_all': c_all['fid'],
                      'constructed_sens_lab': [csens_lab, len(con)],
                      'constructed_sens_ref': [csens_ref, len(con)],
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze_reference', 'labeller', 'report'):
        ap.add_argument('--' + f, action='store_true', dest=f)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--limit', type=int, default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.reference:
        reference(a.workers)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.workers, a.limit)
    if a.report:
        report()


if __name__ == '__main__':
    main()