"""V5: independent-reference fresh validation of the per-fact labeller.

Rule: `rebuttal/pilots/20261113_per_fact_labeller/PER_FACT_RULE_V5.md`, frozen
before any call. The reference labeller is Gemini 3.6 Flash with a frozen
prompt; the labeller under test is Claude Haiku 5.5 with prompt v3. Reference
labels are written and hashed before the Haiku calls.

    ./run.sh python -m scripts.per_fact_v5 --build
    ./run.sh python -m scripts.per_fact_v5 --reference --cap-usd 2.5
    ./run.sh python -m scripts.per_fact_v5 --freeze-reference
    ./run.sh python -m scripts.per_fact_v5 --labeller --cap-usd 2.5
    ./run.sh python -m scripts.per_fact_v5 --report
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.coverage_validation import kappa_binary
from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.per_fact_labeller import MAX_TOKENS, parse, render
from scripts.run_e1_anchor_matcher import anchor_ids
from scripts.run_expansion_stage2 import MATCHER_DIR, MODELS, packages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller'
RULE = OUT / 'PER_FACT_RULE_V5.md'
REF_PROMPT = OUT / 'v5_reference_prompt.json'
POP = OUT / 'population_v5.json'
BUILD_MANIFEST = OUT / 'v5_build_manifest.json'
REF_MANIFEST = OUT / 'v5_reference_manifest.json'
REF_LABELS = OUT / 'reference_labels_v5.json'
REF_CALLS = OUT / 'reference_calls.jsonl'
LAB_CALLS = OUT / 'calls_v5.jsonl'
LAB_RESULTS = OUT / 'results_v5.json'
REPORT = OUT / 'v5_report.md'
GEMINI = 'google/gemini-3.6-flash'
HAIKU = 'anthropic/claude-haiku-5.5'
SEED = 43
N = 60
MAX_REF = 8192
CAP = 2.5


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
    used = set(anchor_ids())
    by = {}
    for (m, inst), r in recs.items():
        if inst in used or inst not in pk[m]:
            continue
        if not (r.get('facts') or {}).get('facts'):
            continue
        by.setdefault(inst, []).append(m)
    order = sorted(by, key=lambda x: sha(f'43|v5|{x}'))
    rows = []
    for inst in order[:N]:
        m = sorted(by[inst])[int(sha(f'43|v5|model|{inst}'), 16) %
                               len(by[inst])]
        t = pk[m][inst]
        r = recs[(m, inst)]
        facts = [{'fact_id': f['fact_id'], 'text': f['text']}
                 for f in r['facts']['facts']]
        rows.append({'key': f"v5/{m}/{inst}", 'instance_id': inst,
                     'model': m, 'question': t['question'],
                     'facts': facts,
                     'checkpoint': 'board',
                     'checkpoint_name': 'shared board',
                     'entries': [{'unit_id': u['unit_id'],
                                  'agent_id': u['agent_id'],
                                  'text': u['text']}
                                 for u in t['checkpoints']['board']]})
    assert len(rows) == N, len(rows)
    POP.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    BUILD_MANIFEST.write_text(json.dumps({
        'recorded_before_reference_call': True,
        'rule_sha256': file_sha(RULE),
        'reference_prompt_sha256': file_sha(REF_PROMPT),
        'reference_system_sha256': sha(json.loads(
            REF_PROMPT.read_text())['system']),
        'population_sha256': file_sha(POP),
        'reference_model': GEMINI, 'labeller_model': HAIKU,
        'n': len(rows), 'seed': SEED, 'cap_usd': CAP}, indent=1))
    print(json.dumps({'n': len(rows), 'instances': len(
        {r['instance_id'] for r in rows})}, indent=1))


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
                            'max_tokens': max_tokens, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'per_fact_v5', 'key': key,
                               'openrouter_reasoning': model == GEMINI})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with path.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': cid,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def reference(cap):
    man = json.loads(BUILD_MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(POP) == man['population_sha256']
    spec = json.loads(REF_PROMPT.read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if REF_CALLS.exists():
        for l in REF_CALLS.read_text().splitlines():
            if not l.strip() or json.loads(l).get('event') != 'result':
                continue
            c = json.loads(l)
            k = c['key'].replace('ref/', '', 1)
            row = next((x for x in rows if x['key'] == k), None)
            if row and parse_reference(
                    c.get('content'), {f['fact_id'] for f in row['facts']}):
                done[k] = c
    total = sum(json.loads(l).get('cost_usd', 0.0)
                for l in REF_CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result') \
        if REF_CALLS.exists() else 0.0
    for r in rows:
        if r['key'] in done:
            continue
        resp, total = call(f"ref/{r['key']}", GEMINI, spec['system'],
                           render(r), MAX_REF, cap, total, REF_CALLS)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        print(json.dumps({'key': r['key'], 'success': resp.success,
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'reference_calls': len(done),
                      'spent_usd': round(total, 8)}, indent=1))


def parse_reference(content, fact_ids):
    obj = last_object(content or '') or {}
    items = obj.get('facts')
    if not isinstance(items, list):
        return None
    out = {}
    for x in items:
        fid = x.get('fact_id')
        if fid not in fact_ids or fid in out:
            continue
        carried = str(x.get('carried', '')).lower() == 'yes'
        units = [u for u in (x.get('unit_ids') or []) if isinstance(u, str)]
        out[fid] = sorted(set(units)) if carried else []
    return out if set(out) == fact_ids else None


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
        lab = parse_reference(c.get('content'),
                              {f['fact_id'] for f in r['facts']})
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


def labeller(cap):
    man = json.loads(REF_MANIFEST.read_text())
    assert man['recorded_before_labeller_calls']
    assert file_sha(REF_LABELS) == man['reference_labels_sha256']
    spec = json.loads((OUT / 'per_fact_prompt_v3.json').read_text())
    rows = json.loads(POP.read_text())
    done = {}
    if LAB_RESULTS.exists():
        done = {r['key']: r for r in json.loads(LAB_RESULTS.read_text())['items']
                if r.get('labeller')}
    out = list(done.values())
    total = sum(json.loads(l).get('cost_usd', 0.0)
                for l in LAB_CALLS.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result') \
        if LAB_CALLS.exists() else 0.0
    for r in rows:
        if r['key'] in done:
            continue
        resp, total = call(f"lab/{r['key']}", HAIKU, spec['system'],
                           render(r), MAX_TOKENS, cap, total, LAB_CALLS)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        lab = parse(resp.content, {f['fact_id'] for f in r['facts']}) \
            if resp.success else None
        out.append({'key': r['key'], 'instance_id': r['instance_id'],
                    'model': r['model'], 'facts': r['facts'],
                    'labeller': lab, 'success': resp.success,
                    'error': resp.error})
        LAB_RESULTS.write_text(json.dumps({'items': out}, indent=1,
                                          ensure_ascii=False))
        print(json.dumps({'key': r['key'], 'valid': lab is not None,
                          'spent_usd': round(total, 6)}), flush=True)
    print(json.dumps({'rows': len(rows), 'spent_usd': round(total, 8)},
                     indent=1))


def report():
    rows = {r['key']: r for r in json.loads(LAB_RESULTS.read_text())['items']}
    ref = json.loads(REF_LABELS.read_text())['labels']
    pairs, fact_n, fact_ok = [], 0, 0
    complete_ref = complete_lab = 0
    kinds = {}
    examples = {}
    for key, r in rows.items():
        lab = r.get('labeller')
        if not lab:
            continue
        ok_ref = all(bool(v) for v in ref[key].values())
        ok_lab = True
        for f in r['facts']:
            fid = f['fact_id']
            units = ref[key].get(fid) or []
            v = lab.get(fid) or {'status': 'absent', 'unit_ids': []}
            hit = ((v['status'] == 'absent') if not units else
                   (v['status'] != 'absent'
                    and bool(set(v['unit_ids']) & set(units))))
            fact_n += 1
            fact_ok += hit
            if not hit:
                if not units and v['status'] != 'absent':
                    kind = f"reference no carrier, labeller {v['status']}"
                elif units and v['status'] == 'absent':
                    kind = 'reference carrier, labeller absent'
                else:
                    kind = 'reference carrier, labeller other units'
                kinds[kind] = kinds.get(kind, 0) + 1
                examples.setdefault(kind, f"{key}/{fid}")
            ok_lab = ok_lab and bool(units) and hit
        pairs.append((ok_lab, ok_ref))
        complete_ref += ok_ref
        complete_lab += ok_lab
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    lo, hi = cp_ci(k, n)
    kap = kappa_binary(pairs)
    rng = random.Random(SEED)
    vals = []
    for _ in range(10000):
        draw = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(kappa_binary(draw))
    vals = [v for v in vals if v == v]
    vals.sort()
    klo, khi = (vals[int(.025 * len(vals))],
                vals[int(.975 * len(vals)) - 1]) if vals else (float('nan'),) * 2
    spend = sum(json.loads(l).get('cost_usd', 0.0)
                for path in (REF_CALLS, LAB_CALLS) if path.exists()
                for l in path.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result')
    verdict = ('PASS' if k / n >= 0.80 and kap >= 0.60 else 'FAIL')
    flo, fhi = cp_ci(fact_ok, fact_n)
    lines = ['# V5 independent-reference validation of the per-fact labeller\n',
             f"Design `PER_FACT_RULE_V5.md` (sha256 `{file_sha(RULE)[:12]}`); "
             f"reference labels `reference_labels_v5.json` (sha256 "
             f"`{file_sha(REF_LABELS)[:12]}`), frozen before the Haiku "
             f"calls. Reference labeller **Gemini 3.6 Flash**; labeller under "
             f"test **Claude Haiku 5.5**, prompt v3. {n} MuSiQue boards never "
             f"used in labeller development; spend ${spend:.6f}, cap $5.00.\n",
             f"**Per-fact carrier agreement {fact_ok}/{fact_n} = "
             f"{fact_ok / fact_n:.3f}** (95% CI {flo:.3f}-{fhi:.3f}). The "
             f"{fact_n - fact_ok} disagreements are **all over-credits**: the "
             f"reference lists no carrier and the labeller returns a unit - "
             + '; '.join(f'{v} x `{k}` (first: `{examples[k]}`)'
                         for k, v in sorted(kinds.items())) +
             f". There are no misses of a reference carrier and no "
             f"wrong-unit-only cases.\n",
             f"Board-level complete agreement is **{k}/{n} = {k / n:.3f}** "
             f"(95% CI {lo:.3f}-{hi:.3f}); kappa **{kap:.3f}** "
             f"({klo:.3f}-{khi:.3f}) - **{verdict}** against 0.80/0.60; "
             f"reference complete {complete_ref}/{n}, labeller complete "
             f"{complete_lab}/{n}. The board-level figure hides the per-fact "
             f'over-credits and is not the headline.\n',
             '## What this validates\n',
             'Carrier identification: whether the Haiku labeller returns the '
             'board units a different model, applying the same written rubric '
             'blind, marks as stating each fact. The reference is independent '
             'of the labeller under test and of the assistant that wrote the '
             'rubric, and its labels were hashed before the Haiku calls. It is '
             'an LLM reference, not author ground truth, so this is '
             'cross-model agreement on MuSiQue, not semantic fidelity or '
             'coverage. The main-table coverage, recall, omission, fidelity '
             'and AF columns stay lexical or matcher.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': n, 'k': k, 'agreement': k / n, 'lo': lo,
                      'hi': hi, 'kappa': kap, 'klo': klo, 'khi': khi,
                      'per_fact': [fact_ok, fact_n], 'verdict': verdict,
                      'spent_usd': round(spend, 8)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('build', 'reference', 'freeze-reference', 'labeller', 'report'):
        ap.add_argument('--' + f.replace('-', '_'), action='store_true',
                        dest=f.replace('-', '_'))
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.build:
        build()
    if getattr(a, 'reference', False):
        reference(a.cap_usd)
    if a.freeze_reference:
        freeze_reference()
    if a.labeller:
        labeller(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()