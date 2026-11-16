"""Injection screening: labeller gate on wave-2 bases and injected pairs.

Rule: `rebuttal/pilots/20261113_injection_screening/SCREENING_RULE.md`, frozen
before any call. Frozen labeller v2; pilot cap $5; every call logged.

    ./run.sh python -m scripts.injection_screening --build
    ./run.sh python -m scripts.injection_screening --pilot --cap-usd 5
    ./run.sh python -m scripts.injection_screening --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, render
from scripts.repilot_llm_labeller_v2 import load_prompt, parse_last
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_injection_screening'
RULE = OUT / 'SCREENING_RULE.md'
BASES = ROOT / 'rebuttal/pilots/20261110_e2a_wave2/judge_input_traces.jsonl'
PAIRS = ROOT / 'rebuttal/annotation/packets_20261110/E2A_wave2_spot/packet.jsonl'
PROMPT = ROOT / 'rebuttal/pilots/20261112_labeller/labeller_prompt_v2.json'
PROMPT_MANIFEST = ROOT / 'rebuttal/pilots/20261112_labeller/labeller_prompt_v2.manifest.json'
SAMPLE = OUT / 'sample.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
MANUAL = OUT / 'spotcheck_manual.json'
REPORT = OUT / 'report.md'
GATE_PROMPT = OUT / 'screening_prompt_v1.json'
GATE_AMENDMENT = OUT / 'GATE_AMENDMENT_V1.md'
GATE_MANIFEST = OUT / 'gate_manifest.json'
GATE_RESULTS = OUT / 'gate_results.json'
SEED = 43
PER_CELL = 8
MAX_TOKENS = 800


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_bases():
    return [json.loads(l) for l in BASES.read_text().splitlines() if l.strip()]


def load_pairs():
    return [json.loads(l) for l in PAIRS.read_text().splitlines() if l.strip()]


def sample_bases():
    rows = load_bases()
    cells = {}
    for r in rows:
        cells.setdefault((r['seed'], r['model_family']), []).append(r)
    picked = []
    for cell in sorted(cells):
        rs = sorted(cells[cell], key=lambda r: sha(f'{SEED}|{r["item_id"]}'))
        picked.extend(rs[:PER_CELL])
    assert len(picked) == PER_CELL * len(cells), len(picked)
    return picked


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
                            'model': spec['model'], 'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'injection_screening', 'key': key,
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


def build():
    picked = sample_bases()
    pairs = load_pairs()
    spec = load_prompt()
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps({
        'seed': SEED, 'per_cell': PER_CELL,
        'base_ids': [r['item_id'] for r in picked],
        'pair_ids': [r['item_id'] for r in pairs]}, indent=1))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'bases_sha256': file_sha(BASES), 'pairs_sha256': file_sha(PAIRS),
        'prompt_file_sha256': file_sha(PROMPT),
        'prompt_system_sha256': sha(spec['system']),
        'sample_sha256': file_sha(SAMPLE),
        'prompt_version': spec['version'], 'model': spec['model'],
        'temperature': 0, 'seed': SEED,
    }, indent=1))
    print(json.dumps({'bases': len(picked), 'pairs': len(pairs),
                      'cells': {f'{s}:{m}': sum(r['seed'] == s and r['model_family'] == m
                                                for r in picked)
                                for s, m in sorted({(r['seed'], r['model_family'])
                                                    for r in picked})}}, indent=1))


def pilot(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(PROMPT) == man['prompt_file_sha256']
    assert file_sha(BASES) == man['bases_sha256']
    assert file_sha(PAIRS) == man['pairs_sha256']
    spec = load_prompt()
    sample = json.loads(SAMPLE.read_text())
    bases = {r['item_id']: r for r in load_bases()}
    pairs = {r['item_id']: r for r in load_pairs()}
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['items']}
    rows = []
    for iid in sample['base_ids']:
        key = f'base/{iid}'
        if key in done:
            rows.append(done[key])
            continue
        row = bases[iid]
        resp, total = call(key, spec, render({'trace': row['trace']}), cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        parsed = parse_last(resp.content or '')
        rows.append({'key': key, 'kind': 'base', 'item_id': iid,
                     'seed': row['seed'], 'model_family': row['model_family'],
                     'success': resp.success, 'parsed': parsed})
        RESULTS.write_text(json.dumps({'items': rows}, indent=1, ensure_ascii=False))
    for iid in sample['pair_ids']:
        for side in ('before', 'after'):
            key = f'pair/{iid}/{side}'
            if key in done:
                rows.append(done[key])
                continue
            row = pairs[iid]
            resp, total = call(key, spec, render({'trace': row[f'{side}_trace']}),
                               cap, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            parsed = parse_last(resp.content or '')
            rows.append({'key': key, 'kind': 'pair', 'item_id': iid, 'side': side,
                         'fault': row.get('spotcheck_fault_type'),
                         'success': resp.success, 'parsed': parsed})
            RESULTS.write_text(json.dumps({'items': rows}, indent=1, ensure_ascii=False))
    RESULTS.write_text(json.dumps({'items': rows}, indent=1, ensure_ascii=False))
    print(json.dumps({'items': len(rows), 'spent_usd': round(total, 8)}, indent=1))


def verdict(rec):
    p = rec.get('parsed')
    return None if not p else p.get('verdict')


def gate_render(trace):
    sup = [f"[s{i}] {s['text'][:6000]}"
           for i, s in enumerate(trace.get('source_supports') or [], 1)]
    pool = [f"{u['unit_id']} [agent={u['agent_id']}]: {u['text'][:1200]}"
            for u in (trace.get('checkpoints') or {}).get('extraction') or []]
    board = [f"{u['unit_id']} [agent={u['agent_id']}]: {u['text'][:1200]}"
             for u in (trace.get('checkpoints') or {}).get('board') or []]
    return (f"QUESTION\n{trace['question']}\n\nCRITICAL FACTS\n" + '\n'.join(sup)
            + "\n\nEXTRACTION POOL\n" + '\n'.join(pool)
            + "\n\nBOARD\n" + '\n'.join(board))


def gate_parse(raw):
    d = last_object(raw or '')
    if not isinstance(d, dict) or not isinstance(d.get('supports'), list):
        return None
    allowed = {'present', 'partial', 'distorted', 'absent'}
    rows = []
    for r in d['supports']:
        if not isinstance(r, dict):
            return None
        p, b = str(r.get('pool', '')).lower(), str(r.get('board', '')).lower()
        if p not in allowed or b not in allowed:
            return None
        rows.append({'id': str(r.get('id') or ''), 'pool': p, 'board': b,
                     'unit_ids': r.get('unit_ids') or [],
                     'reason': str(r.get('reason') or '')[:200]})
    complete = bool(rows) and all(r['pool'] == 'present' and r['board'] == 'present'
                                  for r in rows)
    return {'supports': rows, 'defect_free': complete,
            'declared': d.get('defect_free')}


def gate(cap):
    assert GATE_PROMPT.exists() and GATE_AMENDMENT.exists()
    spec = json.loads(GATE_PROMPT.read_text())
    sample = json.loads(SAMPLE.read_text())
    bases = {r['item_id']: r for r in load_bases()}
    pairs = {r['item_id']: r for r in load_pairs()}
    GATE_MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'amendment_sha256': file_sha(GATE_AMENDMENT),
        'prompt_file_sha256': file_sha(GATE_PROMPT),
        'system_sha256': sha(spec['system']),
        'sample_sha256': file_sha(SAMPLE),
        'model': spec['model'], 'temperature': 0,
    }, indent=1))
    total = spent()
    done = {}
    if GATE_RESULTS.exists():
        done = {r['key']: r for r in json.loads(GATE_RESULTS.read_text())['items']}
    rows = []
    for iid in sample['base_ids']:
        key = f'gate/base/{iid}'
        if key in done:
            rows.append(done[key])
            continue
        resp, total = call(key, spec, gate_render(bases[iid]['trace']), cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        rows.append({'key': key, 'kind': 'base', 'item_id': iid,
                     'seed': bases[iid]['seed'],
                     'model_family': bases[iid]['model_family'],
                     'success': resp.success, 'parsed': gate_parse(resp.content)})
        GATE_RESULTS.write_text(json.dumps({'items': rows}, indent=1, ensure_ascii=False))
    for iid in sample['pair_ids']:
        for side in ('before', 'after'):
            key = f'gate/pair/{iid}/{side}'
            if key in done:
                rows.append(done[key])
                continue
            resp, total = call(key, spec, gate_render(pairs[iid][f'{side}_trace']),
                               cap, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            rows.append({'key': key, 'kind': 'pair', 'item_id': iid, 'side': side,
                         'fault': pairs[iid].get('spotcheck_fault_type'),
                         'success': resp.success, 'parsed': gate_parse(resp.content)})
            GATE_RESULTS.write_text(json.dumps({'items': rows}, indent=1,
                                               ensure_ascii=False))
    GATE_RESULTS.write_text(json.dumps({'items': rows}, indent=1, ensure_ascii=False))
    print(json.dumps({'items': len(rows), 'spent_usd': round(total, 8)}, indent=1))


def report():
    total = spent()
    lines = ['# Injection screening with the labeller gate — pilot\n',
             f"Rule `SCREENING_RULE.md` (sha256 `{file_sha(RULE)[:12]}`); gate "
             f"amendment `GATE_AMENDMENT_V1.md` (sha256 "
             f"`{file_sha(GATE_AMENDMENT)[:12]}`). Spend ${total:.6f}.\n"]
    if RESULTS.exists():
        v2 = [r for r in json.loads(RESULTS.read_text())['items'] if r.get('success')]
        vb = [r for r in v2 if r['kind'] == 'base']
        vp = [r for r in v2 if r['kind'] == 'pair']
        lines += ['**Superseded v2 pass.** v2 called '
                  f"{sum(verdict(r) == 'CORRECT' for r in vb)}/{len(vb)} bases "
                  f"CORRECT and {sum(verdict(r) == 'CORRECT' for r in vp)}/{len(vp)} "
                  'pair sides CORRECT. Its CORRECT is answer-based, so it cannot '
                  'certify a base defect-free; these calls stay on record and are '
                  'not the gate result.\n']
    rows = []
    if GATE_RESULTS.exists():
        rows = [r for r in json.loads(GATE_RESULTS.read_text())['items']
                if r.get('success') and r.get('parsed')]
    bases = [r for r in rows if r['kind'] == 'base']
    pairs = [r for r in rows if r['kind'] == 'pair']
    if GATE_RESULTS.exists():
        allg = json.loads(GATE_RESULTS.read_text())['items']
        nunp = sum(1 for r in allg if r['kind'] == 'base'
                   and r.get('success') and not r.get('parsed'))
        if nunp:
            lines += [f'One base call returned no parseable object ({nunp} of 48); '
                      'it is excluded from the pass rate and counted as a gate '
                      'failure when screening.\n']
    if bases:
        k = sum(r['parsed']['defect_free'] for r in bases)
        lo, hi = cp_ci(k, len(bases))
        lines += [f'**Bases defect-free (evidence-only gate):** {k}/{len(bases)} '
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
        ids = sorted({r['item_id'] for r in pairs})
        passed = 0
        agg = 0
        for iid in ids:
            b = next((r for r in pairs if r['item_id'] == iid and r['side'] == 'before'), None)
            a = next((r for r in pairs if r['item_id'] == iid and r['side'] == 'after'), None)
            bv = None if not b else b['parsed']['defect_free']
            av = None if not a else a['parsed']['defect_free']
            fault = a.get('fault') if a else ''
            ok = bv is True and av is False
            if fault == 'aggregation':
                agg += 1
                verdict_s = 'board unchanged'
            else:
                passed += ok
                verdict_s = 'pass' if ok else 'fail'
            lines.append(f"| {iid[:12]} | {fault} | {bv} | {av} | {verdict_s} |")
        evidence_n = len(ids) - agg
        lo, hi = cp_ci(passed, evidence_n)
        lines += ['', f'Evidence-fault pairs passing: **{passed}/{evidence_n}** '
                      f'({100*passed/evidence_n:.1f}%, 95% CI {100*lo:.1f}-'
                      f'{100*hi:.1f}%); {agg} aggregation pair(s) cannot be '
                      'confirmed by an evidence-only gate (board unchanged by '
                      'design).\n']
    if MANUAL.exists():
        man = json.loads(MANUAL.read_text())['items']
        mb = [m for m in man if m['kind'] == 'base']
        mp = [m for m in man if m['kind'] == 'pair']
        bagree = sum(m['hand'] == m.get('labeller') for m in mb)
        confirm = [m for m in mp if m.get('confirmable')]
        pagree = sum(m.get('hand_before') is True and m.get('hand_after') is False
                     and m.get('gate_before') is True and m.get('gate_after') is False
                     for m in confirm)
        lines += ['## Spot-check against the real content\n',
                  f'Base items agreeing: **{bagree}/{len(mb)}**. '
                  f'Evidence-fault pairs agreeing: **{pagree}/{len(confirm)}**; '
                  f'{len(mp)-len(confirm)} pair(s) not confirmable by an evidence-only gate.\n',
                  '| item | kind | hand | gate | agrees |',
                  '| --- | --- | --- | --- | --- |']
        for m in mb:
            lines.append(f"| {m['item_id'][:12]} | base | {m['hand']} | "
                         f"{m.get('labeller')} | "
                         f"{'yes' if m['hand'] == m.get('labeller') else 'no'} |")
        for m in mp:
            hand = f"before {'free' if m['hand_before'] else 'defect'}, after " \
                   f"{'free' if m['hand_after'] else 'defect'}"
            gat = f"before {'free' if m.get('gate_before') else 'defect'}, after " \
                  f"{'free' if m.get('gate_after') else 'defect'}"
            ok = (m.get('hand_before') is True and m.get('hand_after') is False
                  and m.get('gate_before') is True and m.get('gate_after') is False)
            verdict_s = ('yes' if ok else
                         ('not confirmable' if not m.get('confirmable') else 'no'))
            lines.append(f"| {m['item_id'][:12]} | {m['fault']} | {hand} | {gat} | "
                         f"{verdict_s} |")
        lines += ['', 'Notes:\n']
        for m in man:
            lines.append(f"- {m['item_id'][:12]} ({m['kind']}): {m.get('note','')}")
        lines.append('')
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'gated_bases': len(bases), 'gated_pairs': len(pairs),
                      'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd)
    if a.gate:
        gate(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()