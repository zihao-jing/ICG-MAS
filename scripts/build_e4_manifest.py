"""Build the E4 per-case action/donor manifest from the frozen case list and matcher labels.

No repair, control or scoring outcome is produced or read. The only model calls are the extraction-arm
donor controls (V-ext): one extraction per eligible donor agent per extraction case, logged by the
append-only ledger. Target units, donor units, source spans, board hashes and added-token counts are
written from frozen inputs; the manifest is hashed and frozen before any intervention.

  python -m scripts.build_e4_manifest            # dry run: counts only
  python -m scripts.build_e4_manifest --execute  # donor-control calls, then freeze
"""
import argparse, datetime, hashlib, json, re
from pathlib import Path

from src.audit.critical_fact_validation import load_run, reconstruct_states_and_scores
from src.audit.alignment import _jaccard_sim
from src.audit.base_tokenizers import added_token_count, volume_match
from src.audit.pilot_common import CallLedger, digest, freeze
from src.protocols.relay import _EXTRACTION_SYSTEM, _build_extraction_prompt, _parse_units
from scripts.build_final_author_packet import packages
from scripts.pilot_e1 import messages

COHORT = Path('rebuttal/results/batch1/E4_pool_matcher/E4_cohort_frozen.json')
MATCHER = Path('rebuttal/results/batch1/E4_pool_matcher/matcher')
CFG = Path('rebuttal/pilots/configs/E4-manifest-v1.json')
BASE = {'qwen235b': 'qwen/qwen3-235b-a22b-2507',
        'gpt4omini': 'openai/gpt-4o-mini',
        'gemma31b': 'google/gemma-4-31b-it'}
MAX_UNITS = 3


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def agent_of(unit_id):
    m = re.search(r':a(\d+):', unit_id) or re.search(r':agent-(\d+)', unit_id)
    if not m:
        raise ValueError(f'cannot parse agent from {unit_id}')
    return int(m.group(1))


def source_ids_agents(facts):
    out = set()
    if isinstance(facts, dict):
        facts = facts.get('facts') or []
    for f in facts:
        for s in f.get('source_ids') or []:
            out.add(agent_of(s))
    return out


def order(instance, agents):
    return sorted(agents, key=lambda a: (digest([42, instance, a]), a))


def support_agents(facts):
    return source_ids_agents(facts)


def target_for(diag, instance, facts, carriers, board_by_id):
    """E4-v7 target rules. Returns (group, target_agent, target_unit_ids, target_unit)."""
    cf = {c['fact_id']: c for c in carriers['facts']}
    fm = {f['fact_id']: f for f in facts['facts']}
    if diag == 'extraction_omission':
        bad = [(fid, c) for fid, c in cf.items() if not c.get('extraction')]
        if not bad:
            return diag, None, [], None
        fid, _ = bad[0]
        cand = source_ids_agents([fm[fid]])
        if not cand:
            return diag, None, [], None
        a = order(instance, cand)[0]
        return diag, a, [u['unit_id'] for u in board_by_id.values() if u['agent_id'] == a], None
    if diag == 'selection_omission':
        bad = [(fid, c) for fid, c in cf.items() if c.get('extraction') and not c.get('board')]
        if not bad:
            return diag, None, [], None
        fid, c = bad[0]
        units = [x for e in c['extraction'] for x in e.get('unit_ids', [])]
        agents = {agent_of(u) for u in units if u in board_by_id or ':' in u}
        cand = agents or source_ids_agents([fm[fid]])
        if not cand:
            return diag, None, [], None
        a = order(instance, cand)[0]
        return diag, a, [u['unit_id'] for u in board_by_id.values() if u['agent_id'] == a], None
    if diag == 'distortion':
        bad = []
        for fid, c in cf.items():
            for e in c.get('board') or []:
                if e.get('fidelity') == 'distorted':
                    bad.extend(e.get('unit_ids') or [])
        bad = [u for u in bad if u in board_by_id]
        if not bad:
            return diag, None, [], None
        unit = board_by_id[bad[0]]
        return diag, unit['agent_id'], [unit['unit_id']], unit
    # aggregation / control / partial: first SHA support holder
    cand = support_agents(facts)
    if not cand:
        return diag, None, [], None
    a = order(instance, cand)[0]
    return diag, a, [u['unit_id'] for u in board_by_id.values() if u['agent_id'] == a], None


