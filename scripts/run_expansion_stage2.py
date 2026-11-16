"""Expansion Stage 2: screen 800 unused MuSiQue dev instances at three models.

Approved 2026-11-12 at a $5 cap: 2,400 traces. The instance list continues the
Stage 1 hash ordering after the 200 Stage 1 instances, so the samples are
disjoint. The matcher runs as eight independent shards, each with its own
CallLedger and its own share of the matcher budget; every call is logged.

    ./run.sh python -m scripts.run_expansion_stage2 --prepare
    ./run.sh python -m scripts.run_expansion_stage2 --match
    ./run.sh python -m scripts.run_expansion_stage2 --report

The relay runs are launched by `scripts/run_expansion_stage2.sh`.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from src.audit.critical_fact_validation import build_trace_packages
from src.audit.e4_fix_gates import r4_signals
from src.audit.matcher_v2 import PROMPT_SHA256, VERSION, match_trace
from src.audit.pilot_common import CallLedger, digest, freeze, read_jsonl
from src.audit.semantic_matcher import diagnose
from src.eval.data_loader import load_musique
from scripts.run_e1_anchor_matcher import adapt

ROOT = Path(__file__).resolve().parent.parent
STAGE1 = ROOT / 'rebuttal/pilots/20261112_expansion_stage1'
STAGE1_MANIFEST = STAGE1 / 'manifest.json'
OUT = ROOT / 'rebuttal/pilots/20261112_expansion_stage2'
RESULTS = ROOT / 'rebuttal/results/batch1/expansion_stage2'
INSTANCES = OUT / 'stage2_instances.jsonl'
MANIFEST = OUT / 'manifest.json'
CONFIG = OUT / 'config.json'
MATCHER_DIR = RESULTS / 'matcher'
MATCHER_CFG = ROOT / 'rebuttal/pilots/configs/E1-anchor-matcher-frozen.json'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
IDS100 = ROOT / 'data/musique_100_ids.json'
PREREG = ROOT / 'rebuttal/pilots/prereg/E4-v7.md'
SEED = 42
N_NEW = 800
MODELS = {'gemma31b': 'google/gemma-4-31b-it',
          'gpt4omini': 'openai/gpt-4o-mini',
          'qwen235b': 'qwen/qwen3-235b-a22b-2507'}
MATCHER_MODEL = 'qwen/qwen3-235b-a22b-2507'
N_SHARDS = 8
MAX_CALLS_PER_SHARD = 900
CAP_USD = 5.0
RESERVE_USD = 0.15


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare():
    pool = load_musique(min_hops=2)
    ids100 = set(json.loads(IDS100.read_text()))
    s1 = set(json.loads(STAGE1_MANIFEST.read_text())['instances'])
    remaining = sorted((i for i in pool if i['id'] not in ids100 and i['id'] not in s1),
                       key=lambda i: (digest(['expansion-stage1', SEED, i['id']]), i['id']))
    chosen = remaining[:N_NEW]
    assert len(chosen) == N_NEW
    assert not ({i['id'] for i in chosen} & s1)
    OUT.mkdir(parents=True, exist_ok=True)
    with INSTANCES.open('w') as f:
        for inst in chosen:
            f.write(json.dumps(inst, ensure_ascii=False) + '\n')
    freeze(MANIFEST, {
        'stage': 2, 'seed': SEED, 'n_new': N_NEW, 'models': MODELS,
        'pool_after_min_hops_2': len(pool), 'excluded_original_100': len(ids100),
        'excluded_stage1': len(s1), 'remaining_pool': len(remaining),
        'instances': [i['id'] for i in chosen],
        'instances_sha256': sha(INSTANCES),
        'stage1_manifest_sha256': sha(STAGE1_MANIFEST),
        'frozen_utc': '2026-11-12T00:00:00Z',
        'rule': 'continue the Stage 1 ordering after its 200 instances; take the next 800',
        'no_model_calls_in_prepare': True,
    })
    print(json.dumps({'pool': len(pool), 'remaining_after_stage1': len(remaining),
                      'chosen': len(chosen), 'instances_sha256': sha(INSTANCES),
                      'overlap_stage1': len({i['id'] for i in chosen} & s1)}))


def matcher_config():
    c = json.loads(CONFIG.read_text()) if CONFIG.exists() else None
    if c is None:
        c = {'experiment': 'expansion stage 2 screening', 'model': MATCHER_MODEL,
             'temperature': 0, 'max_tokens': 4096, 'seed': SEED,
             'max_calls': MAX_CALLS_PER_SHARD * N_SHARDS, 'pricing': str(PRICING),
             'instances_sha256': sha(INSTANCES),
             'matcher_config_sha256': sha(MATCHER_CFG), 'prompt_sha256': PROMPT_SHA256,
             'version': VERSION, 'frozen_utc': '2026-11-12T00:00:00Z'}
        freeze(CONFIG, c)
    return c


def packages(model):
    run = RESULTS / f'relay_{model}'
    ps = build_trace_packages(dataset='musique', run_dir=run,
                              protocol='score_ranked_relay', source_id=f'relay_{model}',
                              n_agents=None)
    return {p['instance_id']: p for p in ps}


def rel_costs():
    prices = {m['id']: m['pricing'] for m in json.loads(PRICING.read_text())['models']}
    out = {}
    for model in MODELS:
        path = RESULTS / f'relay_{model}' / 'api_responses.jsonl'
        cost = 0.0
        if path.exists():
            for r in read_jsonl(path):
                u = r.get('usage') or {}
                rate = prices.get(r.get('model')) or next(
                    (v for k, v in prices.items() if str(r.get('model', '')).startswith(k)), None)
                if rate:
                    cost += (u.get('prompt_tokens', 0) * float(rate['prompt'])
                             + u.get('completion_tokens', 0) * float(rate['completion']))
        out[model] = cost
    return out


def ledger_cost(path):
    p = Path(path) / 'calls.jsonl'
    if not p.exists():
        return 0.0
    return sum((r.get('cost_usd') or 0) for r in read_jsonl(p) if r.get('event') == 'result')


def all_keys():
    pk = {m: packages(m) for m in MODELS}
    for m in MODELS:
        assert len(pk[m]) == N_NEW, (m, len(pk[m]))
    return sorted((m, i) for m in MODELS for i in pk[m])


def match_shard(shard, n_shards, per_shard_cap):
    cfg = matcher_config()
    keys = all_keys()[shard::n_shards]
    pk = {m: packages(m) for m in MODELS}
    shard_dir = RESULTS / f'matcher_shard_{shard:02d}'
    MATCHER_DIR.mkdir(parents=True, exist_ok=True)
    ledger = CallLedger(shard_dir, cfg, PREREG, MAX_CALLS_PER_SHARD)
    counts = Counter()
    try:
        for inst_key in keys:
            model, inst = inst_key
            out = MATCHER_DIR / f'{digest(["expansion-stage2", SEED, inst, model])}.json'
            if out.exists():
                counts['skipped'] += 1
                continue
            if ledger_cost(shard_dir) > per_shard_cap:
                counts['cost_stop'] += 1
                break
            p = pk[model][inst]
            rec = {'instance_id': inst, 'model': model,
                   'answer_correct': bool(p['answer_correct']),
                   'answer_f1': p['answer_f1'], 'matcher_frozen': True}
            key = digest(['expansion-stage2', SEED, inst, model])
            try:
                result = match_trace(ledger, key, adapt(p), cfg['model'])
                rec.update(result)
                if result['status'] == 'ok':
                    rec['diagnosis'] = diagnose(result['facts'], result['carriers'],
                                                correct=rec['answer_correct'])
                    counts['ok'] += 1
                else:
                    counts['failed'] += 1
            except Exception as exc:
                rec.update({'status': 'failed', 'failure_stage': 'call',
                            'error': type(exc).__name__ + ': ' + str(exc)})
                counts['failed'] += 1
            freeze(out, rec)
            if sum(counts.values()) % 25 == 0:
                print(json.dumps({'shard': shard, 'done': sum(counts.values()),
                                  'of': len(keys), 'ok': counts['ok'],
                                  'failed': counts['failed'],
                                  'usd': round(ledger_cost(shard_dir), 4)}), flush=True)
    finally:
        ledger.close()
    print(json.dumps({'shard': shard, 'keys': len(keys), **counts,
                      'usd': round(ledger_cost(shard_dir), 5)}), flush=True)


def match():
    man = json.loads(MANIFEST.read_text())
    assert sha(INSTANCES) == man['instances_sha256'], 'instance list changed'
    cfg = matcher_config()
    assert sha(MATCHER_CFG) == cfg['matcher_config_sha256']
    assert PROMPT_SHA256 == cfg['prompt_sha256'] and VERSION == cfg['version']
    relay = rel_costs()
    relay_total = sum(relay.values())
    budget = CAP_USD - relay_total - RESERVE_USD
    per_shard = budget / N_SHARDS
    print(json.dumps({'relay_usd': round(relay_total, 4), 'matcher_budget': round(budget, 4),
                      'per_shard_cap': round(per_shard, 4)}), flush=True)
    if per_shard <= 0:
        raise SystemExit('relay spend leaves no matcher budget')
    procs = []
    for i in range(N_SHARDS):
        log = OUT / f'shard_{i:02d}.log'
        with log.open('w') as f:
            p = subprocess.Popen(
                [sys.executable, '-m', 'scripts.run_expansion_stage2',
                 '--match-shard', str(i), '--shards', str(N_SHARDS),
                 '--shard-cap', f'{per_shard:.6f}'],
                cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        procs.append((i, p, log))
    for i, p, log in procs:
        rc = p.wait()
        print(json.dumps({'shard': i, 'returncode': rc, 'log': str(log.relative_to(ROOT))}),
              flush=True)
    matcher = sum(ledger_cost(RESULTS / f'matcher_shard_{i:02d}') for i in range(N_SHARDS))
    print(json.dumps({'matcher_usd': round(matcher, 4), 'relay_usd': round(relay_total, 4),
                      'total_usd': round(matcher + relay_total, 4), 'cap_usd': CAP_USD}),
          flush=True)


def candidate_rows():
    man = json.loads(MANIFEST.read_text())
    rows = []
    for model in MODELS:
        pk = packages(model)
        for p in MATCHER_DIR.glob('*.json'):
            rec = json.loads(p.read_text())
            if rec['model'] != model or rec.get('status') != 'ok':
                continue
            package = pk[rec['instance_id']]
            facts = {f['fact_id']: f['text'] for f in rec['facts']['facts']}
            carriers = {c['fact_id']: c for c in rec['carriers']['facts']}
            missing = [fid for fid, c in carriers.items() if not c.get('extraction')]
            row = {'instance_id': rec['instance_id'], 'model': model,
                   'answer_correct': rec['answer_correct'], 'diagnosis': rec.get('diagnosis'),
                   'question': package['question'], 'gold': package['gold_answer'],
                   'board': [u['text'] for u in package['checkpoints']['board']],
                   'missing_ids': missing, 'facts': facts}
            if rec.get('diagnosis') == 'extraction_omission' and missing:
                fid = missing[0]
                sig = r4_signals(package['question'], package['gold_answer'], row['board'],
                                 facts, fid, missing)
                row.update({'candidate_fact_id': fid, 'candidate_fact': facts[fid], **sig})
            rows.append(row)
    return man, rows


def stage1_rows():
    from scripts.run_expansion_stage1 import candidate_rows as s1_candidate_rows
    return s1_candidate_rows()[1]


def report():
    man, rows = candidate_rows()
    screened = len(list(MATCHER_DIR.glob('*.json')))
    ok = [r for r in rows if r.get('diagnosis')]
    wrong = [r for r in ok if not r['answer_correct']]
    cands = [r for r in ok if r['diagnosis'] == 'extraction_omission']
    clean = [r for r in cands if r.get('pass')]
    dist = [r for r in ok if r['diagnosis'] == 'distortion']
    diag = Counter(r['diagnosis'] for r in ok)
    by_model = {}
    for m in MODELS:
        mo = [r for r in ok if r['model'] == m]
        mc = [r for r in mo if r['diagnosis'] == 'extraction_omission']
        by_model[m] = {
            'screened_ok': len(mo), 'wrong': sum(not r['answer_correct'] for r in mo),
            'candidates': len(mc), 'rate': round(len(mc) / len(mo), 4) if mo else None,
            'clean': sum(bool(r.get('pass')) for r in mc),
            'distortion': sum(r['diagnosis'] == 'distortion' for r in mo),
            'selection': sum(r['diagnosis'] == 'selection_omission' for r in mo)}
    s1 = stage1_rows()
    s1_ok = [r for r in s1 if r.get('diagnosis')]
    s1_cands = [r for r in s1_ok if r['diagnosis'] == 'extraction_omission']
    s1_clean = [r for r in s1_cands if r.get('pass')]
    s1_dist = [r for r in s1_ok if r['diagnosis'] == 'distortion']
    cum_clean_traces = len(s1_clean) + len(clean)
    cum_clean_unique = len({r['instance_id'] for r in s1_clean + clean})
    cum_dist_traces = len(s1_dist) + len(dist)
    cum_dist_unique = len({r['instance_id'] for r in s1_dist + dist})
    costs = {'relay': rel_costs(),
             'matcher': {f'shard_{i:02d}': ledger_cost(RESULTS / f'matcher_shard_{i:02d}')
                         for i in range(N_SHARDS)}}
    total = sum(costs['relay'].values()) + sum(costs['matcher'].values())
    cand_rate = len(cands) / len(ok) if ok else 0.0
    clean_yield = len(clean) / len(cands) if cands else 0.0
    clean_per_trace = len(clean) / len(ok) if ok else 0.0
    failed = [json.loads(p.read_text()) for p in MATCHER_DIR.glob('*.json')
              if json.loads(p.read_text()).get('status') != 'ok']
    fail_types = Counter(str(r.get('error', '')).split(':')[0] for r in failed)
    lines = ['# Expansion Stage 2: screening', '',
             f"Instances: {man['n_new']} unused MuSiQue dev instances x {len(MODELS)} models "
             f"= {man['n_new'] * len(MODELS)} planned traces. Manifest "
             f"`{man['instances_sha256']}`; Stage 1 manifest `{man['stage1_manifest_sha256']}`. "
             f"Frozen 2026-11-12; no repair arm run.\n",
             f'Matcher records: {screened}; scored ok: {len(ok)}; transport failures: '
             f'{len(failed)} ({", ".join(f"{k}={v}" for k, v in fail_types.items()) or "none"}); '
             f'wrong: {len(wrong)}; extraction-omission candidates: {len(cands)}; '
             f'R3/R4 clean: {len(clean)} ({len({r["instance_id"] for r in clean})} unique).\n',
             '## Yield by model\n',
             '| model | scored | wrong | candidates | candidate rate | clean | distortion | selection |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m, v in by_model.items():
        lines.append(f"| {m} | {v['screened_ok']} | {v['wrong']} | {v['candidates']} | "
                     f"{v['rate']:.1%} | {v['clean']} | {v['distortion']} | {v['selection']} |")
    lines += [f'| **all** | **{len(ok)}** | **{len(wrong)}** | **{len(cands)}** | '
              f'**{cand_rate:.1%}** | **{len(clean)}** | **{len(dist)}** | '
              f'**{diag.get("selection_omission", 0)}** |\n',
              '## Diagnoses\n',
              '| diagnosis | traces | unique instances |',
              '| --- | ---: | ---: |']
    for k, v in diag.most_common():
        lines.append(f"| {k} | {v} | "
                     f"{len({r['instance_id'] for r in ok if r['diagnosis'] == k})} |")
    lines += ['', '## Per-experiment clean counts\n',
              '| experiment | Stage 2 alone | Stage 1 + Stage 2 | reaches 30? |',
              '| --- | ---: | ---: | --- |',
              f'| Extraction | {len(clean)} traces / '
              f'{len({r["instance_id"] for r in clean})} unique | '
              f'{cum_clean_traces} traces / {cum_clean_unique} unique | '
              f'{"yes" if cum_clean_unique >= 30 else "no"} |',
              f'| Direct insertion | same cohort | same cohort | '
              f'{"yes" if cum_clean_unique >= 30 else "no"} |',
              f'| Distortion, diagnosed | {len(dist)} traces / '
              f'{len({r["instance_id"] for r in dist})} unique | '
              f'{cum_dist_traces} traces / {cum_dist_unique} unique | '
              f'{"yes" if cum_dist_unique >= 30 else "no"} |',
              f'| Distortion, swaps at 1/4 yield | about {len(dist) * 0.25:.0f} | '
              f'about {cum_dist_unique * 0.25:.0f} | '
              f'{"yes" if cum_dist_unique * 0.25 >= 30 else "no"} |\n',
              'The distortion swap counts are the plan\'s quarter-yield estimate; swaps are '
              'generated separately by the labeller and must pass R6 before they count.\n',
              '## Cost\n',
              '| item | USD |',
              '| --- | ---: |']
    for m, v in costs['relay'].items():
        lines.append(f'| relay {m} | {v:.4f} |')
    for s, v in costs['matcher'].items():
        lines.append(f'| matcher {s} | {v:.4f} |')
    lines += [f'| **total** | **{total:.4f}** |\n',
              f'Per-pilot cap ${CAP_USD:.2f}. Every relay call is in `api_responses.jsonl` '
              f'under `relay_<model>/`; every matcher call is in each shard\'s `calls.jsonl` '
              f'under `{RESULTS.relative_to(ROOT)}/matcher_shard_*`.\n',
              '## Clean extraction candidates\n',
              '| instance | model | gold | missing | candidate fact | R3 | R4 |',
              '| --- | --- | --- | ---: | --- | --- | --- |']
    for r in clean:
        lines.append(f"| {r['instance_id']} | {r['model']} | {str(r['gold'])[:70]} | "
                     f"{len(r['missing_ids'])} | {str(r.get('candidate_fact',''))[:110]} | "
                     f"{'pass' if r.get('r3_single_fact') else 'fail'} | "
                     f"{'pass' if r.get('r4_pass') else 'fail'} |")
    lines += ['', '## Distortion cases for swap generation\n',
              f'{len(dist)} diagnosed traces, {len({r["instance_id"] for r in dist})} unique '
              f'instances. The case list with source text is in `distortion_cases.jsonl`.\n',
              '## Qwen\n',
              f'Qwen stays in the pool pending review of its per-model yield above '
              f'({by_model["qwen235b"]["clean"]} clean, '
              f'{by_model["qwen235b"]["distortion"]} distortion diagnoses).\n']
    (OUT / 'stage2_report.md').write_text('\n'.join(lines) + '\n')
    with (OUT / 'distortion_cases.jsonl').open('w') as f:
        for r in dist:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(json.dumps({'screened': screened, 'ok': len(ok), 'wrong': len(wrong),
                      'candidates': len(cands), 'candidate_rate': round(cand_rate, 4),
                      'clean': len(clean), 'clean_unique': len({r['instance_id'] for r in clean}),
                      'clean_yield': round(clean_yield, 4),
                      'distortion': len(dist), 'distortion_unique': len({r['instance_id'] for r in dist}),
                      'cum_clean_traces': cum_clean_traces, 'cum_clean_unique': cum_clean_unique,
                      'cum_dist_traces': cum_dist_traces, 'cum_dist_unique': cum_dist_unique,
                      'total_usd': round(total, 4), 'by_model': by_model}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--match', action='store_true')
    ap.add_argument('--match-shard', type=int, default=None)
    ap.add_argument('--shards', type=int, default=N_SHARDS)
    ap.add_argument('--shard-cap', type=float, default=0.0)
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.prepare:
        prepare()
    if a.match:
        match()
    if a.match_shard is not None:
        match_shard(a.match_shard, a.shards, a.shard_cap)
    if a.report:
        report()


if __name__ == '__main__':
    main()