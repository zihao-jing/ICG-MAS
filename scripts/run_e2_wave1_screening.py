"""E2-A wave-1 screening: Gemini 3.6 Flash judges every combined candidate base (68 traces).

Stage-1 gate passed on the 12 pre-registered spot items before this run (gate.json). One call per
unique base trace, frozen prompt `E2_wave1_base_screening`, temperature 0, seed 42, max 10,000 output
tokens, no retry. The judge's per-agent `target_checks` are counted per fault type; no injection is made
and no injection outcome is read.

  python -m scripts.run_e2_wave1_screening           # dry check, no calls
  python -m scripts.run_e2_wave1_screening --execute # capped at 260 calls / $4.00

Output: rebuttal/results/batch1/E2A_wave1_screening
"""
import argparse, datetime, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.pilot_common import CallLedger, digest
from src.audit.judge_render import trace_text

PREREG = Path('rebuttal/pilots/prereg/E2-A.md')
CFG = Path('rebuttal/pilots/configs/E2A-wave1-screening.json')
PROMPTS = Path('rebuttal/judge/judge_prompts_v3.json')
PACKETS = [Path('rebuttal/annotation/author_packet_20261108/E2A_screening.jsonl'),
           Path('rebuttal/annotation/author_packet_20261108/E2A_screening_supplement_wave1.jsonl')]
TASK = 'E2_wave1_base_screening'
TYPES = ['extraction_omission', 'selection_omission', 'distortion', 'aggregation']
REQUIRED = ['defect_free', 'critical_facts', 'sufficient_support_sets',
            'any_partial_or_distorted_carrier', 'target_checks', 'eligible', 'rationale']
OUT = Path('rebuttal/results/batch1/E2A_wave1_screening')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    i, j = s.find('{'), s.rfind('}')
    if i < 0 or j < i:
        return None, ['no JSON object']
    try:
        o = json.loads(s[i:j + 1])
    except Exception as exc:
        return None, ['invalid JSON: ' + str(exc)[:80]]
    miss = [k for k in REQUIRED if k not in o]
    if miss:
        return None, ['missing keys: ' + ','.join(miss)]
    if not isinstance(o['target_checks'], list):
        return None, ['target_checks not a list']
    return o, []


def bases():
    man = json.loads(Path('rebuttal/pilots/20261108_review5/E2A_combined_manifest.json').read_text())
    fam = {c['trace_id']: c['model_family'] for c in man['candidates']}
    by = {}
    for p in PACKETS:
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = r['item_id']
            if key in by:
                assert digest(by[key]['trace']) == digest(r['trace']), 'same trace id, different content'
                by[key]['candidate_agent_ids'] = sorted(set(by[key]['candidate_agent_ids']) | set(r['candidate_agent_ids']))
            else:
                by[key] = {'trace_id': key, 'trace': r['trace'], 'family': fam.get(key, 'gpt'),
                           'candidate_agent_ids': list(r['candidate_agent_ids'])}
    out = list(by.values())
    out.sort(key=lambda r: digest([42, r['trace_id']]))
    return out