def donor_for(instance, facts, board):
    board_agents = {u['agent_id'] for u in board}
    t = None
    support = support_agents(facts)
    return board_agents, support


def spans(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]


def closest_span(context, unit_text):
    ss = spans(context)
    return sorted(ss, key=lambda s: (-_jaccard_sim(s, unit_text), s))[0] if ss else context


def next_units(instance, agent, pool, board, scores):
    ids = {u['unit_id'] for u in board}
    pool_a = [u for u in pool if u['agent_id'] == agent]
    sc = scores.get(agent) or scores.get(str(agent)) or []
    ranked = [u for _, u in sorted(zip(sc, pool_a), key=lambda x: -x[0].get('overall', x[0].get('composite', 0.0))) if u['unit_id'] not in ids]
    return ranked[:2]


def build_cases(ids):
    cohort = json.loads(COHORT.read_text())
    pk = packages(ids)
    mat = {}
    for p in MATCHER.glob('*.json'):
        r = json.loads(p.read_text())
        mat[(r['instance_id'], r['model'])] = r
    sc = {}
    for (model, inst), p in pk.items():
        run = Path(p['run_dir'])
        results, responses = load_run(run)
        _, scores = reconstruct_states_and_scores(responses)
        sc[(model, inst)] = scores.get(inst, {})
    out = []
    for c in cohort['case']:
        key = (c['instance'], c['model'])
        if c['matcher_status'] != 'ok':
            out.append({'instance': c['instance'], 'model': c['model'], 'benchmark': c['benchmark'],
                        'group': c['matcher_diagnosis'], 'matcher_status': 'failed', 'action': 'none: unscored case'})
            continue
        p = pk[(c['model'], c['instance'])]
        r = mat[key]
        board = p['checkpoints']['board']
        board_by_id = {u['unit_id']: u for u in board}
        facts = r['facts']; carriers = r['carriers']
        diag = r['diagnosis']
        group, target, target_ids, target_unit = target_for(diag, c['instance'], facts, carriers, board_by_id)
        row = {'instance': c['instance'], 'model': c['model'], 'benchmark': c['benchmark'],
               'group': diag, 'matcher_status': 'ok', 'target_agent': target,
               'target_unit_ids': target_ids, 'board_sha256': digest(board)}
        if target is None:
            row['action'] = 'none: no valid target'
            out.append(row); continue
        board_agents = {u['agent_id'] for u in board}
        support = support_agents(facts)
        other = board_agents - {target}
        no_support = other - support
        donor = order(c['instance'], no_support or other)[0] if other else None
        row['donor_agent'] = donor
        row['donor_fallback'] = not bool(no_support)
        row['donor_unit_ids'] = [u['unit_id'] for u in board if u['agent_id'] == donor] if donor is not None else []
        if donor is not None:
            dctx = next(s['text'] for s in p['source_contexts'] if s['agent_id'] == donor)
            dunit = next(u for u in board if u['agent_id'] == donor)
            row['donor_span'] = closest_span(dctx, dunit['text'])
        if diag == 'distortion' and target_unit is not None:
            tctx = next(s['text'] for s in p['source_contexts'] if s['agent_id'] == target)
            row['target_span'] = closest_span(tctx, target_unit['text'])
        model = BASE[c['model']]
        if diag == 'selection_omission' and donor is not None:
            rep = next_units(c['instance'], target, p['checkpoints']['extraction'], board, sc[(c['model'], c['instance'])])
            ctl = next_units(c['instance'], donor, p['checkpoints']['extraction'], board, sc[(c['model'], c['instance'])])
            row['repair'] = {'arm': 'R-sel', 'unit_ids': [u['unit_id'] for u in rep], 'units': rep}
            row['control'] = {'arm': 'V-sel', 'unit_ids': [u['unit_id'] for u in ctl], 'units': ctl}
            m = volume_match(model, rep, ctl)
            row['added_tokens'] = {'repair': m['repair_tokens'], 'control': m['control_tokens']}
            row['matched'] = m['matched']
        elif diag == 'distortion' and donor is not None and target_unit is not None:
            rep = [dict(target_unit, text=row['target_span'])]
            dunit = next(u for u in board if u['agent_id'] == donor)
            ctl = [dict(dunit, text=row['donor_span'])]
            row['repair'] = {'arm': 'R-dist', 'unit_ids': [target_unit['unit_id']], 'units': rep}
            row['control'] = {'arm': 'V-dist', 'unit_ids': [dunit['unit_id']], 'units': ctl}
            m = volume_match(model, rep, ctl)
            row['added_tokens'] = {'repair': m['repair_tokens'], 'control': m['control_tokens']}
            row['matched'] = m['matched']
        elif diag == 'extraction_omission' and donor is not None:
            cands = sorted(no_support or other, key=lambda a: (digest([42, c['instance'], 'V-ext', a]), a))
            row['repair'] = {'arm': 'R-ext', 'source_agent': target,
                             'rule': 'fresh extraction from the target source context; unit count fixed at intervention'}
            row['control'] = {'arm': 'V-ext', 'candidates': [{'agent': a, 'sha': digest([42, c['instance'], 'V-ext', a])} for a in cands]}
            row['matched'] = None
        out.append(row)
    return out, pk


