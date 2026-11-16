"""Gold-side re-score of the 30-case proxy set (20261115_q1_second_sample), with a paper-model labeller.

Only the gold side is re-labelled. The gold atoms and the atom-level point prompt (`per_fact_points_prompt_v1.json`,
unchanged) are the same as in the earlier run. The labeller is google/gemini-3.6-flash (paper model); the reference
is claude-opus-5-5 through the claude CLI (same transport as `scripts/part_b_step2_cli.py`). The proxy side keeps its
earlier labels (Claude Haiku 5.5, disclosed).

Stage rule (unchanged): extraction if any gold atom is absent at extraction; else transmission if any atom is absent
at the board; else aggregation. The board is only labelled when the extraction check finds no absent atom.

    ./.conda-env/bin/python -m scripts.gold_side_rescore --pilot    # 5 traces, cap $0.10
    ./.conda-env/bin/python -m scripts.gold_side_rescore --full     # all 30 traces, cap $0.50
    ./.conda-env/bin/python -m scripts.gold_side_rescore --score
"""
import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

import scripts.q1_second_sample as S
from scripts.per_fact_points_run import parse
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261116_gold_rescore'
PROMPT = S.PROMPT
RUN_IDS = S.OUT / 'results.jsonl'          # earlier run: gold and proxy stages (Haiku)
GEM = 'google/gemini-3.6-flash'
OPUS_CLI = 'claude-opus-5-5'
GEM_PRICE = (0.75 / 1e6, 3.75 / 1e6)
OPUS_PRICE = (4.0 / 1e6, 20.0 / 1e6)
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')
PILOT_CAP = 0.10
FULL_CAP = 0.50
PILOT_N = 5
OPUS_N = 8   # Opus reference on the first 8 traces only: ~$0.03 per Opus call (CLI, cache creation counted)
MAX_TOK = 4096
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
MANIFEST = OUT / 'build_manifest.json'


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def traces():
    """The 30 traces of the earlier run, with their population rows, in run order."""
    seen = []
    for l in RUN_IDS.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            if r['instance'] not in seen:
                seen.append(r['instance'])
    pop = {r['instance_id']: r for r in json.loads((S.MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    return [pop[i] for i in seen]


def atoms_for(t):
    gold = (t.get('gold_supports') or [{'text': ''}])[0]['text']
    return gold, [(f'a{i}', a) for i, a in enumerate(S.atoms_of(gold), 1)]


def user_for(spec, t, gold, atoms, cp):
    return spec['user'].format(question=t['question'], fact=gold,
                               atoms='\n'.join(f'{a}: {x}' for a, x in atoms),
                               entries='\n'.join(f"[{u['unit_id']}] (agent {u['agent_id']}) {u['text'][:1500]}"
                                                 for u in t['checkpoints'].get(cp) or []))


def est_out(atoms):
    return min(MAX_TOK, 120 + 28 * len(atoms))


def log(rec):
    with CALLS.open('a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def call_gem(key, spec, user, atoms, total, cap):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * GEM_PRICE[0] + est_out(atoms) * GEM_PRICE[1]
    if total + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'estimate_usd': est})
        return 'SKIP', total
    log({'event': 'intent', 'key': key, 'model': GEM})
    resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=GEM,
                                     max_tokens=MAX_TOK, temperature=0,
                                     metadata={'pilot': 'gold_rescore', 'key': key}))
    u = resp.usage or {}
    cost = u.get('prompt_tokens', est_in) * GEM_PRICE[0] + u.get('completion_tokens', 0) * GEM_PRICE[1]
    log({'event': 'result', 'key': key, 'model': GEM, 'success': resp.success, 'error': resp.error,
         'content': resp.content, 'usage': u, 'cost_usd': round(cost, 8)})
    return resp.content if resp.success else None, total + cost


