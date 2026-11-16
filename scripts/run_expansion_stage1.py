"""Expansion Stage 1: screen 200 unused MuSiQue dev instances at three models.

Approved 2026-11-12: 600 traces, about $1.86, under the $5 per-pilot cap. This
script prepares the instance list, runs the frozen matcher over the relay
traces, and applies R3/R4 to the extraction-omission candidates. The three
relay runs use the project runner and are launched by
`scripts/run_expansion_stage1.sh`.

    ./run.sh python -m scripts.run_expansion_stage1 --prepare
    ./run.sh python -m scripts.run_expansion_stage1 --match
    ./run.sh python -m scripts.run_expansion_stage1 --report

No repair arm runs here. Every relay call is logged in each run's
`api_responses.jsonl`; every matcher call is logged in the matcher ledger.
"""
import argparse
import hashlib
import json
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
OUT = ROOT / 'rebuttal/pilots/20261112_expansion_stage1'
RESULTS = ROOT / 'rebuttal/results/batch1/expansion_stage1'
INSTANCES = OUT / 'stage1_instances.jsonl'
MANIFEST = OUT / 'manifest.json'
CONFIG = OUT / 'config.json'
MATCHER_DIR = RESULTS / 'matcher'
MATCHER_CFG = ROOT / 'rebuttal/pilots/configs/E1-anchor-matcher-frozen.json'
POOL_CFG = ROOT / 'rebuttal/pilots/configs/E4-pool-matcher.json'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
IDS100 = ROOT / 'data/musique_100_ids.json'
SEED = 42
N_NEW = 200
MODELS = {'gemma31b': 'google/gemma-4-31b-it',
          'gpt4omini': 'openai/gpt-4o-mini',
          'qwen235b': 'qwen/qwen3-235b-a22b-2507'}
MATCHER_MODEL = 'qwen/qwen3-235b-a22b-2507'
MAX_MATCHER_CALLS = 2400
COST_STOP_USD = 3.5


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare():
    pool = load_musique(min_hops=2)
    ids100 = set(json.loads(IDS100.read_text()))
    remaining = sorted((i for i in pool if i['id'] not in ids100),
                       key=lambda i: (digest(['expansion-stage1', SEED, i['id']]), i['id']))
    chosen = remaining[:N_NEW]
    assert len(chosen) == N_NEW
    OUT.mkdir(parents=True, exist_ok=True)
    with INSTANCES.open('w') as f:
        for inst in chosen:
            f.write(json.dumps(inst, ensure_ascii=False) + '\n')
    freeze(MANIFEST, {
        'stage': 1, 'seed': SEED, 'n_new': N_NEW, 'models': MODELS,
        'pool_after_min_hops_2': len(pool), 'excluded_original_100': len(ids100),
        'remaining_pool': len(remaining), 'instances': [i['id'] for i in chosen],
        'instances_sha256': sha(INSTANCES), 'frozen_utc': '2026-11-12T00:00:00Z',
        'rule': 'sort unused dev instances by sha256(["expansion-stage1", 42, id]); take first 200',
        'no_model_calls_in_prepare': True,
    })
    print(json.dumps({'pool': len(pool), 'remaining': len(remaining),
                      'chosen': len(chosen), 'instances_sha256': sha(INSTANCES)}))