def extract_donor_units(row, pk, ledger):
    p = pk[(row['model'], row['instance'])]
    model = BASE[row['model']]
    for cand in row['control']['candidates']:
        a = cand['agent']
        ctx = next(s['text'] for s in p['source_contexts'] if s['agent_id'] == a)
        raw = ledger.call(f"{row['instance']}/{row['model']}/V-ext/{a}/extract", model,
                          messages(_EXTRACTION_SYSTEM, _build_extraction_prompt(ctx, p['question'], MAX_UNITS)),
                          max_tokens=4096)
        units = [{'agent_id': a, 'text': t} for t in _parse_units(raw, MAX_UNITS)]
        cand['units'] = units
        cand['prefix_tokens'] = {str(k): added_token_count(model, units[:k]) for k in range(1, len(units) + 1)}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--config', default=str(CFG))
    a = ap.parse_args()
    ids = {c['instance'] for c in json.loads(COHORT.read_text())['case']}
    rows, pk = build_cases(ids)
    ext = [r for r in rows if r.get('group') == 'extraction_omission' and r.get('donor_agent') is not None]
    calls = sum(len(r['control']['candidates']) for r in ext)
    plan = {'cases': len(rows), 'extraction_cases': len(ext),
            'donor_candidates': calls,
            'matched_selection': sum(bool(r.get('matched')) for r in rows if r.get('group') == 'selection_omission'),
            'matched_distortion': sum(bool(r.get('matched')) for r in rows if r.get('group') == 'distortion'),
            'execute': a.execute, 'utc': utc()}
    print(json.dumps(plan, indent=1), flush=True)
    if not a.execute:
        return
    cfg = json.loads(Path(a.config).read_text())
    assert cfg['cases_sha256'] == sha(COHORT), 'frozen case list changed'
    assert cfg['prereg_sha256'] == sha(Path('rebuttal/pilots/prereg/E4-v7.md'))
    assert cfg['expected_calls'] == calls, (cfg['expected_calls'], calls)
    out = Path(cfg['output'])
    ledger = CallLedger(out, cfg, cfg['prereg'], calls)
    try:
        for r in ext:
            extract_donor_units(r, pk, ledger)
            print(json.dumps({'done': r['instance']}), flush=True)
    except Exception:
        ledger.close()
        raise
    spent = sum((x.get('cost_usd') or 0) for x in ledger.done.values())
    if spent > cfg['cost_cap_usd']:
        raise RuntimeError('Cost cap reached')
    ledger.close()
    manifest = {'experiment': 'E4 action/donor manifest', 'prereg': 'E4-v7.md',
                'prereg_sha256': sha(Path('rebuttal/pilots/prereg/E4-v7.md')),
                'case_list_sha256': sha(COHORT), 'frozen_utc': utc(),
                'note': 'no outcome read; only V-ext donor-control extraction calls made',
                'cases': rows,
                'counts': {'cases': len(rows), 'scored': sum(r['matcher_status'] == 'ok' for r in rows),
                           'unscored': sum(r['matcher_status'] != 'ok' for r in rows),
                           'extraction_cases': len(ext), 'donor_calls': calls}}
    freeze(out / 'manifest.json', manifest)
    summary = {'planned_calls': calls, 'calls': len([1 for _ in ledger.done]),
               'failed': sum(not x['success'] for x in ledger.done.values()),
               'cost_usd': round(spent, 6), 'manifest_sha256': sha(out / 'manifest.json'),
               'frozen_utc': manifest['frozen_utc']}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == '__main__':
    main()