def call_opus(key, spec, user, atoms, total, cap, tmp):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * OPUS_PRICE[0] + est_out(atoms) * OPUS_PRICE[1]
    if total + est > cap:
        log({'event': 'skipped', 'key': key, 'reason': 'cap', 'estimate_usd': est})
        return 'SKIP', total
    sp = tmp / 'system.txt'
    sp.write_text(spec['system'])
    log({'event': 'intent', 'key': key, 'model': OPUS_CLI, 'transport': 'claude-cli'})
    cmd = ['claude', '-p', user, '--output-format', 'json', '--model', OPUS_CLI,
           '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
           '--disallowedTools', TOOLS_OFF]
    p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
    try:
        obj = json.loads(p.stdout)
    except json.JSONDecodeError:
        log({'event': 'result', 'key': key, 'model': OPUS_CLI, 'success': False,
             'error': p.stderr[-300:], 'cost_usd': 0.0})
        return None, total
    u = obj.get('usage') or {}
    pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
    pout = u.get('output_tokens', 0)
    api_equiv = pin * OPUS_PRICE[0] + pout * OPUS_PRICE[1]
    log({'event': 'result', 'key': key, 'model': OPUS_CLI, 'transport': 'claude-cli', 'success': True,
         'content': obj.get('result'), 'usage': u, 'cost_usd': round(api_equiv, 8),
         'cli_reported_usd': obj.get('total_cost_usd')})
    return obj.get('result'), total + api_equiv


def done_keys():
    if not RESULTS.exists():
        return set()
    return {(r['instance'], r['labeller'], r['checkpoint']) for r in map(json.loads, RESULTS.read_text().splitlines())
            if r.get('valid')}


def run(n_traces, cap):
    OUT.mkdir(parents=True, exist_ok=True)
    spec = json.loads(PROMPT.read_text())
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps({'recorded_before_any_call': True, 'prompt': str(PROMPT.relative_to(ROOT)),
                                        'labeller': GEM, 'reference': OPUS_CLI,
                                        'proxy_side': 'unchanged (Claude Haiku 5.5, earlier run)',
                                        'cap_pilot_usd': PILOT_CAP, 'cap_full_usd': FULL_CAP}, indent=1))
    total = spent()
    done = done_keys()
    tmp = Path(tempfile.mkdtemp(prefix='gold_rescore_'))
    for idx, t in enumerate(traces()[:n_traces]):
        gold, atoms = atoms_for(t)
        ids = {a for a, _ in atoms}
        for cp in ('extraction', 'board'):
            # the board is labelled only when extraction has no absent atom (set below)
            if cp == 'board' and not board_needed.get(t['instance_id'], True):
                continue
            key = f"{t['instance_id']}/gold/{cp}"
            if (t['instance_id'], GEM, cp) not in done:
                content, total = call_gem(key, spec, user_for(spec, t, gold, atoms, cp), atoms, total, cap)
                if content == 'SKIP':
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                lab = parse(content or '', ids)
                log_result(t['instance_id'], GEM, cp, lab, atoms)
                done.add((t['instance_id'], GEM, cp))
            if cp == 'extraction':
                lab = last_result(t['instance_id'], GEM, cp)
                board_needed[t['instance_id']] = not any(v['status'] == 'absent' for v in (lab or {}).values())
                if not lab:
                    board_needed[t['instance_id']] = True
            if cp == 'extraction' and idx < OPUS_N and (t['instance_id'], 'opus', cp) not in done:
                content, total = call_opus(f"{t['instance_id']}/opus/{cp}", spec,
                                           user_for(spec, t, gold, atoms, cp), atoms, total, cap, tmp)
                if content == 'SKIP':
                    print(json.dumps({'stopped': 'cap', 'spent': round(total, 6)}))
                    return
                if content is not None:
                    log_result(t['instance_id'], 'opus', cp, parse(content, ids), atoms)
                    done.add((t['instance_id'], 'opus', cp))
        print(json.dumps({'instance': t['instance_id'], 'spent': round(total, 6)}), flush=True)
    print(json.dumps({'spent': round(spent(), 6)}))


board_needed = {}


def log_result(instance, labeller, cp, lab, atoms):
    rec = {'instance': instance, 'labeller': labeller, 'checkpoint': cp, 'valid': lab is not None,
           'atoms': {a: lab[a]['status'] for a in lab} if lab else {}}
    with RESULTS.open('a') as f:
        f.write(json.dumps(rec) + '\n')


