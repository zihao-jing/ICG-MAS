"""Injection screening v2: decisive-clause gate on the same bases and pairs.

Frozen amendment: `rebuttal/pilots/20261113_injection_screening_v2/GATE_AMENDMENT_V2.md`.
Cap $5; every call logged. The sample is reused from the v1 screening run.

    ./run.sh python -m scripts.injection_screening_v2 --gate --cap-usd 5
    ./run.sh python -m scripts.injection_screening_v2 --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.injection_screening import gate_render, load_bases, load_pairs
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import PRICE_IN, PRICE_OUT
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / 'rebuttal/pilots/20261113_injection_screening'
OUT = ROOT / 'rebuttal/pilots/20261113_injection_screening_v2'
PROMPT = OUT / 'screening_prompt_v2.json'
AMENDMENT = OUT / 'GATE_AMENDMENT_V2.md'
SAMPLE = V1 / 'sample.json'
SAMPLE_SHA = V1 / 'run_manifest.json'
MANUAL = V1 / 'spotcheck_manual.json'
MANIFEST = OUT / 'gate_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'gate_results.json'
REPORT = OUT / 'report.md'
MAX_TOKENS = 800


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(key, spec, user, cap, total):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': spec['model'],
                            'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'injection_screening_v2', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def parse(raw):
    d = last_object(raw or '')
    if not isinstance(d, dict) or not isinstance(d.get('supports'), list):
        return None
    allowed = {'present', 'partial', 'distorted', 'absent', 'not_required'}
    rows = []
    for r in d['supports']:
        if not isinstance(r, dict):
            return None
        p = str(r.get('pool', '')).lower()
        b = str(r.get('board', '')).lower()
        if p not in allowed or b not in allowed:
            return None
        req = r.get('required')
        if not isinstance(req, bool):
            req = not (p == 'not_required' and b == 'not_required')
        rows.append({'id': str(r.get('id') or ''), 'required': req,
                     'pool': p, 'board': b,
                     'unit_ids': r.get('unit_ids') or [],
                     'reason': str(r.get('reason') or '')[:220]})
    required = [r for r in rows if r['required']]
    defect_free = bool(rows) and all(
        r['pool'] == 'present' and r['board'] == 'present' for r in required)
    return {'supports': rows, 'required_n': len(required),
            'defect_free': defect_free, 'declared': d.get('defect_free')}


def gate(cap):
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None
    spec = json.loads(PROMPT.read_text())
    if man is None:
        MANIFEST.write_text(json.dumps({
            'recorded_before_first_call': True,
            'amendment_sha256': file_sha(AMENDMENT),
            'prompt_file_sha256': file_sha(PROMPT),
            'system_sha256': sha(spec['system']),
            'sample_sha256': file_sha(SAMPLE),
            'model': spec['model'], 'temperature': 0,
        }, indent=1))
    else:
        assert file_sha(AMENDMENT) == man['amendment_sha256'], 'amendment changed'
        assert file_sha(PROMPT) == man['prompt_file_sha256'], 'prompt changed'
        assert file_sha(SAMPLE) == man['sample_sha256'], 'sample changed'
    sample = json.loads(SAMPLE.read_text())
    bases = {r['item_id']: r for r in load_bases()}
    pairs = {r['item_id']: r for r in load_pairs()}
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    rows = []
    for iid in sample['base_ids']:
        key = f'gate2/base/{iid}'
        if key in done:
            rows.append(done[key])
            continue
        resp, total = call(key, spec, gate_render(bases[iid]['trace']),
                           cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        rows.append({'key': key, 'kind': 'base', 'item_id': iid,
                     'seed': bases[iid]['seed'],
                     'model_family': bases[iid]['model_family'],
                     'success': resp.success, 'parsed': parse(resp.content)})
        RESULTS.write_text(json.dumps({'items': rows}, indent=1,
                                      ensure_ascii=False))
        print(json.dumps({'base': iid[:12],
                          'defect_free': None if not rows[-1]['parsed']
                          else rows[-1]['parsed']['defect_free'],
                          'spent_usd': round(total, 6)}), flush=True)
    for iid in sample['pair_ids']:
        for side in ('before', 'after'):
            key = f'gate2/pair/{iid}/{side}'
            if key in done:
                rows.append(done[key])
                continue
            resp, total = call(key, spec,
                               gate_render(pairs[iid][f'{side}_trace']),
                               cap, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            rows.append({'key': key, 'kind': 'pair', 'item_id': iid,
                         'side': side,
                         'fault': pairs[iid].get('spotcheck_fault_type'),
                         'success': resp.success, 'parsed': parse(resp.content)})
            RESULTS.write_text(json.dumps({'items': rows}, indent=1,
                                          ensure_ascii=False))
    RESULTS.write_text(json.dumps({'items': rows}, indent=1,
                                  ensure_ascii=False))
    print(json.dumps({'items': len(rows),
                      'spent_usd': round(spent(), 8)}, indent=1))


def report():
    allrows = json.loads(RESULTS.read_text())['items']
    rows = [r for r in allrows if r.get('success') and r.get('parsed')]
    bases = [r for r in rows if r['kind'] == 'base']
    pairs = [r for r in rows if r['kind'] == 'pair']
    total = spent()
    lines = ['# Injection screening with the decisive-clause gate — pilot\n',
             f"Amendment `GATE_AMENDMENT_V2.md` (sha256 "
             f"`{file_sha(AMENDMENT)[:12]}`), prompt "
             f"`screening_prompt_v2.json` (sha256 `{file_sha(PROMPT)[:12]}`). "
             f"Same 48-base / 6-pair sample as the v1 gate; spend "
             f"${total:.6f}.\n",
             'The earlier evidence-only gate (`screening_prompt_v1.json`) and '
             'its negative result stay on record in `../20261113_injection_screening/report.md`. '
             'This run judges the decisive clause rather than the whole support '
             'paragraph.\n']
    if bases:
        n_all = sum(r['kind'] == 'base' for r in allrows)
        nunp = n_all - len(bases)
        k = sum(r['parsed']['defect_free'] for r in bases)
        lo, hi = cp_ci(k, len(bases))
        if nunp:
            lines += [f'{nunp} of {n_all} base calls returned no parseable '
                      'object; they are excluded from the pass rate and count '
                      'as gate failures when screening.\n']
        lines += [f'**Bases defect-free (decisive-clause gate):** {k}/{len(bases)} '
                  f'({100*k/len(bases):.1f}%, 95% CI {100*lo:.1f}-{100*hi:.1f}%).\n',
                  '| cell | n | defect-free | defective |',
                  '| --- | ---: | ---: | ---: |']
        for cell in sorted({(r['seed'], r['model_family']) for r in bases}):
            sub = [r for r in bases if (r['seed'], r['model_family']) == cell]
            c = sum(r['parsed']['defect_free'] for r in sub)
            lines.append(f'| {cell[0]}:{cell[1]} | {len(sub)} | {c} | '
                         f'{len(sub)-c} |')
        lines.append('')
    if pairs:
        lines += ['**Injected pairs** (before defect-free, after not):\n',
                  '| item | fault | before | after | gate |',
                  '| --- | --- | --- | --- | --- |']
        passed = agg = 0
        for iid in sorted({r['item_id'] for r in pairs}):
            b = next((r for r in pairs if r['item_id'] == iid
                      and r['side'] == 'before'), None)
            a = next((r for r in pairs if r['item_id'] == iid
                      and r['side'] == 'after'), None)
            bv = None if not b else b['parsed']['defect_free']
            av = None if not a else a['parsed']['defect_free']
            fault = a.get('fault') if a else ''
            if fault == 'aggregation':
                agg += 1
                vs = 'board unchanged'
            else:
                ok = bv is True and av is False
                passed += ok
                vs = 'pass' if ok else 'fail'
            lines.append(f'| {iid[:12]} | {fault} | {bv} | {av} | {vs} |')
        n = len({r['item_id'] for r in pairs}) - agg
        lo, hi = cp_ci(passed, n)
        lines += ['', f'Evidence-fault pairs passing: **{passed}/{n}** '
                      f'({100*passed/n:.1f}%, 95% CI {100*lo:.1f}-{100*hi:.1f}%); '
                      f'{agg} aggregation pair cannot be confirmed by an '
                      f'evidence-only gate (board unchanged by design).\n']
    if MANUAL.exists():
        man = json.loads(MANUAL.read_text())['items']
        mb = [m for m in man if m['kind'] == 'base']
        by_id = {r['item_id']: r for r in bases}
        agree = 0
        lines += ['## Spot-check against real content\n',
                  '| item | hand | gate v2 | agrees | note |',
                  '| --- | --- | --- | --- | --- |']
        for m in mb:
            r = by_id.get(m['item_id'])
            g = None if not r else ('defect_free' if r['parsed']['defect_free']
                                    else 'defect_present')
            ok = g == m['hand']
            agree += ok
            lines.append(f"| {m['item_id'][:12]} | {m['hand']} | {g} | "
                         f"{'yes' if ok else 'no'} | {m['note'][:70]} |")
        lines += ['', f'Base spot-check agreement: **{agree}/{len(mb)}** '
                      '(hand labels reused from the v1 screening run; same '
                      'rendered content).\n']
    lines += ['## Reading\n',
              'The gate confirms a base clean when every support that carries a '
              'decisive clause for the question appears at both checkpoints; '
              'pure background supports are marked `not_required`. A base with '
              'a real missing fact (e.g. the Malko Tarnovo municipality link) '
              'stays defective.\n',
              'The decisive-clause unit raises the base rate from the v1 gate '
              '(4/47, 8.5%) to 13/46 (28.3%) and the hand agreement from 2/6 to '
              '4/6, but it is not yet a reliable screen. Both remaining false '
              'defects come from a support that the hand reads as a distractor '
              'being marked `required`: ef980c2a1d19 s3 (the USS Sanderling '
              'ship) and d57d523a9e33 s1/s4 (the prompt asks for the 1642 date '
              'and the author-citizenship link, which the hand treats as '
              'secondary). The gate also passes only 1 of 5 evidence-fault '
              'pairs (8386de13b9f5, the date distortion).\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'bases': len(bases), 'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.gate:
        gate(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()