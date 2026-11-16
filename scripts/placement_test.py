"""Placement test v1: same corrective unit at the target agent vs a hash agent.

Pre-registration: `rebuttal/pilots/prereg/PLACEMENT-TEST-v1.md`, frozen with
its own action manifest before any placement call.

    ./run.sh python -m scripts.placement_test --build
    ./run.sh python -m scripts.placement_test --label --cap-usd 5
    ./run.sh python -m scripts.placement_test --pilot --cap-usd 5
    ./run.sh python -m scripts.placement_test --report
"""
import argparse
import glob
import hashlib
import json
import math
import re
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT, render
from scripts.repilot_llm_labeller_v2 import load_prompt, parse_last
from scripts.answer_equiv import last_object
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_placement'
PREREG = ROOT / 'rebuttal/pilots/prereg/PLACEMENT-TEST-v1.md'
TRACE_GLOB = str(ROOT / 'rebuttal/results/batch1/E4P_seed43/*/traces/*.json')
ACTIONS = OUT / 'action_manifest.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
LABELS = OUT / 'labels.json'
SPOT = OUT / 'spotcheck_manual.json'
PLACEMENT = OUT / 'placement_results.json'
REPORT = OUT / 'report.md'
SEED = 43
PILOT_N = 6
MAX_TOKENS = 1024
LABEL_TOKENS = 800


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def traces():
    out = []
    for p in sorted(glob.glob(TRACE_GLOB)):
        t = json.loads(Path(p).read_text())
        t['_path'] = p
        out.append(t)
    assert len(out) == 78, len(out)
    return out


def target_agent(t):
    scores = t.get('scores') or []
    best, at = None, 0
    for i, units in enumerate(scores):
        vals = [u.get('composite') for u in units or [] if isinstance(u, dict)]
        m = max(vals) if vals else -1
        if best is None or m > best:
            best, at = m, i
    return at, (not scores)


def hash_agent(t, target):
    others = sorted(a for a in range(int(t['n_agents'])) if a != target)
    return min(others, key=lambda a: sha(f'43|{t["trace_id"]}|{a}'))


def insert_text(t, agent):
    supports = {s.get('agent_id'): s.get('text', '') for s in t.get('source_supports') or []}
    text = supports.get(agent, '')
    for pat in (rf'^Agent {agent} holds.*$', rf'^You \(Agent {agent}\) hold.*$',
                rf'^The agent at position {agent} holds.*$',
                rf'^\*\*Your Data \(Position {agent}\)[^\n]*\*\*\n([^\n]+)'):
        m = re.search(pat, text, flags=re.M)
        if m:
            return (m.group(1) if m.lastindex else m.group(0)).strip(), False
    return text[:400], True


def build():
    rows = traces()
    acts = []
    for t in rows:
        tgt, tf = target_agent(t)
        hsh = hash_agent(t, tgt)
        text, xf = insert_text(t, tgt)
        acts.append({'trace_id': t['trace_id'], 'instance_id': t['instance_id'],
                     'model': t['model'], 'gold_answer': t['gold_answer'],
                     'base_correct': bool(t['answer_matches_gold']),
                     'board_sha256': sha(json.dumps(t['board_units'], sort_keys=True)),
                     'target_agent': tgt, 'hash_agent': hsh,
                     'target_fallback': tf, 'text_fallback': xf,
                     'inserted_text': text})
    OUT.mkdir(parents=True, exist_ok=True)
    ACTIONS.write_text(json.dumps({'prereg': str(PREREG.relative_to(ROOT)),
                                   'seed': SEED, 'actions': acts},
                                  indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'prereg_sha256': file_sha(PREREG),
        'actions_sha256': file_sha(ACTIONS),
        'traces_sha256': sha(''.join(sorted(file_sha(t['_path']) for t in rows))),
        'seed': SEED, 'pilot_n': PILOT_N,
        'aggregation_system_sha256': sha(_AGGREGATION_SYSTEM),
        'labeller_file_sha256': file_sha(
            ROOT / 'rebuttal/pilots/20261112_labeller/labeller_prompt_v2.json'),
        'temperature': 0,
    }, indent=1))
    print(json.dumps({'traces': len(acts),
                      'target_fallback': sum(a['target_fallback'] for a in acts),
                      'text_fallback': sum(a['text_fallback'] for a in acts),
                      'base_correct': sum(a['base_correct'] for a in acts)},
                     indent=1))


