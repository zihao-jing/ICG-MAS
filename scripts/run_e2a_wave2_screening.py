"""E2-A option C, wave 2 screening: Gemini 3.6 Flash judges the 219 new MuSiQue bases.

One call per base trace, frozen wave-1 screening prompt `E2_wave1_base_screening`, temperature 0,
seed 42, max 10,000 output tokens, no retry. The wave-1 screening runner and prompt are reused
unchanged (`scripts/run_e2_wave1_screening.py` is imported, not edited). No injection is made and
no injection outcome is read. The $4.00 option-C cap covers the six seed runs ($0.5792) plus these
calls; the screening sub-cap is $3.40.

    python -m scripts.run_e2a_wave2_screening           # dry check, no calls
    python -m scripts.run_e2a_wave2_screening --execute # capped at 219 calls / $3.40

Output: rebuttal/results/batch1/E2A_wave2_screening
"""
import argparse, datetime, hashlib, json
from collections import Counter
from pathlib import Path

from src.audit.pilot_common import CallLedger, digest
from src.audit.judge_render import trace_text
from scripts.run_e2_wave1_screening import parse, eligible_targets, TYPES

PREREG = Path('rebuttal/pilots/prereg/E2-A.md')
CFG = Path('rebuttal/pilots/configs/E2A-wave2-screening.json')
PROMPTS = Path('rebuttal/judge/judge_prompts_v3.json')
PACKET = Path('rebuttal/pilots/20261110_e2a_wave2/judge_input_traces.jsonl')
SEEDS = Path('rebuttal/pilots/20261110_e2a_wave2/seeds.json')
TASK = 'E2_wave1_base_screening'
OUT = Path('rebuttal/results/batch1/E2A_wave2_screening')
WAVE2_RUN_COST_USD = 0.5792  # six seed runs, ledger total (reported before these calls)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bases():
    out = [json.loads(line) for line in PACKET.read_text().splitlines() if line.strip()]
    out.sort(key=lambda r: digest([42, r['item_id']]))
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
    assert sha(PACKET) == cfg['packet_sha256'], 'packet changed since the freeze'
    gate = json.loads(Path(cfg['stage1_gate']).read_text())['gate']
    assert gate['passed'] is True, 'stage-1 gate did not pass'
    rs = bases()
    order_sha = digest([[42, r['item_id']] for r in rs])
    assert order_sha == cfg['traces_order_sha256'], 'trace order changed since the freeze'
    seeds = json.loads(SEEDS.read_text())
    assert seeds['prereg']['sha256'] == sha(PREREG)
    total_cap = WAVE2_RUN_COST_USD + cfg['cost_cap_usd']
    assert total_cap <= cfg['option_c_total_cap_usd'], 'sub-cap exceeds the $4.00 option-C cap'
    print(json.dumps({'bases': len(rs), 'order_sha256': order_sha, 'max_calls': cfg['max_calls'],
                      'cost_cap_usd': cfg['cost_cap_usd'], 'seed_runs_cost_usd': WAVE2_RUN_COST_USD,
                      'option_c_total_cap_usd': cfg['option_c_total_cap_usd'],
                      'execute': a.execute, 'start_utc': utc()}), flush=True)
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
              'eligible_per_model_type': Counter(), 'per_trace_eligible': {},
              'stopped_at_cost_cap': False}
    for n, r in enumerate(rs, 1):
        if counts['cost_usd'] > cfg['cost_cap_usd']:
            counts['stopped_at_cost_cap'] = True
            break
        key = digest(['E2-wave2-screening', 42, r['item_id']])
        msgs = [{'role': 'system', 'content': p['system']},
                {'role': 'user', 'content': p['user_template'].format(trace=trace_text(r['trace']))}]
        rec = {'trace_id': r['item_id'], 'instance_id': r['trace']['instance_id'],
               'seed': r['seed'], 'model_family': r['model_family'],
               'candidate_agent_ids': r['candidate_agent_ids'],
               'messages_sha256': digest(msgs), 'judge_frozen': True}
        try:
            raw = ledger.call(key, cfg['model'], msgs, max_tokens=cfg['max_tokens'], temperature=0)
        except RuntimeError:
            raise
        except Exception as exc:
            rec.update(status='failed', parsed=None, raw='',
                       errors=['call failed: ' + type(exc).__name__ + ': ' + str(exc)[:160]])
            counts['failed'] += 1
            counts['failed_keys'].append(key)
        else:
            parsed, errs = parse(raw)
            rec.update(status='ok' if not errs else 'format_invalid', parsed=parsed, errors=errs, raw=raw)
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
                    counts['eligible_per_model_type'][f"{r['model_family']}|{ft}"] += 1
                counts['targets_checked'] += len(parsed['target_checks'])
                counts['judge_defect_free'][parsed.get('defect_free')] += 1
                counts['judge_eligible'][parsed.get('eligible')] += 1
                rec['eligible_targets'] = [{'agent_id': agent, 'fault_type': ft} for agent, ft in sorted(seen)]
                counts['per_trace_eligible'][r['item_id']] = len(seen)
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
    ledger.close()
    counts['cost_usd'] = round(counts['cost_usd'], 6)
    for k in ('judge_defect_free', 'judge_eligible', 'eligible_pairs_per_type',
              'eligible_traces_per_type', 'eligible_per_model_type'):
        counts[k] = dict(counts[k])
    counts['reached_50_per_type'] = {t: counts['eligible_pairs_per_type'].get(t, 0) >= 50 for t in TYPES}
    counts.update({'end_utc': utc(), 'config_sha256': digest(cfg), 'prereg_sha256': sha(PREREG),
                   'runner_sha256': sha(__file__), 'packet_sha256': sha(PACKET),
                   'stage1_gate_passed': True, 'seed_runs_cost_usd': WAVE2_RUN_COST_USD,
                   'option_c_cost_usd': round(WAVE2_RUN_COST_USD + counts['cost_usd'], 6),
                   'option_c_total_cap_usd': cfg['option_c_total_cap_usd'],
                   'no_injection': True, 'stage2_gate': 'not run', 'author_check_gate': 'not run'})
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=2, default=str) + '\n')
    print(json.dumps({k: counts[k] for k in ('planned', 'calls', 'valid', 'format_invalid', 'failed',
                                             'cost_usd', 'eligible_pairs_per_type',
                                             'reached_50_per_type', 'option_c_cost_usd')}))


if __name__ == '__main__':
    main()