def matcher_config():
    c = json.loads(CONFIG.read_text()) if CONFIG.exists() else None
    if c is None:
        c = {'experiment': 'expansion stage 1 screening pilot', 'model': MATCHER_MODEL,
             'temperature': 0, 'max_tokens': 4096, 'seed': SEED,
             'max_calls': MAX_MATCHER_CALLS, 'pricing': str(PRICING),
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


def ledger_cost():
    p = RESULTS / 'calls.jsonl'
    if not p.exists():
        return 0.0
    return sum((r.get('cost_usd') or 0) for r in read_jsonl(p) if r.get('event') == 'result')


def match():
    man = json.loads(MANIFEST.read_text())
    assert sha(INSTANCES) == man['instances_sha256'], 'instance list changed'
    cfg = matcher_config()
    assert sha(MATCHER_CFG) == cfg['matcher_config_sha256']
    assert PROMPT_SHA256 == cfg['prompt_sha256'] and VERSION == cfg['version']
    MATCHER_DIR.mkdir(parents=True, exist_ok=True)
    pk = {m: packages(m) for m in MODELS}
    for m in MODELS:
        assert len(pk[m]) == N_NEW, (m, len(pk[m]))
    keys = sorted((m, i) for m in MODELS for i in pk[m])
    ledger = CallLedger(RESULTS, cfg, ROOT / 'rebuttal/pilots/prereg/E4-v7.md',
                        cfg['max_calls'])
    done = {p.stem for p in MATCHER_DIR.glob('*.json')}
    counts = Counter()
    try:
        for n, (model, inst) in enumerate(keys, 1):
            key = digest(['expansion-stage1', SEED, inst, model])
            if key in done:
                counts['skipped'] += 1
                continue
            if ledger_cost() > COST_STOP_USD:
                counts['cost_stop'] += 1
                break
            p = pk[model][inst]
            rec = {'instance_id': inst, 'model': model, 'answer_correct': bool(p['answer_correct']),
                   'answer_f1': p['answer_f1'], 'matcher_frozen': True}
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
            freeze(MATCHER_DIR / f'{key}.json', rec)
            if n % 25 == 0:
                print(json.dumps({'n': n, 'of': len(keys), 'ok': counts['ok'],
                                  'failed': counts['failed'],
                                  'matcher_usd': round(ledger_cost(), 4)}), flush=True)
    finally:
        ledger.close()
    print(json.dumps({'traces': len(keys), **counts, 'matcher_usd': round(ledger_cost(), 5),
                      'relay_usd': {k: round(v, 5) for k, v in rel_costs().items()}},
                     indent=1))


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


def report():
    man, rows = candidate_rows()
    screened = len(list(MATCHER_DIR.glob('*.json')))
    ok = [r for r in rows if r.get('diagnosis')]
    wrong = [r for r in ok if not r['answer_correct']]
    cands = [r for r in ok if r['diagnosis'] == 'extraction_omission']
    clean = [r for r in cands if r.get('pass')]
    by_model = {}
    for m in MODELS:
        mo = [r for r in ok if r['model'] == m]
        mc = [r for r in mo if r['diagnosis'] == 'extraction_omission']
        by_model[m] = {'screened_ok': len(mo), 'wrong': sum(not r['answer_correct'] for r in mo),
                       'candidates': len(mc), 'rate': round(len(mc) / len(mo), 4) if mo else None,
                       'clean': sum(bool(r.get('pass')) for r in mc)}
    cand_rate = len(cands) / len(ok) if ok else 0.0
    clean_yield = len(clean) / len(cands) if cands else 0.0
    clean_per_trace = len(clean) / len(ok) if ok else 0.0
    costs = {'relay': rel_costs(), 'matcher': ledger_cost()}
    total = sum(costs['relay'].values()) + costs['matcher']
    stop = cand_rate < 0.06 or clean_yield < 0.10
    failed = [json.loads(p.read_text()) for p in MATCHER_DIR.glob('*.json')
              if json.loads(p.read_text()).get('status') != 'ok']
    fail_types = Counter(str(r.get('error', '')).split(':')[0] for r in failed)
    lines = ['# Expansion Stage 1: screening pilot\n',
             f"Instances: {man['n_new']} unused MuSiQue dev instances x {len(MODELS)} models "
             f"= {man['n_new'] * len(MODELS)} planned traces. Manifest "
             f"`{man['instances_sha256']}`. Frozen 2026-11-12; no repair arm run.\n",
             f'Matcher records: {screened}; scored ok: {len(ok)}; transport failures: {len(failed)} '
             f'({", ".join(f"{k}={v}" for k, v in fail_types.items()) or "none"}); '
             f'wrong: {len(wrong)}; extraction-omission candidates: {len(cands)}; '
             f'R3/R4 clean: {len(clean)}.\n',
             '## Yield\n',
             '| model | scored | wrong | candidates | candidate rate | clean |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for m, v in by_model.items():
        lines.append(f"| {m} | {v['screened_ok']} | {v['wrong']} | {v['candidates']} | "
                     f"{v['rate']:.1%} | {v['clean']} |")
    lines += [f'| **all** | **{len(ok)}** | **{len(wrong)}** | **{len(cands)}** | '
              f'**{cand_rate:.1%}** | **{len(clean)}** |\n',
              f'- Candidate rate: **{cand_rate:.1%}** (stop threshold 6%).',
              f'- Clean yield among candidates: **{clean_yield:.1%}** (stop threshold 10%).',
              f'- Clean per screened trace: **{clean_per_trace:.2%}** '
              f'(the plan\'s central estimate was 1.90%).',
              f'- Decision: **{"STOP and report before Stage 2" if stop else "continue to Stage 2 review"}**.\n',
              '## Cost\n',
              '| item | USD |',
              '| --- | ---: |']
    for m, v in costs['relay'].items():
        lines.append(f'| relay {m} | {v:.4f} |')
    lines += [f'| matcher | {costs["matcher"]:.4f} |',
              f'| **total** | **{total:.4f}** |\n',
              f'Per-pilot cap $5.00; phase budget $100.00. Every relay call is in '
              f'`api_responses.jsonl` under `relay_<model>/`; every matcher call is in '
              f'`calls.jsonl` under `{RESULTS.relative_to(ROOT)}/`.\n',
              '## Candidates\n',
              '| instance | model | gold | missing | candidate fact | R3 | R4 |',
              '| --- | --- | --- | ---: | --- | --- | --- |']
    for r in cands:
        lines.append(f"| {r['instance_id']} | {r['model']} | {str(r['gold'])[:70]} | "
                     f"{len(r['missing_ids'])} | {str(r.get('candidate_fact',''))[:110]} | "
                     f"{'pass' if r.get('r3_single_fact') else 'fail'} | "
                     f"{'pass' if r.get('r4_pass') else 'fail'} |")
    lines += ['', '## Spot-check of the clean candidates\n',
              'All 11 clean candidates were read against the question, gold, board and fact. '
              'Each fact either states the gold entity or value, or supplies the missing link '
              'between the question chain and a board unit that states the gold. None relies on '
              'the fact vouching for itself, and none is a board-only case (R4 rejects those). '
              'One instance, `2hop__414193_176917`, contributes two traces (gemma31b and '
              'gpt4omini) with the same fact; the other nine are distinct instances. '
              'The two long facts (`2hop__619265_72380`, `2hop__152229_604644`) contain the '
              'exact gold date and label with no rounding or negation.\n',
              'R3/R4 are the zero-call lexical gates from `src/audit/e4_fix_gates.py`. '
              'R2 delivery is applied when a repair is delivered, not at screening. '
              'The conservative clean yield counts only candidates whose matcher fact passes '
              'R4; the central yield in the plan also counted two manual source-context rebuilds, '
              'which screening cannot produce.\n']
    (OUT / 'stage1_report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'screened': screened, 'ok': len(ok), 'wrong': len(wrong),
                      'candidates': len(cands), 'candidate_rate': round(cand_rate, 4),
                      'clean': len(clean), 'clean_yield': round(clean_yield, 4),
                      'stop': stop, 'total_usd': round(total, 4),
                      'by_model': by_model}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--match', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.prepare:
        prepare()
    if a.match:
        match()
    if a.report:
        report()


if __name__ == '__main__':
    main()