def eligible_targets(parsed, trace):
    """Judge-side eligible (trace, agent, type) candidates; unknown is never counted eligible."""
    if parsed.get('defect_free') != 'yes' or parsed.get('eligible') != 'yes':
        return []
    out = []
    for t in parsed['target_checks']:
        if t.get('in_every_sufficient_set') != 'yes' or t.get('carrier_outside_agent') != 'no':
            continue
        for ft in t.get('feasible_fault_types') or []:
            if ft in TYPES:
                out.append((t.get('agent_id'), ft))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    cfg = json.loads(CFG.read_text())
    prompts = json.loads(PROMPTS.read_text())
    assert cfg['prereg_sha256'] == sha(PREREG)
    assert sha(PROMPTS) == cfg['prompts_file_sha256']
    assert prompts['prompts_sha256'] == cfg['prompts_sha256']
    p = prompts['prompts'][TASK]
    assert p['judge_model'] == cfg['model'] == 'google/gemini-3.6-flash'
    assert p['system_sha256'] == cfg['system_sha256']
    assert sha(__file__) == cfg['runner_sha256'], 'runner changed since the freeze'
    gate = json.loads(Path(cfg['stage1_gate']).read_text())['gate']
    assert gate['passed'] is True, 'stage-1 gate did not pass'
    for path in PACKETS:
        assert sha(path) in cfg['packet_sha256'], f'packet changed: {path}'
    rs = bases()
    order_sha = digest([[42, r['trace_id']] for r in rs])
    assert order_sha == cfg['traces_order_sha256'], 'trace order changed since the freeze'
    print(json.dumps({'traces': len(rs), 'order_sha256': order_sha, 'max_calls': cfg['max_calls'],
                      'cost_cap_usd': cfg['cost_cap_usd'], 'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'outputs').mkdir(exist_ok=True)
    ledger = CallLedger(OUT, cfg, PREREG, cfg['max_calls'])
    counts = {'planned': len(rs), 'calls': 0, 'valid': 0, 'format_invalid': 0, 'failed': 0,
              'failed_keys': [], 'format_invalid_keys': [], 'cost_usd': 0.0,
              'resolved_models': {}, 'model_mismatch': 0,
              'targets_checked': 0, 'judge_defect_free': Counter(), 'judge_eligible': Counter(),
              'eligible_pairs_per_type': Counter(), 'eligible_traces_per_type': Counter(),
              'eligible_per_model_type': Counter(), 'per_trace_eligible': {}}
    try:
        for n, r in enumerate(rs, 1):
            if counts['cost_usd'] > cfg['cost_cap_usd']:
                counts['stopped_at_cost_cap'] = True
                break
            key = digest(['E2-wave1-screening', 42, r['trace_id']])
            msgs = [{'role': 'system', 'content': p['system']},
                    {'role': 'user', 'content': p['user_template'].format(trace=trace_text(r['trace']))}]
            rec = {'trace_id': r['trace_id'], 'instance_id': r['trace']['instance_id'],
                   'candidate_agent_ids': r['candidate_agent_ids'],
                   'messages_sha256': digest(msgs), 'judge_frozen': True}
            try:
                raw = ledger.call(key, cfg['model'], msgs, max_tokens=cfg['max_tokens'], temperature=0)
                parsed, errs = parse(raw)
                rec.update(status='ok' if not errs else 'format_invalid', parsed=parsed,
                           errors=errs, raw=raw)
                counts['valid'] += (not errs)
                counts['format_invalid'] += bool(errs)
                if errs:
                    counts['format_invalid_keys'].append(key)
                else:
                    elig = eligible_targets(parsed, r['trace'])
                    seen = set()
                    for agent, ft in elig:
                        if (agent, ft) not in seen:
                            seen.add((agent, ft))
                            counts['eligible_pairs_per_type'][ft] += 1
                    for ft in {f for _, f in seen}:
                        counts['eligible_traces_per_type'][ft] += 1
                    for agent, ft in seen:
                        counts['eligible_per_model_type'][f"{r['family']}|{ft}"] += 1
                    counts['targets_checked'] += len(parsed['target_checks'])
                    counts['judge_defect_free'][parsed.get('defect_free')] += 1
                    counts['judge_eligible'][parsed.get('eligible')] += 1
                    rec['eligible_targets'] = [{'agent_id': agent, 'fault_type': ft} for agent, ft in sorted(seen)]
                    counts['per_trace_eligible'][r['trace_id']] = len(seen)
            except Exception as exc:
                rec.update(status='failed', parsed=None, raw='',
                           errors=['call failed: ' + type(exc).__name__ + ': ' + str(exc)[:160]])
                counts['failed'] += 1
                counts['failed_keys'].append(key)
            counts['calls'] += 1
            last = list(ledger.done.values())[-1] if ledger.done else None
            if last and last.get('key') == key:
                rm = last.get('resolved_model')
                if rm:
                    counts['resolved_models'][rm] = counts['resolved_models'].get(rm, 0) + 1
                    counts['model_mismatch'] += int(rm != cfg['model'])
                counts['cost_usd'] += last.get('cost_usd') or 0
            (OUT / 'outputs' / f'{key}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1))
            print(f"{n}/{len(rs)} {rec['status']} {r['trace']['instance_id']} {utc()}", flush=True)
    finally:
        ledger.close()
    counts['cost_usd'] = round(counts['cost_usd'], 6)
    for k in ('judge_defect_free', 'judge_eligible', 'eligible_pairs_per_type',
              'eligible_traces_per_type', 'eligible_per_model_type'):
        counts[k] = dict(counts[k])
    counts['reached_50_per_type'] = {t: counts['eligible_pairs_per_type'].get(t, 0) >= 50 for t in TYPES}
    counts.update({'end_utc': utc(), 'config_sha256': digest(cfg), 'prereg_sha256': sha(PREREG),
                   'runner_sha256': sha(__file__), 'stage1_gate_passed': True})
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=2, default=str) + '\n')
    print(json.dumps({k: counts[k] for k in ('planned', 'calls', 'valid', 'format_invalid', 'failed',
                                             'cost_usd', 'eligible_pairs_per_type', 'reached_50_per_type')}))


if __name__ == '__main__':
    main()