def last_result(instance, labeller, cp):
    out = None
    for r in map(json.loads, RESULTS.read_text().splitlines()):
        if r['instance'] == instance and r['labeller'] == labeller and r['checkpoint'] == cp and r['valid']:
            out = {a: {'status': s} for a, s in r['atoms'].items()}
    return out


def score():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    earlier = {}
    for r in map(json.loads, RUN_IDS.read_text().splitlines()):
        if r.get('kind') == 'gold':
            earlier.setdefault(r['instance'], r)
    proxy = {}
    for r in map(json.loads, RUN_IDS.read_text().splitlines()):
        if r.get('kind') == 'proxy':
            proxy.setdefault(r['instance'], []).append(r)
    stage_new, stage_old = {}, {}
    for inst in {r['instance'] for r in rows}:
        g = last_result(inst, GEM, 'extraction')
        if g is None:
            continue
        if any(v['status'] == 'absent' for v in g.values()):
            stage_new[inst] = 'extraction'
        else:
            b = last_result(inst, GEM, 'board')
            if b is None:
                continue
            stage_new[inst] = 'transmission' if any(v['status'] == 'absent' for v in b.values()) else 'aggregation'
        stage_old[inst] = earlier[inst]['stages'].get('extraction') == 'absent' and 'extraction' or (
            'transmission' if earlier[inst]['stages'].get('board') == 'absent' else 'aggregation')
    # proxy stage from the earlier run (side-level rule: any absent at extraction -> extraction)
    proxy_stage = {}
    for inst, facts in proxy.items():
        st = [f['stages'].get('extraction') for f in facts]
        proxy_stage[inst] = ('extraction' if 'absent' in st else
                             'transmission' if any(f['stages'].get('board') == 'absent' for f in facts) else 'aggregation')
    both = [i for i in stage_new if i in proxy_stage]
    agree = sum(1 for i in both if proxy_stage[i] == stage_new[i])
    cm = {}
    for i in both:
        cm[(proxy_stage[i], stage_new[i])] = cm.get((proxy_stage[i], stage_new[i]), 0) + 1
    # Gemini vs Opus on extraction atoms
    pairs = []
    for inst in {r['instance'] for r in rows}:
        g = last_result(inst, GEM, 'extraction')
        o = None
        for r in map(json.loads, RESULTS.read_text().splitlines()):
            if r['instance'] == inst and r['labeller'] == 'opus' and r['checkpoint'] == 'extraction' and r['valid']:
                o = r['atoms']
        if g and o:
            for a in o:
                if a in g:
                    pairs.append((g[a]['status'], o[a]))
    atom_agree = sum(1 for a, b in pairs if a == b)
    stage_agree_pairs = []
    for inst in {r['instance'] for r in rows}:
        g = last_result(inst, GEM, 'extraction')
        o = [r for r in map(json.loads, RESULTS.read_text().splitlines())
             if r['instance'] == inst and r['labeller'] == 'opus' and r['checkpoint'] == 'extraction' and r['valid']]
        if g and o:
            ga = any(v['status'] == 'absent' for v in g.values())
            oa = any(s == 'absent' for s in o[-1]['atoms'].values())
            stage_agree_pairs.append(ga == oa)
    out = {'traces_scored': len(stage_new), 'proxy_vs_new_gold_agree': agree, 'pairs': len(both),
           'confusion_proxy_by_new_gold': {f'{k[0]} -> {k[1]}': v for k, v in cm.items()},
           'new_gold_stage_counts': {s: sum(1 for v in stage_new.values() if v == s) for s in set(stage_new.values())},
           'old_gold_stage_counts': {s: sum(1 for v in stage_old.values() if v == s) for s in set(stage_old.values())},
           'atom_agreement_gemini_vs_opus_extraction': [atom_agree, len(pairs)],
           'extraction_absent_agreement_gemini_vs_opus': [sum(stage_agree_pairs), len(stage_agree_pairs)],
           'spend_usd': round(spent(), 6)}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--pilot', action='store_true')
    g.add_argument('--full', action='store_true')
    g.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.pilot:
        run(PILOT_N, PILOT_CAP)
    elif a.full:
        run(30, FULL_CAP)
    else:
        score()


if __name__ == '__main__':
    main()