def call(key, model, system, user, max_tokens, cap, total, phase, extra=None):
    pin, pout = (PRICE_IN, PRICE_OUT) if model == MODEL_OPENROUTER else price(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + max_tokens * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'phase': phase, 'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, model, system, user, str(max_tokens)]))
    rec = {'event': 'intent', 'key': key, 'call_id': call_id, 'model': model,
           'phase': phase, 'system_sha256': sha(system), 'user_sha256': sha(user),
           'max_tokens': max_tokens, 'temperature': 0}
    rec.update(extra or {})
    with CALLS.open('a') as f:
        f.write(json.dumps(rec) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=max_tokens, temperature=0,
                     metadata={'pilot': 'placement_test', 'key': key,
                               'phase': phase, 'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    rec = {'event': 'result', 'key': key, 'call_id': call_id, 'model': model,
           'phase': phase, 'success': resp.success, 'error': resp.error,
           'content': resp.content, 'usage': usage, 'cost_usd': round(cost, 8)}
    rec.update(extra or {})
    with CALLS.open('a') as f:
        f.write(json.dumps(rec) + '\n')
    return resp, total + cost


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def label(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(PREREG) == man['prereg_sha256']
    assert file_sha(ACTIONS) == man['actions_sha256']
    spec = load_prompt()
    total = spent()
    done = {}
    if LABELS.exists():
        done = {r['trace_id']: r for r in json.loads(LABELS.read_text())['traces']}
    out = list(done.values())
    for t in traces():
        if t['trace_id'] in done:
            continue
        resp, total = call(f'label/{t["trace_id"]}', MODEL_OPENROUTER,
                           spec['system'], render({'trace': t}), LABEL_TOKENS,
                           cap, total, 'label',
                           {'instance_id': t['instance_id'], 'model': t['model']})
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
            break
        p = parse_last(resp.content or '')
        out.append({'trace_id': t['trace_id'], 'instance_id': t['instance_id'],
                    'model': t['model'], 'base_correct': bool(t['answer_matches_gold']),
                    'success': resp.success, 'parsed': p})
        LABELS.write_text(json.dumps({'traces': out}, indent=1, ensure_ascii=False))
        print(json.dumps({'trace': t['instance_id'], 'model': t['model'],
                          'verdict': None if not p else p['verdict'],
                          'spent_usd': round(total, 6)}), flush=True)
    LABELS.write_text(json.dumps({'traces': out}, indent=1, ensure_ascii=False))
    print(json.dumps({'labelled': len(out), 'spent_usd': round(total, 8)}, indent=1))


def pilot(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(PREREG) == man['prereg_sha256']
    assert file_sha(ACTIONS) == man['actions_sha256']
    acts = {a['trace_id']: a for a in json.loads(ACTIONS.read_text())['actions']}
    labels = {r['trace_id']: r for r in json.loads(LABELS.read_text())['traces']}
    by = {}
    for tid, r in labels.items():
        if not r.get('base_correct') and (r.get('parsed') or {}).get('verdict') == 'DEFECT':
            by.setdefault(r['model'].split('/')[0], []).append(tid)
    picked = []
    for fam in sorted(by):
        ids = sorted(by[fam], key=lambda x: sha(f'43|pilot|{x}'))
        picked.extend(ids[:2])
    picked = picked[:PILOT_N]
    assert len(picked) == PILOT_N, (len(picked), {k: len(v) for k, v in by.items()})
    tr = {t['trace_id']: t for t in traces()}
    total = spent()
    results = []
    for tid in picked:
        a = acts[tid]
        t = tr[tid]
        for arm, agent in (('target', a['target_agent']), ('hash', a['hash_agent'])):
            unit = {'unit_id': f'P-{arm[0]}:{agent}', 'agent_id': agent,
                    'text': a['inserted_text']}
            units = list(t['board_units']) + [unit]
            n = max(int(u['agent_id']) for u in units) + 1
            grouped = [[] for _ in range(n)]
            for u in units:
                grouped[int(u['agent_id'])].append(str(u['text']))
            user = _build_evidence_board_prompt(grouped, t['question'])
            resp, total = call(f'placement/{tid}/{arm}', t['model'],
                               _AGGREGATION_SYSTEM, user, MAX_TOKENS, cap, total,
                               'placement', {'instance_id': t['instance_id'],
                                             'arm': arm, 'agent': agent})
            if resp is None:
                print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                break
            pred = extract_answer(resp.content or '')
            ok = bool(silobench_exact_match(pred, {'answer': t['gold_answer']}))
            results.append({'trace_id': tid, 'instance_id': t['instance_id'],
                            'model': t['model'], 'arm': arm, 'agent': agent,
                            'success': resp.success, 'prediction': pred,
                            'correct': ok,
                            'inserted_text': a['inserted_text']})
            PLACEMENT.write_text(json.dumps({'pilot': picked, 'calls': results},
                                            indent=1, ensure_ascii=False))
    PLACEMENT.write_text(json.dumps({'pilot': picked, 'calls': results},
                                    indent=1, ensure_ascii=False))
    print(json.dumps({'pilot': picked, 'calls': len(results),
                      'spent_usd': round(total, 8)}, indent=1))


def report():
    labels = json.loads(LABELS.read_text())['traces']
    n = len(labels)
    defect = sum((r.get('parsed') or {}).get('verdict') == 'DEFECT' for r in labels)
    correct = sum((r.get('parsed') or {}).get('verdict') == 'CORRECT' for r in labels)
    unparsed = n - defect - correct
    lo, hi = cp_ci(defect, n)
    total = spent()
    lines = ['# Placement test v1 — labelling and pilot\n',
             f"Pre-registration `prereg/PLACEMENT-TEST-v1.md` (sha256 "
             f"`{file_sha(PREREG)[:12]}`); action manifest "
             f"`{file_sha(ACTIONS)[:12]}`. Spend ${total:.6f}.\n",
             'Labels use the frozen **validated** labeller v2: '
             '`rebuttal/pilots/20261112_labeller/labeller_prompt_v2.json`, file '
             'sha256 `7f9e2816…8268c6`, system sha256 `585d0d45…b8e6e`. It was '
             'validated on 150 author-labelled traces (agreement 0.953, 95% CI '
             '0.913-0.987; kappa 0.878, 0.760-0.965; '
             '`rebuttal/pilots/20261112_labeller_v2_full/full_report.md`). The '
             'labeller screens for evidence flow only; answer correctness below '
             'is the frozen exact rule.\n',
             f'**Labelled traces:** {n}/78; DEFECT {defect}/{n} '
             f'({100*defect/n:.1f}%, 95% CI {100*lo:.1f}-{100*hi:.1f}%), '
             f'CORRECT {correct}, unparsed {unparsed}.\n',
             '| model | n | DEFECT | CORRECT |',
             '| --- | ---: | ---: | ---: |']
    for fam in sorted({r['model'].split('/')[0] for r in labels}):
        sub = [r for r in labels if r['model'].split('/')[0] == fam]
        d = sum((r.get('parsed') or {}).get('verdict') == 'DEFECT' for r in sub)
        c = sum((r.get('parsed') or {}).get('verdict') == 'CORRECT' for r in sub)
        lines.append(f'| {fam} | {len(sub)} | {d} | {c} |')
    lines.append('')
    if SPOT.exists():
        items = json.loads(SPOT.read_text())['items']
        agree = sum(1 for m in items if m.get('labeller') == m.get('hand'))
        lo, hi = cp_ci(agree, len(items))
        lines += [f'**Spot-check agreement:** {agree}/{len(items)} '
                  f'({100*agree/len(items):.1f}%, exact Clopper-Pearson 95% CI '
                  f'{100*lo:.1f}-{100*hi:.1f}%). The hand labels were read by the '
                  'worker (this assistant) from each rendered trace, without a '
                  'model; selection was 4 CORRECT and 6 DEFECT-and-wrong traces, '
                  'by `sha256("43|spot|" + trace_id)` within each stratum.\n',
                  '| trace | model | hand | labeller | agrees |',
                  '| --- | --- | --- | --- | --- |']
        for m in items:
            lines.append(f"| {m['instance_id']} | {m['model'].split('/')[0]} | "
                         f"{m['hand']} | {m.get('labeller')} | "
                         f"{'yes' if m['hand'] == m.get('labeller') else 'no'} |")
        lines.append('')
    if PLACEMENT.exists():
        d = json.loads(PLACEMENT.read_text())
        calls = d['calls']
        acts = {a['trace_id']: a for a in json.loads(ACTIONS.read_text())['actions']}
        lines += ['## Placement pilot\n',
                  '| trace | model | base | target agent | hash agent | target | hash |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
        for tid in d['pilot']:
            sub = [c for c in calls if c['trace_id'] == tid]
            tgt = next((c for c in sub if c['arm'] == 'target'), None)
            hsh = next((c for c in sub if c['arm'] == 'hash'), None)
            if not tgt or not hsh:
                lines.append(f"| {tid[:8]} |  |  |  |  |  |  |")
                continue
            lines.append(f"| {tgt['instance_id']} | {tgt['model'].split('/')[0]} | "
                         f"{'yes' if acts[tid]['base_correct'] else 'no'} | "
                         f"{tgt['agent']} | {hsh['agent']} | "
                         f"{'yes' if tgt['correct'] else 'no'} | "
                         f"{'yes' if hsh['correct'] else 'no'} |")
        ct = sum(c['correct'] for c in calls if c['arm'] == 'target')
        ch = sum(c['correct'] for c in calls if c['arm'] == 'hash')
        nt = sum(c['arm'] == 'target' for c in calls)
        nh = sum(c['arm'] == 'hash' for c in calls)
        uniq = len({c['instance_id'] for c in calls})
        lines += ['', f'Target exact **{ct}/{nt}**, hash exact **{ch}/{nh}**; '
                      f'paired difference {ct-ch:+d} at n={min(nt, nh)} '
                      f'(**descriptive only**, no population claim). The six '
                      f'piloted traces are {uniq} unique instances: III-27 and '
                      'III-28 each appear on two models. Many arms answered '
                      '"Insufficient information", so one inserted line did not '
                      'restore the evidence absent from the base trace.\n']
        for c in calls:
            lines.append(f"- {c['instance_id']} / {c['arm']}: "
                         f"{'correct' if c['correct'] else 'wrong'} — "
                         f"`{str(c['prediction'])[:120]}`")
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': n, 'defect': defect, 'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--label', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.label:
        label(a.cap_usd)
    if a.pilot:
        pilot(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()