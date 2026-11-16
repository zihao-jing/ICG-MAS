"""Cost breakdown by model and experiment from every recorded ledger.

Read-only.  Counts each cost-bearing record exactly as `rebuttal/diagnosis/README.md`
documents (all `rebuttal/**/*.jsonl` except the two duplicate `swaps.jsonl`
files).  Model-less positive-cost ledgers are assigned by their recorded rule.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path('rebuttal')
DROP = {
    'rebuttal/pilots/20261112_swap_labeller/swaps.jsonl',
    'rebuttal/pilots/20261112_swap_labeller/stage2/swaps.jsonl',
}
# Model-less positive-cost ledgers, assigned from their frozen rules.
OVERRIDE = {
    '20261113_main_table_redo': 'Claude Haiku 5.5',
    '20261112_rescore': 'Claude Haiku 5.5',
    '20261113_attribution_comparison': 'Gemini 3.6 Flash',
    '20261113_restore_source': 'Gemini 3.6 Flash',
}
MODEL = {
    'anthropic/claude-opus-5.5': 'Opus 5.5',
    'anthropic/claude-haiku-5.5': 'Claude Haiku 5.5',
    'google/gemini-3.6-flash': 'Gemini 3.6 Flash',
    'qwen/qwen3-235b-a22b-2507': 'Qwen-235B',
    'qwen/qwen3-235b-a22b-07-25': 'Qwen-235B (07-25)',
    'qwen3-235b-a22b-2507': 'Qwen-235B',
    'qwen235b': 'Qwen-235B',
    'openai/gpt-4o-mini': 'GPT-4o-mini',
    'gpt4omini': 'GPT-4o-mini',
    'gpt-4o-mini': 'GPT-4o-mini',
    'google/gemma-4-31b-it': 'Gemma-4-31B',
    'google/gemma-4-31b-it-20260402': 'Gemma-4-31B',
    'gemma31b': 'Gemma-4-31B',
    'gemma-4-31b-it': 'Gemma-4-31B',
    'mistralai/mistral-small-2603': 'Mistral-S',
    'mistrals': 'Mistral-S',
    'qwen/qwen3.6-flash': 'Qwen3.6-Flash',
    'qwen36f': 'Qwen3.6-Flash',
    'qwen/qwen3-next-80b-a3b-thinking-2509': 'Qwen-80B',
    'qwen80bt': 'Qwen-80B',
}
NAME = {
    '20261114_board_fidelity_full': 'Board strict fidelity, full run',
    '20261114_board_fidelity_pilot': 'Board strict fidelity, pilot',
    '20261113_label_validation_v10': 'Strict-fidelity label validation v10',
    '20261113_label_validation_v9': 'Label validation v9',
    '20261113_label_validation_v8': 'Label validation v8',
    '20261113_label_validation_v7': 'Label validation v7',
    '20261113_label_validation_v6': 'Label validation v6',
    '20261113_per_fact_labeller': 'Per-fact labeller pilot/validation',
    '20261113_musique_presence_full': 'MuSiQue presence full (A)',
    '20261113_sb_presence_full': 'Silo-Bench presence full (A)',
    '20261113_sb_presence_validation': 'Silo-Bench presence validation',
    '20261113_subclaim_presence_full': 'Sub-claim presence full (B)',
    '20261113_subclaim_validation': 'Sub-claim validation',
    '20261113_subclaim_presence_pilot': 'Sub-claim presence pilot',
    '20261113_main_table_redo': 'Main-table redo labeller',
    '20261113_main_table_presence': 'Main-table presence pilot',
    '20261113_attribution_comparison': 'Who&When-style stage comparison',
    '20261113_restore_source': 'Restore-the-source',
    '20261113_injected_distortion': 'Injected distortion',
    '20261113_placement_redo': 'Placement redo',
    '20261113_placement': 'Placement pilot',
    '20261113_placement_v2': 'Placement v2',
    '20261113_musique_equiv': 'MuSiQue answer equivalence',
    '20261113_answer_equiv_beside': 'Answer-equivalence beside',
    '20261113_coverage_labeller_v3': 'Coverage labeller v3',
    '20261113_coverage_rescore': 'Coverage rescore',
    '20261113_coverage_validation': 'Coverage validation',
    '20261113_coverage_validation_v2': 'Coverage validation v2',
    '20261113_audit_diagnosis_89': 'Audit diagnosis on 89 cases',
    '20261113_injection_screening': 'E2-A injection screening',
    '20261113_injection_screening_v2': 'E2-A injection screening v2',
    '20261114_e2c_card_pilot': 'E2-C card pilot (18 calls)',
    '20261113_e3_full': 'E3 route ablation (offline)',
    '20261113_e3_pilot': 'E3 pilot (offline)',
    '20261112_missing_fact_repair': 'Missing-fact repair',
    '20261112_rescore': 'v2 rescore pilot',
    '20261112_swap_labeller': 'Swap labeller',
    '20261112_answer_equiv': 'Answer equivalence pilot',
    '20261112_labeller': 'LLM labeller pilot',
    '20261112_labeller_v2_full': 'v2 labeller full pilot',
    '20261112_constructed_distortion': 'Constructed distortion',
    '20261108_ww_sanity': 'Who&When sanity',
    '20261108_e2_a_technical': 'E2-A technical pilot',
    '20261108_e2_c_technical': 'E2-C technical pilot',
    '20261108_e4_technical': 'E4 technical pilot',
    '20261108_e4_p_technical': 'E4-P technical pilot',
    '20261108_e4_p_seed43': 'E4-P seed-43 source traces',
    '20261108_judge_pilot': 'Judge pilot',
    '20261108_judge_pilot2': 'Judge pilot 2',
    '20261108_gpt4omini_k1_rebuild': 'GPT-4o-mini k=1 rebuild',
}


def norm_model(rec, exp):
    for k in ('model_id', 'model', 'resolved_model'):
        v = rec.get(k)
        if v:
            return MODEL.get(v, v)
    if exp in OVERRIDE:
        return OVERRIDE[exp]
    return 'Unknown'


def tokens(rec):
    u = rec.get('usage') or rec.get('tokens') or {}
    return int(u.get('prompt_tokens') or 0), int(u.get('completion_tokens') or 0)


def experiment(path):
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if parts[0] == 'pilots' and len(parts) > 1:
        return parts[1]
    if parts[0] == 'results' and len(parts) > 2 and parts[1] == 'batch1':
        return 'batch1/' + parts[2]
    return '/'.join(parts[:-1])


def main():
    by = defaultdict(lambda: {'calls': 0, 'pin': 0, 'pout': 0, 'usd': 0.0,
                              'provider_usd': 0.0, 'est_usd': 0.0,
                              'failed': 0, 'no_tokens': 0, 'no_cost': 0})
    unlogged_intents = 0
    attempts = 0
    total_records = 0
    for p in ROOT.rglob('*.jsonl'):
        if 'external' in p.parts or str(p) in DROP:
            continue
        exp = experiment(p)
        intents, results = set(), set()
        for line in p.read_text(errors='replace').splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get('event') == 'intent':
                intents.add(r.get('call_id'))
                continue
            if 'cost_usd' not in r:
                continue
            total_records += 1
            cid = r.get('call_id')
            if r.get('event') == 'result':
                results.add(cid)
            if 'attempt-' in str(r.get('key', '')):
                attempts += 1
            cost = r.get('cost_usd')
            model = norm_model(r, exp)
            d = by[(model, exp)]
            d['calls'] += 1
            pin, pout = tokens(r)
            d['pin'] += pin
            d['pout'] += pout
            if pin == 0 and pout == 0:
                d['no_tokens'] += 1
            if cost is None:
                d['no_cost'] += 1
                continue
            cost = float(cost)
            d['usd'] += cost
            if r.get('cost_kind') == 'provider':
                d['provider_usd'] += cost
            else:
                d['est_usd'] += cost
            if r.get('success') is False:
                d['failed'] += 1
        unlogged_intents += len(intents - results)

    models = defaultdict(lambda: {'calls': 0, 'pin': 0, 'pout': 0, 'usd': 0.0,
                                  'provider_usd': 0.0, 'est_usd': 0.0,
                                  'failed': 0, 'no_tokens': 0})
    for (model, exp), d in by.items():
        m = models[model]
        for k in ('calls', 'pin', 'pout', 'usd', 'provider_usd', 'est_usd',
                  'failed', 'no_tokens'):
            m[k] += d[k]

    out = {'records': total_records,
           'unresolved_intents': unlogged_intents,
           'retry_attempt_records': attempts,
           'models': dict(sorted(models.items(), key=lambda kv: -kv[1]['usd'])),
           'rows': [dict(model=k[0], experiment=NAME.get(k[1], k[1]), **v)
                    for k, v in sorted(by.items(), key=lambda kv: (kv[0][0], -kv[1]['usd']))]}
    Path('rebuttal/pilots/20261114_cost_breakdown').mkdir(parents=True, exist_ok=True)
    Path('rebuttal/pilots/20261114_cost_breakdown/results.json').write_text(
        json.dumps(out, indent=1) + '\n')
    print(json.dumps({'records': total_records, 'unresolved_intents': unlogged_intents,
                      'retry_attempt_records': attempts,
                      'models': out['models']}, indent=1))


if __name__ == '__main__':
    main()